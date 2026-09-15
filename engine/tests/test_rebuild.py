"""rebuild — the supported multi-lane rebuild (graphyos #71).

The first client's tenant reached into `cli._clear_substrate`, `cartograph.repo_cursor` and
`graphy._portable_flock` because there was no public path for "many lanes, mixed producers" — only
`eat`, which is one ring and prunes. These prove the public path runs the same sequence and that a
lane the engine did not mint survives it.
"""
from __future__ import annotations

import json
import os
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


def _session(repo: Path, n: int, body: str) -> Path:
    """One captured session in the archive the hooks grow — the input the cursor cannot see (graphyos #66)."""
    sessions = repo / ".claude" / "recovery" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions.parent / ".gitignore").write_text("*\n", encoding="utf-8")
    sid = f"abcdef{n:02d}-0000-0000-0000-{n:012d}"
    head = (f"# CONVERSATION FULL SESSION — 1 exchanges, verbatim and in order\n\nsession: {sid}\n"
            f"exchanges 1–1 of 1 · ~40 tokens\nsemantic_sha256: {'0' * 64}\n"
            f"captured_at: 2026-09-09T10:{n:02d}:00+00:00\nresolved_by: SessionEnd:clear\n\n")
    p = sessions / f"{n:05d}__20260909T10{n:02d}00Z__{sid[:8]}.md"
    p.write_text(head + body, encoding="utf-8")
    return p


def _lane_files(home: Path, lane: str) -> dict[str, str]:
    """Every file a producer put in a lane, hashed — nodes · edges · PROVENANCE · its own receipt — plus the
    resolver's sidecar by its edges: `resolved_over` there stamps the roster the resolution was made over, and the
    roster holds the new history shard by design; the container trio build defers is not a producer's file."""
    import hashlib
    skip = {"adjacency.parquet", "nodes.parquet", "container.json", "wormhole_edges.json"}
    out = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted((home / lane).iterdir()) if p.is_file() and p.name not in skip}
    side = json.loads((home / lane / "wormhole_edges.json").read_text(encoding="utf-8"))
    out["wormhole_edges.json#edges"] = hashlib.sha256(json.dumps([side["edges"], side["qualified"]], sort_keys=True)
                                                     .encode("utf-8")).hexdigest()
    return out


def test_GREEN_stale_history_remedy_names_no_eat_and_history_remint_changes_no_other_shard(tmp_path, capsys):
    """graphyos #132, the first client's Windows tenant: after a session capture the history lane read
    STALE and `check` told the tenant to run `graphy eat .` or `graphy shell install` — on a tenant with
    house lanes the first prunes every lane the ring did not mint and the second rewrites the hook wiring
    the house owns. The remedy names `graphy history --remint` and neither of those; the verb re-mints the
    history shard alone into a staged generation and lands it, and every other lane — the code lane and
    the placed lane with its producer's own receipt — is carried byte-for-byte, its shard digest unchanged."""
    import re
    from graphy import cli
    repo = _git_repo(tmp_path)
    _session(repo, 1, "--- [1] USER\n\nlook at core.mod.run\n\n--- [1] ASSISTANT\n\nok\n")
    sub = repo / ".graphy" / "substrate"
    desc = repo / ".graphy" / "tenant.json"
    sub.mkdir(parents=True)
    _place_foreign_lane(sub)
    lanes = [rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
             rebuild_lane.Lane.placed("pg_schema")]
    rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=desc, tenant_id="core", container="none",
                         history=True, lanes=lanes, log=lambda *a: None)
    home = cli.served_data_home(desc)
    assert (home / "history_graph" / "PROVENANCE.json").is_file()
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "core"]) == 0
    capsys.readouterr()
    others = ("core_graph", "pg_schema_graph")
    files = {lane: _lane_files(home, lane) for lane in others}
    assert "emitter_receipt.json" in files["pg_schema_graph"]

    _session(repo, 2, "--- [1] USER\n\nagain core.mod.run\n\n--- [1] ASSISTANT\n\nok\n")
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "core"]) == 1
    err = capsys.readouterr().err
    assert "CHECK RED: history lane: STALE" in err and "cursor lane" not in err
    assert re.search(r"\beat\b", err) is None and "shell install" not in err, err
    assert f"re-mint it: `graphy history --remint --tenant {desc.as_posix()} --tenant-id core`" in err
    assert "the rebuild this tenant declares" not in err                    # init declares no command for the lane
    # a house that declares its rebuild for the lane in the descriptor is told it beside the verb
    raw = json.loads(desc.read_text(encoding="utf-8"))
    raw["build_lanes"]["history_graph"][0] = "bash tools/remint_history.sh"
    desc.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "core"]) == 1
    err = capsys.readouterr().err
    assert "or the rebuild this tenant declares for the lane: `bash tools/remint_history.sh`" in err, err
    assert re.search(r"\beat\b", err) is None and "shell install" not in err, err

    assert cli.main(["history", "--remint", "--tenant", str(desc), "--tenant-id", "core"]) == 0
    out = capsys.readouterr().out
    assert "HISTORY REMINT: history_graph" in out and "2 other lane(s) carried" in out and "core_graph · pg_schema_graph" in out
    assert "HISTORY REMINT OK: history_graph re-minted, 2 other lane(s) carried" in out
    new_home = cli.served_data_home(desc)
    assert new_home != home and home.is_dir()                                   # landed; the replaced generation kept
    assert not (repo / ".graphy" / ".tenant.json.next").exists()
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "core"]) == 0
    capsys.readouterr()
    assert {lane: _lane_files(new_home, lane) for lane in others} == files      # every producer file and every resolved edge
    assert (sub / "pg_schema_graph" / "emitter_receipt.json").is_file()         # the placement stays for the producer
    assert cli.main(["history", "--symbol", "core.mod.run", "--tenant", str(desc), "--tenant-id", "core"]) == 0
    assert "TIMELINE: 2 session(s)" in capsys.readouterr().out


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

    served = Path(desc["data_home"])
    assert served == Path(receipt["substrate"]) and served != sub     # a generation beside the substrate (graphyos #98)
    assert (served / "pg_schema_graph" / "emitter_receipt.json").is_file()
    index = json.loads((served / ".federation_scheme_index.json").read_text(encoding="utf-8"))
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


