"""The pillars door: a tenant's arms deduced from the walk, never from a reading of the code.

A partition of a package into pillars is the one curated input a fan-out takes. This door proposes
it. The proposal is a cut over the corpus's *module graph* — every `imports` · `calls` · `inherits`
· `decorates` edge the compiled store carries between two modules of the corpus — and every
ruling it makes is printed beside the number that made it, so the operator accepts or edits with
the evidence in hand. No model decides an arm; a name decides nothing.

The rule, in the order it runs:

1. **Units.** A module belongs to the unit named by its first `depth` dotted segments (depth 2:
   the package's first-level children — `fastapi.routing.APIRouter` is `fastapi.routing`). The
   root module itself is the facade: it re-exports, it is the router, never an arm.
2. **The edge.** A unit with fewer than `floor` cross-unit edges (in + out) is the edge — too light
   to be a pillar; it lands in `rest`.
3. **Roles.** Fan-out over fan-in is an *orchestrator*; otherwise a *foundation*.
4. **Crowns.** The orchestrators ranked by fan-out; the top `arms - 1` when `arms` is given, else
   every orchestrator whose fan-out is at least half the leader's. Each crown names an arm.
5. **Orchestrators attach**, heaviest first: to the arm whose members consume it most (it is
   orchestrated by that crown); when nothing assigned consumes it, to the arm that takes at least
   `client` of its fan-out (it is that crown's client). An orchestrator nothing orchestrates and
   that spends under `client` of its fan-out on any one arm stands alone: it crowns an arm of
   its own, whatever the leader's league — unless `arms` was given, which bounds the crowns and
   sends it to its nearest arm instead.
6. **Foundations settle**, heaviest fan-in first: when one arm takes at least `owned` of its fan-in
   it is owned by that arm; otherwise it is shared — it joins THE FLOOR, the arm named after the
   foundation with the greatest fan-in, the boundary everything depends on. The floor is an arm
   for the concentration test, so a foundation the floor consumes settles onto the floor.

A unit nothing assigned touches lands in `rest`. Ties break toward the arm whose crown has the
greater fan-out, then by name. The whole thing is a whole-corpus aggregate — one read of the
store's edges, one of its nodes — never a hop.
"""
from __future__ import annotations

import collections
import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from graphy.federated_store import relations_in
from graphy.ir import DEPENDS

__all__ = ["PillarsError", "PillarsArgumentError", "ModuleGraph", "Proposal", "module_graph", "relations_for", "propose", "shape", "census", "render_census", "render",
           "to_partition", "diff", "render_diff"]

# What a unit depends on, for a store no producer declared a thing in (pre-#68): the doors' old constant.
# A store that declares its relations is read through ``relations_for`` — the DEPENDS family its lanes
# minted, so `references` and `writes` count where their producer said they are dependencies (graphyos #140).
RELATIONS = frozenset({"imports", "calls", "inherits", "decorates"})


def relations_for(store) -> frozenset:
    """The edge types a unit's fan-out and fan-in count over this store: its declared DEPENDS family — the
    set `blast` walks (``doors.blast_relations``) — else ``RELATIONS``. Never a vocabulary of this module's own."""
    return relations_in(store, DEPENDS, RELATIONS)
DEFAULT_DEPTH = 2
# The bound on the escalation. Whether a given depth is the right cut is a property of how deeply a
# repo nests its packages — `pkg.tools.thing` rather than `pkg.thing` — which is exactly the thing
# the engine can see and the caller should not have to guess. On a first tenant's 13 code corpora,
# 4 answered at the default and 9 answered when the cut was allowed to deepen; the other 4 have no
# orchestrator at any depth and still refuse (graphyos #75).
DEFAULT_MAX_DEPTH = 4
DEFAULT_FLOOR = 5
DEFAULT_OWNED = 2 / 3
DEFAULT_CLIENT = 1 / 3
DEFAULT_REST = "EDGE"


class PillarsError(RuntimeError):
    pass


class PillarsArgumentError(PillarsError):
    """The CALLER passed something impossible — not a corpus that has no shape.

    The distinction is load-bearing since the census fallback landed: "this lane is not a call
    graph" is answered with its census, and "you asked for one arm" must not be, or a typo is
    silently rewarded with a different door's answer (graphyos #76)."""


