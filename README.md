# graphy

Compile a repo into a graph your agent can query in milliseconds.
A 2D map and a 3D view come with it. Session history stays as text
you can grep.

[![ci](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml/badge.svg)](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/graphyos)](https://pypi.org/project/graphyos/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/graphyos/)
[![MCP registry](https://img.shields.io/badge/MCP-io.github.omnislash157%2Fgraphyos-black)](https://registry.modelcontextprotocol.io/v0/servers?search=graphyos)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

No embeddings. No summarizer. No model picks an edge.
If two things are connected, the code connected them.

Live maps of httpx, FastAPI, Hono, and seven others:
[graphy-os.com](https://graphy-os.com)

```text
What in FastAPI breaks if iterate_in_threadpool changes?

graphy, no model          0.00s    0 tokens     5/5 dependents
haiku + graphy MCP        14.8s    48k in        5/5
opus + 270 KB of source   26.5s    103k in       5/5
```

Same five functions. The store does it without a model in the loop.
The numbers are re-derived in `RECON.md`.

Matt Hartigan, 2026. Apache 2.0.

## Run it

Package is `graphyos`. Command is `graphy`. Python 3.10+.
Linux, macOS, Windows.

```bash
pip install 'graphyos[typescript]'
cd /path/to/your/repo
graphy eat . --no-provision
graphy showcase .
```

Open `.graphy/showcase/index.html`. That is the 2D map.
The 3D view is on the same page's explorer, and on the public gallery.

`--no-provision` means graphy will not run the repo's installer.
Use that on anyone else's tree. Drop the flag only on a repo you trust
when you actually want graphy to provision a build.

Hook the coding agent so the next session starts where this one ended:

```bash
graphy shell install --repo "$PWD"
```

Claude Code on Windows needs Git Bash for those hooks. Codex and Cursor
do not. After `pip install -U graphyos`, restart any live `graphy mcp`.
An old server will treat a new store as stale.

No venv:

```bash
uvx --from 'graphyos[typescript]' graphy showcase .
```

Several packages in one checkout:

```bash
graphy eat . --package app --site-packages . --no-provision
```

`showcase` does not take those flags yet. Eat first.

## What you get

A store under `<repo>/.graphy/` that answers reachability and blast-radius
questions without a model in the loop. The FastAPI numbers above are the
same five dependents, from structure.

The verbs are the same on the terminal and over MCP:

`hunt` · `descend` · `blast` · `walk` · `draw` · `explain` · `history`

`blast` is blast radius. `walk` is does A reach B. `draw` is the neighborhood. `history` is every session that named the symbol, oldest first, with the commits.

Session tails land in `.claude/recovery/` as markdown. Not a summary. The actual back and forth, tool noise stripped, a sha on every tail. Two words through lightning/bloodhound and you get every place they co-occurred.

Rebuild is not a wipe. SessionStart and an hourly cron can remint a stale shard and leave the last good store up while the next one lands. That is the point if models are still writing the repo while you sleep.

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

## More commands

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

| want | command |
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
