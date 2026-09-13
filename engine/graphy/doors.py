"""The doors over the store: descend · blast · explain. Each is one bounded walk over the
compiled store, answered through ``neighbours``/``membership``/``record`` and nothing else — a
door never opens a shard. A symbol is resolved by exact id or by its dotted tail; two matches
refuse and name both, because a name match is never a fact.

    descend  the callees, transitively, down through the ring to the primitives; the package
             crossings the descent makes, each with the chain that made it
    blast    the dependents, transitively, against the edges — who calls, inherits, imports or
             decorates this, in the tenant's own shard and across the ring; and who mentions it —
             the history shard's exchanges that name the symbol itself (graphyos #64), a BY OWNER
             row of their own at hop 1 and never a step further: a conversation that named a
             symbol is a reader of it, not of its callers
    explain  the node's own record (where it lives, its docstring), the docs that explain it
             (the DOC_EXPLAINS family — a doc substrate's binding, or an exchange of the history
             shard that mentions it), the tests that reach it, and the journal page that
             birthed its shard
"""
from __future__ import annotations

import json

from dataclasses import dataclass, field

from graphy.cross_substrate import AGAINST, BOTH, WITH, WIRE_BUCKET, explanations_from_store
from graphy.federated_store import relations_in
from graphy.ir import DEPENDS, REACHES

# The DEFAULTS, not the law (graphyos #68). A store whose lanes declare their relation vocabulary
# answers from the declaration; one whose lanes declare nothing — every shard minted before this
# existed — falls back to exactly these, so the doors are byte-identical on an old store.
DESCEND_RELATIONS = frozenset({"calls"})
BLAST_RELATIONS = frozenset({"calls", "inherits", "imports", "decorates"})


def descend_relations(store) -> frozenset:
    """What ``descend`` walks over this store: the declared REACHES family, else the default."""
    return relations_in(store, REACHES, DESCEND_RELATIONS)


def blast_relations(store) -> frozenset:
    """What ``blast`` walks against over this store: the declared DEPENDS family, else the default."""
    return relations_in(store, DEPENDS, BLAST_RELATIONS)
SEED_RELATIONS = frozenset({"mentions"})   # admitted from the seed only: a conversation that named X is X's reader, never its callers' (graphyos #64)
TEST_ROLE = "test"     # the producer says what a test is; a door never reads a filename


class DoorError(RuntimeError):
    pass


def resolve(store, symbol: str) -> str:
    """The node id a symbol names. Exact id first; else the nodes whose dotted tail is the
    symbol. One match answers, none refuses, two or more refuse and list them."""
    if store.membership(symbol) is not None:
        return symbol
    hits = sorted(store.find(symbol))
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise DoorError(f"{symbol!r} names no node in this store — an exact id or a dotted tail")
    shown = "\n    ".join(hits[:20])
    more = f"\n    … {len(hits) - 20} more" if len(hits) > 20 else ""
    raise DoorError(f"{symbol!r} names {len(hits)} nodes; a door never guesses. Pick one:\n    {shown}{more}")


@dataclass
class Reach:
    node: str
    hop: int
    via: str | None
    relation: str | None
    owner: str


def _bfs(store, seed: str, max_depth: int, relations: frozenset, direction: str,
         seed_relations: frozenset = frozenset()) -> dict[str, Reach]:
    """One frontier per level; an edge counts when its relation is admitted and it points the
    way the door walks (``with`` = out of the frontier node, ``against`` = into it). A relation in
    ``seed_relations`` is admitted only out of the seed itself — it names the seed's own readers and
    never carries the walk further."""
    reached = {seed: Reach(seed, 0, None, None, store.membership(seed) or WIRE_BUCKET)}
    frontier = [seed]
    for hop in range(1, max_depth + 1):
        nxt: list[str] = []
        admitted = relations | seed_relations if hop == 1 else relations
        for node in frontier:
            for nb in store.neighbours(node):
                if nb.relation not in admitted or nb.direction not in (direction, BOTH):
                    continue
                if nb.node in reached:
                    continue
                reached[nb.node] = Reach(nb.node, hop, node, nb.relation,
                                         store.membership(nb.node) or WIRE_BUCKET)
                nxt.append(nb.node)
        frontier = nxt
        if not frontier:
            break
    return reached


