"""The MCP server: the protocol over a pipe, the seven tools over the fixture store. A floor —
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
    assert [t["name"] for t in by_id[2]["result"]["tools"]] == ["hunt", "descend", "blast", "walk", "draw", "explain", "history"]
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


def _move_a_shard(tenant) -> None:
    """One more node in the widgets shard: the digest no longer matches the store's row."""
    from pathlib import Path
    nodes_path = Path(tenant.data_home) / "widgets_graph" / "nodes.json"
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    nodes["widgets://func/widgets.later"] = {"kind": "node", "node_type": "func", "id": "widgets://func/widgets.later",
                                             "name": "later", "dotted": "widgets.later", "file": "widgets/later.py", "line": 1}
    nodes_path.write_text(json.dumps(nodes), encoding="utf-8")


def test_mcp_refuses_a_store_that_went_stale_after_boot(tmp_path, capsys):
    """graphyos #97: the CLI ran `open_for`'s freshness comparison per invocation and the server ran it
    once at boot, so a store the CLI refused as STALE answered confidently on the MCP face — the
    specimen was a hunt returning 40 nodes, many of them paths deleted months earlier. Boot on a fresh
    store, move a shard, and the next tool call refuses with the CLI's STALE text, verbatim."""
    import pytest
    from graphy import federated_store as fs
    tenant, _desc, roster = _fixture(tmp_path)
    tools = mcp.open_tools(tenant, "doors", roster)
    assert "by tail" in tools.hunt("gadget")              # the store is fresh at boot and answers
    _move_a_shard(tenant)
    with pytest.raises(fs.StoreError) as refused:          # the CLI's words, from the CLI's own door
        fs.open_for(roster, tenant=tenant, tenant_id="doors", on_stale="refuse")
    cli_words = str(refused.value)
    assert "is STALE" in cli_words and tools.generation in cli_words
    from graphy import cli
    assert cli.main(["explain", "get_request_handler", "--tenant", str(_desc), "--tenant-id", "doors"]) == 2
    cli_line = capsys.readouterr().err.strip().splitlines()[-1]   # what the CLI face printed, the same minute
    replies = _rpc(tools,
                   {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "hunt", "arguments": {"symbol": "gadget"}}},
                   {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "blast", "arguments": {"symbol": "get_request_handler"}}},
                   {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "explain", "arguments": {"symbol": "get_request_handler"}}})
    by_id = {r.get("id"): r for r in replies}
    for rid, verb in ((1, "HUNT"), (2, "BLAST"), (3, "EXPLAIN")):
        r = by_id[rid]["result"]
        assert r["isError"] is True, r
        assert r["content"][0]["text"] == fs.refused(verb, refused.value), r
    assert by_id[3]["result"]["content"][0]["text"] == cli_line     # verbatim: the two faces print one line


def test_mcp_opens_what_the_cli_opens_on_every_call(tmp_path, monkeypatch, capsys):
    """graphyos #134: the held design hashed the inputs once and kept the store open between calls, so on Windows a
    `graphy build` under a live server could not replace it. Every call now opens the store the way `graphy <verb>`
    does — the inputs digested — and closes it; under `warn` a stale store answers every call, as the CLI does."""
    from graphy import federated_store as fs
    tenant, _desc, roster = _fixture(tmp_path)
    tools = mcp.open_tools(tenant, "doors", roster, on_stale="warn")
    real, digests = fs._compute_input_digest, []
    monkeypatch.setattr(fs, "_compute_input_digest", lambda *a, **k: (digests.append(1), real(*a, **k))[1])
    for _ in range(3):
        assert "by tail" in tools.call("hunt", {"symbol": "gadget"})
    assert len(digests) == 3, "a call answered from a store it did not open"
    _move_a_shard(tenant)
    assert "by tail" in tools.call("hunt", {"symbol": "gadget"})
    assert "by tail" in tools.call("hunt", {"symbol": "gadget"})
    assert capsys.readouterr().err.count("is STALE") == 2
    tools.close()


