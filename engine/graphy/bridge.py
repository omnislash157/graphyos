"""bridge — a walk from one tenant into another, through a declared join.

Two tenants open in one process, each through its own descriptor, each reading only its own
data_home: ``open_for`` takes the tenant it is handed and nothing else, so neither store ever
sees the other's shards, registry, scheme index or journal. The bridge holds the two stores side
by side and walks a frontier of ``(side, id)`` pairs.

The join is the law's wormhole: the same literal is a node id in both stores because both tenants
minted the same package into their ring. The bridge crosses on such a literal only when its
scheme is DECLARED (``--join <scheme>``). No join declared refuses; a join naming a scheme one
side does not carry refuses; a literal shared under an undeclared scheme is two nodes that happen
to spell the same, and the walk stays on its side. No model, no name match, no resolver: a
crossing is the identity of one string.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from graphy import federated_store as fstore
from graphy.tenant import Tenant

__all__ = ["BridgeError", "Side", "Hop", "BridgeResult", "open_sides", "verify_joins", "cross",
           "render"]

JOIN = "join"


class BridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Side:
    """One tenant as the bridge sees it: its name, its descriptor, its own store."""
    tenant_id: str
    tenant: Tenant
    store: object

    @property
    def data_home(self) -> Path:
        return Path(self.tenant.data_home)


@dataclass(frozen=True)
class Hop:
    side_src: str
    src: str
    relation: str          # an edge type, or JOIN for the crossing
    direction: str         # with · against · both, or the join scheme for a crossing
    side_dst: str
    dst: str
    owner_src: str
    owner_dst: str

    @property
    def crossing(self) -> bool:
        return self.relation == JOIN


@dataclass
class BridgeResult:
    seed: str
    target: str
    joins: tuple[str, ...]
    found: bool
    hops: list = field(default_factory=list)
    visited: int = 0
    stopped_by: str | None = None
    seed_sides: tuple[str, ...] = ()
    target_sides: tuple[str, ...] = ()

    @property
    def crossings(self) -> int:
        return sum(1 for h in self.hops if h.crossing)


def _scheme(node_id: str) -> str:
    return node_id.split("://", 1)[0] if "://" in node_id else ""


def open_sides(pairs: list[tuple[Tenant, str]], *, on_stale: str = "refuse",
               roster_of=None) -> list[Side]:
    """Open every (tenant, tenant_id) through its own descriptor. Two sides naming the same
    data_home are one tenant twice, and refused: a bridge joins different estates."""
    if len(pairs) < 2:
        raise BridgeError(f"a bridge needs two tenants, got {len(pairs)} — one tenant is `graphy walk`")
    sides: list[Side] = []
    seen_homes: dict[Path, str] = {}
    seen_ids: set[str] = set()
    for tenant, tenant_id in pairs:
        if not tenant_id or not tenant_id.strip():
            raise BridgeError("every side needs a --tenant-id — graphy resolves identity only through a declared Tenant")
        if tenant_id in seen_ids:
            raise BridgeError(f"tenant-id {tenant_id!r} names two sides — each side of a bridge is its own tenant")
        home = Path(tenant.data_home).resolve()
        if home in seen_homes:
            raise BridgeError(f"{tenant_id!r} and {seen_homes[home]!r} share the data_home {home} — "
                              "a bridge joins two tenants, not one tenant twice")
        roster = roster_of(tenant) if roster_of else _roster(tenant)
        store = fstore.open_for(roster, tenant=tenant, tenant_id=tenant_id, on_stale=on_stale)
        sides.append(Side(tenant_id=tenant_id, tenant=tenant, store=store))
        seen_homes[home] = tenant_id
        seen_ids.add(tenant_id)
    return sides


def _roster(tenant: Tenant) -> list[str]:
    from graphy import journal
    return sorted({journal._names(key)[1] for key in tenant.build_lanes})


def verify_joins(sides: list[Side], joins: list[str], *, roster_of=None,
                 allow_skew: bool = False) -> dict[str, dict[str, dict]]:
    """Every declared join scheme must be carried by every side; the receipt is, per side, how
    many node ids it holds under the scheme and the release its shard's PROVENANCE pins. Two
    sides pinning different releases is the version-identity law's refusal — the literal would
    name two things — unless the operator carries the skew with ``allow_skew``, and then it is
    printed, never silent. An undeclared join is a refusal, never a default."""
    from graphy.release import roster_releases, UNPINNED
    if not joins:
        raise BridgeError("no --join declared — a bridge crosses only on a declared scheme; "
                          "name the package both tenants minted (e.g. --join typing_extensions)")
    receipt: dict[str, dict[str, dict]] = {}
    pins_of_side = {}
    for s in sides:
        roster = roster_of(s.tenant) if roster_of else _roster(s.tenant)
        pins_of_side[s.tenant_id] = roster_releases(s.data_home, roster)
    for scheme in joins:
        if not scheme or "://" in scheme or "/" in scheme:
            raise BridgeError(f"--join {scheme!r} is not a scheme — name the bare package, e.g. typing_extensions")
        row: dict[str, dict] = {}
        for s in sides:
            n = len(s.store.grep(f"{scheme}://"))
            by_slug = pins_of_side[s.tenant_id].get(scheme) or {}
            pins = sorted({r.pin for r in by_slug.values()}) or [UNPINNED]
            row[s.tenant_id] = {"nodes": n, "release": " | ".join(pins), "skew": False}
        missing = [tid for tid, r in row.items() if r["nodes"] == 0]
        if missing:
            raise BridgeError(f"--join {scheme}: no node under {scheme}:// in tenant(s) "
                              f"{', '.join(missing)} — a join is a literal both sides carry; "
                              "mint the package into that ring or name another")
        pinned = {r["release"] for r in row.values() if r["release"] != UNPINNED}
        if len(pinned) > 1:
            named = " · ".join(f"{tid} {r['release']}" for tid, r in row.items())
            if not allow_skew:
                raise BridgeError(f"--join {scheme}: the two sides pin different releases ({named}) — "
                                  "a node id is a name, and the same literal would mean two things; "
                                  "re-mint one ring at the other's release, or carry the skew with --allow-release-skew")
            for r in row.values():
                r["skew"] = True
        receipt[scheme] = row
    return receipt


def cross(sides: list[Side], joins: list[str], seed: str, target: str, *,
          max_depth: int = 8, max_nodes: int = 250_000) -> BridgeResult:
    """Breadth-first over (side, id). A hop follows one side's own edges; a crossing moves the
    same literal to another side that holds it, only when its scheme is declared."""
    joined = frozenset(joins)
    by_id = {s.tenant_id: s for s in sides}
    seed_sides = tuple(s.tenant_id for s in sides if s.store.membership(seed) is not None)
    target_sides = tuple(s.tenant_id for s in sides if s.store.membership(target) is not None)
    res = BridgeResult(seed=seed, target=target, joins=tuple(joins), found=False,
                       seed_sides=seed_sides, target_sides=target_sides)
    if not seed_sides:
        res.stopped_by = "seed-absent"
        return res
    if not target_sides:
        res.stopped_by = "target-absent"
        return res

    prev: dict[tuple[str, str], tuple] = {(sid, seed): (None, None, None) for sid in seed_sides}
    frontier = list(prev)
    hops = 0
    reached: tuple[str, str] | None = next(((sid, seed) for sid in seed_sides if seed == target), None)
    stopped = None
    while reached is None and stopped is None and frontier and hops < max_depth:
        hops += 1
        nxt: list[tuple[str, str]] = []
        for state in frontier:
            sid, nid = state
            nbrs = [((sid, nb.node), nb.relation, nb.direction) for nb in by_id[sid].store.neighbours(nid)]
            if _scheme(nid) in joined:
                for other in sides:
                    if other.tenant_id != sid and other.store.membership(nid) is not None:
                        nbrs.append(((other.tenant_id, nid), JOIN, _scheme(nid)))
            for nstate, rel, direction in nbrs:
                if nstate in prev:
                    continue
                prev[nstate] = (state, rel, direction)
                if nstate[1] == target:
                    reached = nstate
                    break
                if len(prev) > max_nodes:
                    stopped = "max_nodes"
                    break
                nxt.append(nstate)
            if reached is not None or stopped:
                break
        frontier = nxt
    res.visited = len(prev)
    if reached is None:
        if stopped is None and hops >= max_depth and frontier:
            stopped = "max_depth"
        res.stopped_by = stopped
        return res

    chain: list[tuple[str, str]] = []
    at: tuple[str, str] | None = reached
    while at is not None:
        chain.append(at)
        at = prev[at][0]
    chain.reverse()
    for a, b in zip(chain, chain[1:]):
        _p, rel, direction = prev[b]
        res.hops.append(Hop(side_src=a[0], src=a[1], relation=rel, direction=direction or "unknown",
                            side_dst=b[0], dst=b[1],
                            owner_src=by_id[a[0]].store.membership(a[1]) or "",
                            owner_dst=by_id[b[0]].store.membership(b[1]) or ""))
    res.found = True
    return res


def render(res: BridgeResult, receipt: dict[str, dict[str, dict]] | None = None, *,
           max_depth: int = 8, max_nodes: int = 250_000) -> tuple[str, int]:
    """The hops as text and the exit code: 0 a path, 1 no path or unanswerable."""
    lines: list[str] = []
    for scheme, row in (receipt or {}).items():
        lines.append(f"JOIN {scheme}: " + " · ".join(
            f"{tid} holds {r['nodes']} node(s) at {r['release']}" for tid, r in row.items()))
        if any(r.get("skew") for r in row.values()):
            lines.append(f"JOIN {scheme} SKEW: the sides pin different releases and the operator carries it — "
                         "the crossing literal names two releases of one package")
    if res.found:
        lines.append(f"BRIDGE PATH: seed={res.seed} target={res.target} hops={len(res.hops)} "
                     f"crossings={res.crossings} visited={res.visited}")
        first = res.hops[0] if res.hops else None
        lines.append(f"  [{first.side_src if first else res.seed_sides[0]}] {res.seed}")
        for h in res.hops:
            if h.crossing:
                arrow = f"=={JOIN} {h.direction}==>"
            elif h.direction == "with":
                arrow = f"--{h.relation}-->"
            elif h.direction == "against":
                arrow = f"<--{h.relation}--"
            else:
                arrow = f"<--{h.relation}-->"
            lines.append(f"    {arrow} [{h.side_dst}] {h.dst}")
        return "\n".join(lines), 0
    if res.stopped_by == "seed-absent":
        lines.append(f"BRIDGE UNANSWERABLE: seed {res.seed} absent from every side")
    elif res.stopped_by == "target-absent":
        lines.append(f"BRIDGE UNANSWERABLE: target {res.target} absent from every side")
    elif res.stopped_by == "max_depth":
        lines.append(f"BRIDGE BUDGET-EXHAUSTED: max_depth={max_depth} (visited={res.visited}) — "
                     "a path may still exist; raise --max-depth")
    elif res.stopped_by == "max_nodes":
        lines.append(f"BRIDGE BUDGET-EXHAUSTED: max_nodes={max_nodes} (visited={res.visited}) — "
                     "a path may still exist; raise --max-nodes")
    else:
        lines.append(f"BRIDGE NO-PATH: search exhausted (visited={res.visited}) — "
                     f"no declared join ({', '.join(res.joins)}) connects them")
    return "\n".join(lines), 1