def test_GREEN_placed_lane_declared_relations_drive_blast_and_descend(tmp_path, capsys):
    """graphyos #110, the production tenant's acceptance case measured on 0.2.4 (which predates #68):
    `blast <table>` answered dependents=0 and `descend <reader>` reached no schema node although adj
    held the `reads_table` edge. Through the supported rebuild and the CLI doors a tenant runs: the
    house vocabulary a placed lane declares is followed by class, and a type it leaves undeclared is
    named NOT WALKED, never followed."""
    import graphy.cli as cli

    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    sub.mkdir(parents=True)
    _place_foreign_lane(sub)
    d = sub / "pg_schema_graph"
    table, view, index = ("pg_schema://table/pg_schema.public.invoices", "pg_schema://view/pg_schema.public.v_invoices",
                          "pg_schema://index/pg_schema.public.invoices_pk")
    nodes = json.loads((d / "nodes.json").read_text())
    nodes[view] = {"kind": "node", "node_type": "view", "id": view, "dotted": "pg_schema.public.v_invoices",
                   "module": "pg_schema", "role": "view"}
    nodes[index] = {"kind": "node", "node_type": "index", "id": index, "dotted": "pg_schema.public.invoices_pk",
                    "module": "pg_schema", "role": "index"}
    (d / "nodes.json").write_text(json.dumps(nodes))
    edges = json.loads((d / "edges.json").read_text())
    edges += [{"kind": "edge", "edge_type": "sourced_from", "src": view, "dst": table},
              {"kind": "edge", "edge_type": "indexes_on", "src": index, "dst": table}]
    (d / "edges.json").write_text(json.dumps(edges))
    prov = json.loads((d / "PROVENANCE.json").read_text())
    prov["counts"] = {"node_count": 3, "edge_count": 3, "edge_types": {"reads_table": 1, "sourced_from": 1, "indexes_on": 1}}
    prov["vocabulary"]["relations"] = {"reads_table": ["depends", "reaches"], "sourced_from": ["depends", "reaches"]}
    (d / "PROVENANCE.json").write_text(json.dumps(prov))
    rebuild_lane.rebuild(
        root=repo, substrate=sub, descriptor=repo / ".graphy" / "tenant.json", tenant_id="core",
        lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
               rebuild_lane.Lane.placed("pg_schema")],
        container="none", log=lambda *_a, **_k: None,
    )
    argv = ["--tenant", str(repo / ".graphy" / "tenant.json"), "--tenant-id", "core"]
    capsys.readouterr()
    assert cli.main(["blast", table, *argv]) == 0
    out = capsys.readouterr().out
    assert "core://func/core.mod.run" in out and view in out           # the reader and the view, by declared class
    assert "hop1=2" in out                                              # both at hop 1
    assert index not in out.split("NOT WALKED")[0] and "NOT WALKED: indexes_on 1" in out
    assert cli.main(["descend", "core.mod.run", *argv]) == 0
    assert table in capsys.readouterr().out                             # the reader reaches the schema node


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


