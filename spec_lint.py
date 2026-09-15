#!/usr/bin/env python3
"""spec_lint — a spec is a contract a machine reads before a byte is built.

A spec is terse: headers, bullets, fenced commands. No paragraphs. Every blocker class the review
rounds of 2026-09-13..15 found (graphyos #80–#127, #93) is a PATTERN here: either a LINT the spec
must satisfy mechanically, or a SCAR the spec must name. `--patterns` prints the build checklist.

    python3 spec_lint.py specs/<n>.md      # SPEC OK | SPEC RED (exit 1) | SPEC REFUSED (exit 2)
    python3 spec_lint.py --all             # every specs/*.md
    python3 spec_lint.py --patterns        # the checklist: every lint and scar, one line each
    python3 spec_lint.py --selftest        # every rule red on its _bad fixture, silent on its _neg

The shape (spec_lint_fixtures/good.md is the reference):

    # <title>
    issue: graphyos #<n>
    host: linux, windows
    scars: S1 S2
    recurs: #<n> r<k> B<j>, …          (only when the scope adds a check)
    ## Contract       - C<n> <one fact>
    ## Scope          - IN: <path> · - OUT: <path or area>
    ## Hazards        - <pattern id> C<n>[,C<m>] P<n>[,P<m>]
    ## Probes         ```bash  # P<n> C<n> <pattern ids>  then its commands  ```
    ## Production     ```bash  # host: <linux|windows> <where>  then its commands  ```

A waiver is on the line it waives: `<!-- spec_lint: waive R<n> — <reason> -->`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "spec_lint_fixtures"
SECTIONS = ("Contract", "Scope", "Hazards", "Probes", "Production")
HEADERS = ("issue", "host", "scars")

# ── the patterns: the lowest common denominator of every REVISE blocker, one line each ────────────
# kind lint: the spec must carry the hazard in ## Hazards, bound to a contract line and a probe whose
#            commands match `probe` (the shape that proves it). A trigger reads ## Contract and ## Scope.
# kind scar: not mechanical. The spec must name it in `scars:` when its trigger fires.
PATTERNS = {
    # A · the record contradicts the tree
    "A1": dict(kind="lint", cls="A", text="no count in prose: a number lives beside the command that prints it",
               trigger=None, probe=None),
    "A2": dict(kind="lint", cls="A", text="every contract line has a probe that exercises it, member by member",
               trigger=None, probe=None),
    # B · green on Linux, wrong on Windows
    "W1": dict(kind="lint", cls="B", text="bytes written are asserted on disk: LF, no CR, the shebang intact",
               trigger=r"\b(writes?|written|file|hook|script|shebang|json|receipt|template)\b",
               probe=r"read_bytes|\bod\b|xxd|\\r|open\([^)]*['\"]rb"),
    "W2": dict(kind="lint", cls="B", text="a child's output is decoded as utf-8, never the locale",
               trigger=r"\b(subprocess|child|stdout|stderr|pipe|decode)\b",
               probe=r"encoding=|utf-8|PYTHONIOENCODING|cp1252"),
    "W3": dict(kind="lint", cls="B", text="a path in output survives a space, a dot-name and a drive letter",
               trigger=r"\b(path|paths|command|wiring|argv|quote|quoted)\b",
               probe=r"First Last|[\"'][^\"'\n]*[/\\][^\"'\n]* [^\"'\n]*[\"']|\\ "),
    "W4": dict(kind="lint", cls="B", text="a command runs through the shell its harness uses on that host",
               trigger=r"\b(hook|hooks|shell|bash|cmd|powershell|\.cmd|\.sh)\b",
               probe=r"\bcmd\b|bash|powershell|\bsh -c"),
    "W5": dict(kind="lint", cls="B", text="a file a process holds is never renamed or removed under it",
               trigger=r"\b(rename|replace|land|landing|swap|remove|held|store)\b",
               probe=r"held|hold|open_for|SQLiteStore|rename|replace"),
    "W6": dict(kind="lint", cls="B", text="the answer is a fresh clone's, never this box's config",
               trigger=r"\bgit (config|attributes?|clone|checkout|add)\b|\.gitattributes|autocrlf|\blocale\b|core\.\w+",
               probe=r"git clone|autocrlf|GIT_CONFIG|mktemp"),
    "W7": dict(kind="lint", cls="B", text="the Windows job runs the probes on the tree that lands",
               trigger=r"\b(windows|nt|cp1252|crlf|msvcrt|drive)\b",
               probe=r"gh workflow run|gh run (view|watch)|store-windows|windows-latest"),
    # C · hand-parsing an unbounded language
    "C1": dict(kind="lint", cls="C", text="never hand-parse an unbounded language; refuse at a boundary",
               trigger=r"\b(parse|parser|tokeni[sz]e|grammar)\b.{0,40}\b(bash|shell|command line|sql|javascript|regex)\b",
               probe=r"REFUSED|refuse"),
    # D · silent where it must say could-not-tell
    "D1": dict(kind="lint", cls="D", text="every fallback names its state; a traceback is never the answer",
               trigger=r"\b(fallback|default|skip|skips|ignore|missing|absent|corrupt|torn|unreadable|fail[- ]open|fails)\b",
               probe=r"Traceback|REFUSED|COULD-NOT-TELL|SKIPPED"),
    # E · right once, wrong the second time
    "E1": dict(kind="lint", cls="E", text="run it three times: the second and third run read what the first wrote",
               trigger=r"\b(install|eat|rebuild|land|refresh|remint|re-mint|cache|store|generation|merge|idempotent)\b",
               probe=r"for \w+ in (1 2 3|\$\(seq 3\)|\{1\.\.3\})|seq 3|three"),
    "E2": dict(kind="lint", cls="E", text="the last release's files on disk upgrade cleanly",
               trigger=r"\b(template|wiring|layout|format|schema|descriptor|install|upgrade)\b",
               probe=r"v0\.\d|==0\.\d|git show v|git archive v|release"),
    "E3": dict(kind="lint", cls="E", text="an interrupt or a failure mid-way leaves the served state whole",
               trigger=r"\b(land|landing|rebuild|stage|swap|replace|atomic|rename)\b",
               probe=r"kill|SIGINT|interrupt|raise|monkeypatch|fail"),
    # F · a checker that is itself wrong
    "F1": dict(kind="lint", cls="F", text="a new check is proven red on its specimen and silent on a near miss",
               trigger=r"\b(review\.py|spec_lint\.py|burden\.py|workflows\.py|check|door)\b",
               probe=r"--selftest|_bad|_neg|near-miss"),
    # G · bound by name, or one input read two ways
    "G1": dict(kind="lint", cls="G", text="match the whole token by one parser; a near miss must not bind",
               trigger=r"\b(match|matches|matched|bind|binds|bound|resolve|resolves|label|substring|suffix|prefix|rewrite|rewrites)\b",
               probe=r"near[-_ ]miss|josh\.shaw|\.sh[a-z]|fullmatch"),
    # the scars: judgment no linter reaches, named so the builder reads them before the first edit
    "S1": dict(kind="scar", cls="done", text="green is not done: a test, a token or a gate going green proves nothing in production",
               trigger=r"."),
    "S2": dict(kind="scar", cls="B", text="a real user's path holds a space, a `.sh`, a `%`, a quote, a drive letter",
               trigger=r"\b(path|paths|hook|hooks|command|wiring|install)\b"),
    "S3": dict(kind="scar", cls="B", text="this box is one sample: its config, locale, git, bash and tmp path are not the world",
               trigger=r"\b(windows|git|shell|bash|locale|encoding|config)\b"),
    "S4": dict(kind="scar", cls="A", text="edit docs last, run the gate after the last edit, cite only the run of the tree that lands",
               trigger=r"\b(RECON|README|CLAUDE\.md|record|doc|docs|changelog)\b"),
    "S5": dict(kind="scar", cls="F", text="a checker built to catch a blocker is new code the next round attacks; build one on the second sighting",
               trigger=r"\b(review\.py|check|door|battery)\b"),
    "S6": dict(kind="scar", cls="A", text="a rule changed in one file lives in every file that states it; grep for the old words",
               trigger=r"\b(rule|law|skill|CLAUDE\.md|card)\b"),
    "S8": dict(kind="scar", cls="F", text="a probe proves its line only when it fails on the code before the change; run it there once",
               trigger=r"."),
    "S7": dict(kind="scar", cls="E", text="the last release is on users' disks: an upgrade reads files this change no longer writes",
               trigger=r"\b(template|wiring|format|layout|schema|install)\b"),
}

FLOOR_TOOLS = re.compile(r"(^|[\s/])(pytest|review\.py|standalone_check\.sh|workflows\.py|burden\.py|census\.sh|"
                         r"release\.sh|spec_lint\.py|scrub\.py|measure\.py)\b")
PROD_TARGET = re.compile(r"\b(graphy|quickstart\.sh|rebuild\.sh|eat|mcp|shell install|curl|gh run)\b")
COUNT = re.compile(r"\b\d[\d,.]*\s+(tests?|rows?|checks?|runs?|files?|marks?|seams?|passed|failed|findings?|"
                   r"rounds?|lines?|edges?|nodes?|blockers?|issues?|shards?|lanes?|steps?|sections?)\b", re.I)
CANNOT_FAIL = re.compile(r"\|\s*(tail|head|cat|sort|uniq|wc)\b[^|]*$|\|\|\s*true\s*$|;\s*(true|echo\b.*)$|\bexit 0\s*$")
WAIVE = re.compile(r"<!--\s*spec_lint:\s*waive\s+(R\d+)\s*[—-]\s*(.+?)\s*-->")


@dataclass
class Finding:
    rule: str
    line: int
    text: str


class SpecRefused(RuntimeError):
    """The spec cannot be read as a spec. Never an empty finding list."""


def _sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    heads = [(i, m.group(1)) for i, ln in enumerate(lines) if (m := re.match(r"^## (\w+)\s*(?:<!--.*?-->\s*)?$", ln))]
    out = {}
    for k, (i, name) in enumerate(heads):
        out[name] = (i + 1, heads[k + 1][0] if k + 1 < len(heads) else len(lines))
    return out


def _blocks(lines: list[str], span: tuple[int, int], tag: str) -> list[dict]:
    """Fenced command blocks in a section, each opened by a `# <tag><id> …` comment line."""
    out, in_fence, cur = [], False, None
    for i in range(*span):
        ln = lines[i]
        if ln.startswith("```"):
            in_fence = not in_fence
            cur = None
            continue
        if not in_fence:
            continue
        m = re.match(rf"^#\s*({tag}\d+|host:)\s*(.*)$", ln.strip())
        if m:
            cur = {"id": m.group(1).rstrip(":"), "tags": m.group(2).replace(",", " ").split(), "line": i + 1, "cmds": []}
            out.append(cur)
        elif cur is not None and ln.strip() and not ln.strip().startswith("#"):
            cur["cmds"].append((i + 1, ln))
    return out


def lint_text(text: str) -> list[Finding]:
    lines = text.splitlines()
    waived = {(m.group(1), i + 1) for i, ln in enumerate(lines) for m in WAIVE.finditer(ln)}
    found: list[Finding] = []

    def add(rule: str, line: int, msg: str) -> None:
        if (rule, line) not in waived:
            found.append(Finding(rule, line, msg))

    head = {}
    for i, ln in enumerate(lines[:12]):
        m = re.match(r"^(issue|host|scars|recurs):\s*(.*)$", ln)
        if m:
            head[m.group(1)] = (i + 1, m.group(2).strip())
    secs = _sections(lines)
    if not lines or not lines[0].startswith("# ") or not secs:
        raise SpecRefused("not a spec: no `# title` first line or no `## section`")

    # R1 · shape
    for h in HEADERS:
        if h not in head:
            add("R1", 1, f"header `{h}:` is missing")
    missing = [s for s in SECTIONS if s not in secs]
    if missing:
        add("R1", 1, f"section(s) missing: {', '.join(missing)}")
    order = [s for s in secs if s in SECTIONS]
    if order != [s for s in SECTIONS if s in secs]:
        add("R1", 1, f"sections out of order: {' · '.join(order)}")

    # R2 · terse: outside fences only headings, header keys, bullets, blank lines, waivers
    in_fence = False
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not ln.strip() or ln.startswith("#") or WAIVE.search(ln):
            continue
        if re.match(r"^(issue|host|scars|recurs):", ln) or re.match(r"^\s*- ", ln):
            if len(ln) > 160:
                add("R2", i + 1, f"line is {len(ln)} chars; a contract line is one fact under 160")
            continue
        add("R2", i + 1, "prose outside a bullet or a fence")

    def bullets(name: str) -> list[tuple[int, str]]:
        if name not in secs:
            return []
        a, b = secs[name]
        return [(i + 1, lines[i].strip()[2:]) for i in range(a, b) if lines[i].strip().startswith("- ")]

    contract, scope, hazards = bullets("Contract"), bullets("Scope"), bullets("Hazards")
    probes = _blocks(lines, secs["Probes"], "P") if "Probes" in secs else []
    prod = _blocks(lines, secs["Production"], "") if "Production" in secs else []
    probe_ids = {p["id"]: p for p in probes}

    # R3 · every contract line has an id and a probe tagged with it (per member: A2)
    cids = []
    for ln, txt in contract:
        m = re.match(r"^(C\d+)\s+\S", txt)
        if not m:
            add("R3", ln, "a contract line starts `C<n> `")
            continue
        if m.group(1) in cids:
            add("R3", ln, f"{m.group(1)} is declared twice")
        cids.append(m.group(1))
        if not any(m.group(1) in p["tags"] for p in probes):
            add("R3", ln, f"{m.group(1)} has no probe tagged with it — a contract probed nowhere ships a default")
    if not contract:
        add("R3", secs.get("Contract", (1, 1))[0], "the contract is empty")

    # R4 · no count in prose (A1)
    for name in ("Contract", "Scope", "Hazards"):
        for ln, txt in bullets(name):
            bare = re.sub(r"`[^`]*`", "", txt)
            m = COUNT.search(bare)
            if m:
                add("R4", ln, f"a count in prose (`{m.group(0)}`): state the command, not the number")

    # R5 · every probe and production command can exit non-zero
    for blk in probes + prod:
        if not blk["cmds"]:
            add("R5", blk["line"], f"{blk['id'] or 'host'} carries no command")
        for ln, cmd in blk["cmds"]:
            if CANNOT_FAIL.search(cmd.strip()) and not re.search(r"\|\s*(grep\s+-\w*q|test\b)[^|]*$", cmd):
                add("R5", ln, "this line always exits 0: end it in `grep -q` or `test`, never a tail, a true or an echo")

    # R6 · production is the done token: a real target, named hosts, not the floor
    host_line, hosts = head.get("host", (1, ""))
    declared_hosts = {h.strip().lower() for h in hosts.replace(",", " ").split() if h.strip()}
    prod_hosts = set()
    if not prod:
        add("R6", secs.get("Production", (1, 1))[0], "no production block: done is it works in production, never a green floor")
    for blk in prod:
        if not blk["tags"]:
            add("R6", blk["line"], "a production block names its host: `# host: <linux|windows> <where>`")
            continue
        prod_hosts.add(blk["tags"][0].lower())
        real = [c for _, c in blk["cmds"] if not FLOOR_TOOLS.search(c)]
        if not real or not any(PROD_TARGET.search(c) for c in real):
            add("R6", blk["line"], "production runs the floor only: run the product against a real repo or tenant")
    for h in declared_hosts - prod_hosts:
        add("R6", host_line, f"host `{h}` is declared and no production block runs there")

    # R7 · hazards: each triggered lint pattern is carried, bound to a contract line and a probe of its shape
    body = "\n".join(t for _, t in contract + scope)
    carried = {}
    for ln, txt in hazards:
        toks = txt.replace(",", " ").split()
        if not toks or toks[0] not in PATTERNS or PATTERNS[toks[0]]["kind"] != "lint":
            add("R7", ln, "a hazard line starts with a lint pattern id (`python3 spec_lint.py --patterns`)")
            continue
        carried[toks[0]] = (ln, [t for t in toks if re.fullmatch(r"C\d+", t)], [t for t in toks if re.fullmatch(r"P\d+", t)])
    for pid, pat in PATTERNS.items():
        if pat["kind"] != "lint" or pat["trigger"] is None:
            continue
        if not re.search(pat["trigger"], body, re.I):
            continue
        if pid not in carried:
            add("R7", secs.get("Hazards", (1, 1))[0], f"{pid} is triggered and not carried: {pat['text']}")
            continue
        ln, cs, ps = carried[pid]
        if not cs or any(c not in cids for c in cs):
            add("R7", ln, f"{pid} names no contract line, or one that does not exist")
        if not ps or any(p not in probe_ids for p in ps):
            add("R7", ln, f"{pid} names no probe, or one that does not exist")
            continue
        shaped = [p for p in ps if pid in probe_ids[p]["tags"]
                  and re.search(pat["probe"], "\n".join(c for _, c in probe_ids[p]["cmds"]), re.I)]
        if not shaped:
            add("R7", ln, f"{pid}'s probes do not prove it: tag the probe `{pid}` and give it the shape /{pat['probe']}/")
    if ("W1" in carried or "W2" in carried or "W4" in carried or "W7" in carried) and "windows" not in declared_hosts:
        add("R7", host_line, "a Windows hazard is carried and `host:` does not name windows")

    # R8 · scars: each triggered scar is named
    named = set(head.get("scars", (1, ""))[1].replace(",", " ").split())
    for sid, pat in PATTERNS.items():
        if pat["kind"] == "scar" and re.search(pat["trigger"], body, re.I) and sid not in named:
            add("R8", head.get("scars", (1, ""))[0], f"scar {sid} applies and is not named: {pat['text']}")

    # R9 · a new check: it recurs (second sighting) and its probes run the selftest
    if re.search(r"\b(review\.py|spec_lint\.py|burden\.py|workflows\.py)\b", "\n".join(t for _, t in scope if t.startswith("IN:"))):
        refs = re.findall(r"#\d+ r\d+ B\d+", head.get("recurs", (1, ""))[1])
        if len(refs) < 2:
            add("R9", head.get("recurs", (1, ""))[0], "a check lands on its second sighting: `recurs:` names at least two blockers")
        if not any("--selftest" in c for p in probes for _, c in p["cmds"]):
            add("R9", secs.get("Probes", (1, 1))[0], "a new check's probes run `--selftest`")
    # R10 · a pytest probe names tests that exist: every `-k` term and `::` node id resolves in the file it names
    for blk in probes + prod:
        for ln, cmd in blk["cmds"]:
            for m in re.finditer(r"pytest\b(?P<args>[^|;&]*)", cmd):
                args = m.group("args")
                for node in re.findall(r"(tests/[\w/]+\.py)::(\w+)", args):
                    names = _test_names(node[0])
                    if names is None:
                        add("R10", ln, f"{node[0]} does not exist under engine/")
                    elif node[1] not in names:
                        add("R10", ln, f"{node[0]} has no test `{node[1]}`")
                files = [f for f in re.findall(r"(tests/[\w/]+\.py)(?!::)", args)]
                km = re.search(r"-k\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))", args)
                if not km:
                    continue
                expr = next(g for g in km.groups() if g is not None)
                terms = [t for t in re.split(r"\s+(?:and|or|not)\s+|\bnot\s+|[()]", expr) if t.strip()]
                pool: set[str] = set()
                for f in files:
                    names = _test_names(f)
                    if names is None:
                        add("R10", ln, f"{f} does not exist under engine/")
                    else:
                        pool |= names
                if not files:
                    continue
                for t in terms:
                    t = t.strip()
                    if not re.fullmatch(r"[\w.\[\]-]+", t):
                        add("R10", ln, f"`-k {expr}`: `{t}` is not a pytest keyword term (a space or a slash never matches)")
                    elif not any(t in n for n in pool):
                        add("R10", ln, f"`-k {expr}`: no test in {', '.join(files)} matches `{t}` — the probe runs nothing")
    return found


def _test_names(rel: str) -> set[str] | None:
    """The test functions a tracked test file defines, read from its source (`def test_…`), or None when absent."""
    f = HERE / "engine" / rel
    if not f.is_file():
        return None
    return set(re.findall(r"^def (test_\w+)", f.read_text(encoding="utf-8", errors="replace"), re.M))


def lint_file(path: Path) -> list[Finding]:
    if not path.is_file():
        raise SpecRefused(f"{path} is not a file")
    return lint_text(path.read_text(encoding="utf-8"))


RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10")


def selftest() -> int:
    """Every rule red on `R<n>_bad.md`, silent on `R<n>_neg.md`; `good.md` clean. A missing fixture is red."""
    bad = 0
    good = lint_file(FIXTURES / "good.md")
    if good:
        print(f"FAIL good.md carries {len(good)} finding(s): " + "; ".join(f"{f.rule}:{f.line} {f.text}" for f in good))
        bad += 1
    for r in RULES:
        for kind, want in (("bad", True), ("neg", False)):
            p = FIXTURES / f"{r}_{kind}.md"
            if not p.is_file():
                print(f"FAIL {p.name} is missing — a rule with no {kind} fixture is unproven")
                bad += 1
                continue
            hit = any(f.rule == r for f in lint_file(p))
            if hit != want:
                print(f"FAIL {p.name}: {r} {'did not fire' if want else 'fired on a near miss'}")
                bad += 1
            else:
                print(f" ok  {p.name}")
    if bad:
        print(f"SPEC LINT SELFTEST FAILED: {bad}")
        return 1
    print(f"SPEC LINT SELFTEST OK: {len(RULES)} rule(s), each red on its bad fixture and silent on its near miss")
    return 0


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="spec_lint")
    ap.add_argument("spec", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help="every specs/*.md")
    ap.add_argument("--patterns", action="store_true", help="print the build checklist")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.patterns:
        for pid, p in PATTERNS.items():
            print(f"{pid}  {p['kind']:4}  {p['cls']:4}  {p['text']}")
        return 0
    if a.selftest:
        return selftest()
    specs = sorted((HERE / "specs").glob("*.md")) if a.all else a.spec
    if not specs:
        print("SPEC REFUSED: no spec named (a path, or --all over specs/*.md)")
        return 2
    red = 0
    report = {}
    for p in specs:
        try:
            fs = lint_file(p)
        except SpecRefused as exc:
            print(f"SPEC REFUSED: {exc}")
            return 2
        report[str(p)] = [f.__dict__ for f in fs]
        if not a.json:
            for f in fs:
                print(f"{p}:{f.line}: {f.rule} {f.text}")
            print(f"{'SPEC OK' if not fs else 'SPEC RED'}: {p} · {len(fs)} finding(s)")
        red += bool(fs)
    if a.json:
        print(json.dumps(report, indent=2))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
