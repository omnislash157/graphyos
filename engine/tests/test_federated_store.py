from __future__ import annotations

import json
import sqlite3
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


def test_RED_unmeasurable_input_raises_never_serves(tmp_path, monkeypatch):
    tenant, data_home = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    shutil.rmtree(data_home / "widgets_graph")
    # the shard is gone on purpose: the transient-ENOENT retry has nothing to wait for
    monkeypatch.setattr("graphy.cartograph.time.sleep", lambda _seconds: None)
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


def test_GREEN_open_for_hashes_shard_bytes_and_never_parses_them(tmp_path, monkeypatch):
    """A walk is a query, never a load: the freshness check reads nodes.json / edges.json (and the
    sidecar) for hashing only. Every file open during open_for is recorded; the shard payloads
    are opened read-binary and json.loads never sees their bytes."""
    import builtins
    import io
    from graphy import native_json_graph_ir as nj
    tenant, data_home = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    nj._RAW.clear()
    nj._SHARDS.clear()
    payloads = {}
    for gd in (data_home / "fastapi_graph", data_home / "widgets_graph"):
        for name in nj.SHARD_INPUTS:
            if (gd / name).is_file():
                payloads[str(gd / name)] = (gd / name).read_bytes()
    opened: list[tuple[str, str]] = []
    real_open = builtins.open

    def spy_open(file, mode="r", *a, **k):
        opened.append((str(file), mode))
        return real_open(file, mode, *a, **k)

    parsed: list[int] = []
    real_loads = json.loads

    def spy_loads(s, *a, **k):
        raw = s if isinstance(s, (bytes, bytearray)) else s.encode("utf-8")
        parsed.append(len(raw))
        assert raw not in payloads.values(), "open_for parsed a shard payload — that is a load"
        return real_loads(s, *a, **k)

    real_path_open = Path.open

    def spy_path_open(self, mode="r", *a, **k):
        # 3.10's pathlib opens through an accessor bound to io.open at import, past the io spy
        opened.append((str(self), mode))
        return real_path_open(self, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(io, "open", spy_open)
    monkeypatch.setattr(Path, "open", spy_path_open)
    monkeypatch.setattr(json, "loads", spy_loads)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test", db_path=db)
    assert store.membership("widgets://module/widgets") == "widgets"
    shard_opens = [(f, m) for f, m in opened if f in payloads]
    assert shard_opens, "the freshness check never touched the shard bytes"
    assert all(m == "rb" for _f, m in shard_opens), shard_opens
    assert all(f in payloads or "_graph" not in f for f, _m in opened), opened
    assert not [n for n in parsed if n in {len(b) for b in payloads.values()}]
    # a byte moved in any input still reads STALE — the verdict is as strict as before
    monkeypatch.undo()
    _mutate_widgets(data_home)
    with pytest.raises(fs.StoreError, match="STALE"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test", db_path=db)


def test_GREEN_one_parse_per_shard_per_process_and_a_rewrite_reparses(tmp_path, monkeypatch):
    from graphy import native_json_graph_ir as nj
    tenant, data_home = _walk_fixture(tmp_path)
    nj._RAW.clear()
    nj._SHARDS.clear()
    gd = data_home / "widgets_graph"
    real_loads = json.loads
    count = []
    monkeypatch.setattr(json, "loads", lambda s, *a, **k: count.append(1) or real_loads(s, *a, **k))
    a = nj.load_graph_ir(gd)
    n = len(count)
    assert n >= 2
    b = nj.load_graph_ir(gd)
    assert b is a and len(count) == n, "a second load of an untouched shard parsed again"
    assert a.input_digest == nj.shard_input_digest(gd)
    _mutate_widgets(data_home)
    c = nj.load_graph_ir(gd)
    assert c is not a and len(count) > n and c.input_digest != a.input_digest


def test_RED_store_under_an_older_input_digest_format_refuses_naming_recompile(tmp_path):
    import sqlite3
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    con = sqlite3.connect(db)
    con.execute("UPDATE meta SET v=? WHERE k='input_digest'", (json.dumps({"fastapi": "abc"}),))
    con.commit()
    con.close()
    with pytest.raises(fs.StoreError, match="digest format"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test", db_path=db)


def test_GREEN_the_parse_memo_is_bounded(tmp_path):
    from graphy import native_json_graph_ir as nj
    nj._RAW.clear()
    nj._SHARDS.clear()
    for i in range(nj.MEMO_SHARDS + 5):
        gd = tmp_path / f"s{i}_graph"
        _write_graph(gd, {f"s{i}://module/s{i}": {"kind": "node", "node_type": "module", "id": f"s{i}://module/s{i}",
                                                 "dotted": f"s{i}", "file": "x.py", "loc": 1, "docstring": ""}}, [])
        nj.load_graph_ir(gd)
    assert len(nj._RAW) == nj.MEMO_SHARDS and len(nj._SHARDS) == nj.MEMO_SHARDS
    assert str(tmp_path / "s0_graph") not in nj._RAW and str(tmp_path / f"s{nj.MEMO_SHARDS + 4}_graph") in nj._RAW


def test_GREEN_owned_reads_the_columns_and_decodes_no_record(tmp_path, monkeypatch):
    """The aggregates' whole-corpus read is the columns: owned() decodes no JSON, yields exactly
    COLUMNS per node, and every value equals the full record's — the record is record()'s alone."""
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    store = fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test", db_path=db)
    real_loads, calls = json.loads, []

    def spy_loads(s, *a, **k):
        calls.append(s)
        return real_loads(s, *a, **k)
    monkeypatch.setattr(fs.json, "loads", spy_loads)
    rows = list(store.owned("fastapi"))
    assert rows and not calls, f"owned() decoded {len(calls)} record(s); the columns are the read"
    for nid, cols in rows:
        assert tuple(cols) == fs.COLUMNS
        full = store.record(nid)
        assert cols == {k: full.get(k) for k in fs.COLUMNS}
    assert calls, "record() is the one decode"
    assert any(c["module"] for _n, c in rows) and any(c["node_type"] == "module" for _n, c in rows)
    con = sqlite3.connect(db)
    idx = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    con.close()
    assert {"idx_nodes_owner_module", "idx_nodes_owner_type"} <= idx


def test_GREEN_shard_store_owned_yields_the_same_columns(tmp_path):
    """Both readers speak one shape: ShardStore.owned() projects the mesh record to COLUMNS."""
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    shard = fs.ShardStore(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test")
    sqlite_rows = dict(fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test",
                                   db_path=db).owned("fastapi"))
    assert dict(shard.owned("fastapi")) == sqlite_rows


def test_RED_store_under_the_blob_only_schema_refuses_naming_recompile(tmp_path):
    """A store compiled before the columns (format 3) is not this build's: refused, naming recompile."""
    tenant, _ = _walk_fixture(tmp_path)
    db = _compile(tenant, tmp_path)
    con = sqlite3.connect(db)
    con.execute("UPDATE meta SET v='3' WHERE k='generation_format'")
    con.commit()
    con.close()
    with pytest.raises(fs.StoreError, match="generation format"):
        fs.open_for(["fastapi", "widgets"], tenant=tenant, tenant_id="store-test", db_path=db)


def test_GREEN_the_tmp_store_syncs_once_before_the_rename(tmp_path, monkeypatch):
    """The tmp file pays no durability while it fills — the two pragmas run on its connection before
    the schema — and the finished file is fsynced once, then renamed: what lands under the store's
    name is complete, never torn, and no statement waits on the disk."""
    import os
    tenant, _ = _walk_fixture(tmp_path)
    events: list[tuple] = []
    real_connect = sqlite3.connect

    class _Spy:
        def __init__(self, con):
            self._con = con

        def execute(self, sql, *a):
            events.append(("execute", sql.split()[0], sql))
            return self._con.execute(sql, *a)

        def __getattr__(self, name):
            return getattr(self._con, name)

    def connect(path, *a, **k):
        events.append(("connect", str(path)))
        return _Spy(real_connect(path, *a, **k))

    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(fs.sqlite3, "connect", connect)
    monkeypatch.setattr(fs.os, "fsync", lambda fd: (events.append(("fsync", os.readlink(f"/proc/self/fd/{fd}"))), real_fsync(fd)))
    monkeypatch.setattr(fs.os, "replace", lambda a, b: (events.append(("replace", str(a), str(b))), real_replace(a, b)))
    dbp = _compile(tenant, tmp_path)
    tmp = next(e[1] for e in events if e[0] == "connect")
    assert tmp.startswith(str(dbp) + ".tmp."), events
    first_two = [e[2] for e in events if e[0] == "execute"][:2]
    assert first_two == list(fs.TMP_STORE_PRAGMAS), first_two          # before the schema, on the tmp connection
    order = [e[:2] for e in events if e[0] in ("fsync", "replace")]
    assert order == [("fsync", tmp), ("replace", tmp)], order
    assert sqlite3.connect(dbp).execute("PRAGMA journal_mode").fetchone()[0] == "delete"   # the pragma lived on the tmp connection only


def test_GREEN_two_builds_under_two_hash_seeds_land_the_same_row_order(tmp_path):
    """The mesh keeps its edges in a set, which iterates in hash order — salted per process — so a
    store's rowids used to follow the seed and every tie a door breaks by row order broke
    differently between two builds of one shard (graphyos #26). The rows land sorted: the same
    order under any seed."""
    import os
    import subprocess
    import sys
    tenant, data_home = _walk_fixture(tmp_path)
    script = (
        "import sys; from pathlib import Path; import graphy.federated_store as fs; from graphy.tenant import Tenant\n"
        "t = Tenant(root=Path(sys.argv[1]), data_home=Path(sys.argv[2]), adapters=(), build_lanes={}, join_keys=Path(sys.argv[3]),\n"
        "           cursor='sha256:' + '0' * 64, policy='refuse', journal=Path(sys.argv[1]) / 'journal')\n"
        "fs.compile_store(['fastapi', 'widgets'], sys.argv[4], tenant=t, tenant_id='store-test')\n"
    )
    orders = []
    for seed in ("1", "2", "3"):
        db = tmp_path / f"seed{seed}.sqlite"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        subprocess.run([sys.executable, "-c", script, str(tmp_path), str(data_home), str(tenant.join_keys), str(db)],
                       check=True, env=env, cwd=str(Path(fs.__file__).parents[1]))
        orders.append(sqlite3.connect(db).execute("SELECT src, dst, rel FROM edges ORDER BY rowid").fetchall())
    assert orders[0] == orders[1] == orders[2], "the row order followed the hash seed"
    assert orders[0] == sorted(orders[0]) and len(orders[0]) > 100
