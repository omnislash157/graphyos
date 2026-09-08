from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import graphy.cartograph as carto
from graphy.tenant import Tenant


def _tenant(tmp_path: Path, *, data_home: Path | None = None,
            join_keys: Path | None = None, build_lanes=None) -> Tenant:
    data_home = data_home or tmp_path / "data"
    data_home.mkdir(parents=True, exist_ok=True)
    join_keys = join_keys or tmp_path / "registry.json"
    if not join_keys.exists():
        join_keys.write_text(json.dumps({
            "substrate_roster": {"grandfathered": [], "admitted": {}},
            "registered_joins": {"literal_joins": []},
        }), encoding="utf-8")
    return Tenant(
        root=tmp_path, data_home=data_home, adapters=(),
        build_lanes=build_lanes or {}, join_keys=join_keys,
        cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal",
    )


def _write_graph_dir(graph_dir: Path, built_at_sha: str | None = "abc1234") -> None:
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "stats.json").write_text(json.dumps({"built_at_sha": built_at_sha}), encoding="utf-8")



def test_GREEN_fresh_passes_silently(tmp_path, monkeypatch, capsys):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "fastapi_graph"
    _write_graph_dir(graph_dir, built_at_sha="abc1234")
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: "abc1234")
    carto.ensure_fresh(graph_dir, tenant)
    captured = capsys.readouterr()
    assert captured.err == "" and captured.out == ""


def test_GREEN_aging_warns_capsys(tmp_path, monkeypatch, capsys):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "fastapi_graph"
    _write_graph_dir(graph_dir, built_at_sha="abc1234")
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: "def5678")
    monkeypatch.setattr(carto, "_behind_commits", lambda repo_root, built, head: 5)
    carto.ensure_fresh(graph_dir, tenant)
    captured = capsys.readouterr()
    assert "STALE GRAPH" in captured.err
    assert "AGING snapshot" in captured.err