def _place_skills_lane(sub: Path, declare: bool) -> str:
    """A skills shard the tenant's own emitter wrote: a skill `governs` the code it rules. `declare`
    is whether its PROVENANCE names `governs` a doc relation — the first client's 67 admitted edges
    that appeared under DOCS zero times were this shape undeclared (graphyos #86)."""
    d = sub / "skills_graph"
    d.mkdir(parents=True, exist_ok=True)
    skill = "skills://skill/skills.release_checklist"
    (d / "nodes.json").write_text(json.dumps({
        skill: {"kind": "node", "node_type": "skill", "id": skill, "dotted": "skills.release_checklist",
                "module": "skills", "role": "skill"},
    }), encoding="utf-8")
    (d / "edges.json").write_text(json.dumps([
        {"kind": "edge", "edge_type": "governs", "src": skill, "dst": "core://func/core.mod.run"},
    ]), encoding="utf-8")
    vocab = {"producer": "skills_census", "relations": {"governs": ["lexical"]}, "undeclared": []}
    if declare:
        vocab["doc_relations"] = ["governs"]
    (d / "PROVENANCE.json").write_text(json.dumps({
        "surface": "skills_graph.records",
        "counts": {"node_count": 1, "edge_count": 1, "edge_types": {"governs": 1}},
        "vocabulary": vocab,
    }), encoding="utf-8")
    return skill


@pytest.mark.parametrize("declare", [False, True])
def test_GREEN_a_doc_lane_that_declares_its_relation_is_listed_under_explain_docs(tmp_path, capsys, declare):
    """graphyos #86: `explain … DOCS` pinned two schemes, so a placed skills shard whose `governs`
    edges were admitted and walkable never appeared there. The lane's PROVENANCE declares its doc
    relation, the rebuild carries it into the scheme index's `_meta`, the build folds it into the
    store, and the CLI door — through the counting proxy — lists the skill. Undeclared, the index
    carries no doc keys and the answer is today's: DOCS none."""
    import graphy.cli as cli

    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    sub.mkdir(parents=True)
    skill = _place_skills_lane(sub, declare)
    rebuild_lane.rebuild(
        root=repo, substrate=sub, descriptor=repo / ".graphy" / "tenant.json", tenant_id="core",
        lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
               rebuild_lane.Lane.placed("skills")],
        container="none", log=lambda *_a, **_k: None,
    )
    served = Path(json.loads((repo / ".graphy" / "tenant.json").read_text())["data_home"])
    meta = json.loads((served / ".federation_scheme_index.json").read_text(encoding="utf-8"))["_meta"]
    capsys.readouterr()
    assert cli.main(["explain", "core.mod.run", "--tenant", str(repo / ".graphy" / "tenant.json"),
                     "--tenant-id", "core"]) == 0
    out = capsys.readouterr().out
    if declare:
        assert meta["doc_schemes"] == ["skills"] and meta["doc_relations"] == ["governs"]
        assert f"hop1 governs" in out and skill in out and "DOCS (DOC_EXPLAINS endpoints, 1)" in out
    else:
        assert "doc_schemes" not in meta and "doc_relations" not in meta
        assert skill not in out and "DOCS: none" in out


def _rebuild_with_skills(tmp_path: Path, vocab_doc, extra_nodes: dict | None = None):
    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    sub.mkdir(parents=True)
    _place_skills_lane(sub, declare=True)
    d = sub / "skills_graph"
    prov = json.loads((d / "PROVENANCE.json").read_text())
    prov["vocabulary"]["doc_relations"] = vocab_doc
    (d / "PROVENANCE.json").write_text(json.dumps(prov))
    if extra_nodes:
        nodes = json.loads((d / "nodes.json").read_text())
        nodes.update(extra_nodes)
        (d / "nodes.json").write_text(json.dumps(nodes))
    rebuild_lane.rebuild(
        root=repo, substrate=sub, descriptor=repo / ".graphy" / "tenant.json", tenant_id="core",
        lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
               rebuild_lane.Lane.placed("skills")],
        container="none", log=lambda *_a, **_k: None,
    )
    return Path(json.loads((repo / ".graphy" / "tenant.json").read_text())["data_home"])


def test_RED_a_malformed_doc_declaration_refuses_by_name_and_a_bare_string_is_one_relation(tmp_path):
    """Round 1 of #86's review: `"governs"` and `["governs", 3]` were dropped silently — `CHECK OK`
    and `DOCS: none`, the empty answer standing in for could-not-tell."""
    sub = _rebuild_with_skills(tmp_path / "string", "governs")
    meta = json.loads((sub / ".federation_scheme_index.json").read_text())["_meta"]
    assert meta["doc_relations"] == ["governs"] and meta["doc_schemes"] == ["skills"]
    with pytest.raises(rebuild_lane.RebuildError, match=r"lane 'skills' PROVENANCE vocabulary.doc_relations is \['governs', 3\]"):
        _rebuild_with_skills(tmp_path / "mixed", ["governs", 3])


