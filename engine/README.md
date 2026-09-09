# Graphy

**Created by Matt Hartigan, 2026.**

Bolt it onto a repo and it eats the whole thing: your package and every package it imports,
minted into one walkable substrate, resolved through the code's own scope, compiled into a
store, with parquet beside every shard. A walk is a query, never a load. If a hop parses a
file, it is not a traversal.

## Install

```bash
pip install 'graphyos[estate]'   # the distribution; [estate] adds duckdb for the parquet estate
```

Everything you type after install is `graphy` — the import, the CLI, the artifacts. Python 3.10+.

## Use

```bash
graphy eat      --repo <abs> --site-packages <abs> [--package <name>]   # the bolt-on: everything below, into <repo>/.graphy
graphy smash    --package <name> --site-packages <abs> --out <abs>      # mint a package and its import ring
graphy init     --tenant <descriptor> --root <abs> --data-home <abs> …   # declare a tenant: every path absolute, nothing ambient
graphy converge --tenant <descriptor> --tenant-id <name> [--resolve]     # the seam per shard pair; resolve text labels through scope
graphy build    --tenant <descriptor> --tenant-id <name>                 # compile the store; emit the parquet when duckdb is present
graphy walk     --tenant <descriptor> --tenant-id <name> --seed <id> --target <id>
graphy estate   --tenant <descriptor> --tenant-id <name> --sql "<over adj, nodes and walks>"
graphy traversals --tenant <descriptor> --tenant-id <name> [--replay]
graphy descend  <symbol> --tenant <descriptor> --tenant-id <name>   # the callees down to the primitives, every package crossing
graphy blast    <symbol> …                                           # the dependents against the edges, own shard and ring
graphy explain  <symbol> …                                           # the record, the docs, the tests that reach it, the journal page
graphy mcp      --tenant <descriptor> --tenant-id <name>              # the five doors as MCP tools on stdio, for Claude Code / Cursor / any client
graphy shell install --repo <abs>       # the hooks and the walk-before-edit gate, into an eaten repo — see graphy/shell/README.md
graphy check    --tenant <descriptor> --tenant-id <name>                 # read-only audit: exit 0 healthy, 1 a verdict, 2 never ran
graphy fanout   --graph-dir <shard> --out <dir>                          # the fan-out, with a receipt
graphy harness  --repo <abs> [--tenant <descriptor> --tenant-id <name>] [--corpus <pkg>]  # the hub: GRAPH.md, arms, drawings, walk receipts
```

## The four pillars

```
json   JSON is the cheapest machine currency
keys   we own the join keys, in one central registry
ast    AST is hierarchy, not magic — anything with rules becomes AST
lens   the whole world is traversable through our lens
```

## Two laws worth stating up front

**No ambient fallback. An absent tenant refuses.** The engine never defaults to a tenant, a
root, or a data home. Every one of them is a declared field on the descriptor, and an absent
one is an error rather than a guess. Two tenants run in one process without either being able
to read the other's data.

**No model ever decides an edge.** Every edge is one of exactly three things: structural (built
from the syntax tree), a wormhole (the same literal is a node id in two or more graphs — free by
construction), or a label resolved through the scope that binds it (the module's own definitions
and imports, `self`, `super`). Similarity alone parks forever and never graduates; a name match
is never an edge.

## Vocabulary is declared per producer

The Graph IR is the boundary — typed node, edge, provenance and evidence records. AST is one
producer among several, never the contract. Each adapter declares its own vocabulary and they
mutually refuse: `validate_graph(nodes, edges, Vocabulary(...))` returns a count or raises.

## License

Apache 2.0 — see `LICENSE`. Attribution propagates through `NOTICE` (Apache §4(d)).
"Graphy" and "GraphyOS" are trademarks; the license grants no trademark rights (§6).

<!-- mcp-name: io.github.omnislash157/graphyos -->