def declined(store, seed: str, admitted: frozenset, direction: str) -> dict[str, int]:
    """The edges ON THE SEED that point the way this door walks and were NOT admitted, counted by
    relation (graphyos #69).

    A door that answers zero is making one of two very different statements — "nothing depends on
    this" or "I declined to read every edge that does" — and for a tool whose whole contract is that
    no model decided an edge, printing the same thing for both is the worst available answer. The
    store knows the difference one query away, so the door says which it means."""
    out: dict[str, int] = {}
    for nb in store.neighbours(seed):
        if nb.direction not in (direction, BOTH) or nb.relation in admitted:
            continue
        out[nb.relation] = out.get(nb.relation, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def render_declined(counts: dict[str, int], classes: dict[str, list[str]], *, answered: int) -> str:
    """``NOT WALKED: …``, or empty when there is nothing a reader could act on.

    Two kinds of unwalked edge, and conflating them is how a true notice becomes noise. A relation
    its producer DECLARED structural or lexical was skipped on purpose — `contains` sits on nearly
    every node in a code shard, and telling a reader to go declare it, on every healthy blast, would
    train them to scroll past the line that matters. A relation NOBODY declared took the default,
    and that is the one worth a word, because it is the case where the door's silence and the
    graph's content actually disagree (graphyos #69).

    So the notice is printed when the answer was zero — where a reader could otherwise conclude
    "nothing depends on this" — or when an undeclared relation was skipped at any result size."""
    if not counts:
        return ""
    undeclared = {r: n for r, n in counts.items() if not classes.get(r)}
    if answered and not undeclared:
        return ""
    shown = " · ".join(f"{rel} {n}" for rel, n in counts.items())
    line = f"  NOT WALKED: {shown} — {sum(counts.values())} edge(s) on this seed this door does not walk."
    if undeclared:
        names = " · ".join(sorted(undeclared))
        line += (f" No producer declared what {names} mean, so the default was taken. Declare them in "
                 f"the minting producer's vocabulary (graphy.ir: depends · reaches · structural · "
                 f"lexical) and re-mint that lane.")
    else:
        told = " · ".join(f"{r}={'/'.join(classes[r])}" for r in counts)
        line += f" Every one is declared and deliberate: {told}."
    return line


def chain(reached: dict[str, Reach], node: str) -> list[str]:
    out: list[str] = []
    at: str | None = node
    while at is not None:
        out.append(at)
        at = reached[at].via
    out.reverse()
    return out


@dataclass
class Crossing:
    src_owner: str
    dst_owner: str
    hop: int
    src: str
    dst: str
    relation: str
    count: int = 1


@dataclass
class Descent:
    seed: str
    owner: str
    depth: int
    reached: dict[str, Reach]
    by_owner: dict[str, int]
    crossings: list[Crossing]
    primitives: list[Reach]
    packages: list[str] = field(default_factory=list)
    declined: dict[str, int] = field(default_factory=dict)      # graphyos #69
    declined_classes: dict[str, list[str]] = field(default_factory=dict)


def descend(store, seed: str, max_depth: int = 4) -> Descent:
    walked = descend_relations(store)
    reached = _bfs(store, seed, max_depth, walked, WITH)
    by_owner: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    crossings: dict[tuple[str, str], Crossing] = {}
    for r in reached.values():
        by_owner[r.owner] = by_owner.get(r.owner, 0) + 1
        first_seen.setdefault(r.owner, r.hop)
        if r.hop > 0 and r.owner != reached[r.via].owner:
            key = (reached[r.via].owner, r.owner)
            c = crossings.get(key)
            if c is None:
                crossings[key] = Crossing(key[0], key[1], r.hop, r.via, r.node, r.relation or "")
            else:
                c.count += 1
                if r.hop < c.hop:
                    c.hop, c.src, c.dst, c.relation = r.hop, r.via, r.node, r.relation or ""
    # a primitive is a callee that calls nothing the store carries, at the deepest hops first
    primitives = [r for r in reached.values() if r.hop > 0 and not any(
        nb.relation in walked and nb.direction in (WITH, BOTH) for nb in store.neighbours(r.node))]
    primitives.sort(key=lambda r: (-r.hop, r.owner, r.node))
    packages = sorted(first_seen, key=lambda o: (first_seen[o], o))
    return Descent(seed, reached[seed].owner, max_depth, reached, by_owner,
                   sorted(crossings.values(), key=lambda c: (c.hop, c.src_owner, c.dst_owner)),
                   primitives, packages, (_dec := declined(store, seed, walked, WITH)),
                   {r: list(getattr(store, 'relations', {}).get(r) or []) for r in _dec})


@dataclass
class Blast:
    seed: str
    owner: str
    depth: int
    reached: dict[str, Reach]
    by_owner: dict[str, int]
    by_hop: dict[int, int]
    own: list[Reach]
    ring: list[Reach]
    declined: dict[str, int] = field(default_factory=dict)      # graphyos #69
    declined_classes: dict[str, list[str]] = field(default_factory=dict)


def blast(store, seed: str, max_depth: int = 4) -> Blast:
    walked = blast_relations(store)
    reached = _bfs(store, seed, max_depth, walked, AGAINST, SEED_RELATIONS)
    owner = reached[seed].owner
    by_owner: dict[str, int] = {}
    by_hop: dict[int, int] = {}
    own: list[Reach] = []
    ring: list[Reach] = []
    for r in reached.values():
        if r.hop == 0:
            continue
        by_owner[r.owner] = by_owner.get(r.owner, 0) + 1
        by_hop[r.hop] = by_hop.get(r.hop, 0) + 1
        (own if r.owner == owner else ring).append(r)
    key = lambda r: (r.hop, r.owner, r.node)  # noqa: E731
    return Blast(seed, owner, max_depth, reached, by_owner, dict(sorted(by_hop.items())),
                 sorted(own, key=key), sorted(ring, key=key),
                 (_dec := declined(store, seed, walked | SEED_RELATIONS, AGAINST)),
                 {r: list(getattr(store, "relations", {}).get(r) or []) for r in _dec})


@dataclass
class Explanation:
    seed: str
    owner: str
    record: dict | None
    docs: list[dict]
    tests: list[Reach]
    journal: dict | None
    journal_note: str
    tests_note: str = ""          # why TESTS is empty, from the mechanism and never a guess (graphyos #69, #72)


def minted_from_distribution(tenant, owner: str) -> str | None:
    """The distribution a lane was minted from, when its provenance says so — else None.

    A ring lane's corpus sits inside the site-packages the ring was resolved from, and `ring.json`
    records that directory. A repo eaten in place does not, even when its package happens to be
    installed. So "this came from a wheel" is read off two receipts that already exist, and a lane
    that cannot prove it simply does not claim it (graphyos #72)."""
    if tenant is None:
        return None
    try:
        from pathlib import Path as _P
        home = _P(tenant.data_home)
        prov = json.loads((home / f"{owner}_graph" / "PROVENANCE.json").read_text(encoding="utf-8"))
        corpus = prov.get("corpus") or {}
        path = corpus.get("path")
        dist = corpus.get("distribution")
        if not path or not dist:
            return None
        site = json.loads((home / "ring.json").read_text(encoding="utf-8")).get("site_packages")
        if not site:
            return None
        _P(path).resolve().relative_to(_P(site).resolve())        # raises when it is not under it
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    version = corpus.get("version")
    return f"{dist} {version}" if version else str(dist)


def explain(store, seed: str, max_depth: int = 3, tenant=None) -> Explanation:
    owner = store.membership(seed) or WIRE_BUCKET
    record = store.record(seed)
    docs = explanations_from_store(store, seed, max_depth)
    dependents = _bfs(store, seed, max_depth, blast_relations(store), AGAINST, SEED_RELATIONS)
    tests: list[Reach] = []
    for r in dependents.values():
        if r.hop == 0:
            continue
        rec = store.record(r.node) or {}
        if rec.get("role") == TEST_ROLE:
            tests.append(r)
    tests.sort(key=lambda r: (r.hop, r.owner, r.node))
    page, note = None, "no tenant declared — the journal is not reachable"
    if tenant is not None:
        from graphy import journal
        try:
            header, pages, torn = journal.read_journal(owner, tenant=tenant)
        except (OSError, ValueError) as exc:
            note = f"journal unreadable ({type(exc).__name__}: {exc})"
        else:
            if header is None and not pages:
                note = f"no journal page for {owner}_graph under {tenant.journal}"
            else:
                page = pages[0] if pages else header
                note = f"{len(pages)} page(s), {torn} torn"
    # The mechanism, never a cause. This line used to read "the ring is minted from wheels, which
    # carry no test suite" for EVERY seed no test reached — a stranger's own untested function, a
    # Postgres table in a foreign lane, anything. A door that never guesses an edge must not guess a
    # reason; the DOCS line one row above is the model, naming what it looked through (graphyos #72).
    walked = " · ".join(sorted(blast_relations(store))) or "no admitted relation"
    tests_note = f"none reach it within depth {max_depth} against the {walked} family"
    dist = minted_from_distribution(tenant, owner)
    if dist is not None:
        tests_note += f" — {owner} is minted from the installed {dist}, and a wheel carries no test suite"
    return Explanation(seed, owner, record, docs, tests, page, note, tests_note)


# ── rendering ───────────────────────────────────────────────────────────────────────────────

_ARROW = {WITH: "─calls▶", AGAINST: "◀─", BOTH: "◀─▶"}


def _fmt_chain(reached: dict[str, Reach], node: str) -> str:
    ids = chain(reached, node)
    parts = [ids[0]]
    for b in ids[1:]:
        parts.append(f" ─{reached[b].relation}▶ {b}")
    return "".join(parts)


def render_descend(d: Descent, limit: int = 12) -> str:
    lines = [f"DESCEND seed={d.seed} owner={d.owner} depth={d.depth} reached={len(d.reached) - 1} "
             f"packages={' → '.join(d.packages)}"]
    lines.append("  BY OWNER: " + "  ".join(f"{o}={n}" for o, n in sorted(d.by_owner.items(), key=lambda kv: -kv[1])))
    if (note := render_declined(d.declined, d.declined_classes, answered=len(d.reached) - 1)):
        lines.append(note)
    for c in d.crossings:
        lines.append(f"  CROSSING {c.src_owner} → {c.dst_owner} @hop{c.hop} ×{c.count}: {_fmt_chain(d.reached, c.dst)}")
    if d.primitives:
        lines.append(f"  PRIMITIVES (callees that call nothing the store carries, deepest first, {len(d.primitives)}):")
        for r in d.primitives[:limit]:
            lines.append(f"    hop{r.hop} {r.owner:<16} {r.node}")
        if len(d.primitives) > limit:
            lines.append(f"    … {len(d.primitives) - limit} more (--limit)")
    return "\n".join(lines)


def render_blast(b: Blast, limit: int = 12) -> str:
    total = len(b.reached) - 1
    lines = [f"BLAST seed={b.seed} owner={b.owner} depth={b.depth} dependents={total} "
             f"own={len(b.own)} ring={len(b.ring)}"]
    lines.append("  BY HOP: " + "  ".join(f"hop{h}={n}" for h, n in b.by_hop.items()))
    lines.append("  BY OWNER: " + "  ".join(f"{o}={n}" for o, n in sorted(b.by_owner.items(), key=lambda kv: -kv[1])))
    if (note := render_declined(b.declined, b.declined_classes, answered=len(b.reached) - 1)):
        lines.append(note)
    for title, rows in (("OWN", b.own), ("RING", b.ring)):
        if not rows:
            continue
        lines.append(f"  {title} ({len(rows)}), nearest first:")
        for r in rows[:limit]:
            lines.append(f"    hop{r.hop} {r.owner:<16} {r.node}  ◀─{r.relation}─ {r.via}")
        if len(rows) > limit:
            lines.append(f"    … {len(rows) - limit} more (--limit)")
    return "\n".join(lines)


def render_explain(e: Explanation, limit: int = 12) -> str:
    lines = [f"EXPLAIN seed={e.seed} owner={e.owner}"]
    rec = e.record
    if rec is None:
        lines.append("  RECORD: none retained — this id was seen only as an edge endpoint")
    else:
        where = f"{rec.get('file')}:{rec.get('line')}" if rec.get("file") else "(no file)"
        sig = ", ".join(rec.get("args") or [])
        lines.append(f"  RECORD: {rec.get('node_type', '?')} {rec.get('dotted') or rec.get('name')} at {where}"
                     + (f" ({sig})" if sig else "") + (f" -> {rec['returns']}" if rec.get("returns") else ""))
        doc = (rec.get("docstring") or "").strip()
        if doc:
            head = doc.splitlines()
            for line in head[:6]:
                lines.append(f"    │ {line[:110]}")
            if len(head) > 6:
                lines.append(f"    │ … {len(head) - 6} more line(s)")
        else:
            lines.append("    │ (no docstring)")
    if e.docs:
        lines.append(f"  DOCS (DOC_EXPLAINS endpoints, {len(e.docs)}):")
        for d in e.docs[:limit]:
            lines.append(f"    hop{d['hops']} {d['relation']:<14} {d['id']}")
    else:
        lines.append("  DOCS: none — no rostered doc substrate binds this node through the DOC_EXPLAINS family")
    if e.tests:
        lines.append(f"  TESTS (test modules that reach it against the edges, {len(e.tests)}):")
        for r in e.tests[:limit]:
            lines.append(f"    hop{r.hop} {r.owner:<16} {r.node}")
        if len(e.tests) > limit:
            lines.append(f"    … {len(e.tests) - limit} more (--limit)")
    else:
        lines.append(f"  TESTS: {e.tests_note}" if e.tests_note else
                     "  TESTS: none reach it within the depth")
    if e.journal:
        j = e.journal
        lines.append(f"  HISTORY: {e.owner}_graph journal — {e.journal_note}; first page "
                     f"{j.get('at') or j.get('ts') or ''} cursor={j.get('cursor') or j.get('cursor_after') or '?'}")
    else:
        lines.append(f"  HISTORY: {e.journal_note}")
    return "\n".join(lines)