def test_RED_a_doc_lane_carrying_another_lanes_scheme_refuses_naming_both(tmp_path):
    """Round 1 of #86's review: a skills lane that also carried a stub `core://` node owned `core`, so
    `core` became a doc scheme and code — the seed itself — was listed under its own DOCS."""
    stub = {"core://func/core.mod.run": {"kind": "node", "node_type": "func", "id": "core://func/core.mod.run",
                                         "dotted": "core.mod.run", "module": "core", "role": "code"}}
    with pytest.raises(rebuild_lane.RebuildError, match=r"lane 'skills' declares doc relations \['governs'\] but lane 'core' also owns \['core'\]"):
        _rebuild_with_skills(tmp_path, ["governs"], extra_nodes=stub)


def _plugin_door(repo: Path):
    """What the shipped Claude Code plugin runs against a repo — its argv read from `.claude-plugin/plugin.json`,
    `${CLAUDE_PROJECT_DIR}` filled — stopped at the moment it would serve: (rc, the generation it opened)."""
    from graphy import cli
    from graphy import mcp as mcp_server
    manifest = json.loads((Path(__file__).parents[2] / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    argv = [a.replace("${CLAUDE_PROJECT_DIR}", str(repo)) for a in manifest["mcpServers"]["graphy"]["args"]]
    served: list[str] = []
    real = mcp_server.serve
    mcp_server.serve = lambda tools: (served.append(tools.generation), 0)[1]
    try:
        rc = cli._REAL_MAIN(argv) if hasattr(cli, "_REAL_MAIN") else cli.main(argv)
    finally:
        mcp_server.serve = real
    return rc, (served[0] if served else None)


def _generations(repo: Path) -> list[str]:
    return sorted(p.name for p in (repo / ".graphy").iterdir() if ".gen-" in p.name)


@pytest.mark.parametrize("lane", ["rebuild", "eat"])
def test_GREEN_store_stays_servable_through_a_rebuild(tmp_path, capsys, monkeypatch, lane):
    """graphyos #98: the rebuild's clear removed the served store, so a door started inside the window
    refused — and a client connects its servers once, so that session lost the door for its life. The
    next generation is now staged beside the served data home and lands in one descriptor rename after
    build: the door the plugin ships (default `--on-stale refuse`) opens the last good store FRESH at every
    step, because nothing it reads is touched; a store held open across the whole rebuild still answers;
    the generation it served is discarded after the landing, and no stage or staged descriptor is left."""
    from graphy import cli
    from graphy import federated_store as fs
    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    desc = repo / ".graphy" / "tenant.json"

    def run(**kw):
        if lane == "eat":
            assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
        else:
            sub.mkdir(parents=True, exist_ok=True)
            _place_foreign_lane(sub)
            rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=desc, tenant_id="core", container="none",
                                 lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
                                        rebuild_lane.Lane.placed("pg_schema")], log=lambda *a: None, **kw)

    run()
    rc, first = _plugin_door(repo)
    assert rc == 0 and first
    held = fs.SQLiteStore(fs.store_path_for(cli._roster(cli._load_tenant(str(desc))), tenant=cli._load_tenant(str(desc))))
    held_gen = held.generation()
    old_home = cli.served_data_home(desc)
    # a door that read the descriptor a moment before the landing: it opens the generation that descriptor names
    before_rename = tmp_path / "read_before_the_rename.json"
    before_rename.write_bytes(desc.read_bytes())

    seen: list[tuple[str, int, str | None]] = []
    real_main = cli.main
    monkeypatch.setattr(cli, "_REAL_MAIN", real_main, raising=False)

    def main(argv):
        if argv[0] in ("smash", "init", "converge", "build", "check"):
            seen.append((f"before {argv[0]}", *_plugin_door(repo)))
        if argv[0] == "check":                     # landed: the previous generation is still whole (review round 2)
            t = cli._load_tenant(str(before_rename))
            fs.open_for(cli._roster(t), tenant=t, tenant_id="core", on_stale="refuse").close()
        return real_main(argv)

    monkeypatch.setattr(cli, "main", main)
    (repo / "core" / "extra.py").write_text("def more():\n    return 3\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "two"], cwd=repo, check=True)
    if lane == "eat":
        assert real_main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    else:
        run()
    monkeypatch.setattr(cli, "main", real_main)

    steps = [s for s, _, _ in seen]
    assert {"before smash", "before init", "before converge", "before build", "before check"} <= set(steps), steps
    before_land = [x for x in seen if x[0] != "before check"]
    assert all(rc == 0 and gen == first for _, rc, gen in before_land), seen   # the shipped door serves, fresh, every step
    rc, after = _plugin_door(repo)
    assert rc == 0 and after and after != first                                 # the next generation landed
    assert held.generation() == held_gen and held.find("core.mod.run")          # a door held across it still answers
    new_home = cli.served_data_home(desc)
    assert new_home != old_home and old_home.is_dir()                           # the replaced generation is kept whole
    assert _generations(repo) == sorted([old_home.name, new_home.name])
    assert not (repo / ".graphy" / ".tenant.json.next").exists()
    if lane == "rebuild":
        assert (sub / "pg_schema_graph" / "emitter_receipt.json").is_file()     # the placement stays for the producer
    # the next landing removes the generation older than the one it replaces
    (repo / "core" / "later.py").write_text("def later():\n    return 4\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "three"], cwd=repo, check=True)
    run()
    if os.name == "nt":
        # the store `held` keeps open pins its files here (#98, #124): the discard is best-effort, the generation
        # older than the replaced one stays on disk until the handle closes, and the landing still served every step
        assert old_home.exists() and {new_home.name, cli.served_data_home(desc).name} <= set(_generations(repo))
    else:
        assert not old_home.exists() and _generations(repo) == sorted([new_home.name, cli.served_data_home(desc).name])
    from graphy import doors, traversal
    if traversal.have_duckdb() and os.name != "nt":            # on Windows the pinned generation is not gone yet
        # the held door's cache has nowhere to land: the discarded generation is never recreated to hold one
        out = traversal.door(held, old_home / traversal.DIRNAME, "blast", doors.resolve(held, "core.mod.run"), 1)
        assert out.source == "live" and out.stored is None and "is gone" in (out.note or ""), out
        assert not old_home.exists()
    held.close()


@pytest.mark.parametrize("at", ["smash", "build"])
def test_RED_an_interrupted_rebuild_never_touches_the_served_store(tmp_path, capsys, monkeypatch, at):
    """Round 1 of #98's review: the marker design left `.rebuild_in_flight` behind a ^C, so a torn substrate
    was served under warn forever with a false reason. A rebuild interrupted at any step now leaves the served
    generation exactly as it was — FRESH under refuse — and removes its own stage and staged descriptor."""
    from graphy import cli
    from graphy import federated_store as fs
    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    desc = repo / ".graphy" / "tenant.json"
    sub.mkdir(parents=True)
    _place_foreign_lane(sub)
    lanes = lambda: [rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
                     rebuild_lane.Lane.placed("pg_schema")]
    rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=desc, tenant_id="core", lanes=lanes(),
                         container="none", log=lambda *a: None)
    before = desc.read_bytes()
    home = cli.served_data_home(desc)
    real_main = cli.main

    def main(argv):
        if argv[0] == at:
            raise KeyboardInterrupt
        return real_main(argv)

    monkeypatch.setattr(cli, "main", main)
    (repo / "core" / "mod.py").write_text("def run():\n    return 2\n", encoding="utf-8")
    with pytest.raises(KeyboardInterrupt):
        rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=desc, tenant_id="core", lanes=lanes(),
                             container="none", log=lambda *a: None, cursor="sha256:" + "2" * 64)
    monkeypatch.setattr(cli, "main", real_main)
    assert desc.read_bytes() == before and cli.served_data_home(desc) == home
    assert _generations(repo) == [home.name] and not (repo / ".graphy" / ".tenant.json.next").exists()
    t = cli._load_tenant(str(desc))
    fs.open_for(cli._roster(t), tenant=t, tenant_id="core", on_stale="refuse").close()   # FRESH, never STALE
    assert "STALE" not in capsys.readouterr().err


