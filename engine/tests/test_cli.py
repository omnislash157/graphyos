from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import graphy.cli as cli
import graphy.federated_store as fs

CURSOR = "sha256:" + "0" * 64

_WALK_STATES = (
    "WALK PATH:",
    "WALK NO-PATH:",
    "WALK BUDGET-EXHAUSTED:",
    "WALK UNANSWERABLE:",
    "WALK REFUSED:",
)




def _write_graph(dirpath: Path, nodes: dict, edges: list) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (dirpath / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def _write_registry(join_keys: Path) -> None:
    join_keys.write_text(json.dumps({
        "_meta": {"description": "synthetic cli registry"},
        "registered_joins": {"literal_joins": {}},
    }), encoding="utf-8")


def _write_scheme_index(data_home: Path) -> None:
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {},
        "widgets": {"own": ["widgets"], "out": []},
    }), encoding="utf-8")


def _descriptor(root: Path) -> Path:
    data_home = root / "data"
    descriptor = root / "tenant.json"
    descriptor.write_text(json.dumps({
        "root": str(root),
        "data_home": str(data_home),
        "adapters": [],
        "build_lanes": {"widgets_graph": [None, "static-dep"]},
        "join_keys": str(root / "registry.json"),
        "cursor": CURSOR,
        "policy": "refuse",
        "journal": str(root / "journal"),
    }), encoding="utf-8")
    return descriptor


def _single_node_fixture(root: Path) -> Path:
    _write_graph(root / "data/widgets_graph", {
        "widgets://module/widgets": {
            "kind": "node", "node_type": "module", "id": "widgets://module/widgets",
            "dotted": "widgets", "file": "widgets/__init__.py", "loc": 3,
            "docstring": "",
        },
    }, [])
    _write_registry(root / "registry.json")
    _write_scheme_index(root / "data")
    return _descriptor(root)


def _walk_fixture(root: Path) -> Path:
    _write_graph(root / "data/widgets_graph", {
        "widgets://module/widgets": {
            "kind": "node", "node_type": "module", "id": "widgets://module/widgets",
            "dotted": "widgets", "file": "widgets/__init__.py", "loc": 3, "docstring": "",
        },
        "widgets://func/widgets.gadget": {
            "kind": "node", "node_type": "func", "id": "widgets://func/widgets.gadget",
            "name": "gadget", "dotted": "widgets.gadget", "file": "widgets/gadget.py",
            "line": 1,
        },
        "widgets://func/widgets.sprocket": {
            "kind": "node", "node_type": "func", "id": "widgets://func/widgets.sprocket",
            "name": "sprocket", "dotted": "widgets.sprocket", "file": "widgets/sprocket.py",
            "line": 1,
        },
        "widgets://func/widgets.island": {
            "kind": "node", "node_type": "func", "id": "widgets://func/widgets.island",
            "name": "island", "dotted": "widgets.island", "file": "widgets/island.py",
            "line": 1,
        },
    }, [
        {"kind": "edge", "edge_type": "imports", "src": "widgets://module/widgets",
         "dst": "widgets://func/widgets.gadget", "name": "gadget", "alias": "gadget",
         "line": 1},
        {"kind": "edge", "edge_type": "imports", "src": "widgets://func/widgets.gadget",
         "dst": "widgets://func/widgets.sprocket", "name": "sprocket", "alias": "sprocket",
         "line": 2},
    ])
    _write_registry(root / "registry.json")
    _write_scheme_index(root / "data")
    return _descriptor(root)


def _mutate_nodes(nodes_path: Path) -> None:
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    nodes["widgets://func/widgets.mutated"] = {
        "kind": "node", "node_type": "func", "id": "widgets://func/widgets.mutated",
        "name": "mutated", "dotted": "widgets.mutated", "file": "widgets/mutated.py",
        "line": 1,
    }
    nodes_path.write_text(json.dumps(nodes), encoding="utf-8")


def _digest_tree(root: Path) -> str:
    hasher = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            hasher.update(str(p.relative_to(root)).encode("utf-8"))
            hasher.update(p.read_bytes())
    return hasher.hexdigest()


def _assert_walk_state(combined: str, want: str) -> None:
    for other in _WALK_STATES:
        if want.startswith(other):
            continue
        assert other not in combined, (
            f"state collapse: expected {want!r} but sibling state {other} is present")
    assert want in combined




def test_bare_graphy_prints_usage_exit_2(capsys):
    rc = cli.main([])
    out = capsys.readouterr()
    assert rc == 2
    assert "usage" in (out.out + out.err).lower()


@pytest.mark.parametrize("verb,prefix", [
    ("init", "INIT REFUSED:"),
    ("build", "BUILD REFUSED:"),
    ("walk", "WALK REFUSED:"),
    ("check", "CHECK REFUSED:"),
])
def test_verb_refuses_absent_tenant_with_prefix_and_exit_2(verb, prefix, capsys):
    rc = cli.main([verb])
    out = capsys.readouterr()
    assert rc == 2
    assert prefix in (out.out + out.err)


def test_build_refuses_malformed_descriptor_carrying_tenant_error(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "root": "relative/root", "data_home": str(tmp_path / "data"),
        "adapters": [], "build_lanes": {},
        "join_keys": str(tmp_path / "registry.json"),
        "cursor": "c", "policy": "refuse", "journal": str(tmp_path / "journal"),
    }), encoding="utf-8")
    rc = cli.main(["build", "--tenant", str(bad), "--tenant-id", "cli-build"])
    out = capsys.readouterr()
    assert rc == 2
    assert "BUILD REFUSED:" in out.err
    assert "root must be absolute" in out.err




def test_init_lstat_first_refusal_leaves_target_byte_untouched(tmp_path, capsys):
    target = tmp_path / "tenant.json"
    original = b'{"sentinel": true}'
    target.write_bytes(original)
    rc = cli.main(["init", "--tenant", str(target), "--root", str(tmp_path),
                   "--data-home", str(tmp_path / "data"),
                   "--join-keys", str(tmp_path / "registry.json"),
                   "--journal", str(tmp_path / "journal"), "--cursor", "c",
                   "--policy", "refuse"])
    out = capsys.readouterr()
    assert rc == 2
    assert "INIT REFUSED:" in out.err
    assert target.read_bytes() == original


