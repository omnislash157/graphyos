"""graphyos #124: a verb closes every store it opens.

On Windows a file a process still holds cannot be renamed or replaced, so every sqlite connection a
verb leaves open is a sharing violation for the next step — `eat` then a rename of `.graphy`, a
recompile onto a store a reader still holds, a rebuild landing a generation a door still reads. The
platform is not needed to prove the class: every connection `sqlite3.connect` hands out during a verb
is tracked, and after the verb returns each one must be closed. A leak here is a `WinError 5` there.
"""
from __future__ import annotations

import io
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from graphy import cli
from graphy import federated_store as fs


@pytest.fixture
def tracked(monkeypatch):
    """Every connection sqlite3.connect hands out while the fixture is live, in order."""
    opened: list[sqlite3.Connection] = []
    real = sqlite3.connect

    def connect(*a, **k):
        con = real(*a, **k)
        opened.append(con)
        return con

    monkeypatch.setattr(sqlite3, "connect", connect)
    return opened


def _closed(con: sqlite3.Connection) -> bool:
    try:
        con.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


def _assert_all_closed(opened: list, what: str) -> None:
    assert opened, f"{what}: no store was opened — the probe measured nothing"
    held = [c for c in opened if not _closed(c)]
    assert not held, f"{what}: {len(held)} of {len(opened)} sqlite connection(s) still open after the verb returned"


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "core").mkdir(parents=True)
    (repo / "core" / "__init__.py").write_text("from core.mod import run\n", encoding="utf-8")
    (repo / "core" / "mod.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "one"],
                   cwd=repo, check=True)
    return repo


@pytest.fixture(scope="module")
def eaten(tmp_path_factory):
    repo = _git_repo(tmp_path_factory.mktemp("lifecycle"))
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    # a curated partition, so `arms` has a cut to render and `harness` a hub to compile
    (repo / ".graphy" / "partition.json").write_text(
        json.dumps({"groups": {"CORE": ["core"]}, "rest": "EDGE"}), encoding="utf-8")
    return repo


def _tenant_argv(repo: Path) -> list[str]:
    return ["--tenant", str(repo / ".graphy" / "tenant.json"), "--tenant-id", "core"]


VERBS = {
    "walk": lambda r: ["walk", *_tenant_argv(r), "--seed", "core://module/core", "--target", "core://func/core.mod.run", "--no-store"],
    "descend": lambda r: ["descend", "core.mod.run", *_tenant_argv(r), "--no-store"],
    "blast": lambda r: ["blast", "core.mod.run", *_tenant_argv(r), "--no-store"],
    "explain": lambda r: ["explain", "core.mod.run", *_tenant_argv(r)],
    "pillars": lambda r: ["pillars", *_tenant_argv(r), "--corpus", "core"],
    "draw": lambda r: ["draw", *_tenant_argv(r), "--corpus", "core"],
    "recon": lambda r: ["recon", *_tenant_argv(r)],
    "history": lambda r: ["history", "--symbol", "core.mod.run", *_tenant_argv(r)],
    "traversals": lambda r: ["traversals", *_tenant_argv(r)],
    "check": lambda r: ["check", *_tenant_argv(r)],
    "harness": lambda r: ["harness", "--repo", str(r), "--corpus", "core"],
    "arms": lambda r: ["arms", *_tenant_argv(r), "--corpus", "core",
                       "--partition", str(r / ".graphy" / "partition.json"), "--dir", str(r / ".graphy" / "arms"), "--verify"],
}


@pytest.mark.parametrize("verb", sorted(VERBS))
def test_a_verb_leaves_no_store_open(verb, eaten, tracked, capsys):
    from graphy import traversal
    if verb == "traversals" and not traversal.have_duckdb():
        pytest.skip("duckdb is not installed — `traversals` refuses before it opens a store, so there is nothing to track")
    rc = cli.main(VERBS[verb](eaten))
    out = capsys.readouterr()
    assert rc in (0, 1, 2), (rc, out.err)
    _assert_all_closed(tracked, f"graphy {verb} (rc {rc}: {out.err.strip()[:200]})")