@pytest.mark.durable
def test_DURABLE_a_generation_lands_while_a_door_holds_the_served_store(tmp_path):
    """Round 1 of #98's review, B3: SQLite opens a store without FILE_SHARE_DELETE on Windows, so an
    `os.replace` over a store a running `graphy mcp` holds fails with a sharing violation — the marker
    design moved that failure to the end of the rebuild. The landing replaces only the descriptor; the
    held store is left where it is (garbage no descriptor names) and removed by the next landing once
    nothing holds it. Marked durable so the windows-latest job proves it where it matters."""
    import sqlite3
    from graphy import cli
    sub = tmp_path / ".graphy" / "substrate"
    desc = tmp_path / ".graphy" / "tenant.json"
    old = sub.with_name("substrate.gen-old")
    (old / "core_graph").mkdir(parents=True)
    for name in ("nodes.json", "edges.json", "PROVENANCE.json"):
        (old / "core_graph" / name).write_text("{}", encoding="utf-8")
    db = old / ".mesh_store_0.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()
    desc.write_text(json.dumps({"data_home": str(old)}), encoding="utf-8")
    held = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    assert held.execute("SELECT x FROM t").fetchall() == [(1,)]
    stage, staged, prev = cli.stage_generation(sub, desc)
    assert prev == old and (stage / "core_graph" / "nodes.json").is_file()
    staged.write_text(json.dumps({"data_home": str(stage)}), encoding="utf-8")
    cli.land_generation(stage, staged, desc, prev, sub)                 # never raises over a held store
    assert cli.served_data_home(desc) == stage and not staged.exists()
    assert held.execute("SELECT x FROM t").fetchall() == [(1,)]         # the held door still answers
    held.close()
    cli.discard_generations(sub, live=stage)
    assert not old.exists() and stage.is_dir()