@dataclass
class ModuleGraph:
    corpus: str
    depth: int
    root: str                                  # the package root's dotted name (the facade)
    size: dict[str, int]                       # unit -> nodes in it
    weight: dict[tuple[str, str], int]         # (unit, unit) -> cross-unit edges
    modules: dict[str, set] = field(default_factory=dict)   # unit -> its module dotted names
    relations: frozenset = RELATIONS                          # the edge types the weights count (``relations_for``)

    @property
    def total(self) -> int:
        return sum(self.weight.values())

    def fan_out(self, u: str) -> int:
        return sum(c for (a, _b), c in self.weight.items() if a == u)

    def fan_in(self, u: str) -> int:
        return sum(c for (_a, b), c in self.weight.items() if b == u)

    def consumers(self, u: str) -> dict[str, int]:
        return {a: c for (a, b), c in self.weight.items() if b == u}

    def suppliers(self, u: str) -> dict[str, int]:
        return {b: c for (a, b), c in self.weight.items() if a == u}


def _module_of(record: dict | None, node_id: str) -> str | None:
    """The module a node lives in, as the producer said it (``module``). A record without it was
    minted before producers emitted the field: it is skipped, never derived from a file path."""
    if not record:
        return None
    m = record.get("module")
    return str(m) if m else None


def module_graph(store, corpus: str, depth: int = DEFAULT_DEPTH) -> ModuleGraph:
    """The corpus's module graph collapsed to units of `depth` dotted segments, from the store."""
    if depth < 1:
        raise PillarsError(f"depth must be at least 1, got {depth}")
    module_of: dict[str, str] = {}
    for nid, rec in store.owned(corpus):
        if rec and rec.get("role") == "test":
            continue                      # a test is the producer's word; a harness is never a pillar
        m = _module_of(rec, nid)
        if m:
            module_of[nid] = m
    if not module_of:
        raise PillarsError(f"the store owns no module-bearing node for corpus {corpus!r}")
    root = min((m for m in module_of.values()), key=lambda m: (m.count("."), m))
    root = root.split(".")[0]

    def unit(m: str) -> str:
        return ".".join(m.split(".")[:depth])

    size: dict[str, int] = collections.Counter(unit(m) for m in module_of.values())
    modules: dict[str, set] = collections.defaultdict(set)
    for m in module_of.values():
        modules[unit(m)].add(m)
    weight: dict[tuple[str, str], int] = collections.Counter()
    relations = relations_for(store)
    for src, dst, rel in store.edges():
        if rel not in relations:
            continue
        ms, md = module_of.get(src), module_of.get(dst)
        if ms is None or md is None:
            continue
        us, ud = unit(ms), unit(md)
        if us != ud:
            weight[(us, ud)] += 1
    return ModuleGraph(corpus=corpus, depth=depth, root=root, size=dict(size), weight=dict(weight),
                       modules={u: set(v) for u, v in modules.items()}, relations=relations)


@dataclass
class Ruling:
    unit: str
    arm: str                      # an arm name, or the rest name
    role: str                     # orchestrator | foundation | facade | edge
    fan_in: int
    fan_out: int
    how: str                      # the one-line evidence


@dataclass
class Proposal:
    corpus: str
    depth: int
    floor: int
    owned: float
    client: float
    rest: str
    crowns: dict[str, str]                 # arm -> the crown unit
    floor_arm: str | None                  # the floor's arm name, when a floor formed
    arms: dict[str, list[str]]             # arm -> units, crown first
    rulings: list[Ruling]
    total: int
    relations: frozenset = RELATIONS       # the edge types the proposal was cut over

    def arm_of(self, unit: str) -> str:
        for r in self.rulings:
            if r.unit == unit:
                return r.arm
        return self.rest


_ARM_CHARS = re.compile(r"[^A-Za-z0-9_]+")


def _arm_name(unit: str, taken: Iterable[str]) -> str:
    # an arm name is a section file and an html id: the crown's last segment with everything
    # outside [A-Za-z0-9_] folded to `_` — a unit named `pkg.```` names its arm ARM, never ``` (graphyos #46)
    base = _ARM_CHARS.sub("_", unit.rsplit(".", 1)[-1]).strip("_").upper() or "ARM"
    name, n = base, 2
    while name in taken:
        name, n = f"{base}{n}", n + 1
    return name