def test_a_verb_leaves_no_store_open_after_eat_and_the_home_renames(tmp_path, tracked):
    """The issue's first specimen: `eat` runs the harness over the store it just built, and the
    rename of `.graphy` that follows must not meet a handle the verb left behind."""
    repo = _git_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    _assert_all_closed(tracked, "graphy eat")
    (repo / ".graphy").rename(repo / ".was")
    assert not (repo / ".graphy").exists()


def test_a_verb_leaves_no_store_open_when_the_library_doors_return(eaten, tracked):
    """The entry points that are not CLI verbs: the MCP server over one store, the pre-edit gate,
    the harness lane — each closes what it opened when it returns."""
    from graphy import mcp
    desc = eaten / ".graphy" / "tenant.json"
    tenant = cli._load_tenant(str(desc))
    tools = mcp.open_tools(tenant, "core", cli._roster(tenant))
    inp = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": "hunt", "arguments": {"symbol": "run"}}}) + "\n")
    assert mcp.serve(tools, inp=inp, out=io.StringIO()) == 0
    _assert_all_closed(tracked, "mcp.serve")


def test_the_mcp_server_closes_the_store_it_reopened_from(tmp_path, tracked):
    """graphyos #97: the server reopens on what the CLI would open when an input moved; the store it
    served before is closed the moment the new one is open — one handle at a time, and none after close."""
    from graphy import mcp
    repo = _git_repo(tmp_path)
    eat = ["eat", str(repo), "--package", "core", "--site-packages", str(repo)]
    assert cli.main(eat) == 0
    desc = repo / ".graphy" / "tenant.json"
    tenant = cli._load_tenant(str(desc))
    tools = mcp.open_tools(tenant, "core", cli._roster(tenant), descriptor=desc)
    old = tools.store
    (repo / "core" / "later.py").write_text("def later():\n    return 2\n", encoding="utf-8")
    assert cli.main(eat) == 0
    del tracked[:]
    assert "core.later" in tools.call("hunt", {"symbol": "later"})
    assert _closed(old._db), "the store a direct call opened is still open after a served call"
    _assert_all_closed(tracked, "mcp reopen: a served call holds nothing when it returns (graphyos #134)")
    tools.close()


def _stale(repo: Path) -> None:
    """Move the served shard past the store: one more node in nodes.json, the digest no longer matches."""
    nodes_path = cli.served_data_home(repo / ".graphy" / "tenant.json") / "core_graph" / "nodes.json"
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    nodes["core://func/core.mod.later"] = {"kind": "node", "node_type": "func", "id": "core://func/core.mod.later",
                                          "name": "later", "dotted": "core.mod.later", "file": "core/mod.py", "line": 9}
    nodes_path.write_text(json.dumps(nodes), encoding="utf-8")


def test_a_verb_leaves_no_store_open_when_open_for_refuses_stale(tmp_path, tracked):
    """`open_for` opened the store, then refused it as stale — and the refusal carried the open
    handle out in its traceback, so the recompile the refusal advertised could not replace the file."""
    repo = _git_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    tenant = cli._load_tenant(str(repo / ".graphy" / "tenant.json"))
    _stale(repo)
    del tracked[:]                                       # only the refusal's own connection is judged
    with pytest.raises(fs.StoreError):
        fs.open_for(cli._roster(tenant), tenant=tenant, tenant_id="core", on_stale="refuse")
    _assert_all_closed(tracked, "open_for on_stale=refuse")


def test_a_store_is_a_context_manager_and_close_is_idempotent(eaten, tracked):
    tenant = cli._load_tenant(str(eaten / ".graphy" / "tenant.json"))
    with fs.open_for(cli._roster(tenant), tenant=tenant, tenant_id="core") as store:
        assert store.membership("core://module/core") == "core"
    _assert_all_closed(tracked, "with open_for(...)")
    store.close()
    store.close()