def test_RED_unreadable_stats_refuses_naming_file(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "fastapi_graph"
    graph_dir.mkdir(parents=True)
    (graph_dir / "stats.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        carto.ensure_fresh(graph_dir, tenant)
    assert "stats.json" in str(exc.value)
    assert str(graph_dir / "stats.json") in str(exc.value)


def test_RED_head_unmeasurable_refuses(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "fastapi_graph"
    _write_graph_dir(graph_dir, built_at_sha="abc1234")
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: None)
    with pytest.raises(RuntimeError, match="UNMEASURABLE"):
        carto.ensure_fresh(graph_dir, tenant)


def test_RED_built_unmeasurable_refuses(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "fastapi_graph"
    _write_graph_dir(graph_dir, built_at_sha=None)
    with pytest.raises(RuntimeError, match="ABSENT or its cursor is unreadable"):
        carto.ensure_fresh(graph_dir, tenant)



def test_GREEN_declared_lane_invokes_exact_command(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "widgets_graph"
    _write_graph_dir(graph_dir, built_at_sha="abc1234")
    marker = tmp_path / "marker.txt"
    command = f'echo lane-invoked > "{marker}"'
    tenant = _tenant(tmp_path, build_lanes={"widgets_graph": (command, "walk-time-auto")})
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: "def5678")
    carto.ensure_fresh(graph_dir, tenant)
    assert marker.exists()
    assert marker.read_text(encoding="utf-8").strip() == "lane-invoked"


def test_RED_no_lane_never_invents_command(tmp_path, monkeypatch, capsys):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "widgets_graph"
    _write_graph_dir(graph_dir, built_at_sha="abc1234")
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: "def5678")
    monkeypatch.setattr(carto, "_behind_commits", lambda repo_root, built, head: 5)
    calls = []

    def _no_run(*args, **kwargs):
        calls.append(args)
        return pytest.importorskip("subprocess").CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr(carto.subprocess, "run", _no_run)
    carto.ensure_fresh(graph_dir, tenant)
    captured = capsys.readouterr()
    assert "STALE GRAPH" in captured.err
    assert calls == [], "no command may be invented for a lane-less graph"

    monkeypatch.setattr(carto, "_behind_commits", lambda repo_root, built, head: 500)
    calls.clear()
    with pytest.raises(RuntimeError, match="GROSSLY stale"):
        carto.ensure_fresh(graph_dir, tenant)
    assert calls == []



def test_GREEN_write_graph_publish_roundtrip(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    out_dir = Path(tenant.data_home) / "widgets_graph"
    graph = carto.cartograph([
        {"kind": "node", "id": "widgets://module/widgets", "node_type": "module", "dotted": "widgets"},
        {"kind": "edge", "edge_type": "imports", "src": "widgets://module/widgets",
         "dst": "fastapi://module/fastapi"},
        {"kind": "stat", "stat_type": "test_stat"},
    ])
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: "abc1234")
    carto.write_graph(graph, out_dir, repo_root=Path(tenant.root))
    assert (out_dir / "nodes.json").exists()
    assert (out_dir / "edges.json").exists()
    assert (out_dir / "clusters.json").exists()
    assert (out_dir / "adjacency.json").exists()
    stats = json.loads((out_dir / "stats.json").read_text(encoding="utf-8"))
    assert stats["built_at_sha"] == "abc1234"
    assert stats["node_count"] == 1
    assert stats["edge_count"] == 1
    assert stats["cluster_count"] == 1
    assert stats["counters"]["test_stat"] == 1
    nodes = json.loads((out_dir / "nodes.json").read_text(encoding="utf-8"))
    assert "widgets://module/widgets" in nodes



def test_RED_ensure_fresh_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        carto.ensure_fresh(tmp_path / "x_graph")
    with pytest.raises(ValueError, match="tenant is required"):
        carto.ensure_fresh(tmp_path / "x_graph", None)


def test_GREEN_ensure_fresh_declared_tenant_proceeds(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    graph_dir = tmp_path / "fastapi_graph"
    _write_graph_dir(graph_dir, built_at_sha="abc1234")
    monkeypatch.setattr(carto, "repo_head_sha", lambda repo_root=None: "abc1234")
    carto.ensure_fresh(graph_dir, tenant)



def test_removal_audit_rebuild_tables_and_composer_absent():
    src = Path(carto.__file__).read_text(encoding="utf-8")
    assert "_CODE_GRAPH_REBUILD" not in src
    assert "_DATA_GRAPH_REBUILD" not in src
    assert "graph_journal" not in src
    assert "_journal_page" not in src
    assert "sys.executable" not in src
    assert ("host_" + "sdk.tools") not in src



def test_publish_inplace_routes_out_placeholder_through_sibling_temp(tmp_path):
    lane = {"widgets_graph": (
        "mkdir -p {out} && printf NEW > {out}/nodes.json && echo {out} > {out}/received.txt",
        "walk-time-auto")}
    tenant = _tenant(tmp_path, build_lanes=lane)
    live = tmp_path / "graphs" / "widgets_graph"
    live.mkdir(parents=True)
    (live / "nodes.json").write_text("OLD", encoding="utf-8")

    carto.code_graph_publish_inplace("widgets_graph", live, tenant=tenant)

    assert (live / "nodes.json").read_text(encoding="utf-8") == "NEW"
    received = (live / "received.txt").read_text(encoding="utf-8").strip()
    assert ".widgets_graph.build." in received
    assert received != str(live)
    assert not [p for p in live.parent.iterdir() if ".build." in p.name or ".old." in p.name]


def test_out_quoting_is_platform_correct(monkeypatch):
    import shlex as _shlex
    spaced = Path("C:\\Users\\Jane Doe\\graphs\\.widgets_graph.build.42")

    monkeypatch.setattr(carto.os, "name", "posix")
    q = carto._shell_quote_out(Path("/tmp/sp aced/.widgets_graph.build.42"))
    assert _shlex.split(q) == ["/tmp/sp aced/.widgets_graph.build.42"]

    monkeypatch.setattr(carto.os, "name", "nt")
    q = carto._shell_quote_out(spaced)
    assert q == '"C:\\Users\\Jane Doe\\graphs\\.widgets_graph.build.42"'
    assert "'" not in q


def test_publish_inplace_refuses_command_without_out_placeholder(tmp_path):
    lane = {"widgets_graph": ("printf NEW > /dev/null", "walk-time-auto")}
    tenant = _tenant(tmp_path, build_lanes=lane)
    live = tmp_path / "graphs" / "widgets_graph"
    live.mkdir(parents=True)
    (live / "nodes.json").write_text("OLD", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"\{out\}"):
        carto.code_graph_publish_inplace("widgets_graph", live, tenant=tenant)
    assert (live / "nodes.json").read_text(encoding="utf-8") == "OLD"


def test_publish_inplace_failed_command_preserves_live(tmp_path):
    lane = {"widgets_graph": ("mkdir -p {out} && false", "walk-time-auto")}
    tenant = _tenant(tmp_path, build_lanes=lane)
    live = tmp_path / "graphs" / "widgets_graph"
    live.mkdir(parents=True)
    (live / "nodes.json").write_text("OLD", encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed"):
        carto.code_graph_publish_inplace("widgets_graph", live, tenant=tenant)
    assert (live / "nodes.json").read_text(encoding="utf-8") == "OLD"
    assert not [p for p in live.parent.iterdir() if ".build." in p.name or ".old." in p.name]



def _live_widgets(tenant) -> Path:
    live = Path(tenant.data_home) / "widgets_graph"
    live.mkdir(parents=True, exist_ok=True)
    (live / "nodes.json").write_text(json.dumps({"widgets://module/widgets": {}}), encoding="utf-8")
    (live / "stats.json").write_text(json.dumps({"built_at_sha": "cafe1234"}), encoding="utf-8")
    return live


def test_publish_wire_appends_exactly_one_page(tmp_path):
    lane = {"widgets_graph": (
        "mkdir -p {out} && printf '{\"widgets://module/widgets\": {}, "
        "\"widgets://func/widgets.gadget\": {}}' > {out}/nodes.json && "
        "printf '{\"built_at_sha\": \"beef5678\"}' > {out}/stats.json",
        "walk-time-auto")}
    tenant = _tenant(tmp_path, build_lanes=lane)
    live = _live_widgets(tenant)

    carto.code_graph_publish_inplace("widgets_graph", live, tenant=tenant)

    jpath = Path(tenant.journal) / "widgets_graph.journal.jsonl"
    assert jpath.exists(), "the publish wire never paged the journal"
    records = [json.loads(l) for l in jpath.read_text(encoding="utf-8").splitlines() if l.strip()]
    pages = [r for r in records if r.get("kind") == "page"]
    assert len(pages) == 1, f"exactly one publish page expected, got {len(pages)}"
    page = pages[0]
    assert page["seq"] == 1
    assert "prev_cursor" in page and page["prev_cursor"] == "cafe1234"
    assert page["graph"] == "widgets"
    assert page["n_born"] == 1


def test_publish_wire_poisoned_journal_never_breaks_publish(tmp_path, monkeypatch, capsys):
    import graphy.journal as journal_mod

    lane = {"widgets_graph": (
        "mkdir -p {out} && printf NEW > {out}/nodes.json", "walk-time-auto")}
    tenant = _tenant(tmp_path, build_lanes=lane)
    live = _live_widgets(tenant)

    def _poisoned(*a, **k):
        raise RuntimeError("poisoned journal")

    monkeypatch.setattr(journal_mod, "observe_publish", _poisoned)
    carto.code_graph_publish_inplace("widgets_graph", live, tenant=tenant)
    assert (live / "nodes.json").read_text(encoding="utf-8") == "NEW"
    assert "[journal-observer]" in capsys.readouterr().err


def _git_repo(path: Path) -> str:
    import subprocess
    path.mkdir(parents=True, exist_ok=True)
    (path / "a.py").write_text("def a():\n    return 1\n")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "i"], cwd=path, check=True)
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=path, capture_output=True, text=True).stdout.strip()


def test_GREEN_working_tree_dirt_joins_the_cursor(tmp_path):
    """graphyos #39: a clean tree's cursor is exactly `git:<head>` (unchanged); an uncommitted edit
    grows a `+<digest>` that moves with the bytes, an untracked file counts, the tenant's own home
    never does, and reverting the edit restores the clean cursor."""
    repo = tmp_path / "r"
    head = _git_repo(repo)
    clean, n = carto.repo_cursor(repo)
    assert (clean, n) == (f"git:{head}", 0)
    assert carto.cursor_drift(clean, repo) is None
    (repo / "a.py").write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    dirty1, n = carto.repo_cursor(repo)
    assert dirty1.startswith(f"git:{head}+") and len(dirty1) == len(clean) + 17 and n == 1
    assert carto.cursor_drift(clean, repo) == "the working tree moved past the store: 1 file(s) modified or untracked since the build"
    assert carto.cursor_drift(dirty1, repo) is None
    assert carto.cursor_drift("sha256:" + "0" * 64, repo) is None, "a content cursor never drifts"
    # the same file edited again: status is identical, the bytes are not — the digest moves
    (repo / "a.py").write_text("def a():\n    return 1\n\ndef b():\n    return 3\n")
    dirty2, _ = carto.repo_cursor(repo)
    assert dirty2 != dirty1 and dirty2.startswith(f"git:{head}+")
    # an untracked file counts; the eat's home (its own product) never does
    (repo / "new.py").write_text("x = 1\n")
    home = repo / ".graphy"
    (home / "substrate").mkdir(parents=True)
    (home / "substrate" / "ring.json").write_text("{}")
    dirty3, n = carto.repo_cursor(repo, exclude=(home,))
    assert n == 2 and dirty3 not in (dirty1, dirty2)
    assert carto.repo_cursor(repo)[1] == 3        # without the exclude the home's file is dirt
    assert carto.cursor_drift(dirty3, repo, exclude=(home,)) is None
    # a short head and a long head are the same head; a subdirectory reads the same tree
    full = subprocess_head(repo)
    assert carto.cursor_drift(dirty3.replace(head, full, 1), repo, exclude=(home,)) is None
    (repo / "pkg").mkdir()
    assert carto.repo_cursor(repo / "pkg", exclude=(home,)) == (dirty3, 2), "a subdirectory reads the same tree"
    # revert: the clean cursor again, byte for byte
    (repo / "new.py").unlink()
    (repo / "a.py").write_text("def a():\n    return 1\n")
    assert carto.repo_cursor(repo, exclude=(home,)) == (clean, 0)
    assert carto.cursor_drift(dirty3, repo, exclude=(home,)) == (
        "the working tree moved past the store: the edits it was built from are gone (the tree is clean)")
    # a commit past the store names the HEAD
    (repo / "a.py").write_text("def a():\n    return 5\n")
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "j"], cwd=repo, check=True)
    assert carto.cursor_drift(clean, repo).startswith(f"HEAD moved past the store: built at {head}, HEAD is ")
    assert carto.repo_cursor(tmp_path / "nowhere") == (None, 0)


def subprocess_head(repo: Path) -> str:
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
