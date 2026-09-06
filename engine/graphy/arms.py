"""arms — the walk-derived half of an arm file, as a marked generated region.

An arm file is judgment prose around a region the walk writes: every symbol the cut places in
the arm, by module; every ``inherits`` edge that leaves the arm; the taps that re-walk it. The
region is bounded by two HTML comments the reader never sees rendered. The opening marker
stamps the store generation the region was rendered from, the partition's sha, and the sha of
the region's own body. ``generate`` writes the region into each arm file, creating a stub around
it when no file exists and never touching a byte outside the markers. ``verify`` re-renders from
the live store and names every arm whose region differs — the walk moved, or a hand edited
inside the markers — so the drift is named, never absorbed. Byte-identical, or the receipt names
the drift.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from graphy.fanout import Cut
from graphy.pillars import _module_of

__all__ = ["ArmsError", "Region", "Verdict", "render_region", "render_all", "generate", "verify",
           "read_region"]

JOIN_RELATIONS = frozenset({"inherits"})
FANIN_RELATIONS = frozenset({"calls", "inherits", "decorates"})
_OPEN = re.compile(r"<!-- graphy:arm (?P<name>[A-Za-z0-9_.-]+) generated[^\n]*\n"
                   r"\s*store=(?P<store>\S+) cut=(?P<cut>\S+) content=(?P<content>\S+) -->\n")
_CLOSE_FMT = "<!-- /graphy:arm {name} -->"


class ArmsError(RuntimeError):
    pass


@dataclass
class Region:
    name: str
    body: str
    store: str
    cut: str

    @property
    def content_sha(self) -> str:
        return "sha256:" + hashlib.sha256(self.body.encode("utf-8")).hexdigest()

    def text(self) -> str:
        head = (f"<!-- graphy:arm {self.name} generated — do not edit inside this region; "
                f"`graphy arms` regenerates it, `graphy arms --verify` names drift\n"
                f"     store={self.store} cut={self.cut} content={self.content_sha} -->\n")
        return head + self.body + _CLOSE_FMT.format(name=self.name) + "\n"


@dataclass
class Verdict:
    name: str
    state: str                       # match · moved · edited · no-region · no-file
    detail: str = ""
    diff: list = field(default_factory=list)


def _tail(node_id: str) -> str:
    return node_id.split("/", 3)[-1] if "://" in node_id else node_id


def _short(dotted: str, corpus: str) -> str:
    return dotted[len(corpus) + 1:] if dotted.startswith(corpus + ".") else dotted


def _inventory(store, corpus: str, cut: Cut) -> tuple[dict, dict, dict]:
    """(group -> module -> {classes: {dotted: method_count}, funcs: [dotted]}), node -> group,
    node -> record."""
    records: dict[str, dict] = {}
    group_of: dict[str, str] = {}
    by_group: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"classes": {}, "funcs": []}))
    for nid, rec in store.owned(corpus):
        if not rec:
            continue
        records[nid] = rec
        mod = _module_of(rec, nid)
        if not mod:
            continue
        g = cut.group_of(mod)
        group_of[nid] = g
        kind = rec.get("node_type")
        dotted = rec.get("dotted") or _tail(nid)
        if kind == "class":
            by_group[g][mod]["classes"].setdefault(dotted, 0)
        elif kind == "func":
            by_group[g][mod]["funcs"].append(dotted)
    for nid, rec in records.items():
        if rec.get("node_type") != "method":
            continue
        dotted = rec.get("dotted") or _tail(nid)
        cls = dotted.rsplit(".", 1)[0]
        g = group_of.get(nid)
        if g is None:
            continue
        mod = _module_of(rec, nid)
        classes = by_group[g][mod]["classes"]
        if cls in classes:
            classes[cls] += 1
    return by_group, group_of, records


def _joins_and_crowns(store, corpus: str, group_of: dict, records: dict) -> tuple[dict, dict]:
    """The inherits edges leaving each arm, and each arm's crown: the node with the greatest
    fan-in (calls · inherits · decorates) from outside its own module."""
    joins: dict[str, list[tuple[str, str]]] = defaultdict(list)
    fanin: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for src, dst, rel in store.edges():
        gs = group_of.get(src)
        if gs is None:
            continue
        gd = group_of.get(dst)
        if rel in JOIN_RELATIONS and gd != gs:
            joins[gs].append((src, dst))
        if rel in FANIN_RELATIONS and gd is not None:
            ms = _module_of(records.get(src), src)
            md = _module_of(records.get(dst), dst)
            if ms != md:
                fanin[gd][dst] += 1
    crowns = {g: max(sorted(c), key=lambda n: c[n]) for g, c in fanin.items() if c}
    return joins, crowns


def render_region(name: str, corpus: str, cut: Cut, inventory: dict, joins: list, crown: str | None,
                  group_of: dict, *, tenant_dir: str, tenant_id: str) -> str:
    lines = ["## The walk's inventory — generated", "",
             "Every symbol the partition places in this arm, by module; a class carries its method count. "
             "The prose above is judgment; this region is the walk, re-rendered from the store on every "
             "rebuild and refused when it drifts.", ""]
    if not inventory:
        lines += ["(the partition places no symbol here)", ""]
    for mod in sorted(inventory):
        parts = []
        classes = inventory[mod]["classes"]
        if classes:
            parts.append("classes: " + " · ".join(
                f"`{_short(c, corpus).rsplit('.', 1)[-1]}`" + (f" ({n})" if n else "")
                for c, n in sorted(classes.items())))
        funcs = inventory[mod]["funcs"]
        if funcs:
            parts.append("functions: " + " · ".join(f"`{f.rsplit('.', 1)[-1]}`" for f in sorted(funcs)))
        lines.append(f"**`{mod}`** — " + ("; ".join(parts) if parts else "the module alone"))
    lines += ["", "## The inherits joins out — generated", ""]
    if joins:
        for src, dst in sorted(set(joins)):
            gd = group_of.get(dst)
            where = f"[{gd}]" if gd else dst.split("://", 1)[0] if "://" in dst else "?"
            lines.append(f"- `{_short(_tail(src), corpus)}` ──inherits──▶ `{_tail(dst)}` {where}")
    else:
        lines.append("(no inherits edge leaves this arm)")
    lines += ["", "## Re-walk — generated", "", "```bash", f"T={tenant_dir}"]
    if crown:
        lines.append(f"python3 -m graphy blast {crown} --tenant $T/tenant.json --tenant-id {tenant_id}")
    lines += [f"python3 -m graphy pillars --tenant $T/tenant.json --tenant-id {tenant_id} --corpus {corpus} --against $T/partition.json",
              f"python3 -m graphy arms --tenant $T/tenant.json --tenant-id {tenant_id} --corpus {corpus} --partition $T/partition.json --dir $T/arms --verify",
              "```", ""]
    return "\n".join(lines) + "\n"


def render_all(store, corpus: str, cut: Cut, *, tenant_dir: str, tenant_id: str) -> dict[str, Region]:
    if cut.groups is None:
        raise ArmsError("arms need a partition cut — a depth cut names no arm")
    inventory, group_of, records = _inventory(store, corpus, cut)
    joins, crowns = _joins_and_crowns(store, corpus, group_of, records)
    gen = store.generation()
    cut_sha = f"sha256:{cut.sha256}" if cut.sha256 else "unpinned"
    out = {}
    for name in cut.groups:
        body = render_region(name, corpus, cut, inventory.get(name, {}), joins.get(name, []),
                             crowns.get(name), group_of, tenant_dir=tenant_dir, tenant_id=tenant_id)
        out[name] = Region(name=name, body=body, store=gen, cut=cut_sha)
    return out


def read_region(text: str, name: str) -> tuple[Region | None, tuple[int, int] | None]:
    """The region named in a file's text and its span, or (None, None) when absent."""
    m = _OPEN.search(text)
    while m and m.group("name") != name:
        m = _OPEN.search(text, m.end())
    if not m:
        return None, None
    close = _CLOSE_FMT.format(name=name)
    end = text.find(close, m.end())
    if end < 0:
        raise ArmsError(f"arm {name}: the region opens but never closes — restore the `{close}` marker")
    body = text[m.end():end]
    reg = Region(name=name, body=body, store=m.group("store"), cut=m.group("cut"))
    span = (m.start(), end + len(close) + (1 if text[end + len(close):end + len(close) + 1] == "\n" else 0))
    return reg, span