def test_mcp_follows_the_descriptor_a_landing_renamed_onto_a_new_generation(tmp_path, capsys):
    """The production shape (`graphy mcp --repo`, the plugin): a re-eat lands a new generation beside the
    served one and renames the descriptor onto it, so the old shards never move and the digest still
    matches — the first cut of #97 kept answering from the generation the descriptor no longer named
    while the CLI served the new one. The server follows the descriptor: the next call answers from the
    new generation, names the symbol the re-eat minted, and says on stderr that it reopened."""
    import subprocess
    from pathlib import Path
    from graphy import cli
    repo = tmp_path / "repo"
    (repo / "core").mkdir(parents=True)
    (repo / "core" / "__init__.py").write_text("from core.mod import run\n", encoding="utf-8")
    (repo / "core" / "mod.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "one"], cwd=repo, check=True)
    eat = ["eat", str(repo), "--package", "core", "--site-packages", str(repo)]
    assert cli.main(eat) == 0
    desc = repo / ".graphy" / "tenant.json"
    tenant = cli._load_tenant(str(desc))
    tools = mcp.open_tools(tenant, "core", cli._roster(tenant), descriptor=desc)
    boot, home = tools.generation, Path(tenant.data_home)
    assert "names no node" in tools.call("hunt", {"symbol": "later"})
    (repo / "core" / "later.py").write_text("def later():\n    return 2\n", encoding="utf-8")
    assert cli.main(eat) == 0                                 # a new generation, landed by the descriptor rename
    landed = cli.served_data_home(desc)
    assert landed != home and home.is_dir(), "the old generation is kept for a reader that began on it"
    capsys.readouterr()
    answer = tools.call("hunt", {"symbol": "later"})
    assert "core://func/core.later.later" in answer, answer
    assert tools.generation != boot and Path(tools.tenant.data_home) == landed
    err = capsys.readouterr().err
    assert f"reopened on generation {tools.generation} (was {boot})" in err, err
    assert "later" in tools.call("hunt", {"symbol": "later"}) and capsys.readouterr().err == ""   # once
    tools.close()


def test_mcp_answers_again_after_the_build_its_own_refusal_prescribes(tmp_path, capsys):
    """Review round 1 of #97: the refusal says `rebuild the store with graphy build`, which lands at the
    store's own path by `os.replace`; the first cut kept the held handle on the unlinked file and compared
    live shards against its row forever — refusing every call until restart while the CLI answered.
    `shell install`'s re-mint into the served generation is the same shape. The server opens what the
    CLI opens now, so the call after the build answers."""
    import pytest
    from graphy import cli
    tenant, desc, roster = _fixture(tmp_path)
    tools = mcp.open_tools(tenant, "doors", roster, descriptor=desc)
    assert "by tail" in tools.call("hunt", {"symbol": "gadget"})
    _move_a_shard(tenant)
    with pytest.raises(mcp.ToolError, match="is STALE"):
        tools.call("hunt", {"symbol": "gadget"})
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "doors"]) == 0
    assert cli.main(["explain", "get_request_handler", "--tenant", str(desc), "--tenant-id", "doors"]) == 0
    capsys.readouterr()
    out = tools.call("hunt", {"symbol": "gadget"})
    assert "by tail" in out and "widgets://func/widgets.later" in tools.call("hunt", {"symbol": "later"})
    assert "reopened on generation" in capsys.readouterr().err
    tools.close()


def test_mcp_follows_a_roster_narrowed_in_the_descriptor_in_place(tmp_path, capsys):
    """Round 1's sibling: the same data home, the descriptor rewritten with one lane fewer and the store
    rebuilt — the CLI opens the narrowed roster's store (`store_path_for` is keyed by the roster); the
    first cut's server kept its boot roster and store. The server's roster is the descriptor's."""
    from graphy import cli
    tenant, desc, roster = _fixture(tmp_path)
    tools = mcp.open_tools(tenant, "doors", roster, descriptor=desc)
    assert "by tail" in tools.call("hunt", {"symbol": "gadget"})
    raw = json.loads(desc.read_text(encoding="utf-8"))
    lanes = {k: v for k, v in raw["build_lanes"].items() if not k.startswith("widgets")}
    assert len(lanes) == len(raw["build_lanes"]) - 1
    raw["build_lanes"] = lanes
    desc.write_text(json.dumps(raw), encoding="utf-8")
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "doors"]) == 0
    assert cli.main(["explain", "gadget", "--tenant", str(desc), "--tenant-id", "doors"]) != 0   # the CLI: no such node now
    capsys.readouterr()
    assert "names no node" in tools.call("hunt", {"symbol": "gadget"})
    assert tools.roster == cli._roster(cli._load_tenant(str(desc))) and "widgets" not in tools.roster
    tools.close()


def test_RED_the_server_reports_the_packages_version(tmp_path):
    """serverInfo.version is graphy.__version__, read from the package — the server said 0.1.0
    against a 0.2.0 package once (graphyos #43)."""
    import graphy
    tools = _tools(tmp_path)
    init = _rpc(tools, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26"}})[0]["result"]
    assert init["serverInfo"] == {"name": "graphy", "version": graphy.__version__}
    assert init["serverInfo"]["version"] != "0.1.0"
