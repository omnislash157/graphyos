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
