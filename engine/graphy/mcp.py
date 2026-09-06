"""The MCP server: the doors over one tenant's compiled store, on stdio, for any client that
speaks the Model Context Protocol (Claude Code, Cursor, Claude Desktop, …).

    graphy mcp --tenant <descriptor> --tenant-id <name>

Six tools — hunt · descend · blast · walk · draw · explain — each the same walk the CLI verb runs,
returning the same text. The store is opened once at startup and its generation is pinned for
the session; every answer carries it. Zero dependencies: the protocol is newline-delimited
JSON-RPC 2.0 over stdin/stdout, and this module speaks the three methods a tool server needs
(initialize · tools/list · tools/call) plus ping. Nothing here writes; a walk lands its rows in
the traversal store exactly as `graphy walk` does.
"""
from __future__ import annotations

import io
import json
import sys
from typing import Any, Callable

from graphy import doors, traversal
from graphy import federated_store as fstore

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "graphy", "version": "0.1.0"}

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
]


class ToolError(RuntimeError):
    pass


class Doors:
    """The six tools over one opened store."""

    def __init__(self, store, tenant, tenant_id: str):
        self.store, self.tenant, self.tenant_id = store, tenant, tenant_id
        self.generation = store.generation()

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
        if which == "descend":
            out = doors.render_descend(doors.descend(c, seed, depth), limit)
        elif which == "blast":
            out = doors.render_blast(doors.blast(c, seed, depth), limit)
        else:
            out = doors.render_explain(doors.explain(c, seed, depth, tenant=self.tenant), limit)
        return f"{out}\nDOOR: {which} reads={c.reads} generation={self.generation}"

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
                                              "'what does this reach', walk for 'does A reach B', explain for 'what is this'.")})
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


def open_tools(tenant, tenant_id: str, roster: list[str], on_stale: str = "refuse") -> Doors:
    store = fstore.open_for(roster, tenant=tenant, tenant_id=tenant_id, on_stale=on_stale)
    return Doors(store, tenant, tenant_id)