def test_a_verb_leaves_no_store_open_when_open_for_refuses_before_the_stale_check(tmp_path, tracked):
    """Review round 1 of #124: the first fix closed the two stale refusals and left the two before them
    open — the digest raising on a shard file the store was compiled from that is gone, and the
    constructor's own refusals (no `input_digest` row: "recompile with `compile_store`", the exact
    replace a held handle refuses on Windows). Every refusal after the connect closes."""
    repo = _git_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    desc = repo / ".graphy" / "tenant.json"
    tenant = cli._load_tenant(str(desc))
    roster = cli._roster(tenant)
    nodes = cli.served_data_home(desc) / "core_graph" / "nodes.json"
    saved = nodes.read_bytes()
    nodes.unlink()                                       # the digest cannot be measured
    del tracked[:]
    with pytest.raises(fs.StoreError):
        fs.open_for(roster, tenant=tenant, tenant_id="core")
    _assert_all_closed(tracked, "open_for with a shard file gone")
    nodes.write_bytes(saved)
    db = sqlite3.connect(fs.store_path_for(roster, tenant=tenant))
    db.execute("DELETE FROM meta WHERE k='input_digest'")  # the constructor refuses: recompile
    db.commit()
    db.close()
    del tracked[:]
    with pytest.raises(fs.StoreError, match="recompile"):
        fs.open_for(roster, tenant=tenant, tenant_id="core")
    _assert_all_closed(tracked, "open_for on a store the constructor refuses")


def test_the_mcp_server_holds_no_store_between_calls(tmp_path, tracked, monkeypatch):
    """graphyos #134: between two tool calls a live server holds no connection, and during each call it holds
    exactly the one it opened — so `graphy build` replaces the store under a live server on Windows."""
    from graphy import mcp
    repo = _git_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    desc = repo / ".graphy" / "tenant.json"
    tenant = cli._load_tenant(str(desc))
    del tracked[:]
    tools = mcp.open_tools(tenant, "core", cli._roster(tenant), descriptor=desc)
    _assert_all_closed(tracked, "mcp boot")
    during: list[int] = []
    real_hunt = mcp.Doors.hunt
    monkeypatch.setattr(mcp.Doors, "hunt", lambda self, *a, **k: (during.append(sum(not _closed(c) for c in tracked)),
                                                                   real_hunt(self, *a, **k))[1])
    for _ in range(2):
        assert "core.mod.run" in tools.call("hunt", {"symbol": "run"})
        _assert_all_closed(tracked, "between two mcp calls")
    assert during == [1, 1], during
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "core"]) == 0
    assert "core.mod.run" in tools.call("hunt", {"symbol": "run"})
    _assert_all_closed(tracked, "after a build under the live server")
    tools.close()


def test_the_mcp_server_closes_its_store_on_a_failing_call(tmp_path, tracked, monkeypatch):
    """graphyos #134: a tool that raises mid-call — a fault, a bad argument, a refusal — still closes the store it opened."""
    from graphy import mcp
    repo = _git_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    tenant = cli._load_tenant(str(repo / ".graphy" / "tenant.json"))
    tools = mcp.open_tools(tenant, "core", cli._roster(tenant))
    del tracked[:]
    monkeypatch.setattr(mcp.Doors, "hunt", lambda self, *a, **k: (self.store.find("run"), (_ for _ in ()).throw(RuntimeError("fault")))[1])
    reply = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "hunt", "arguments": {"symbol": "run"}}}, tools)
    assert reply["result"]["isError"] is True and "fault" in reply["result"]["content"][0]["text"]
    assert tracked, "the failing call opened no store — the probe proves nothing"
    _assert_all_closed(tracked, "a failing mcp call")
    with pytest.raises(mcp.ToolError, match="bad arguments"):
        tools.call("walk", {"nope": 1})
    _assert_all_closed(tracked, "a call with bad arguments")
