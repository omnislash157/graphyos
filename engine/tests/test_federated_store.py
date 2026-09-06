from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

import pytest

import graphy.cross_substrate as cs
import graphy.federated_store as fs
import graphy.query as query
from graphy.tenant import Tenant

FIXTURES = Path(__file__).parent / "fixtures"
FASTAPI_GRAPH = FIXTURES / "fastapi_graph"



def _write_graph(dirpath: Path, nodes: dict, edges: list) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (dirpath / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def _registry(join_keys: Path) -> None:
    join_keys.write_text(json.dumps({
        "_meta": {"description": "synthetic store registry"},
        "registered_joins": {"literal_joins": {
            "termtype://": "axis",
            "cwe://": "axis",
        }},
    }), encoding="utf-8")


def _scheme_index(data_home: Path) -> None:
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {},
        "fastapi": {"own": ["fastapi"], "out": []},
        "widgets": {"own": ["widgets"], "out": ["fastapi"]},
    }), encoding="utf-8")


def _tenant(tmp_path: Path, *, data_home: Path | None = None,
            join_keys: Path | None = None) -> Tenant:
    data_home = data_home or tmp_path
    join_keys = join_keys or tmp_path / "registry.json"
    if not data_home.exists():
        data_home.mkdir(parents=True)
    _registry(join_keys)
    return Tenant(
        root=tmp_path,
        data_home=data_home,
        adapters=(),
        build_lanes={},
        join_keys=join_keys,
        cursor="sha256:" + "0" * 64,
        policy="refuse",
        journal=tmp_path / "journal",
    )


def _walk_fixture(tmp_path: Path) -> tuple[Tenant, Path]:
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    shutil.copytree(FASTAPI_GRAPH, data_home / "fastapi_graph")
    _write_graph(data_home / "widgets_graph", {
        "widgets://module/widgets": {
            "kind": "node", "node_type": "module", "id": "widgets://module/widgets",
            "dotted": "widgets", "file": "widgets/__init__.py", "loc": 3, "docstring": "",
        },
        "widgets://func/widgets.gadget": {
            "kind": "node", "node_type": "func", "id": "widgets://func/widgets.gadget",
            "name": "gadget", "dotted": "widgets.gadget", "file": "widgets/gadget.py", "line": 1,
        },
    }, [
        {"kind": "edge", "edge_type": "imports", "src": "widgets://module/widgets",
         "dst": "fastapi://module/fastapi", "name": "FastAPI", "alias": "FastAPI", "line": 1},
    ])
    _scheme_index(data_home)
    tenant = _tenant(tmp_path, data_home=data_home)
    return tenant, data_home


def _compile(tenant: Tenant, tmp_path: Path, *, substrates: list | None = None,
             db: str = "s.sqlite", tenant_id: str = "store-test") -> Path:
    substrates = substrates or ["fastapi", "widgets"]
    dbp = tmp_path / db
    fs.compile_store(substrates, dbp, tenant=tenant, tenant_id=tenant_id)
    return dbp


def _mutate_widgets(data_home: Path) -> None:
    path = data_home / "widgets_graph" / "nodes.json"
    nodes = json.loads(path.read_text(encoding="utf-8"))
    nodes["widgets://func/widgets.mutated"] = {
        "kind": "node", "node_type": "func", "id": "widgets://func/widgets.mutated",
        "name": "mutated", "dotted": "widgets.mutated", "file": "widgets/mutated.py", "line": 1,
    }
    path.write_text(json.dumps(nodes), encoding="utf-8")


def _advertised_argv(message: str) -> list:
    marker = "python -m graphy.federated_store "
    idx = message.find(marker)
    assert idx != -1, f"no advertised command in message: {message!r}"
    return shlex.split(message[idx + len(marker):])



def test_GREEN_compile_then_open_answers_and_digest_matches_recompute(tmp_path):
    tenant, data_home = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test",
                        db_path=db)
    assert store.membership("fastapi://module/fastapi") == "fastapi"
    assert store.membership("widgets://module/widgets") == "widgets"
    assert store._input_digest == fs._compute_input_digest(
        ["fastapi", "widgets"], tenant=tenant)
    assert (data_home / "fastapi_graph").is_dir()
    assert (data_home / "widgets_graph").is_dir()