def test_RED_rebuild_and_check_agree_on_dirt_when_the_substrate_sits_apart_from_the_descriptor(tmp_path):
    """Review round 2 of #98, B2: rebuild excluded the descriptor's directory while check excluded the data home,
    so with the substrate under `data/` and only `data/substrate/` gitignored, the untracked `substrate.gen-*`
    was dirt to one and not the other — every rebuild read CHECK RED STALE. Both ask `cartograph.cursor_exclude`."""
    repo = _git_repo(tmp_path)
    (repo / ".gitignore").write_text("data/substrate/\ntenant/\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "ignore"], cwd=repo, check=True)
    sub, desc = repo / "data" / "substrate", repo / "tenant" / "tenant.json"
    desc.parent.mkdir()
    for _ in range(2):
        receipt = rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=desc, tenant_id="core", container="none",
                                       lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core")],
                                       log=lambda *a: None)
        assert "+" not in receipt["cursor"], receipt["cursor"]          # the stage is never dirt


def test_RED_a_copied_checkout_never_follows_its_descriptor_into_the_original(tmp_path, capsys):
    """Review round 2 of #98, B3: `cp -r repo repo2` carries a descriptor whose absolute data_home is repo's;
    eating repo2 seeded its stage from repo's shards, read repo's ring for #70 ownership and moved repo's stored
    traversals away. A served home outside this substrate's own generations is never followed."""
    import shutil
    from graphy import cli
    repo = _git_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    home1 = cli.served_data_home(repo / ".graphy" / "tenant.json")
    # the original's stored traversals, planted by hand so the floor needs no duckdb (CI's floor installs none)
    (home1 / "traversals" / "g" / "doors").mkdir(parents=True)
    (home1 / "traversals" / "g" / "doors" / "blast.json").write_text("{}", encoding="utf-8")
    before = sorted(p.relative_to(home1).as_posix() for p in home1.rglob("*"))
    repo2 = tmp_path / "repo2"
    shutil.copytree(repo, repo2, symlinks=True)
    (repo2 / "core" / "mod.py").write_text("def run():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "two"], cwd=repo2, check=True)
    assert cli.main(["eat", str(repo2), "--package", "core", "--site-packages", str(repo2)]) == 0
    home2 = cli.served_data_home(repo2 / ".graphy" / "tenant.json")
    assert home2.parent == repo2 / ".graphy"
    assert sorted(p.relative_to(home1).as_posix() for p in home1.rglob("*")) == before   # the original is untouched
    capsys.readouterr()
    assert cli.main(["check", "--tenant", str(repo / ".graphy" / "tenant.json"), "--tenant-id", "core"]) == 0


def test_RED_a_substrate_from_before_generations_never_brings_back_a_pruned_lane(tmp_path, capsys):
    """Review round 3 of #98, B1: the first landing from a pre-generation layout keeps `substrate/` whole for a
    reader still opening it, and the next stage overlaid every shard in it — a lane that landing had pruned came
    back, neither ring named it, and every later eat refused as if another producer had put it there. The
    placement directory supplies only the placed lanes a rebuild names."""
    import shutil
    from graphy import cli
    repo = _git_repo(tmp_path)
    home, desc = repo / ".graphy", repo / ".graphy" / "tenant.json"
    sub = home / "substrate"
    eat = lambda: cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)])
    assert eat() == 0
    g0 = cli.served_data_home(desc)
    g0.rename(sub)                                                       # the layout every tenant had before #98
    desc.write_text(desc.read_text(encoding="utf-8").replace(str(g0), str(sub)), encoding="utf-8")
    ring = json.loads((sub / "ring.json").read_text(encoding="utf-8"))
    ring["minted"]["dep"] = dict(ring["minted"]["core"], slug="dep")    # a dependency the last ring named
    (sub / "ring.json").write_text(json.dumps(ring), encoding="utf-8")
    shutil.copytree(sub / "core_graph", sub / "dep_graph")
    assert eat() == 0
    assert "EAT DROPPED (1): dep_graph" in capsys.readouterr().out
    assert eat() == 0, capsys.readouterr().err                          # never refused over the pruned lane
    assert sorted(p.name for p in cli.served_data_home(desc).glob("*_graph")) == ["core_graph", "history_graph"]


