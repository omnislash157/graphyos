"""recon — the counterpart to ``eat``: a compiled store becomes the briefing you hand an agent.

``eat`` gets a stranger a graph and then the product stops and waits for them to already know that
``pillars`` is the orientation verb, that its depth needs escalating when it refuses, that ``blast``
is the pre-edit check, that ``estate`` takes raw SQL. None of that is discoverable from having
installed it, so the engine answers questions and ships none.

Measured on the first tenant: the MCP server was up in every session for months and ``pillars`` had
never been run once. The orientation it produces in one command was being re-derived by reading
source — at far greater cost and worse accuracy. Every developer who installs this either writes
that script themselves or never learns it was possible.

    graphy eat .        # I have a graph
    graphy recon        # I have a briefing

It is orchestration over verbs that already exist, and it invents nothing: every number here is a
count off compiled edges, and the sections a model cannot get a pillar shape for say so rather than
being filled in with prose.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from graphy import pillars as pillars_lane

__all__ = ["ReconError", "DEPTHS", "recon", "render", "default_out"]


class ReconError(RuntimeError):
    pass


# The escalation. A corpus nesting one level deeper than the default was being told it has no
# architecture; walking 2 → 3 → 4 and taking the first depth that answers is what the first tenant's
# stand-in did by hand for 13 lanes, 4 of which only answered past the default (graphyos #38).
DEPTHS = (2, 3, 4)

HOW_TO_READ = """## How to read this

```text
crown         the entry point — high out-degree, near-zero in. Start reading here.
orchestrator  calls more than it is called. Behaviour lives here.
foundation    called more than it calls. Load-bearing — changing it is expensive.
facade        the package root: re-exports, and traffic that is really its children's.
edge          under the cross-unit floor. Peripheral, or dead.
cross-arm     the traffic matrix between clusters. Asymmetry names the dependency.
```

Paste the section for the corpus you are touching. Then, for the symbol you are actually about
to change, ask the graph rather than this file:

```bash
graphy blast <symbol> --tenant {descriptor} --tenant-id {tenant_id}     # what breaks
graphy descend <symbol> --tenant {descriptor} --tenant-id {tenant_id}   # what it reaches
graphy explain <symbol> --tenant {descriptor} --tenant-id {tenant_id}   # what it is
```

Every relation a producer declared is walked, including a tenant's own: a door names the relations
it declined and why, so a zero is never mistaken for "nothing depends on this".
"""


def default_out(tenant) -> Path:
    """Beside the substrate, where the eaten repo's own .gitignore already covers it."""
    return Path(tenant.data_home) / "RECON.md"


def _census(tenant, corpus: str) -> dict:
    """A lane's own counts, from the receipt it already carries."""
    p = Path(tenant.data_home) / f"{corpus}_graph" / "PROVENANCE.json"
    try:
        prov = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    counts = prov.get("counts") or {}
    return {"nodes": counts.get("node_count"), "edges": counts.get("edge_count"),
            "node_types": counts.get("node_types") or {}, "edge_types": counts.get("edge_types") or {},
            "producer": (prov.get("producer") or {}).get("adapter") or (prov.get("vocabulary") or {}).get("producer"),
            "relations": (prov.get("vocabulary") or {}).get("relations") or {}}


def _shape(store, corpus: str, depths=DEPTHS):
    """The first depth that produces a pillar shape, or the REASON there is none, as a string.

    A corpus with no cross-unit structure is not a failure and is not argued with: a data lane
    minted by a foreign producer has nodes and edges and no module hierarchy, and saying so is the
    honest answer (graphyos #39)."""
    why = "the store owns no module-bearing node for this corpus"
    for depth in depths:
        try:
            g = pillars_lane.module_graph(store, corpus, depth=depth)
        except pillars_lane.PillarsError as exc:
            why = str(exc)
            continue
        if not g.size or g.total == 0:
            why = (f"no cross-unit edge at depth {depth} — the corpus is one unit, or its producer "
                   f"mints records rather than a module hierarchy")
            continue
        try:
            # ONE arm is a shape. Requiring two rejected a corpus whose honest answer is "this is
            # one pillar", which is a real and common answer for a small package — and it was the
            # first thing this lane got wrong on its own repo.
            return g, pillars_lane.propose(g), depth
        except pillars_lane.PillarsError as exc:
            why = str(exc)
    return why


