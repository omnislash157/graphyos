"""The MCP server: the doors over one tenant's compiled store, on stdio, for any client that
speaks the Model Context Protocol (Claude Code, Cursor, Claude Desktop, …).

    graphy mcp --tenant <descriptor> --tenant-id <name>

Seven tools — hunt · descend · blast · walk · draw · explain · history — each the same walk the CLI
verb runs, returning the same text. The store is opened at startup and every answer carries the generation it
was read from; before every tool call the server asks whether a fresh `graphy <verb> --tenant` would
still open that store (a stat of every input, the store file and the descriptor) and, when not, opens
what the CLI would open now — refusing STALE in the CLI's words when the CLI would (graphyos #97).
Zero dependencies: the protocol is newline-delimited
JSON-RPC 2.0 over stdin/stdout, and this module speaks the three methods a tool server needs
(initialize · tools/list · tools/call) plus ping. Nothing here writes; a walk lands its rows in
the traversal store exactly as `graphy walk` does.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any, Callable

from graphy import __version__, doors, traversal
from graphy import federated_store as fstore
from graphy.tenant import TenantError

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "graphy", "version": __version__}      # the package's own, never a second copy (graphyos #43)

_SYMBOL = {"type": "string", "description": "an exact node id (fastapi://func/fastapi.routing.get_request_handler) or its dotted tail (get_request_handler, routing.get_request_handler)"}
_DEPTH = lambda d: {"type": "integer", "default": d, "minimum": 1, "maximum": 12, "description": f"hops to walk (default {d})"}  # noqa: E731
_LIMIT = {"type": "integer", "default": 12, "minimum": 1, "description": "rows per section (default 12)"}

TOOLS = [
    {"name": "hunt",
     "description": "Find the nodes a symbol names in the compiled store: exact id, dotted tail, or a substring of the id. Returns id · owner · file:line. Use it first when a name is bare or ambiguous — every other tool needs one node.",
     "inputSchema": {"type": "object", "properties": {"symbol": _SYMBOL, "limit": {"type": "integer", "default": 25}},
                     "required": ["symbol"], "additionalProperties": False}},
    {"name": "descend",
     "description": "What a symbol calls, transitively, down through the import ring to the primitives — and every package crossing with the chain that made it. The answer to 'what does this reach across packages'.",
     "inputSchema": {"type": "object", "properties": {"symbol": _SYMBOL, "depth": _DEPTH(4), "limit": _LIMIT},
                     "required": ["symbol"], "additionalProperties": False}},
    {"name": "blast",
     "description": "The blast radius: everything that depends on a symbol, transitively, against the calls/inherits/imports/decorates edges — split into the symbol's own package and the rest of the ring. The answer to 'if this changes, what breaks'.",
     "inputSchema": {"type": "object", "properties": {"symbol": _SYMBOL, "depth": _DEPTH(4), "limit": _LIMIT},
                     "required": ["symbol"], "additionalProperties": False}},
    {"name": "walk",
     "description": "Does A reach B: a bounded breadth-first path from one node id to another through the store, across packages. Both ends must be exact node ids (hunt gives them). The walk is kept, so asking again is free.",
     "inputSchema": {"type": "object", "properties": {"seed": {"type": "string", "description": "the exact node id to walk FROM"},
                                                      "target": {"type": "string", "description": "the exact node id to walk TO"},
                                                      "max_depth": _DEPTH(6)},
                     "required": ["seed", "target"], "additionalProperties": False}},
    {"name": "draw",
     "description": "Draw it for the human: a symbol's neighbourhood (radius hops either way) or, with no symbol, the corpus's unit map — a computed layered layout as ASCII, ready to paste. Structure from the store, no drawing by hand.",
     "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "an exact node id or its dotted tail; omit for the unit map"},
                                                      "radius": _DEPTH(2), "corpus": {"type": "string", "description": "the corpus for the unit map (required when the tenant holds several)"},
                                                      "lr": {"type": "boolean", "default": True}},
                     "additionalProperties": False}},
    {"name": "explain",
     "description": "What explains a symbol: where it lives and its docstring, the docs bound to it, the test modules that reach it, and the journal page that birthed its shard. Each absence is named with its cause.",
     "inputSchema": {"type": "object", "properties": {"symbol": _SYMBOL, "depth": _DEPTH(3), "limit": _LIMIT},
                     "required": ["symbol"], "additionalProperties": False}},
    {"name": "history",
     "description": "How the product changed over time, from the record: the sessions where a term (and a second, within a window) was said — or, with symbol instead of term, the sessions whose exchanges mention a code node — oldest first with timestamps, the symbols each session discussed, the commits it made, the RECON sections and issues they name, the receipt numbers that moved. Every line is a node of the history shard; no model wrote it.",
     "inputSchema": {"type": "object", "properties": {"term": {"type": "string", "description": "the first word or phrase (hunts the archive)"},
                                                      "partner": {"type": "string", "description": "the second, co-occurring within the window"},
                                                      "window": {"type": "integer", "default": 10},
                                                      "sessions": {"type": "string", "description": "the sessions archive; default the project's .claude/recovery/sessions"},
                                                      "symbol": {"type": "string", "description": "instead of term: an exact node id or its dotted tail — the exchanges that mention it, from the store"}},
                     "additionalProperties": False}},
]


class ToolError(RuntimeError):
    pass


class Doors:
    """The seven tools over one opened store."""

    def __init__(self, store, tenant, tenant_id: str, roster: list[str], on_stale: str = "refuse",
                 descriptor: str | Path | None = None):
        self.store, self.tenant, self.tenant_id = store, tenant, tenant_id
        self.roster, self.on_stale = list(roster), on_stale
        self.descriptor = Path(descriptor) if descriptor is not None else None
        self.generation = store.generation()
        self._fresh_at: tuple | None = None        # the input signature the served store was opened under

    def _assert_fresh(self, which: str) -> None:
        """One contract, two faces (graphyos #97): what a fresh CLI invocation would open now, this call
        answers from. While every input's stat — the shards, the index, the registry, the store file, the
        descriptor — is what it was when the served store was opened, the call is served as is. When any
        moved, the server does exactly what `graphy <verb> --tenant` does and nothing less: the descriptor
        re-read, the roster derived, `open_for` on a fresh connection (which refuses STALE in the CLI's
        words, or warns), the old store closed once the new one is open. Never a check on a held store —
        round 1 found `graphy build` at the store's own path (the refusal's own advice, and `shell
        install`'s re-mint) leaving a held handle on the unlinked file, refusing forever; and a roster
        narrowed in the descriptor in place never followed. A refusal leaves the server as it was and the
        next call tries again (the signature is recorded only on a successful open). A read, never a write."""
        from graphy.cli import _load_tenant, _roster
        if self._fresh_at is not None and self._signature(self.store.path, self.roster, self.tenant) == self._fresh_at:
            return
        try:
            tenant = _load_tenant(str(self.descriptor)) if self.descriptor is not None else self.tenant
            roster = _roster(tenant) if self.descriptor is not None else self.roster
            path = fstore.store_path_for(roster, tenant=tenant)
            sig = self._signature(path, roster, tenant)           # before the open: a write after it moves the next call
            store = fstore.open_for(roster, tenant=tenant, tenant_id=self.tenant_id, on_stale=self.on_stale)
        except (fstore.StoreError, TenantError, AttributeError, TypeError, KeyError, OSError) as exc:
            raise ToolError(fstore.refused(which.upper(), exc)) from exc   # the CLI's catch set, its line
        was = self.generation
        self.store.close()
        self.store, self.tenant, self.roster, self.generation = store, tenant, roster, store.generation()
        self._fresh_at = sig
        if self.generation != was:
            print(f"graphy mcp: {self.descriptor or 'the tenant'} now serves {tenant.data_home} — reopened on "
                  f"generation {self.generation} (was {was})", file=sys.stderr)

    def _signature(self, store_path, roster: list[str], tenant) -> tuple:
        return fstore.input_signature(store_path, roster, tenant=tenant, descriptor=self.descriptor)

    def close(self) -> None:
        """The server's one store, released when the server stops: a long-lived process that kept
        it would refuse every rebuild's rename on Windows (graphyos #124)."""
        self.store.close()

    def __enter__(self) -> "Doors":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _counted(self):
        c = traversal.Counting(self.store)
        c.find = self.store.find
        return c

    def hunt(self, symbol: str, limit: int = 25) -> str:
        ids = sorted(self.store.find(symbol))
        how = "tail"
        if not ids:
            ids = sorted(self.store.grep(symbol))
            how = "substring"
        if not ids:
            return f"HUNT: {symbol!r} names no node in this store (tail and substring both empty)"
        lines = [f"HUNT: {symbol!r} → {len(ids)} node(s) by {how}"]
        for nid in ids[:limit]:
            rec = self.store.record(nid) or {}
            where = f"{rec.get('file')}:{rec.get('line')}" if rec.get("file") else ""
            lines.append(f"  {nid}  [{self.store.membership(nid)}]  {where}".rstrip())
        if len(ids) > limit:
            lines.append(f"  … {len(ids) - limit} more (limit)")
        return "\n".join(lines)

    def _door(self, which: str, symbol: str, depth: int, limit: int) -> str:
        c = self._counted()
        try:
            seed = doors.resolve(c, symbol)
        except doors.DoorError as exc:
            raise ToolError(f"{which.upper()} UNANSWERABLE: {exc}") from exc
        if which == "explain":
            out = doors.render_explain(doors.explain(c, seed, depth, tenant=self.tenant), limit)
            return f"{out}\nDOOR: {which} reads={c.reads} generation={self.generation}"
        try:                               # the same rows the CLI lands and recalls (graphyos #111)
            o = traversal.door(self.store, traversal.home_for(self.tenant), which, seed, depth)
        except (traversal.TraversalError, OSError) as exc:
            raise ToolError(f"{which.upper()} REFUSED: {exc}") from exc
        render = doors.render_descend if which == "descend" else doors.render_blast
        trav = (f"TRAVERSAL SKIPPED: {o.note}" if o.note
                else f"TRAVERSAL: source={o.source} reads={o.reads}" + (" stored" if o.stored else ""))
        return f"{render(o.result, limit)}\nDOOR: {which} reads={o.reads} generation={self.generation}\n{trav}"

    def history(self, term: str | None = None, partner: str | None = None, window: int = 10, sessions: str | None = None,
                symbol: str | None = None) -> str:
        from graphy import timeline as timeline_lane
        from graphy.lightning.archive import sessions_dir
        from pathlib import Path
        if bool(term) == bool(symbol) or (symbol and (partner or window != 10)):
            raise ToolError("HISTORY REFUSED: one ask per call — term (with partner, window) hunts the archive, symbol "
                            "reads the store's mentions and no window; give exactly one")
        try:
            if symbol:                                         # sessions names the archive's captures the shard lacks
                t = timeline_lane.timeline_symbol(self.store, symbol, Path(sessions).expanduser() if sessions else None)
            else:
                corpus = Path(sessions).expanduser() if sessions else sessions_dir()
                t = timeline_lane.timeline(self.store, term, partner, corpus, window=window)
        except timeline_lane.TimelineError as exc:
            raise ToolError(f"HISTORY REFUSED: {exc}") from exc
        return f"{timeline_lane.render(t)}\nDOOR: history generation={self.generation}"

    def descend(self, symbol: str, depth: int = 4, limit: int = 12) -> str:
        return self._door("descend", symbol, depth, limit)

    def blast(self, symbol: str, depth: int = 4, limit: int = 12) -> str:
        return self._door("blast", symbol, depth, limit)

    def explain(self, symbol: str, depth: int = 3, limit: int = 12) -> str:
        return self._door("explain", symbol, depth, limit)

    def walk(self, seed: str, target: str, max_depth: int = 6) -> str:
        try:
            o = traversal.walk(self.store, traversal.home_for(self.tenant), seed, target, max_depth=max_depth)
        except traversal.TraversalError as exc:
            raise ToolError(f"WALK REFUSED: {exc}") from exc
        r = o.result
        if r.found:
            nodes = [r.seed] + [s.dst for s in r.steps]
            head = f"WALK PATH: hops={len(r.steps)} visited={r.visited} steps={' -> '.join(nodes)}"
        elif r.stopped_by is None:
            head = f"WALK NO-PATH: search exhausted (visited={r.visited}) — the snapshot genuinely does not connect them"
        elif r.stopped_by in ("seed-absent", "target-absent"):
            head = f"WALK UNANSWERABLE: {r.stopped_by.replace('-', ' ')} from this snapshot — hunt for the exact id"
        else:
            head = f"WALK BUDGET-EXHAUSTED: {r.stopped_by} (visited={r.visited}) — a path may still exist; raise max_depth"
        tail = (f"TRAVERSAL SKIPPED: {o.note}" if o.note
                else f"TRAVERSAL: source={o.source} reads={o.reads}" + (" stored" if o.stored else ""))
        return f"{head}\n{tail}\ngeneration={self.generation}"

    def draw(self, symbol: str | None = None, radius: int = 2, corpus: str | None = None, lr: bool = True) -> str:
        from graphy import draw as draw_lane
        c = self._counted()
        c.owned, c.edges = self.store.owned, self.store.edges
        try:
            if symbol:
                pic = draw_lane.neighbourhood(c, doors.resolve(c, symbol), radius=radius)
            else:
                owners = sorted({o for o in (self.store.membership(n) for n, _ in self.store.edges()) if o} - {"wire"}) if not corpus else [corpus]
                if len(owners) != 1:
                    raise ToolError(f"DRAW UNANSWERABLE: the tenant holds {len(owners)} corpora ({', '.join(owners)}) — name one with corpus")
                pic = draw_lane.units(c, owners[0])
            text = draw_lane.render(pic, emit="ascii", lr=lr)
        except (draw_lane.DrawError, doors.DoorError) as exc:
            raise ToolError(f"DRAW UNANSWERABLE: {exc}") from exc
        return f"{text}\nDRAW: {pic.summary()} reads={c.reads} generation={self.generation}"

    def call(self, name: str, arguments: dict) -> str:
        fn: Callable[..., str] | None = {t["name"]: getattr(self, t["name"]) for t in TOOLS}.get(name)
        if fn is None:
            raise ToolError(f"unknown tool {name!r}; the tools are {', '.join(t['name'] for t in TOOLS)}")
        self._assert_fresh(name)
        try:
            return fn(**(arguments or {}))
        except TypeError as exc:
            raise ToolError(f"{name}: bad arguments ({exc})") from exc


# ── the JSON-RPC loop ───────────────────────────────────────────────────────────────────────

def _result(rid, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(msg: dict, tools: Doors) -> dict | None:
    """One request → one response; a notification → None."""
    rid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method is None:
        return None
    if rid is None:                       # a notification; the only ones we get are lifecycle
        return None
    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return _result(rid, {"protocolVersion": version, "capabilities": {"tools": {}},
                             "serverInfo": SERVER_INFO,
                             "instructions": (f"graphy over tenant {tools.tenant_id!r}, store generation {tools.generation}. "
                                              "Every answer is a walk over the code's structure; no model decided an edge. "
                                              "Start with hunt when a name is bare; blast for 'what breaks', descend for "
                                              "'what does this reach', walk for 'does A reach B', explain for 'what is this', "
                                              "history for 'how did this change over time' (two words, or a symbol: the sessions and commits).")})
    if method == "ping":
        return _result(rid, {})
    if method == "tools/list":
        return _result(rid, {"tools": TOOLS})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            text = tools.call(name, args)
            return _result(rid, {"content": [{"type": "text", "text": text}], "isError": False})
        except ToolError as exc:
            return _result(rid, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        except Exception as exc:  # noqa: BLE001 — a tool fault is a tool result, never a dead server
            return _result(rid, {"content": [{"type": "text", "text": f"{name}: {type(exc).__name__}: {exc}"}], "isError": True})
    return _error(rid, -32601, f"method not found: {method}")


def serve(tools: Doors, inp: io.TextIOBase | None = None, out: io.TextIOBase | None = None) -> int:
    inp = inp or sys.stdin
    out = out or sys.stdout
    try:
        for line in inp:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                out.write(json.dumps(_error(None, -32700, "parse error")) + "\n"); out.flush()
                continue
            if not isinstance(msg, dict):
                out.write(json.dumps(_error(None, -32600, "invalid request")) + "\n"); out.flush()
                continue
            reply = handle(msg, tools)
            if reply is not None:
                out.write(json.dumps(reply, ensure_ascii=False) + "\n")
                out.flush()
        return 0
    finally:
        tools.close()                      # the server's store lives exactly as long as its input (graphyos #124)


def open_tools(tenant, tenant_id: str, roster: list[str], on_stale: str = "refuse",
               descriptor: str | Path | None = None) -> Doors:
    """The server's doors over the store `open_for` accepts now. `descriptor` is the file the tenant was
    loaded from; given, every tool call follows it (a landing renames it onto a new generation)."""
    store = fstore.open_for(roster, tenant=tenant, tenant_id=tenant_id, on_stale=on_stale)
    return Doors(store, tenant, tenant_id, roster, on_stale=on_stale, descriptor=descriptor)