def test_RED_a_symlinked_substrate_keeps_one_generation_back_and_no_more(tmp_path):
    """Review round 3 of #98, B2: family membership compared fully resolved paths, so with `substrate` a symlink
    no generation was ever its own — every rebuild seeded from the old substrate, carried no traversals, and left
    one more full copy of the store on disk. The substrate is spelled with its parent resolved and its leaf as named."""
    from graphy import cli
    repo = _git_repo(tmp_path)
    real = tmp_path / "real_substrate"
    real.mkdir()
    (repo / ".graphy").mkdir()
    sub, desc = repo / ".graphy" / "substrate", repo / ".graphy" / "tenant.json"
    try:                                   # a directory link, which Windows distinguishes and grants only to a privileged seat
        sub.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"this seat cannot create a symlink, so the symlinked substrate cannot be staged: {exc}")
    _place_foreign_lane(sub)
    for n in range(4):
        if n:
            (repo / "core" / f"x{n}.py").write_text(f"def f{n}():\n    return {n}\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", str(n)], cwd=repo, check=True)
        rebuild_lane.rebuild(root=repo, substrate=sub, descriptor=desc, tenant_id="core", container="none", log=lambda *a: None,
                             lanes=[rebuild_lane.Lane.mint("core", package="core", site_packages=repo, corpus=repo / "core"),
                                    rebuild_lane.Lane.placed("pg_schema")])
    gens = sorted(p.name for p in (repo / ".graphy").iterdir() if ".gen-" in p.name)
    assert len(gens) == 2 and cli.served_data_home(desc).name in gens, gens
    assert (real / "pg_schema_graph" / "emitter_receipt.json").is_file()     # the producer's placement stands


def test_RED_a_refresh_sibling_keeps_its_name_across_landings_and_is_never_a_generation(tmp_path):
    """Review round 4 of #98: `refresh.plan_for` named its sibling after the served data home, now
    `substrate.gen-<token>`, so the sibling's name moved on every landing and a forced refresh orphaned the last one
    — which `_of_family` never discarded while `_excluded` hid it from the cursor and `generation_base` called it a
    generation. One predicate (`_shared.generation_of`) answers all three, and the sibling is named by the base."""
    from graphy import cartograph, refresh
    sub, desc = tmp_path / "substrate", tmp_path / "tenant.json"

    def land():
        stage, staged, prev = cli.stage_generation(sub, desc)
        staged.write_text(json.dumps({"data_home": str(stage)}), encoding="utf-8")
        cli.land_generation(stage, staged, desc, prev, sub)
        return stage

    from graphy import cli
    plans = []
    for _ in range(3):
        home = land()
        plans.append(refresh.plan_for(type("T", (), {"data_home": home}), desc, "pkg", {"corpus": {"version": "1.0"}}, "2.0").data_home)
    assert {p.name for p in plans} == {"substrate.2.0"}
    dotted = tmp_path / "substrate.gen-x.2.0"                     # a sibling spelled after a token, as the old plan did
    assert not cli._of_family(sub, dotted) and not cartograph._excluded(dotted / "venv" / "x", sub)
    assert cartograph.generation_base(dotted) == dotted


def _blast_text(repo: Path, capsys) -> tuple[int, str]:
    """`blast` against a known id through the served descriptor — the client's 5 s poll — with the
    generation stamp removed, so two answers compare on what they say."""
    import re
    from graphy import cli
    capsys.readouterr()                                    # the step before printed; the poll's answer is its own
    rc = cli.main(["blast", "core.mod.run", "--tenant", str(repo / ".graphy" / "tenant.json"), "--tenant-id", "core",
                   "--no-store"])
    out = capsys.readouterr()
    return rc, re.sub(r"generation=\S+", "generation=<gen>", out.out)