def _stub(name: str) -> str:
    return (f"# {name} — (the judgment prose goes here, outside the generated region)\n\n"
            f"> Walk-derived; the region below is the walk's, the prose is the operator's.\n\n")


def generate(regions: dict[str, Region], arms_dir: str | Path) -> list[tuple[str, str]]:
    """Write every region into <arms_dir>/<NAME>.md — replaced in place, appended when the file
    has none, a stub created when the file is absent. Returns (name, what) per arm."""
    d = Path(arms_dir)
    d.mkdir(parents=True, exist_ok=True)
    done = []
    for name, reg in regions.items():
        p = d / f"{name}.md"
        new = reg.text()
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            old, span = read_region(text, name)
            if span is not None:
                out = text[:span[0]] + new + text[span[1]:]
                what = "unchanged" if out == text else "replaced"
            else:
                out = text.rstrip("\n") + "\n\n" + new
                what = "appended"
        else:
            out = _stub(name) + new
            what = "created"
        if what != "unchanged":
            p.write_text(out, encoding="utf-8")
        done.append((name, what))
    return done


def verify(regions: dict[str, Region], arms_dir: str | Path) -> list[Verdict]:
    d = Path(arms_dir)
    verdicts = []
    for name, want in regions.items():
        p = d / f"{name}.md"
        if not p.is_file():
            verdicts.append(Verdict(name, "no-file", f"no {p.name} under {d}"))
            continue
        text = p.read_text(encoding="utf-8")
        m = _OPEN.search(text)
        while m and m.group("name") != name:
            m = _OPEN.search(text, m.end())
        have, _span = read_region(text, name)
        if have is None:
            verdicts.append(Verdict(name, "no-region", f"{p.name} carries no generated region"))
            continue
        stamped = m.group("content")
        if stamped != have.content_sha:
            verdicts.append(Verdict(name, "edited", f"{p.name}: the region's bytes do not match its own "
                                    f"content stamp — a hand edited inside the markers"))
            continue
        if have.body == want.body:
            verdicts.append(Verdict(name, "match", f"store {want.store}"))
            continue
        diff = [l.rstrip("\n") for l in difflib.unified_diff(
            have.body.splitlines(), want.body.splitlines(), lineterm="", n=0)
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
        verdicts.append(Verdict(name, "moved", f"{p.name}: the walk moved — region rendered from store "
                                f"{have.store}, the live store is {want.store}; {len(diff)} line(s) differ", diff))
    return verdicts


def render_verdicts(verdicts: list[Verdict], limit: int = 8) -> tuple[str, int]:
    drifted = [v for v in verdicts if v.state != "match"]
    lines = []
    for v in verdicts:
        if v.state == "match":
            continue
        lines.append(f"  {v.name:14} {v.state:10} {v.detail}")
        for l in v.diff[:limit]:
            lines.append(f"      {l}")
        if len(v.diff) > limit:
            lines.append(f"      … {len(v.diff) - limit} more")
    if drifted:
        head = (f"ARMS DRIFT: {len(drifted)} of {len(verdicts)} arm(s) differ from the walk — "
                f"`graphy arms` (without --verify) re-renders the region; the prose outside it is untouched")
        return "\n".join([head] + lines), 1
    gen = verdicts[0].detail if verdicts else ""
    return f"ARMS OK: {len(verdicts)} arm(s) match the walk ({gen})", 0