def test_GREEN_store_vs_direct_parity_one_hop(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test",
                        db_path=db)
    mesh = cs.load_set(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test")

    assert store.membership("fastapi://module/fastapi") == \
        mesh.node_owner["fastapi://module/fastapi"]
    assert store.record("fastapi://module/fastapi") == \
        mesh.node_records["fastapi://module/fastapi"]

    shard = fs.ShardStore.from_mesh(mesh, ["fastapi", "widgets"])
    for nid in ("widgets://module/widgets", "fastapi://module/fastapi"):
        assert {(n.node, n.relation, n.direction) for n in store.neighbours(nid)} == \
            {(n.node, n.relation, n.direction) for n in shard.neighbours(nid)}, nid

    a = fs.path_to(store, "widgets://module/widgets", "fastapi://module/fastapi",
                   max_depth=2)
    b = cs.path_to(mesh, "widgets://module/widgets", "fastapi://module/fastapi",
                   max_depth=2)
    assert a.found and b.found
    assert [(s.src, s.dst, s.relation, s.direction) for s in a.steps] == \
        [(s.src, s.dst, s.relation, s.direction) for s in b.steps]



def test_RED_compile_store_absent_tenant_refuses_naming_tenant(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant is required"):
        fs.compile_store(["fastapi"], tmp_path / "s.sqlite", tenant_id="store-test")
    with pytest.raises(ValueError, match="tenant is required"):
        fs.compile_store(["fastapi"], tmp_path / "s.sqlite", tenant=None,
                         tenant_id="store-test")


def test_RED_compile_store_absent_tenant_id_refuses_naming_tenant_id(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.compile_store(["fastapi"], tmp_path / "s.sqlite", tenant=tenant)
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.compile_store(["fastapi"], tmp_path / "s.sqlite", tenant=tenant, tenant_id="")
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.compile_store(["fastapi"], tmp_path / "s.sqlite", tenant=tenant, tenant_id="   ")


def test_GREEN_compile_store_declared_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    assert db.is_file()



def test_RED_open_for_absent_tenant_refuses_naming_tenant(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant is required"):
        fs.open_for(["fastapi"], tenant_id="store-test")
    with pytest.raises(ValueError, match="tenant is required"):
        fs.open_for(["fastapi"], tenant=None, tenant_id="store-test")


def test_RED_open_for_absent_tenant_id_refuses_naming_tenant_id(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.open_for(["fastapi"], tenant=tenant)
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.open_for(["fastapi"], tenant=tenant, tenant_id="")
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.open_for(["fastapi"], tenant=tenant, tenant_id="   ")


def test_GREEN_open_for_declared_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test",
                        db_path=db)
    assert len(store.generation()) == 16



def test_RED_store_path_for_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        fs.store_path_for(["fastapi"])
    with pytest.raises(ValueError, match="tenant is required"):
        fs.store_path_for(["fastapi"], tenant=None)


def test_GREEN_store_path_for_declared_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    p = fs.store_path_for(["fastapi", "widgets"], tenant=tenant)
    assert p.parent == Path(tenant.data_home)
    assert p.name.startswith(".mesh_store_")
    assert p.name.endswith(".sqlite")



def test_RED_compute_input_digest_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        fs._compute_input_digest(["fastapi"])


def test_GREEN_compute_input_digest_declared_through_public_caller(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test",
                        db_path=db)
    assert store._input_digest == fs._compute_input_digest(
        ["fastapi", "widgets"], tenant=tenant)
    with pytest.raises(ValueError, match="tenant_id is required"):
        fs.compile_store(["fastapi"], tmp_path / "other.sqlite", tenant=tenant)



def test_RED_cli_absent_identity_flags_refuse_naming_the_flag(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        fs.main(["--mesh-set", "fastapi"])
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "--tenant-id" in err and "--data-home" in err and "--join-keys" in err


def test_GREEN_cli_declared_identity_compiles(tmp_path, capsys):
    tenant, _ = _walk_fixture(tmp_path)
    rc = fs.main(["--mesh-set", "fastapi",
                  "--data-home", str(tenant.data_home),
                  "--join-keys", str(tenant.join_keys),
                  "--tenant-id", "cli-test"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "compiled" in out
    assert fs.store_path_for(["fastapi"], tenant=tenant).is_file()



def test_GREEN_two_tenants_isolated_by_path(tmp_path):
    tenant_a, _ = _walk_fixture(tmp_path / "a")
    tenant_b, _ = _walk_fixture(tmp_path / "b")
    assert fs.store_path_for(["fastapi"], tenant=tenant_a) != \
        fs.store_path_for(["fastapi"], tenant=tenant_b)

    _compile(tenant_a, tmp_path / "a", db="s.sqlite")
    store_a = fs.open_for(["fastapi", "widgets"], tenant=tenant_a,
                          tenant_id="iso-test", db_path=tmp_path / "a" / "s.sqlite")
    assert store_a.generation()

    with pytest.raises(fs.StoreError, match="no compiled store"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant_b, tenant_id="iso-test")



def test_RED_stale_store_refuses_naming_the_digest_mismatch(tmp_path):
    tenant, data_home = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="t", db_path=db)
    served = store.generation()

    _mutate_widgets(data_home)
    with pytest.raises(fs.StoreError, match="is STALE"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="t",
                    db_path=db, on_stale="refuse")


def test_RED_unmeasurable_input_raises_never_serves(tmp_path):
    tenant, data_home = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    shutil.rmtree(data_home / "widgets_graph")
    with pytest.raises(fs.StoreError, match="could not tell"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="t",
                    db_path=db, on_stale="warn")


def test_RED_unmeasurable_registry_raises_never_serves(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    Path(tenant.join_keys).unlink()
    with pytest.raises(fs.StoreError, match="registry"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="t", db_path=db)



def test_GREEN_query_main_store_lane_executes(tmp_path, capsys):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    rc = query.main(["fastapi://module/fastapi", "--mesh-set", "fastapi,widgets",
                     "--store", str(db), "--depth", "1",
                     "--data-home", str(tenant.data_home),
                     "--join-keys", str(tenant.join_keys),
                     "--tenant-id", "lane-test"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "fastapi://module/fastapi" in out


def test_GREEN_query_main_materialize_lane_executes(tmp_path, capsys):
    tenant, _ = _walk_fixture(tmp_path)
    rc = query.main(["fastapi://module/fastapi", "--mesh-set", "fastapi,widgets",
                     "--materialize", "--depth", "1",
                     "--data-home", str(tenant.data_home),
                     "--join-keys", str(tenant.join_keys),
                     "--tenant-id", "lane-test"])
    assert rc == 0


def test_GREEN_cross_substrate_main_store_lane_executes(tmp_path, capsys):
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    rc = cs.main(["widgets://module/widgets", "--path-to", "fastapi://module/fastapi",
                  "--store", str(db),
                  "--data-home", str(tenant.data_home),
                  "--join-keys", str(tenant.join_keys),
                  "--tenant-id", "lane-test"])
    assert rc == 0


def test_RED_query_main_without_identity_flags_refuses_naming_the_flag(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        query.main(["fastapi://module/fastapi", "--mesh-set", "fastapi"])
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "--tenant-id" in err and "--data-home" in err and "--join-keys" in err


def test_RED_cross_substrate_main_without_identity_flags_refuses_naming_the_flag(
        tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        cs.main(["widgets://module/widgets", "--path-to", "fastapi://module/fastapi"])
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "--tenant-id" in err



def test_GREEN_advertised_missing_command_parses_and_repairs(tmp_path):
    base = tmp_path / "sp aced home"
    base.mkdir()
    tenant, _ = _walk_fixture(base)
    db = base / "explicit store.sqlite"
    with pytest.raises(fs.StoreError) as exc:
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                    db_path=db)
    msg = str(exc.value)
    assert "Build it:" in msg
    argv = _advertised_argv(msg)
    assert argv[argv.index("--tenant-id") + 1] == "adv test id"
    assert argv[argv.index("--data-home") + 1] == str(tenant.data_home)
    assert argv[argv.index("--join-keys") + 1] == str(tenant.join_keys)
    assert argv[argv.index("--out") + 1] == str(db)
    rc = fs.main(argv)
    assert rc == 0
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                        db_path=db)
    assert store.generation()


def test_GREEN_advertised_warn_command_parses(tmp_path, capsys):
    base = tmp_path / "sp aced home"
    base.mkdir()
    tenant, data_home = _walk_fixture(base)
    db = _compile(tenant, base, db="explicit store.sqlite", tenant_id="adv test id")
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                        db_path=db)
    served = store.generation()

    _mutate_widgets(data_home)
    warned = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                         db_path=db, on_stale="warn")
    assert warned.generation() == served
    err = capsys.readouterr().err
    assert "Rebuild it:" in err
    argv = _advertised_argv(err)
    assert argv[argv.index("--tenant-id") + 1] == "adv test id"
    assert argv[argv.index("--out") + 1] == str(db)
    rc = fs.main(argv)
    assert rc == 0
    fresh = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                        db_path=db)
    assert fresh.generation() != served


def test_GREEN_advertised_refuse_command_parses(tmp_path):
    base = tmp_path / "sp aced home"
    base.mkdir()
    tenant, data_home = _walk_fixture(base)
    db = _compile(tenant, base, db="explicit store.sqlite", tenant_id="adv test id")
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                        db_path=db)
    served = store.generation()

    _mutate_widgets(data_home)
    with pytest.raises(fs.StoreError) as exc:
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                    db_path=db, on_stale="refuse")
    msg = str(exc.value)
    assert "Rebuild it:" in msg
    argv = _advertised_argv(msg)
    assert argv[argv.index("--tenant-id") + 1] == "adv test id"
    assert argv[argv.index("--out") + 1] == str(db)
    rc = fs.main(argv)
    assert rc == 0
    fresh = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="adv test id",
                        db_path=db)
    assert fresh.generation() != served