def recon(store, tenant, tenant_id: str, *, corpora=None, depths=DEPTHS) -> dict:
    """Walk every corpus in the tenant and return the briefing's data."""
    roster = list(corpora) if corpora is not None else sorted(
        s.removesuffix("_graph") for s in tenant.build_lanes)
    if not roster:
        raise ReconError("recon: the tenant declares no build_lanes — there is nothing to brief on")
    sections = []
    for corpus in roster:
        shaped = _shape(store, corpus, depths)
        census = _census(tenant, corpus)
        if isinstance(shaped, str):
            # The reason comes from `pillars` itself, at the deepest cut tried. "no orchestrator at
            # depth 4 — every unit is consumed more than it consumes" tells a reader something;
            # "no pillar shape" tells them nothing and was what this lane said first.
            sections.append({"corpus": corpus, "shape": None, "census": census,
                             "why": shaped.removeprefix("PILLARS UNANSWERABLE: ")})
        else:
            g, p, depth = shaped
            sections.append({"corpus": corpus, "shape": {"depth": depth, "arms": len(p.arms),
                                                         "total": p.total,
                                                         "render": pillars_lane.render(p, g)},
                             "census": census, "why": None})
    return {"tenant_id": tenant_id, "generation": store.generation(),
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "corpora": roster, "sections": sections}


def _counts_table(census: dict) -> list[str]:
    rows = []
    if census.get("node_types"):
        rows.append("| node type | count |")
        rows.append("|---|---|")
        for k, v in sorted(census["node_types"].items(), key=lambda kv: (-kv[1], kv[0])):
            rows.append(f"| `{k}` | {v} |")
    if census.get("edge_types"):
        rows.append("")
        rows.append("| edge type | count | declared |")
        rows.append("|---|---|---|")
        rel = census.get("relations") or {}
        for k, v in sorted(census["edge_types"].items(), key=lambda kv: (-kv[1], kv[0])):
            cls = " · ".join(rel.get(k, [])) or "_undeclared → lexical_"
            rows.append(f"| `{k}` | {v} | {cls} |")
    return rows


def render(data: dict, *, descriptor: str, tenant_id: str) -> str:
    shaped = [s for s in data["sections"] if s["shape"]]
    flat = [s for s in data["sections"] if not s["shape"]]
    out = [
        f"# RECON — {tenant_id}: the shape of this codebase, counted off compiled edges",
        "",
        f"> `graphy recon` over `{descriptor}`. Every number is a count over the compiled store; "
        f"no model decided anything here.",
        f"> {len(data['corpora'])} corpora — {len(shaped)} with a pillar shape, "
        f"{len(flat)} answered by census. Store generation `{data['generation']}`.",
        "",
        HOW_TO_READ.format(descriptor=descriptor, tenant_id=tenant_id),
    ]
    for s in data["sections"]:
        out.append("")
        out.append(f"## {s['corpus']}")
        c = s["census"]
        if c.get("nodes") is not None:
            producer = f", minted by `{c['producer']}`" if c.get("producer") else ""
            out.append("")
            out.append(f"{c['nodes']} node(s) · {c['edges']} edge(s){producer}.")
        if s["shape"]:
            sh = s["shape"]
            out.append("")
            out.append(f"Pillars at depth {sh['depth']} — {sh['arms']} arm(s) over {sh['total']} "
                       f"cross-unit edges.")
            out.append("")
            out.append("```text")
            out.append(sh["render"])
            out.append("```")
        else:
            out.append("")
            out.append(f"**No pillar shape.** {s['why']}")
        rows = _counts_table(c)
        if rows:
            out.append("")
            out.extend(rows)
    out += [
        "",
        "## Staleness",
        "",
        f"A snapshot taken at {data['at']} against store generation `{data['generation']}`. "
        "It goes stale the moment code moves; `graphy check` is what tells you, and this file "
        "will not. Regenerate rather than trusting the date on it:",
        "",
        "```bash",
        f"graphy recon --tenant {descriptor} --tenant-id {tenant_id}",
        "```",
        "",
        "Written beside the substrate, which the eaten repo already gitignores. Never commit it — "
        "it is a build product of a store, and the store is the truth.",
        "",
    ]
    return "\n".join(out)
