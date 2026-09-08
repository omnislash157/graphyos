from __future__ import annotations

import json
from pathlib import Path


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



def test_removal_audit_rebuild_tables_and_composer_absent():
    """The build-lane runner is gone with the rebuild tables (graphyos #41): no shell over a
    descriptor string, no `_build` · `ensure_fresh` · `code_graph_publish_inplace` to call it."""
    src = Path(carto.__file__).read_text(encoding="utf-8")
    assert "shell=True" not in src
    for gone in ("_build", "ensure_fresh", "code_graph_publish_inplace", "_shell_quote_out", "_behind_commits"):
        assert not hasattr(carto, gone), f"{gone} is dead code that ran a descriptor string through a shell"
    assert "_CODE_GRAPH_REBUILD" not in src
    assert "_DATA_GRAPH_REBUILD" not in src
    assert "graph_journal" not in src
    assert "_journal_page" not in src
    assert "sys.executable" not in src
    assert ("host_" + "sdk.tools") not in src



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