def test_GREEN_generation_verbs_keep_the_door_answering(tmp_path, capsys):
    """graphyos #133: a house driver that runs the CLI verbs itself unlinked `tenant.json` up front, so for the
    whole rebuild (423.7 s on the first client's tenant) `blast` refused `tenant descriptor not found`. The #98
    helpers are verbs now: `generation stage` seeds the next generation beside the served one, the driver mints
    into it and runs init · converge · build against the staged descriptor, `generation land` proves the stage's
    store and renames the descriptor. `blast` against a known id answers the same at every step; the landed
    generation answers with the symbol the rebuild added; the replaced generation is kept one back."""
    from graphy import cli
    from graphy import smash as smash_lane
    repo = _git_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    desc = repo / ".graphy" / "tenant.json"
    assert cli.main(["eat", str(repo), "--package", "core", "--site-packages", str(repo)]) == 0
    capsys.readouterr()
    rc, first = _blast_text(repo, capsys)
    assert rc == 0 and "BLAST seed=core://func/core.mod.run" in first
    old_home = cli.served_data_home(desc)
    (repo / "core" / "extra.py").write_text("from core.mod import run\n\ndef more():\n    return run() + 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "two"], cwd=repo, check=True)

    answers = {}
    # a stage, and what it printed
    assert cli.main(["generation", "stage", "--substrate", str(sub), "--tenant", str(desc)]) == 0
    out = capsys.readouterr().out
    stage = Path(out.splitlines()[0].split("GENERATION STAGED: ", 1)[1])
    staged = repo / ".graphy" / ".tenant.json.next"
    assert stage.is_dir() and stage.parent == sub.parent and ".gen-" in stage.name and f"descriptor: {staged}" in out
    assert (stage / "core_graph" / "nodes.json").is_file() and not staged.exists()   # seeded; the descriptor is init's to write
    answers["stage"] = _blast_text(repo, capsys)
    # land before init: refused, the served generation untouched
    assert cli.main(["generation", "land", "--stage", str(stage), "--tenant", str(desc), "--tenant-id", "core"]) == 2
    assert "no staged descriptor" in capsys.readouterr().err and cli.served_data_home(desc) == old_home
    # the driver's own lanes into the stage, then the verbs against the staged descriptor
    assert cli.main(["smash", "--package", "core", "--site-packages", str(repo), "--out", str(stage), "--corpus", str(repo / "core")]) == 0
    answers["smash"] = _blast_text(repo, capsys)
    ring = json.loads((stage / smash_lane.RING_NAME).read_text(encoding="utf-8"))
    lanes = [f"--lane={m['slug']}_graph:static-dep" for m in ring["minted"].values()]
    assert cli.main(["init", "--tenant", str(staged), "--root", str(repo), "--data-home", str(stage),
                     "--join-keys", str(stage / "registry.json"), "--journal", str(stage / "journal"),
                     "--cursor", "sha256:" + "3" * 64, "--policy", "refuse", *lanes]) == 0
    answers["init"] = _blast_text(repo, capsys)
    # the house's own scheme index, the way every house driver writes it: from ring.json
    index = {"_meta": {"description": "house index", "standard": ring.get("standard", [])}, **ring["scheme_index"]}
    (stage / ".federation_scheme_index.json").write_text(json.dumps(index), encoding="utf-8")
    # land before build, with the staged descriptor present: still refused — no store to land
    assert cli.main(["generation", "land", "--stage", str(stage), "--tenant", str(desc), "--tenant-id", "core"]) == 2
    assert "no fresh store" in capsys.readouterr().err and cli.served_data_home(desc) == old_home
    assert cli.main(["converge", "--tenant", str(staged), "--tenant-id", "core", "--resolve"]) == 0
    answers["converge"] = _blast_text(repo, capsys)
    assert cli.main(["build", "--tenant", str(staged), "--tenant-id", "core", "--container", "none"]) == 0
    answers["build"] = _blast_text(repo, capsys)
    for step, (rc, text) in answers.items():
        assert rc == 0 and text == first, (step, text)                       # the door answered the same at every step
    assert cli.served_data_home(desc) == old_home and staged.is_file()
    # the landing: one rename; the new generation answers with the symbol the rebuild added
    assert cli.main(["generation", "land", "--stage", str(stage), "--tenant", str(desc), "--tenant-id", "core"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"GENERATION LANDED: {desc} → {stage}") and f"replaced {old_home}" in out
    assert cli.served_data_home(desc) == stage and not staged.exists() and old_home.is_dir()
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "core"]) == 0
    capsys.readouterr()
    rc, after = _blast_text(repo, capsys)
    assert rc == 0 and "core://func/core.extra.more" in after and "core://func/core.extra.more" not in first
    # landing the served generation again, a stage that is not a generation, a substrate that is one: refused by name
    assert cli.main(["generation", "land", "--stage", str(stage), "--tenant", str(desc), "--tenant-id", "core"]) == 2
    assert "no staged descriptor" in capsys.readouterr().err
    assert cli.main(["generation", "land", "--stage", str(sub), "--tenant", str(desc), "--tenant-id", "core"]) == 2
    assert "is not a generation" in capsys.readouterr().err
    assert cli.main(["generation", "stage", "--substrate", str(stage), "--tenant", str(desc)]) == 2
    assert "names a generation" in capsys.readouterr().err
    assert _generations(repo) == sorted([old_home.name, stage.name])
