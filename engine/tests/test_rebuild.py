"""rebuild — the supported multi-lane rebuild (graphyos #71).

The first client's tenant reached into `cli._clear_substrate`, `cartograph.repo_cursor` and
`graphy._portable_flock` because there was no public path for "many lanes, mixed producers" — only
`eat`, which is one ring and prunes. These prove the public path runs the same sequence and that a
lane the engine did not mint survives it.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import graphy
from graphy import rebuild as rebuild_lane


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


def _place_foreign_lane(sub: Path) -> None:
    """A shard from a producer this engine never wrote — the tenant's own emitter, already run.

    It binds a code node to a table on its own edge type, which is exactly the shape the doors were
    blind to before graphyos #68, and declares that vocabulary in its PROVENANCE.
    """
    d = sub / "pg_schema_graph"
    d.mkdir(parents=True, exist_ok=True)
    table = "pg_schema://table/pg_schema.public.invoices"
    (d / "nodes.json").write_text(json.dumps({
        table: {"kind": "node", "node_type": "table", "id": table,
                "dotted": "pg_schema.public.invoices", "module": "pg_schema", "role": "table"},
    }), encoding="utf-8")
    (d / "edges.json").write_text(json.dumps([
        {"kind": "edge", "edge_type": "reads_table", "src": "core://func/core.mod.run",
         "dst": table, "line": 2},
    ]), encoding="utf-8")
    (d / "PROVENANCE.json").write_text(json.dumps({
        "surface": "pg_schema_graph.records",
        "counts": {"node_count": 1, "edge_count": 1, "edge_types": {"reads_table": 1}},
        "vocabulary": {"producer": "sql_census", "relations": {"reads_table": ["depends"]},
                       "undeclared": []},
    }), encoding="utf-8")
    (d / "emitter_receipt.json").write_text(json.dumps({"rows": 1}), encoding="utf-8")


def _sp(tmp_path: Path, repo: Path) -> Path:
    """A site-packages holding the repo's own package: the ring closes over it and nothing else."""
    return repo


def test_GREEN_a_code_lane_and_a_foreign_lane_rebuild_through_the_public_entry_point(tmp_path, capsys):
    """The done check of graphyos #71: one minted lane, one lane a foreign producer wrote, through
    the public API — no underscore imports — landing a descriptor that declares both and a store
    that passes `check`."""
    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    sub.mkdir(parents=True)
    _place_foreign_lane(sub)
    receipt = rebuild_lane.rebuild(
        root=repo, substrate=sub, descriptor=repo / ".graphy" / "tenant.json", tenant_id="core",
        lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=_sp(tmp_path, repo),
                                      corpus=repo / "core"),
               rebuild_lane.Lane.placed("pg_schema")],
        container="none",
    )
    assert receipt["minted"] == ["core"] and receipt["placed"] == ["pg_schema"]
    assert "core_graph" in receipt["lanes"] and "pg_schema_graph" in receipt["lanes"]
    assert receipt["cursor"].startswith("git:")

    # the placed lane survived the clear, with the file the clear would otherwise have stripped
    assert (sub / "pg_schema_graph" / "nodes.json").is_file()
    assert (sub / "pg_schema_graph" / "emitter_receipt.json").is_file()

    desc = json.loads((repo / ".graphy" / "tenant.json").read_text(encoding="utf-8"))
    assert "pg_schema_graph" in desc["build_lanes"] and "core_graph" in desc["build_lanes"]

    index = json.loads((sub / ".federation_scheme_index.json").read_text(encoding="utf-8"))
    assert index["pg_schema"]["own"] == ["pg_schema"]      # schemes read from the placed lane's own edges

    out = capsys.readouterr().out
    assert "REBUILD OK" in out and "1 minted · 1 placed" in out
    assert "CHECK OK" in out


def test_GREEN_the_placed_lane_is_walkable_and_its_declared_vocabulary_reaches_the_door(tmp_path):
    """A lane the engine did not mint is not a second-class lane: the walk crosses into it on the
    literal, and the relation it declares is one a door walks (graphyos #68 + #71 together)."""
    import graphy.doors as doors
    import graphy.federated_store as fs
    import graphy.cli as cli

    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    sub.mkdir(parents=True)
    _place_foreign_lane(sub)
    rebuild_lane.rebuild(
        root=repo, substrate=sub, descriptor=repo / ".graphy" / "tenant.json", tenant_id="core",
        lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
               rebuild_lane.Lane.placed("pg_schema")],
        container="none", log=lambda *_a, **_k: None,
    )
    tenant = cli._load_tenant(str(repo / ".graphy" / "tenant.json"))
    roster = [s.removesuffix("_graph") for s in tenant.build_lanes]
    store = fs.open_for(roster, tenant=tenant, tenant_id="core")
    assert store.relations.get("reads_table") == ["depends"]     # the placed lane's declaration folded
    table = "pg_schema://table/pg_schema.public.invoices"
    b = doors.blast(store, table, max_depth=2)
    assert [r.node for r in b.reached.values() if r.hop > 0] == ["core://func/core.mod.run"]


def test_RED_rebuild_refuses_a_placed_lane_with_no_shard_and_an_empty_roster(tmp_path):
    """The engine never runs a foreign producer, so a placed lane with nothing on disk is a caller
    error and is named as one rather than producing a roster with a hole in it."""
    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    sub.mkdir(parents=True)
    with pytest.raises(rebuild_lane.RebuildError, match="hold no shard"):
        rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=repo / ".graphy" / "tenant.json",
                             tenant_id="core",
                             lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo,
                                                           corpus=repo / "core"),
                                    rebuild_lane.Lane.placed("pg_schema")])
    with pytest.raises(rebuild_lane.RebuildError, match="no lanes declared"):
        rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=repo / "t.json",
                             tenant_id="core", lanes=[])
    with pytest.raises(rebuild_lane.RebuildError, match="every lane is placed"):
        rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=repo / "t.json",
                             tenant_id="core", lanes=[rebuild_lane.Lane.placed("pg_schema")])


def test_RED_a_lane_is_named_and_a_minted_lane_names_its_corpus(tmp_path):
    """The descriptor's law one level up: a lane that cannot say what it is refuses at construction,
    not at the smash that would have guessed."""
    with pytest.raises(rebuild_lane.RebuildError, match="must name package"):
        rebuild_lane.Lane(slug="core", producer="python_ast")
    with pytest.raises(rebuild_lane.RebuildError, match="does not mint it"):
        rebuild_lane.Lane(slug="pg_schema", package="pg_schema")
    with pytest.raises(rebuild_lane.RebuildError, match="slug is required"):
        rebuild_lane.Lane(slug="  ")


def test_GREEN_the_three_private_names_the_first_tenant_imported_are_public_now():
    """The done check's second bullet, asserted rather than described. A tenant's rebuild imported
    `cli._clear_substrate`, `cartograph.repo_cursor` and `graphy._portable_flock`; the first two are
    public here and the flock is internal to the call that needs it."""
    for name in ("Lane", "RebuildError", "clear_substrate", "repo_cursor"):
        assert name in graphy.__all__, name
        assert getattr(graphy, name, None) is not None, name
    # `rebuild` the FUNCTION is deliberately not exported at the package top level: a function of
    # that name would shadow the module of that name, and `graphy.rebuild.rebuild` would stop
    # resolving. The module is the namespace, and it is reachable.
    assert "rebuild" not in graphy.__all__
    assert callable(rebuild_lane.rebuild)
    # the flock is NOT exported: it is the call's business, not the caller's
    assert "_portable_flock" not in graphy.__all__