def propose(g: ModuleGraph, arms: int | None = None, floor: int = DEFAULT_FLOOR,
            owned: float = DEFAULT_OWNED, client: float = DEFAULT_CLIENT,
            rest: str = DEFAULT_REST) -> Proposal:
    if arms is not None and arms < 2:
        raise PillarsArgumentError(f"--arms must be at least 2 (the crowns and the floor), got {arms}")
    if not isinstance(floor, int) or isinstance(floor, bool) or floor < 0:
        raise PillarsArgumentError(f"floor must be a count of edges, 0 or more, got {floor!r}")
    if not 0.5 < owned <= 1:
        raise PillarsArgumentError(f"owned must be a fraction in (0.5, 1], got {owned}")
    if not 0 < client <= 1:
        raise PillarsArgumentError(f"client must be a fraction in (0, 1], got {client}")
    total = g.total
    fan_in = {u: g.fan_in(u) for u in g.size}
    fan_out = {u: g.fan_out(u) for u in g.size}
    traffic = {u: fan_in[u] + fan_out[u] for u in g.size}
    rulings: dict[str, Ruling] = {}
    assigned: dict[str, str] = {}          # unit -> arm
    crowns: dict[str, str] = {}
    arm_units: dict[str, list[str]] = {}

    # 1 + 2: the facade and the edge
    live: list[str] = []
    for u in sorted(g.size):
        if u == g.root:
            rulings[u] = Ruling(u, rest, "facade", fan_in[u], fan_out[u],
                                "the package root re-exports; the router, never an arm")
        elif traffic[u] < floor:
            rulings[u] = Ruling(u, rest, "edge", fan_in[u], fan_out[u],
                                f"{traffic[u]} cross-unit edge(s), under the floor of {floor}")
        else:
            live.append(u)

    # 3: roles
    orchestrators = sorted((u for u in live if fan_out[u] > fan_in[u]), key=lambda u: (-fan_out[u], u))
    foundations = sorted((u for u in live if fan_out[u] <= fan_in[u]), key=lambda u: (-fan_in[u], u))
    if not orchestrators:
        raise PillarsError(f"corpus {g.corpus!r} has no orchestrator at depth {g.depth} — every unit is "
                           f"consumed more than it consumes; cut deeper (--depth) or it is one pillar")

    # 4: crowns
    lead = fan_out[orchestrators[0]]
    if arms is not None:
        crown_units = orchestrators[: max(1, arms - 1)]
        why = f"the top {len(crown_units)} orchestrator(s) by fan-out (--arms {arms})"
    else:
        crown_units = [u for u in orchestrators if fan_out[u] * 2 >= lead]
        why = f"fan-out at least half the leader's ({lead})"
    for u in crown_units:
        name = _arm_name(u, crowns)
        crowns[name] = u
        assigned[u] = name
        arm_units[name] = [u]
        rulings[u] = Ruling(u, name, "orchestrator", fan_in[u], fan_out[u], f"crown — {why}")
    crown_rank = {name: i for i, name in enumerate(crowns)}

    def tiebreak(arm: str) -> tuple:
        return (crown_rank.get(arm, len(crown_rank)), arm)

    def by_arm(partners: dict[str, int]) -> dict[str, int]:
        out: dict[str, int] = collections.Counter()
        for u, c in partners.items():
            if u in assigned:
                out[assigned[u]] += c
        return dict(out)

    def best(counts: dict[str, int]) -> tuple[str, int] | None:
        if not counts:
            return None
        top = max(counts.values())
        return min((a for a, c in counts.items() if c == top), key=tiebreak), top

    # 5 + 6: rounds to a fixed point — orchestrators attach, then foundations settle; a unit whose
    # partners are all still unassigned waits for the next round. The floor forms in the first round a
    # foundation goes unowned, and attracts an orchestrator only as the last resort.
    floor_arm: str | None = None
    waiting = {u for u in live if u not in assigned}

    def settle_round(force: bool) -> bool:
        nonlocal floor_arm
        moved = False
        for u in sorted((u for u in waiting if u in orchestrators), key=lambda u: (-traffic[u], u)):
            hit = best(by_arm(g.consumers(u)))
            if hit:
                arm, c = hit
                how = f"orchestrated by {arm} ({c} of {fan_in[u]} consuming edges)"
            else:
                supplied = by_arm(g.suppliers(u))
                unsettled = [v for v in g.suppliers(u) if v in waiting]
                hit = best({a: c for a, c in supplied.items() if a != floor_arm})
                if hit is None and unsettled and not force:
                    continue                      # its suppliers are still unsettled — wait a round
                if hit and (arms is not None or hit[1] >= client * fan_out[u]):
                    arm, c = hit
                    strength = (f"≥ {client:.2f}" if c >= client * fan_out[u]
                                else f"under {client:.2f}, the nearest arm — --arms {arms} forbids a crown of its own")
                    how = f"client of {arm} ({c} of {fan_out[u]} consumed edges, {strength})"
                elif hit:
                    arm = _arm_name(u, crowns)
                    crowns[arm] = u
                    crown_rank[arm] = len(crown_rank)
                    arm_units[arm] = []
                    how = (f"crown — stands alone: no arm orchestrates it, and the most it spends on one arm "
                           f"is {hit[1]} of {fan_out[u]} ({hit[0]}), under {client:.2f}")
                elif floor_arm is not None and supplied.get(floor_arm):
                    arm, c = floor_arm, supplied[floor_arm]
                    how = f"leans only on the floor ({c} of {fan_out[u]} consumed edges)"
                else:
                    continue                      # nothing assigned touches it yet
            assigned[u] = arm
            arm_units[arm].append(u)
            waiting.discard(u)
            rulings[u] = Ruling(u, arm, "orchestrator", fan_in[u], fan_out[u], how)
            moved = True
        blocked = False                           # a heavier foundation is waiting: no lesser one forms the floor
        for u in sorted((u for u in waiting if u in foundations), key=lambda u: (-fan_in[u], u)):
            counts = by_arm(g.consumers(u))
            unsettled = [v for v in g.consumers(u) if v in waiting and v in orchestrators]
            hit = best(counts)
            if hit and fan_in[u] > 0 and hit[1] >= owned * fan_in[u]:
                arm, c = hit
                how = f"owned by {arm} ({c} of {fan_in[u]} consuming edges, ≥ {owned:.2f})"
            elif (unsettled or blocked) and not force:
                blocked = True                    # an orchestrator that consumes it is still attaching — wait a round
                continue
            else:
                spread = ", ".join(f"{a} {c}" for a, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
                if floor_arm is None:
                    floor_arm = _arm_name(u, crowns)
                    crowns[floor_arm] = u
                    crown_rank[floor_arm] = len(crown_rank)
                    arm_units[floor_arm] = []
                    how = (f"the floor's crown — the greatest fan-in ({fan_in[u]}) no arm owns "
                           f"({spread or 'no arm consumes it yet'})")
                else:
                    how = f"shared — no arm takes {owned:.2f} of its fan-in ({spread or 'no arm consumes it'})"
                arm = floor_arm
            assigned[u] = arm
            arm_units[arm].append(u)
            waiting.discard(u)
            rulings[u] = Ruling(u, arm, "foundation", fan_in[u], fan_out[u], how)
            moved = True
        return moved

    while waiting:
        if not settle_round(force=False) and not settle_round(force=True):
            break
    for u in sorted(waiting):
        role = "orchestrator" if u in orchestrators else "foundation"
        rulings[u] = Ruling(u, rest, role, fan_in[u], fan_out[u],
                            "no assigned unit consumes it or is consumed by it")

    order = list(crowns)
    ordered = [rulings[u] for u in sorted(rulings, key=lambda u: (
        order.index(rulings[u].arm) if rulings[u].arm in crowns else len(order), -traffic[u], u))]
    return Proposal(corpus=g.corpus, depth=g.depth, floor=floor, owned=owned, client=client, rest=rest, crowns=crowns,
                    floor_arm=floor_arm, arms={a: arm_units[a] for a in order}, rulings=ordered, total=total, relations=g.relations)


def census(data_home, corpus: str) -> dict:
    """What a lane holds, read from the receipt it already carries — no recomputation.

    Every orientation door in this engine is a code door: `pillars` ranks orchestrators by call
    direction, `descend` follows `calls`, `blast` follows the dependency family. A shard that is not
    code has no door that answers "what is in here", and the engine invites exactly those shards
    through the `static-dep` lane kind.

    The refusal `pillars` gives such a lane is CORRECT — a table does not call another table — and
    useless, because the lane is richly structured and the engine already wrote the structure down.
    A first tenant's `pg_schema` holds `column 12,469 · index 504 · table 311 · view 173` joined by
    `contains · indexes_on · references · protects`, and reading that one line out of the provenance
    by hand was a better briefing than anything `pillars` could produce for it (graphyos #76).
    """
    import json as _json
    from pathlib import Path as _P

    path = _P(data_home) / f"{corpus}_graph" / "PROVENANCE.json"
    try:
        prov = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PillarsError(
            f"corpus {corpus!r} has no readable shard receipt at {path} ({type(exc).__name__}) — "
            f"there is no census to give and no pillar shape to fall back from"
        ) from exc
    counts = prov.get("counts") or {}
    vocab = prov.get("vocabulary") or {}
    return {
        "corpus": corpus,
        "nodes": counts.get("node_count"),
        "edges": counts.get("edge_count"),
        "node_types": counts.get("node_types") or {},
        "edge_types": counts.get("edge_types") or {},
        # Whose vocabulary a reader is looking at. A lane minted by a producer this engine never
        # wrote means its type names are that producer's, not this one's.
        "producer": (prov.get("producer") or {}).get("adapter") or vocab.get("producer"),
        "relations": vocab.get("relations") or {},
    }


def render_census(c: dict) -> str:
    """``CENSUS: pg_schema — 13,513 node(s) · 26,025 edge(s), minted by sql_census`` and its types."""
    producer = f", minted by {c['producer']}" if c.get("producer") else ""
    head = (f"CENSUS: {c['corpus']} — {(c['nodes'] or 0):,} node(s) · {(c['edges'] or 0):,} edge(s)"
            f"{producer}")
    lines = [head]
    if c["node_types"]:
        lines.append("  node types: " + " · ".join(
            f"{k} {v:,}" for k, v in sorted(c["node_types"].items(), key=lambda kv: (-kv[1], kv[0]))))
    if c["edge_types"]:
        rel = c.get("relations") or {}
        lines.append("  edge types: " + " · ".join(
            f"{k} {v:,}" + (f" [{'/'.join(rel[k])}]" if rel.get(k) else "")
            for k, v in sorted(c["edge_types"].items(), key=lambda kv: (-kv[1], kv[0]))))
    if not c["node_types"] and not c["edge_types"]:
        lines.append("  the receipt carries no type census — the shard was minted before producers "
                     "wrote one, or by a producer that writes none")
    return "\n".join(lines)


def shape(store, corpus: str, *, depth: int | None = None, max_depth: int = DEFAULT_MAX_DEPTH,
          **kw) -> tuple[ModuleGraph, Proposal, int]:
    """The module graph, its proposal and the depth that answered — escalating the cut when asked.

    ``depth`` pins it: one attempt at exactly that cut, refusing as it always did. ``depth=None``
    starts at ``DEFAULT_DEPTH`` and deepens to ``max_depth``, returning the first cut that produces
    a shape, because the old refusal named the remedy — "cut deeper (--depth) or it is one pillar" —
    and then made the caller do it by hand.

    A corpus with no orchestrator at ANY depth still refuses, and the refusal says how deep it tried,
    so a genuine "this has no pillar shape" means something it did not mean before (graphyos #75).
    """
    if depth is not None:
        g = module_graph(store, corpus, depth=depth)
        return g, propose(g, **kw), depth
    if max_depth < DEFAULT_DEPTH:
        raise PillarsArgumentError(f"max_depth {max_depth} is shallower than the default cut {DEFAULT_DEPTH}")
    last: PillarsError | None = None
    for d in range(DEFAULT_DEPTH, max_depth + 1):
        try:
            g = module_graph(store, corpus, depth=d)
            return g, propose(g, **kw), d
        except PillarsArgumentError:
            # A caller error does not get retried at a deeper cut and does not become "no shape at
            # any depth": the argument is wrong at every depth, and swallowing it here turned a typo
            # into a census three lines later.
            raise
        except PillarsError as exc:
            last = exc
    # The pinned refusal says "cut deeper (--depth)". After an escalation that advice is already
    # spent, so it is replaced rather than appended to — telling a caller to do the thing the door
    # just did four times is how a refusal stops being read.
    detail = str(last).split(" — ", 1)[-1].split("; cut deeper")[0]
    raise PillarsError(
        f"corpus {corpus!r} has no orchestrator at any depth from {DEFAULT_DEPTH} to {max_depth} — "
        f"{detail}. Either it is one pillar, or raise the bound with --max-depth")


def to_partition(p: Proposal, note: str | None = None) -> dict[str, Any]:
    """The proposal as the partition file `graphy fanout --partition` cuts by."""
    doc: dict[str, Any] = {"groups": {a: list(units) for a, units in p.arms.items() if units}, "rest": p.rest}
    doc["_meta"] = note or (f"proposed by graphy pillars over corpus {p.corpus} at depth {p.depth} "
                            f"(floor {p.floor} edges, owned {p.owned:.2f}, client {p.client:.2f}); crowns: "
                            + ", ".join(f"{a}={u}" for a, u in p.crowns.items()))
    return doc


def render(p: Proposal, g: ModuleGraph | None = None) -> str:
    lines = [f"PILLARS: {p.corpus} at depth {p.depth} — {len(p.arms)} arm(s) over {p.total} cross-unit edges "
             f"({' · '.join(sorted(p.relations))}); floor {p.floor} edges, owned {p.owned:.2f}, client {p.client:.2f}"]
    for arm, units in p.arms.items():
        crown = p.crowns[arm]
        kind = "the floor" if arm == p.floor_arm else "crown"
        lines.append(f"  {arm:14} {kind}: {crown}  ·  {len(units)} unit(s)")
        for u in units:
            r = next(x for x in p.rulings if x.unit == u)
            lines.append(f"    {u:36} {r.role:12} in {r.fan_in:3}  out {r.fan_out:3}  — {r.how}")
    tail = [r for r in p.rulings if r.arm == p.rest]
    lines.append(f"  {p.rest:14} rest  ·  {len(tail)} unit(s)")
    for r in tail:
        lines.append(f"    {r.unit:36} {r.role:12} in {r.fan_in:3}  out {r.fan_out:3}  — {r.how}")
    if g is not None:
        lines.append("  cross-arm edges (from \\ to)")
        order = list(p.arms) + [p.rest]
        cross: dict[tuple[str, str], int] = collections.Counter()
        for (a, b), c in g.weight.items():
            cross[(p.arm_of(a), p.arm_of(b))] += c
        lines.append(f"    {'':14} " + " ".join(f"{a:>12}" for a in order))
        for a in order:
            lines.append(f"    {a:14} " + " ".join(f"{cross[(a, b)]:12}" for b in order))
    return "\n".join(lines)


def diff(p: Proposal, cut) -> list[dict[str, Any]]:
    """Every unit the proposal places differently from a curated partition (a fanout.Cut)."""
    moved = []
    for r in p.rulings:
        curated = cut.group_of(r.unit)
        if curated != r.arm:
            moved.append({"unit": r.unit, "proposed": r.arm, "curated": curated, "role": r.role,
                          "fan_in": r.fan_in, "fan_out": r.fan_out, "how": r.how})
    return moved


def render_diff(moved: list[dict[str, Any]], against: str) -> str:
    if not moved:
        return f"PILLARS AGREE: the proposal reproduces {against}"
    lines = [f"PILLARS DIFFER: {len(moved)} unit(s) cut differently from {against}"]
    for m in moved:
        lines.append(f"  {m['unit']:36} proposed {m['proposed']:14} curated {m['curated']:14} — {m['how']}")
    return "\n".join(lines)


def write_partition(path: str | Path, doc: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
