# graphy

Eat a codebase. Walk it. Draw it. Remember what you said about it.

[![ci](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml/badge.svg)](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/graphyos)](https://pypi.org/project/graphyos/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/graphyos/)
[![MCP registry](https://img.shields.io/badge/MCP-io.github.omnislash157%2Fgraphyos-black)](https://registry.modelcontextprotocol.io/v0/servers?search=graphyos)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Models will build you a slop cathedral overnight. `/clear` then burns the three hours you spent learning the floor plan. graphy compiles the repo into a graph the agent walks instead of rereads, hangs a 2D map and a 3D galaxy on it, and keeps the session tails as text you can grep.

No embeddings. No summarizer. No model picks an edge. If two things are connected, the code connected them.

The pictures for ten repos people know: [graphy-os.com](https://graphy-os.com)

![graphy's own pillars, drawn from its own store](docs/pillars.svg)

Matt Hartigan, 2026. Apache 2.0.

## Run it

Package is `graphyos`. Command is `graphy`. Python 3.10+. Linux, macOS, Windows.

```bash
pip install 'graphyos[typescript]'
cd /path/to/your/repo
graphy eat .
graphy showcase .
```

Open `.graphy/showcase/index.html`. That is the 2D atlas. The 3D galaxy is on the same page's explorer, and on the public gallery for httpx, FastAPI, Hono, zod, and the rest.

Hook the session so the next one starts where this one died, and so a rebuild can ride SessionStart:

```bash
graphy shell install --repo "$PWD"
```

Claude Code on Windows needs Git Bash for those hooks. Codex and Cursor get `.cmd` twins and do not. After `pip install -U graphyos`, kill any live `graphy mcp` and start it again — an old server will call a new store stale and tell you to rebuild something that is fine.

Or skip the venv:

```bash
uvx --from 'graphyos[typescript]' graphy showcase .
```

Stranger's repo? Do not let eat run their build.

```bash
graphy eat . --no-provision
graphy showcase https://github.com/you/your-repo.git --no-provision
```

Several packages in one checkout:

```bash
graphy eat . --package app --site-packages .
```

`showcase` still does not take those flags. Eat first.

## What you get

A store under `<repo>/.graphy/` that answers questions without a model in the loop.

```text
iterate_in_threadpool in Starlette is about to change.
What in FastAPI breaks, and through which call chain?

graphy alone, no model          0.00s    0 tokens     5/5 dependents
haiku + graphy MCP             14.8s    48k in        5/5
opus + 270 KB of source        26.5s    103k in       5/5
```

Same five functions. The store does it in a millisecond. Full run is `RECON.md` §20.

The verbs are the same on the terminal and over MCP:

`hunt` · `descend` · `blast` · `walk` · `draw` · `explain` · `history`

`blast` is blast radius. `walk` is does A reach B. `draw` is the neighborhood. `history` is every session that named the symbol, oldest first, with the commits.

Session tails land in `.claude/recovery/` as markdown. Not a summary. The actual back and forth, tool noise stripped, a sha on every tail. Two words through lightning/bloodhound and you get every place they co-occurred.

Rebuild is a generation, not a wipe. SessionStart and an hourly cron can remint a stale shard and leave the last good store up while the next one lands. That is the point if models are still writing the repo while you sleep.

## What an edge is

Three things, and only three.

1. **Structural.** The tree said so: import, contains, inherits, decorates, calls, or a name used as a value (dispatch table, callback, decorator argument).
2. **Wormhole.** The same node id exists in two shards by construction. `starlette://module/starlette.routing` is an edge target in FastAPI and a node in Starlette. That is a join, not a guess.
3. **Resolved label.** A call the producer left as text, bound through the scope that actually binds it. Same module, import, re-export, `self`, `super`. If no rule reaches it, it stays text, with the reason.

A name match is never an edge. The first version of this welded literals. That lied the first time two modules shared a name. This one does not.

Shards stay shards. The estate is SQL over all of them. You can mint a database next to a bot and walk invoice ids without flattening the world into one soup.

## Languages

Python via the stdlib parser. TypeScript / TSX / JavaScript via tree-sitter (`[typescript]`). SvelteKit `$lib` and `compilerOptions.paths` resolve. Nothing else yet.

`[estate]` is DuckDB for the parquet estate. Without it the JSON doors still work and the build says `CONTAINER SKIPPED` instead of pretending.

## Windows

Supported. CI `store-windows` runs the floor on `windows-latest`. A 32-lane tenant, 177k nodes / 460k edges, compiled green off the published wheel. Shards minted there are byte-identical to shards minted on Linux. Locks are real (`msvcrt.locking`). Verbs close their store so Windows does not `WinError 5` the landing. Consoles that only speak cp1252 do not crash a draw.

Claude Code memory hooks still go through Git Bash. No bash, that lane refuses by name.

## Wire an agent

```bash
claude plugin marketplace add omnislash157/graphyos
claude plugin install graphy@graphyos
```

Or point anything that speaks MCP at it after eat:

```json
{
  "mcpServers": {
    "graphy": {
      "command": "graphy",
      "args": ["mcp", "--repo", "."]
    }
  }
}
```

`graphy mcp --repo <dir>` walks up to the nearest eaten ancestor the way git finds `.git`.

## A few more doors

```bash
# does A reach B, across packages
graphy walk --tenant .graphy/tenant.json --tenant-id httpx \
    --seed httpx://module/httpx --target certifi://module/certifi

# the ring as SQL
graphy estate --tenant .graphy/tenant.json --tenant-id httpx \
    --sql "SELECT a.corpus, n.corpus, count(*) FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus GROUP BY 1, 2"

# still true?
graphy check --tenant .graphy/tenant.json --tenant-id httpx

# clone, eat, walk, print the done token
bash quickstart.sh https://github.com/encode/httpx.git
```

| want | door |
|---|---|
| mint one package anywhere | `graphy smash` |
| upstream moved, current store untouched | `graphy refresh` |
| two tenants, a declared join, hops tagged by side | `graphy bridge` |
| cut the repo into named pillars | `graphy pillars` / `graphy fanout` |
| arm files vs the store | `graphy arms --verify` |
| GRAPH.md + drawings + first walk | `graphy harness --repo .` |
| remint history only, do not `eat` a house tenant | `graphy history --remint` |

Not built yet, by name: the shard index. That lives on the Issues board.

Worked tenants: [`engine/tenants/fastapi/FASTAPI.md`](engine/tenants/fastapi/FASTAPI.md), [`engine/tenants/hono/HONO.md`](engine/tenants/hono/HONO.md), [`engine/tenants/sqlalchemy/SQLALCHEMY.md`](engine/tenants/sqlalchemy/SQLALCHEMY.md). Memory lane in full: [`engine/graphy/shell/README.md`](engine/graphy/shell/README.md).

## This checkout

```text
engine/               the product. pip install this. it is graphy.
CLAUDE.md             router for an agent working in this repo
RECON.md              every number in this README, with the command that re-derives it
standalone_check.sh   fresh venv, engine/ alone → GRAPHY_STANDALONE_OK
quickstart.sh         clone + eat + walk → GRAPHY_QUICKSTART_OK
CHANGELOG.md          the issues, in order
```

`engine/` is the only place engine work lands.

<!-- mcp-name: io.github.omnislash157/graphyos -->