def test_init_write_only_what_validates_creates_nothing(tmp_path, capsys):
    target = tmp_path / "never.json"
    rc = cli.main(["init", "--tenant", str(target), "--root", "relative/root",
                   "--data-home", str(tmp_path / "data"),
                   "--join-keys", str(tmp_path / "registry.json"),
                   "--journal", str(tmp_path / "journal"), "--cursor", "c",
                   "--policy", "refuse"])
    out = capsys.readouterr()
    assert rc == 2
    assert "INIT REFUSED:" in out.err
    assert "root must be absolute" in out.err
    assert not target.exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "registry.json").exists()
    assert not (tmp_path / "journal").exists()


def test_init_build_check_lifecycle_green(tmp_path, capsys):
    descriptor = tmp_path / "tenant.json"
    data_home = tmp_path / "data"
    rc = cli.main(["init", "--tenant", str(descriptor), "--root", str(tmp_path),
                   "--data-home", str(data_home),
                   "--join-keys", str(tmp_path / "registry.json"),
                   "--journal", str(tmp_path / "journal"), "--cursor", CURSOR,
                   "--policy", "refuse", "--lane", "widgets_graph:static-dep"])
    out = capsys.readouterr()
    assert rc == 0
    assert "INIT OK:" in out.out
    assert descriptor.is_file()
    assert (tmp_path / "registry.json").is_file()
    assert data_home.is_dir()

    _write_graph(data_home / "widgets_graph", {
        "widgets://module/widgets": {
            "kind": "node", "node_type": "module", "id": "widgets://module/widgets",
            "dotted": "widgets", "file": "widgets/__init__.py", "loc": 3,
            "docstring": "",
        },
    }, [])
    _write_scheme_index(data_home)
    capsys.readouterr()
    rc = cli.main(["build", "--tenant", str(descriptor), "--tenant-id", "cli-init"])
    out = capsys.readouterr()
    assert rc == 0
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-init"])
    out = capsys.readouterr()
    assert rc == 0
    assert "CHECK OK:" in out.out




