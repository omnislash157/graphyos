"""The MCP server: the protocol over a pipe, the six tools over the fixture store. A floor —
the proof is the demo and the Claude Code client run in RECON."""
from __future__ import annotations

import io
import json

import graphy.mcp as mcp
from graphy.cli import _roster
from test_doors import SEED, _fixture


def _tools(tmp_path):
    tenant, _desc, roster = _fixture(tmp_path)
    return mcp.open_tools(tenant, "doors", roster)


def _rpc(tools, *msgs) -> list[dict]:
    inp = io.StringIO("".join(json.dumps(m) + "\n" for m in msgs) + "\n{not json}\n")
    out = io.StringIO()
    assert mcp.serve(tools, inp, out) == 0
    return [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]


def test_handshake_list_call_and_errors(tmp_path):
    tools = _tools(tmp_path)
    replies = _rpc(tools,
                   {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                   {"jsonrpc": "2.0", "method": "notifications/initialized"},
                   {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                   {"jsonrpc": "2.0", "id": 3, "method": "ping"},
                   {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "blast", "arguments": {"symbol": "get_request_handler"}}},
                   {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "descend", "arguments": {"symbol": "__init__"}}},
                   {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
                   {"jsonrpc": "2.0", "id": 7, "method": "resources/list"})
    by_id = {r.get("id"): r for r in replies}
    init = by_id[1]["result"]
    assert init["protocolVersion"] == "2025-03-26" and init["capabilities"] == {"tools": {}}
    assert tools.generation in init["instructions"]
    assert [t["name"] for t in by_id[2]["result"]["tools"]] == ["hunt", "descend", "blast", "walk", "draw", "explain"]
    assert by_id[3]["result"] == {}
    blast = by_id[4]["result"]
    assert blast["isError"] is False and blast["content"][0]["text"].startswith("BLAST seed=" + SEED)
    assert "widgets://func/widgets.gadget" in blast["content"][0]["text"]
    assert by_id[5]["result"]["isError"] is True and "never guesses" in by_id[5]["result"]["content"][0]["text"]
    assert by_id[6]["result"]["isError"] is True and "unknown tool" in by_id[6]["result"]["content"][0]["text"]
    assert by_id[7]["error"]["code"] == -32601
    assert by_id[None]["error"]["code"] == -32700          # the unparsable line
    assert len(replies) == 8                               # the notification got no reply


def test_hunt_walk_explain(tmp_path):
    tools = _tools(tmp_path)
    hunt = tools.hunt("gadget")
    assert "widgets://func/widgets.gadget  [widgets]  widgets/gadget.py:1" in hunt and "by tail" in hunt
    assert "by substring" in tools.hunt("gadg")
    assert "names no node" in tools.hunt("zzz_nothing")
    walk = tools.walk("widgets://func/widgets.tests.test_gadget.test_it", SEED)
    assert walk.startswith("WALK PATH: hops=2") and "TRAVERSAL" in walk
    assert tools.walk("nope://x", SEED).startswith("WALK UNANSWERABLE: seed absent")
    exp = tools.explain("get_request_handler")
    assert "RECORD: func fastapi.routing.get_request_handler at fastapi/routing.py" in exp
    assert "widgets.tests.test_gadget.test_it" in exp