def test_check_red_stale_generation(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    _mutate_nodes(tmp_path / "data/widgets_graph/nodes.json")
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK RED:" in out.err
    assert "STALE" in out.err


def test_check_could_not_tell_missing_override_registry(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    (tmp_path / "registry.json").unlink()
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK COULD-NOT-TELL:" in out.err
    assert "registry" in out.err


def test_check_could_not_tell_absent_roster_dir(tmp_path, capsys, monkeypatch):
    # the directory is gone on purpose: the transient-ENOENT retry has nothing to wait for
    monkeypatch.setattr("graphy.cartograph.time.sleep", lambda _seconds: None)
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    graph_dir = tmp_path / "data/widgets_graph"
    for p in sorted(graph_dir.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
    graph_dir.rmdir()
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK COULD-NOT-TELL:" in out.err


def test_check_could_not_tell_missing_nodes_json(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    (tmp_path / "data/widgets_graph/nodes.json").unlink()
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK COULD-NOT-TELL:" in out.err


def test_check_edges_shard_missing_is_could_not_tell(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    (tmp_path / "data/widgets_graph/edges.json").unlink()
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "Traceback" not in combined
    lines = out.err.rstrip("\n").splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("CHECK COULD-NOT-TELL:")
    assert "edges" in lines[0]


def test_check_edges_shard_malformed_is_could_not_tell(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    (tmp_path / "data/widgets_graph/edges.json").write_text("not json", encoding="utf-8")
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "Traceback" not in combined
    lines = out.err.rstrip("\n").splitlines()
    findings = [line for line in lines if line.startswith("CHECK ")]
    assert len(findings) >= 1
    store_line = next(line for line in findings if "store lane" in line)
    assert store_line.startswith("CHECK COULD-NOT-TELL:")
    assert "shard" in store_line


def test_check_shard_unreadable_is_could_not_tell(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    nodes = tmp_path / "data/widgets_graph/nodes.json"
    nodes.chmod(0)
    try:
        rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    finally:
        nodes.chmod(0o644)
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "Traceback" not in combined
    lines = out.err.rstrip("\n").splitlines()
    findings = [line for line in lines if line.startswith("CHECK ")]
    assert len(findings) >= 1
    store_line = next(line for line in findings if "store lane" in line)
    assert store_line.startswith("CHECK COULD-NOT-TELL:")
    assert "nodes" in store_line


def test_check_red_missing_input_digest_meta_row(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    tenant = cli._load_tenant(str(descriptor))
    store_path = fs.store_path_for(["widgets"], tenant=tenant)
    db = sqlite3.connect(store_path)
    db.execute("DELETE FROM meta WHERE k='input_digest'")
    db.commit()
    db.close()
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK RED:" in out.err
    assert "input_digest" in out.err


def test_check_could_not_tell_unreadable_scheme_index(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    index = tmp_path / "data/.federation_scheme_index.json"
    index.write_text("{not json", encoding="utf-8")
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK COULD-NOT-TELL:" in out.err
    assert "scheme index" in out.err




def test_check_names_the_registry_as_the_offending_member(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    (tmp_path / "registry.json").write_text("[]", encoding="utf-8")
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "Traceback" not in combined
    lines = out.err.rstrip("\n").splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("CHECK COULD-NOT-TELL:")
    assert "registry" in lines[0]
    assert "scheme index" not in lines[0]
    assert "registry, scheme index, or shard" not in lines[0]


def test_check_names_the_scheme_index_as_the_offending_member(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    (tmp_path / "data/.federation_scheme_index.json").write_text("[]", encoding="utf-8")
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "Traceback" not in combined
    lines = out.err.rstrip("\n").splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("CHECK COULD-NOT-TELL:")
    assert "scheme index" in lines[0]
    assert "registry" not in lines[0]
    assert "registry, scheme index, or shard" not in lines[0]


def test_check_names_the_offending_shard_by_graph_name(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    nodes = tmp_path / "data/widgets_graph/nodes.json"
    nodes.chmod(0)
    try:
        rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    finally:
        nodes.chmod(0o644)
    out = capsys.readouterr()
    combined = out.out + out.err
    assert rc == 1
    assert "Traceback" not in combined
    findings = [line for line in out.err.splitlines() if line.startswith("CHECK ")]
    store_line = next(line for line in findings if "store lane" in line)
    assert store_line.startswith("CHECK COULD-NOT-TELL:")
    assert "shard" in store_line
    assert "widgets_graph" in store_line


def test_check_wrong_shape_findings_are_not_interchangeable(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()

    (tmp_path / "registry.json").write_text("[]", encoding="utf-8")
    assert cli.main(["check", "--tenant", str(descriptor),
                     "--tenant-id", "cli-check"]) == 1
    reg_err = capsys.readouterr().err
    _write_registry(tmp_path / "registry.json")

    (tmp_path / "data/.federation_scheme_index.json").write_text("[]", encoding="utf-8")
    assert cli.main(["check", "--tenant", str(descriptor),
                     "--tenant-id", "cli-check"]) == 1
    idx_err = capsys.readouterr().err
    _write_scheme_index(tmp_path / "data")

    nodes = tmp_path / "data/widgets_graph/nodes.json"
    nodes.chmod(0)
    try:
        assert cli.main(["check", "--tenant", str(descriptor),
                         "--tenant-id", "cli-check"]) == 1
    finally:
        nodes.chmod(0o644)
    shard_err = capsys.readouterr().err

    reg_store = next(line for line in reg_err.splitlines() if "store lane" in line)
    idx_store = next(line for line in idx_err.splitlines() if "store lane" in line)
    shard_store = next(line for line in shard_err.splitlines() if "store lane" in line)
    assert reg_store != idx_store
    assert reg_store != shard_store
    assert idx_store != shard_store


def test_check_preserves_repeated_whitespace_in_dynamic_values(tmp_path, capsys):
    root = tmp_path / "root  with  runs"
    descriptor = _single_node_fixture(root)
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "cli-check"])
    out = capsys.readouterr()
    assert rc == 1
    lines = out.err.rstrip("\n").splitlines()
    assert len(lines) == 1
    assert str(root) in out.err


def test_check_is_read_only_on_healthy_and_broken_tenants(tmp_path, capsys):
    descriptor = _single_node_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    before = _digest_tree(tmp_path)
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "ro-test"])
    out = capsys.readouterr()
    assert rc == 0
    assert "CHECK OK:" in out.out
    assert before == _digest_tree(tmp_path)
    _mutate_nodes(tmp_path / "data/widgets_graph/nodes.json")
    before = _digest_tree(tmp_path)
    rc = cli.main(["check", "--tenant", str(descriptor), "--tenant-id", "ro-test"])
    out = capsys.readouterr()
    assert rc == 1
    assert "CHECK RED:" in out.err
    assert before == _digest_tree(tmp_path)




def test_walk_refuses_stale_store_and_opens_with_warning_on_opt_in(tmp_path, capsys):
    descriptor = _walk_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    _mutate_nodes(tmp_path / "data/widgets_graph/nodes.json")
    rc = cli.main(["walk", "--tenant", str(descriptor), "--tenant-id", "cli-walk",
                   "--seed", "widgets://module/widgets",
                   "--target", "widgets://func/widgets.sprocket"])
    out = capsys.readouterr()
    assert rc == 2
    assert "WALK REFUSED:" in out.err
    rc = cli.main(["walk", "--tenant", str(descriptor), "--tenant-id", "cli-walk",
                   "--seed", "widgets://module/widgets",
                   "--target", "widgets://func/widgets.sprocket",
                   "--on-stale", "warn"])
    out = capsys.readouterr()
    assert rc == 0
    assert "WALK PATH:" in out.out
    assert "STALE" in out.err
    assert "serving generation" in out.err


def test_walk_on_stale_heal_raises_value_error(tmp_path):
    descriptor = _walk_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    with pytest.raises(ValueError):
        cli.main(["walk", "--tenant", str(descriptor), "--tenant-id", "cli-walk",
                  "--seed", "widgets://module/widgets",
                  "--target", "widgets://func/widgets.sprocket",
                  "--on-stale", "heal"])




@pytest.mark.parametrize("seed,target,extra,want_rc,want", [
    ("widgets://module/widgets", "widgets://func/widgets.sprocket", [],
     0, "WALK PATH:"),
    ("widgets://module/widgets", "widgets://func/widgets.island", [],
     1, "WALK NO-PATH: search exhausted"),
    ("widgets://module/widgets", "widgets://func/widgets.sprocket",
     ["--max-depth", "0"], 1, "WALK BUDGET-EXHAUSTED: max_depth"),
    ("widgets://module/widgets", "widgets://func/widgets.sprocket",
     ["--max-nodes", "1"], 1, "WALK BUDGET-EXHAUSTED: max_nodes"),
    ("widgets://module/nope", "widgets://func/widgets.sprocket", [],
     1, "WALK UNANSWERABLE: seed"),
    ("widgets://module/widgets", "widgets://func/nope", [],
     1, "WALK UNANSWERABLE: target"),
])
def test_walk_partition_state_bound_to_exit_code(
        tmp_path, capsys, seed, target, extra, want_rc, want):
    descriptor = _walk_fixture(tmp_path)
    assert cli.main(["build", "--tenant", str(descriptor),
                     "--tenant-id", "cli-build"]) == 0
    capsys.readouterr()
    rc = cli.main(["walk", "--tenant", str(descriptor), "--tenant-id", "cli-walk",
                   "--seed", seed, "--target", target] + extra)
    out = capsys.readouterr()
    assert rc == want_rc
    _assert_walk_state(out.out + out.err, want)




def test_python_m_graphy_wire_subprocess():
    graphy_os = Path(__file__).parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "graphy", "--help"],
        cwd=str(graphy_os), capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower()


def test_GREEN_cli_loads_no_verb_module_and_no_http_client():
    """Every verb's module is imported inside its handler: a fresh interpreter that imports
    graphy.cli holds the import surface (ir · parity · tenant) and nothing else of graphy, and
    none of urllib.request · http.client · email.parser — the index's fetch pays for those only
    when a remote base is read. Checked in a subprocess so pytest's own imports are not in the way."""
    probe = ("import sys, json, graphy.cli\n"
             "print(json.dumps(sorted(m for m in sys.modules if m.startswith('graphy')"
             " or m in ('urllib.request', 'urllib.error', 'http.client', 'email.parser'))))")
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True).stdout
    loaded = json.loads(out)
    assert loaded == ["graphy", "graphy.cli", "graphy.ir", "graphy.parity", "graphy.tenant"], loaded


def test_GREEN_parser_producer_names_pin_the_minting_registry():
    """The parser lists the producers by name so --help never loads the minting lane; the
    tuple is the registry's keys, or this fails by name when a producer is added."""
    from graphy import smash
    assert cli._PRODUCER_NAMES == tuple(sorted(smash.PRODUCERS))


def test_RED_eat_settles_the_package_before_it_provisions_anything(tmp_path, monkeypatch, capsys):
    """A repo with two importable packages and no --package is refused by name before a venv is
    made or pip runs: the choice costs nothing, the provisioning a minute (graphyos #34)."""
    import graphy.provision as provision
    repo = tmp_path / "repo"
    for name in ("alpha", "beta"):
        (repo / name).mkdir(parents=True)
        (repo / name / "__init__.py").write_text("x = 1\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "twin"\nversion = "0"\n')
    called = []
    monkeypatch.setattr(provision, "provision", lambda *a, **k: (called.append(a), (_ for _ in ()).throw(RuntimeError("never")))[1])
    assert cli.main(["eat", str(repo)]) == 2
    err = capsys.readouterr().err
    assert "2 importable package(s)" in err and "alpha, beta" in err and "--package" in err
    assert called == [], "the repo was provisioned before the package was settled"
    assert not (repo / ".graphy").exists()


def test_GREEN_eat_no_provision_runs_nothing_of_the_repo_and_mints_an_empty_ring(tmp_path, monkeypatch, capsys):
    """`graphy eat --no-provision`: the provisioner is never called (no venv, no pip, no npm), the
    line says the ring is empty, the package is minted from its source with every import
    unresolved by name, and the eat lands green (graphyos #35)."""
    import subprocess
    import graphy.provision as provision
    repo = tmp_path / "repo"
    (repo / "solo").mkdir(parents=True)
    (repo / "solo" / "__init__.py").write_text("import os\nimport requests\nfrom . import b\n")
    (repo / "solo" / "b.py").write_text("def f():\n    return 1\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "solo"\nversion = "0"\n')
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo, check=True)
    called = []
    monkeypatch.setattr(provision, "provision", lambda *a, **k: (called.append(a), (_ for _ in ()).throw(RuntimeError("never")))[1])
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    out = capsys.readouterr().out
    assert "PROVISION SKIPPED: --no-provision; the ring is empty, every import is unresolved" in out
    assert "EAT OK" in out and "unresolved requests" in out
    assert called == [], "the repo was provisioned under --no-provision"
    assert not (repo / ".graphy" / "venv").exists()
    assert not list((repo / ".graphy" / "no-ring").iterdir()), "the empty ring holds something"
    ring = json.loads((repo / ".graphy" / "substrate" / "ring.json").read_text())
    assert ring["root"] == "solo" and list(ring["minted"]) == ["solo"]
    # RED: the two ways of naming the ring contradict, and the refusal comes before anything lands
    (repo / ".graphy").rename(repo / ".was")
    assert cli.main(["eat", str(repo), "--no-provision", "--site-packages", str(tmp_path)]) == 2
    assert "contradict" in capsys.readouterr().err and not (repo / ".graphy").exists()


def test_RED_check_names_a_working_tree_that_moved_past_the_store(tmp_path, capsys):
    """graphyos #39: after an eat, an uncommitted edit makes `graphy check` read STALE naming the
    file count, exit 1; eating again over the dirty tree reads CHECK OK; a commit past it reads
    STALE naming the HEAD."""
    import subprocess
    repo = tmp_path / "repo"
    (repo / "solo").mkdir(parents=True)
    (repo / "solo" / "__init__.py").write_text("from . import b\n")
    (repo / "solo" / "b.py").write_text("def f():\n    return 1\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "solo"\nversion = "0"\n')
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "i"], cwd=repo, check=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    desc = str(repo / ".graphy" / "tenant.json")
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    out = capsys.readouterr().out
    assert "CHECK OK" in out and "working tree is dirty" not in out
    assert json.loads(Path(desc).read_text())["cursor"] == f"git:{head}", "a clean tree's cursor is the HEAD alone"
    (repo / "solo" / "b.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
    assert cli.main(["check", "--tenant", desc, "--tenant-id", "solo"]) == 1
    err = capsys.readouterr().err
    assert "CHECK RED: cursor lane: STALE — the working tree moved past the store: 1 file(s) modified or untracked since the build" in err
    assert "graphy eat ." in err
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    out = capsys.readouterr().out
    assert "EAT: the working tree is dirty (1 file(s) past HEAD) — the cursor carries it" in out and "CHECK OK" in out
    assert json.loads(Path(desc).read_text())["cursor"].startswith(f"git:{head}+")
    assert cli.main(["check", "--tenant", desc, "--tenant-id", "solo"]) == 0
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "j"], cwd=repo, check=True)
    assert cli.main(["check", "--tenant", desc, "--tenant-id", "solo"]) == 1
    assert f"STALE — HEAD moved past the store: built at {head}, HEAD is " in capsys.readouterr().err


# graphyos #43 — the first five minutes: the walk example never targets its own seed, and a
# refusal prints alone, before any banner.

def test_RED_walk_example_targets_the_ring_else_the_first_submodule_never_the_seed(tmp_path):
    from graphy.cli import _walk_target
    sub = tmp_path / "sub"
    (sub / "pkg_graph").mkdir(parents=True)
    (sub / "pkg_graph" / "nodes.json").write_text(json.dumps({
        "pkg://module/pkg": {}, "pkg://module/pkg.zeta": {}, "pkg://module/pkg.alpha": {},
        "pkg://func/pkg.alpha.f": {}}))
    assert _walk_target(sub, "pkg", ["click"]) == "click://module/click"          # the ring first
    assert _walk_target(sub, "pkg", []) == "pkg://module/pkg.alpha"               # else the first submodule
    (sub / "pkg_graph" / "nodes.json").write_text(json.dumps({"pkg://module/pkg": {}}))
    assert _walk_target(sub, "pkg", []) == "pkg://module/pkg"                     # one module, no ring: the seed stands
    assert _walk_target(tmp_path / "nowhere", "pkg", []) == "pkg://module/pkg"


def test_RED_eat_refusal_prints_alone_before_any_banner(tmp_path):
    """A directory with no importable package: the refusal is the whole output, on stderr, and
    no `EAT: repo` banner is printed — the banner used to come first on stdout and the two
    streams interleaved in a terminal (graphyos #43)."""
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = subprocess.run([sys.executable, "-m", "graphy", "eat", str(empty)],
                          cwd=str(Path(__file__).parent.parent), capture_output=True, text=True)
    assert proc.returncode == 2
    assert proc.stderr.startswith("EAT REFUSED: no importable package(s) under")
    assert "EAT: repo" not in proc.stdout + proc.stderr


# --- graphyos #49: a static manifest addresses any eaten repo through `graphy mcp --repo` ------------

def _eaten_repo(tmp_path: Path, root: str = "click") -> Path:
    repo = tmp_path / "repo"
    home = repo / ".graphy"
    sub = home / "substrate"
    sub.mkdir(parents=True)
    (home / "tenant.json").write_text(json.dumps({"data_home": str(sub)}), encoding="utf-8")
    (sub / "ring.json").write_text(json.dumps({"root": root, "minted": {root: {}}}), encoding="utf-8")
    return repo


def test_repo_tenant_reads_the_descriptor_eat_wrote_and_the_root_the_ring_names(tmp_path):
    repo = _eaten_repo(tmp_path)
    desc, package = cli.repo_tenant(repo)
    assert desc == repo / ".graphy" / "tenant.json" and package == "click"
    assert cli.mcp_args(desc, package) == ["mcp", "--repo", str(repo)]
    # a descriptor anywhere else keeps the explicit pair — the plugin form only fits eat's layout
    assert cli.mcp_args(tmp_path / "t.json", "x") == ["mcp", "--tenant", str(tmp_path / "t.json"), "--tenant-id", "x"]


@pytest.mark.parametrize("breakage", ["no-repo", "no-ring", "no-root", "empty-root", "no-data-home"])
def test_RED_repo_tenant_refuses_by_name_never_guesses(tmp_path, breakage):
    repo = _eaten_repo(tmp_path)
    sub = repo / ".graphy" / "substrate"
    if breakage == "no-repo":
        repo = tmp_path / "never-eaten"
    elif breakage == "no-ring":
        (sub / "ring.json").unlink()
    elif breakage == "no-root":
        (sub / "ring.json").write_text(json.dumps({"minted": {}}), encoding="utf-8")
    elif breakage == "empty-root":
        (sub / "ring.json").write_text(json.dumps({"root": "  "}), encoding="utf-8")
    elif breakage == "no-data-home":
        (repo / ".graphy" / "tenant.json").write_text("{}", encoding="utf-8")
    with pytest.raises(cli.TenantError) as exc:
        cli.repo_tenant(repo)
    assert "graphy eat" in str(exc.value) or "names no" in str(exc.value) or "empty root" in str(exc.value)


def test_mcp_repo_flag_refuses_an_uneaten_repo_and_a_mixed_form(tmp_path, capsys):
    assert cli.main(["mcp", "--repo", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("MCP REFUSED: no tenant at") and "graphy eat" in err
    repo = _eaten_repo(tmp_path)
    assert cli.main(["mcp", "--repo", str(repo), "--tenant-id", "click"]) == 2
    assert "does not combine" in capsys.readouterr().err
    assert cli.main(["mcp"]) == 2
    assert "--repo <eaten repo>" in capsys.readouterr().err


def test_plugin_manifest_and_registry_entry_run_the_repo_door_at_the_package_version():
    """The two static manifests at the root run `graphy mcp --repo` and carry the package's
    version — the release gate refuses drift; this is the floor under it."""
    import graphy
    root = Path(__file__).parents[2]
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    server = json.loads((root / "server.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "graphy" and plugin["version"] == graphy.__version__
    assert plugin["mcpServers"]["graphy"]["command"] == "graphy"
    assert plugin["mcpServers"]["graphy"]["args"] == ["mcp", "--repo", "${CLAUDE_PROJECT_DIR}"]
    assert server["name"] == "io.github.omnislash157/graphyos" and server["version"] == graphy.__version__
    (pkg,) = server["packages"]
    assert pkg["registryType"] == "pypi" and pkg["identifier"] == "graphyos" and pkg["version"] == graphy.__version__
    assert pkg["transport"] == {"type": "stdio"}
    assert [a.get("value") or a.get("name") for a in pkg["packageArguments"]] == ["mcp", "--repo"]
    # the registry's ownership proof for a PyPI package lives in the README the wheel ships — the one
    # pyproject names, never the repo's own — as `mcp-name: <server name>` followed by a boundary
    import re
    pyproject = (root / "engine" / "pyproject.toml").read_text(encoding="utf-8")
    readme_name = re.search(r'^readme = "(.+)"$', pyproject, re.M).group(1)
    readme = (root / "engine" / readme_name).read_text(encoding="utf-8")
    assert re.search(r"mcp-name: " + re.escape(server["name"]) + r"(?=\s|-->|<)", readme), readme_name
    assert len(server["description"]) <= 100   # the registry's cap, enforced server-side only
    # the marketplace (graphyos #56): one entry, the checkout itself as its github source, the plugin's version
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    (entry,) = market["plugins"]
    assert market["name"] == "graphyos" and market["owner"]["name"]
    assert entry["name"] == "graphy" and entry["source"] == {"source": "github", "repo": "omnislash157/graphyos"}
    assert entry["version"] == market["metadata"]["version"] == graphy.__version__


# graphyos #66 — eat mints the repo's own record beside the code shard; shell install re-mints it;
# check names the archive the cursor cannot see.

_SESSION_HEAD = ("# CONVERSATION FULL SESSION — 1 exchanges, verbatim and in order\n\nsession: {sid}\n"
                 "exchanges 1–1 of 1 · ~40 tokens\nsemantic_sha256: {sha}\ncaptured_at: {at}\nresolved_by: SessionEnd:clear\n\n")


def _session_file(sessions: Path, n: int, body: str) -> Path:
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions.parent / ".gitignore").write_text("*\n")     # what `shell install` writes: the archive never reaches the repo
    sid = f"abcdef{n:02d}-0000-0000-0000-{n:012d}"
    p = sessions / f"{n:05d}__20260909T10{n:02d}00Z__{sid[:8]}.md"
    p.write_text(_SESSION_HEAD.format(sid=sid, sha="0" * 64, at=f"2026-09-09T10:{n:02d}:00+00:00") + body, encoding="utf-8")
    return p


def _solo_git_repo(tmp_path: Path) -> Path:
    import subprocess
    repo = tmp_path / "repo"
    (repo / "solo").mkdir(parents=True)
    (repo / "solo" / "__init__.py").write_text("from . import b\n")
    (repo / "solo" / "b.py").write_text("def f():\n    return 1\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "solo"\nversion = "0"\n')
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "i"], cwd=repo, check=True)
    return repo


def test_GREEN_eat_mints_the_history_shard_beside_the_code_and_the_walk_reaches_the_exchange(tmp_path, capsys):
    """`graphy eat` over a git checkout with a sessions archive: HISTORY OK, the lane declared, every
    exchange a node welded to the symbol it names, so `explain` lists the exchange and `history --symbol`
    walks into its session — no by-hand mint (graphyos #66)."""
    repo = _solo_git_repo(tmp_path)
    _session_file(repo / ".claude" / "recovery" / "sessions", 1, "--- [1] USER\n\nfix solo.b.f please\n\n--- [1] ASSISTANT\n\nchanged f in solo/b.py\n")
    desc = str(repo / ".graphy" / "tenant.json")
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    out = capsys.readouterr().out
    assert "HISTORY OK: 1 commit(s) · 1 session(s)" in out and "2 exchange(s) · 2 mention(s)" in out and "CHECK OK" in out
    assert "history_graph" in json.loads(Path(desc).read_text())["build_lanes"]
    nodes = json.loads((repo / ".graphy" / "substrate" / "history_graph" / "nodes.json").read_text())
    assert "history://exchange/abcdef01-0000-0000-0000-000000000001/1/user" in nodes
    index = json.loads((repo / ".graphy" / "substrate" / ".federation_scheme_index.json").read_text())
    assert "history" in index and "solo" in index["history"]["out"], "the scheme index never learned the history shard"
    assert cli.main(["explain", "solo.b.f", "--tenant", desc, "--tenant-id", "solo"]) == 0
    assert "mentions       history://exchange/" in capsys.readouterr().out
    assert cli.main(["history", "--symbol", "solo.b.f", "--tenant", desc, "--tenant-id", "solo"]) == 0
    assert "TIMELINE: 1 session(s)" in capsys.readouterr().out


def test_RED_check_names_a_grown_archive_the_cursor_cannot_see_and_install_re_mints(tmp_path, capsys):
    """A session captured after the eat leaves HEAD and the working tree alone (the archive ignores
    itself), so only the history lane can see it: CHECK RED naming it, exit 1; `shell install` re-mints
    the shard and recompiles the store, and the timeline reaches the new session (graphyos #66)."""
    from graphy.shell import install as shell_install
    repo = _solo_git_repo(tmp_path)
    sessions = repo / ".claude" / "recovery" / "sessions"
    _session_file(sessions, 1, "--- [1] USER\n\nfix solo.b.f please\n\n--- [1] ASSISTANT\n\nok\n")
    desc = str(repo / ".graphy" / "tenant.json")
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    capsys.readouterr()
    _session_file(sessions, 2, "--- [1] USER\n\nagain solo.b.f\n\n--- [1] ASSISTANT\n\nok\n")
    assert cli.main(["check", "--tenant", desc, "--tenant-id", "solo"]) == 1
    err = capsys.readouterr().err
    assert "CHECK RED: history lane: STALE — the inputs digest" in err and "cursor lane" not in err
    info = shell_install.install(repo, python=sys.executable, log=lambda *_: None)
    assert info["history"] == "re-minted, store recompiled"
    capsys.readouterr()
    assert cli.main(["history", "--symbol", "solo.b.f", "--tenant", desc, "--tenant-id", "solo"]) == 0
    assert "TIMELINE: 2 session(s)" in capsys.readouterr().out


def test_GREEN_eat_skips_the_history_shard_by_name_on_a_directory_that_is_not_a_checkout(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "solo").mkdir(parents=True)
    (repo / "solo" / "__init__.py").write_text("def f():\n    return 1\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "solo"\nversion = "0"\n')
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    out = capsys.readouterr().out
    assert "HISTORY SKIPPED: " in out and "not a git checkout" in out and "EAT OK" in out
    lanes = json.loads((repo / ".graphy" / "tenant.json").read_text())["build_lanes"]
    assert list(lanes) == ["solo_graph"]
    assert not (repo / ".graphy" / "substrate" / "history_graph").exists()


def test_GREEN_the_usage_line_lists_every_verb_the_parser_registers():
    """`graphy --help`'s positional line is the verb list a stranger reads, and it was typed by hand
    beside the subparsers it was supposed to describe. It drifted: `history` and `refresh` parsed,
    ran, and had their own `--help`, but the usage line did not name them — so the first tenant,
    probing for the history lane, read the line and concluded the verb was not there. The metavar is
    now derived from `sub.choices`, and this proves the two can never disagree again."""
    import argparse
    parser = cli._build_parser()
    (sub,) = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert sub.metavar == "{" + ",".join(sub.choices) + "}"
    listed = set(sub.metavar.strip("{}").split(","))
    assert listed == set(sub.choices), listed ^ set(sub.choices)
    assert {"history", "refresh", "harness"} <= listed          # the three the hand-kept line missed
    assert sub.metavar in parser.format_help().replace("\n", "").replace(" ", "")


def _two_package_repo(tmp_path):
    """A git checkout with two importable packages and no dependencies — the monorepo shape."""
    repo = tmp_path / "mono"
    repo.mkdir(parents=True)
    for name in ("pkg_a", "pkg_b"):
        (repo / name).mkdir()
        (repo / name / "mod.py").write_text(f'def f_{name}():\n    return "{name}"\n', encoding="utf-8")
        (repo / name / "__init__.py").write_text(f"from {name}.mod import f_{name}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "two"],
                   cwd=repo, check=True)
    return repo


def _lanes(repo):
    return sorted(d.name for d in (repo / ".graphy" / "substrate").glob("*_graph"))


def test_RED_eat_refuses_to_delete_a_lane_it_did_not_mint_and_force_is_the_deliberate_path(tmp_path, capsys):
    """`eat` pruned every lane the import ring did not name, at rc 0, with no count and no name.
    On the first client's tenant that was 22 of 32 lanes — the live Postgres schema, the customer
    book, the item lexicon, the session memory — and `check` recommended the command that did it.

    The engine cannot tell "a dependency was dropped, prune it" from "something else minted this,
    keep it", so the DELETION is what refuses and `--force` is the deliberate path (graphyos #70)."""
    repo = _two_package_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "pkg_a", "--site-packages", str(repo)]) == 0
    assert _lanes(repo) == ["history_graph", "pkg_a_graph"]
    capsys.readouterr()

    assert cli.main(["eat", str(repo), "--package", "pkg_b", "--site-packages", str(repo)]) == 2
    err = capsys.readouterr().err
    assert "EAT REFUSED" in err and "pkg_a_graph" in err and "--force" in err
    assert "NOTHING WAS DELETED" in err
    # both lanes stand: the refusal is not a rollback, it is a deletion that did not happen
    assert _lanes(repo) == ["history_graph", "pkg_a_graph", "pkg_b_graph"]

    assert cli.main(["eat", str(repo), "--package", "pkg_b", "--site-packages", str(repo), "--force"]) == 0
    out = capsys.readouterr().out
    assert "EAT PRUNED (1, --force): pkg_a_graph" in out      # and it names what it removed
    assert _lanes(repo) == ["history_graph", "pkg_b_graph"]


def test_GREEN_a_re_eat_of_the_same_package_prunes_nothing_and_never_refuses(tmp_path, capsys):
    """The refusal must not fire on the ordinary path: eating the same package twice names the same
    lanes, so there is nothing outside the ring and no --force is ever needed."""
    repo = _two_package_repo(tmp_path)
    assert cli.main(["eat", str(repo), "--package", "pkg_a", "--site-packages", str(repo)]) == 0
    capsys.readouterr()
    assert cli.main(["eat", str(repo), "--package", "pkg_a", "--site-packages", str(repo)]) == 0
    out, err = capsys.readouterr()
    assert "EAT REFUSED" not in err and "EAT PRUNED" not in out
    assert _lanes(repo) == ["history_graph", "pkg_a_graph"]


def test_GREEN_check_recommends_the_lane_safe_verb_before_the_one_that_prunes(tmp_path):
    """`check`'s stale-history remediation led with `graphy eat .`, which on a multi-lane tenant is
    the command that deletes the other lanes — the audit recommending the data loss (graphyos #70).
    The safe verb goes first and the caveat on the other is explicit."""
    src = Path(cli.__file__).read_text(encoding="utf-8")
    start = src.index("re-mint it: `graphy shell install")
    remediation = src[start:src.index('"))', start)]
    assert remediation.index("shell install") < remediation.index("graphy eat ."), remediation
    assert "touches no other lane" in remediation
    assert "lanes ARE its ring" in remediation        # the caveat, not a bare alternative


def _bridge_tenant(tmp_path, *, resolved: bool, break_it: bool = False):
    """A roster of two lanes: one that carries nodes, and one that carries ONLY edges pointing at
    them — a pure bridge, which is a real shape and was entirely unguarded (graphyos #73)."""
    from graphy.tenant import Tenant
    data = tmp_path / "data"
    (data / "code_graph").mkdir(parents=True)
    (data / "bridge_graph").mkdir(parents=True)
    kept = "code://func/code.mod.f"
    nodes = {kept: {"kind": "node", "node_type": "func", "id": kept, "dotted": "code.mod.f",
                    "file": "code/mod.py", "line": 1}}
    if not break_it:
        nodes["code://func/code.mod.g"] = {"kind": "node", "node_type": "func",
                                           "id": "code://func/code.mod.g", "dotted": "code.mod.g",
                                           "file": "code/mod.py", "line": 5}
    (data / "code_graph" / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (data / "code_graph" / "edges.json").write_text("[]", encoding="utf-8")
    (data / "code_graph" / "PROVENANCE.json").write_text(json.dumps({"counts": {}}), encoding="utf-8")
    (data / "bridge_graph" / "nodes.json").write_text("{}", encoding="utf-8")     # edges-only
    (data / "bridge_graph" / "edges.json").write_text(json.dumps([
        {"kind": "edge", "edge_type": "reads_table", "src": kept, "dst": "code://func/code.mod.g"},
    ]), encoding="utf-8")
    prov = {"counts": {"node_count": 0, "edge_count": 1, "edge_types": {"reads_table": 1}}}
    if resolved:
        prov["endpoints"] = "resolved"
    (data / "bridge_graph" / "PROVENANCE.json").write_text(json.dumps(prov), encoding="utf-8")
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    return Tenant(root=tmp_path, data_home=data, adapters=(),
                  build_lanes={"code_graph": (None, "static-dep"), "bridge_graph": (None, "static-dep")},
                  join_keys=join_keys, cursor="sha256:" + "0" * 64, policy="refuse",
                  journal=tmp_path / "journal")


def test_GREEN_an_edges_only_lane_is_a_named_shape_and_a_declared_lane_goes_red_when_it_dangles(tmp_path):
    """A shard with an empty nodes.json and a populated edges.json compiled and passed `check` with
    no finding at all — a pure bridge, useful and unguarded, so the day a sibling stopped minting an
    id the bridge dropped that edge in silence. On a first client's 32-lane tenant 6,673 edges
    pointed at no node anywhere and `check` was green.

    The count alone is deliberately not an error: for a code lane most dangling endpoints are
    third-party and stdlib call targets the tenant chose not to mint, so a red on the number would
    be red for every healthy roster. The SILENCE was the defect. A lane says `endpoints: resolved`
    when it means its edges must land, and only then is a dangling endpoint an error."""
    # endpoints all resolve → the bridge is named as a shape, nothing dangles
    audit = cli._endpoint_audit(_bridge_tenant(tmp_path / "ok", resolved=True))
    bridge = next(l for l in audit if l["slug"] == "bridge")
    assert bridge["nodes"] == 0 and bridge["edges"] == 1 and bridge["edge_types"] == ["reads_table"]
    assert bridge["dangling"] == 0 and bridge["endpoints"] == "resolved"

    # the same lane with its target removed, DECLARED resolved → the endpoint is named
    audit = cli._endpoint_audit(_bridge_tenant(tmp_path / "red", resolved=True, break_it=True))
    bridge = next(l for l in audit if l["slug"] == "bridge")
    assert bridge["dangling"] == 1
    assert bridge["first_dangling"] == ("reads_table", "dst", "code://func/code.mod.g")

    # …and undeclared, the same break is a shape the check reports rather than an error
    audit = cli._endpoint_audit(_bridge_tenant(tmp_path / "note", resolved=False, break_it=True))
    bridge = next(l for l in audit if l["slug"] == "bridge")
    assert bridge["dangling"] == 1 and bridge["endpoints"] is None


def test_GREEN_check_is_red_only_for_a_lane_that_declared_its_endpoints_resolve(tmp_path, capsys):
    """The verdicts end to end: the declared lane fails the check by name, the undeclared one is a
    NOTE on stdout and the check still passes."""
    import graphy.federated_store as fs

    for kind, resolved, want_rc in (("red", True, 1), ("note", False, 0)):
        tenant = _bridge_tenant(tmp_path / kind, resolved=resolved, break_it=True)
        (tenant.data_home / ".federation_scheme_index.json").write_text(json.dumps({
            "_meta": {}, "code": {"own": ["code"], "out": []}, "bridge": {"own": ["bridge"], "out": ["code"]},
        }), encoding="utf-8")
        roster = ["code", "bridge"]
        fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="t")
        desc = tmp_path / kind / "tenant.json"
        desc.write_text(json.dumps({
            "root": str(tmp_path / kind), "data_home": str(tenant.data_home), "adapters": [],
            "build_lanes": {"code_graph": [None, "static-dep"], "bridge_graph": [None, "static-dep"]},
            "join_keys": str(tenant.join_keys), "cursor": tenant.cursor, "policy": "refuse",
            "journal": str(tenant.journal)}), encoding="utf-8")
        rc = cli.main(["check", "--tenant", str(desc), "--tenant-id", "t"])
        out, err = capsys.readouterr()
        if want_rc == 1:
            assert rc == 1
            assert "declares `endpoints: resolved`" in err and "code.mod.g" in err
        else:
            assert "CHECK NOTE" in out and "edges-only" in out
            assert "resolve to no node in this roster" in out
            assert "declares `endpoints: resolved`" not in err


def test_GREEN_recon_briefs_every_corpus_and_says_why_where_there_is_no_pillar_shape(tmp_path, capsys):
    """`eat` gets a stranger a graph and then the product stopped, waiting for them to already know
    that `pillars` is the orientation verb and that its depth needs escalating. Measured on the
    first tenant: the MCP server was up for months and `pillars` had never been run once — the
    orientation it produces in one command was being re-derived by reading source (graphyos #74).

    The briefing covers EVERY corpus with no --corpus required, and a corpus with no pillar shape
    says why in the words `pillars` itself used rather than being left out or filled in with prose."""
    from graphy import recon as recon_lane
    import graphy.federated_store as fs

    tenant = _bridge_tenant(tmp_path, resolved=False)     # two lanes, neither with a module hierarchy
    (tenant.data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "code": {"own": ["code"], "out": []}, "bridge": {"own": ["bridge"], "out": ["code"]},
    }), encoding="utf-8")
    roster = ["code", "bridge"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="t")
    store = fs.open_for(roster, tenant=tenant, tenant_id="t")

    data = recon_lane.recon(store, tenant, "t")
    assert [s["corpus"] for s in data["sections"]] == ["bridge", "code"]     # every corpus, none dropped
    assert data["generation"] == store.generation()
    for s in data["sections"]:
        assert s["shape"] is None and s["why"], s["corpus"]                  # and each says WHY

    page = recon_lane.render(data, descriptor="/x/tenant.json", tenant_id="t")
    assert "# RECON — t:" in page
    assert "## How to read this" in page and "crown" in page and "cross-arm" in page
    assert "## bridge" in page and "## code" in page
    assert "**No pillar shape.**" in page
    assert "## Staleness" in page and store.generation() in page
    assert "graphy blast <symbol> --tenant /x/tenant.json --tenant-id t" in page
    # the edge-type census carries what each relation was DECLARED as (graphyos #68)
    assert "| edge type | count | declared |" in page


def test_GREEN_recon_writes_beside_the_substrate_and_names_what_it_found(tmp_path, capsys):
    """The verb end to end: no --corpus, no --out, a file beside the substrate the eaten repo
    already gitignores, and a receipt line naming shaped against census."""
    tenant = _bridge_tenant(tmp_path, resolved=False)
    (tenant.data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "code": {"own": ["code"], "out": []}, "bridge": {"own": ["bridge"], "out": ["code"]},
    }), encoding="utf-8")
    import graphy.federated_store as fs
    roster = ["code", "bridge"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="t")
    desc = tmp_path / "tenant.json"
    desc.write_text(json.dumps({
        "root": str(tmp_path), "data_home": str(tenant.data_home), "adapters": [],
        "build_lanes": {"code_graph": [None, "static-dep"], "bridge_graph": [None, "static-dep"]},
        "join_keys": str(tenant.join_keys), "cursor": tenant.cursor, "policy": "refuse",
        "journal": str(tenant.journal)}), encoding="utf-8")
    assert cli.main(["recon", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    out = capsys.readouterr().out
    assert "RECON OK: 2 corpus/corpora" in out and "by census" in out
    landed = tenant.data_home / "RECON.md"
    assert landed.is_file() and "# RECON — t:" in landed.read_text(encoding="utf-8")
    assert b"\r\n" not in landed.read_bytes()     # LF on every host, asserted on the BYTES (graphyos #93)


def test_RED_recon_refuses_without_a_tenant_and_names_the_reason(tmp_path, capsys):
    assert cli.main(["recon", "--tenant-id", "t"]) == 2
    assert "RECON REFUSED: --tenant and --tenant-id are required" in capsys.readouterr().err
