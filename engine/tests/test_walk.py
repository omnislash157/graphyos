from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import graphy.cross_substrate as cs
from graphy.tenant import Tenant

FIXTURES = Path(__file__).parent / "fixtures"
FASTAPI_GRAPH = FIXTURES / "fastapi_graph"



def _write_graph(dirpath: Path, nodes: dict, edges: list) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (dirpath / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def _registry(join_keys: Path) -> None:
    join_keys.write_text(json.dumps({
        "_meta": {"description": "synthetic walk registry"},
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



def test_GREEN_declared_load_set_unions_and_assigns_provenance(tmp_path):
    tenant, data_home = _walk_fixture(tmp_path)
    mesh = cs.load_set(["fastapi", "widgets"], tenant=tenant, tenant_id="walk-test")

    assert mesh.node_owner["fastapi://module/fastapi"] == "fastapi"
    assert mesh.node_owner["widgets://module/widgets"] == "widgets"
    assert "widgets://func/widgets.gadget" in mesh.node_index["widgets"]
    assert "fastapi://module/fastapi" in mesh.node_index["fastapi"]

    assert mesh.stats.cross_edges >= 1
    assert mesh.stats.unresolved_cross >= 1

    assert (data_home / "fastapi_graph").is_dir()
    assert (data_home / "widgets_graph").is_dir()


def test_GREEN_tenant_paths_are_the_consumed_identity(tmp_path):
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    shutil.copytree(FASTAPI_GRAPH, data_home / "fastapi_graph")
    _scheme_index(data_home)
    join_keys = tmp_path / "registry.json"
    _registry(join_keys)
    tenant = Tenant(
        root=tmp_path, data_home=data_home, adapters=(),
        build_lanes={}, join_keys=join_keys, cursor="sha256:" + "0" * 64,
        policy="refuse", journal=tmp_path / "journal",
    )

    real = cs.load_override_ir
    captured_registry_paths = []
    def spy(registry_path, *, tenant_id):
        captured_registry_paths.append(Path(registry_path))
        return real(registry_path, tenant_id=tenant_id)
    cs.load_override_ir = spy
    try:
        mesh = cs.load_set(["fastapi"], tenant=tenant, tenant_id="path-consumed")
    finally:
        cs.load_override_ir = real

    assert mesh.stats.nodes > 0
    assert "fastapi://module/fastapi" in mesh.node_index["fastapi"]
    assert captured_registry_paths
    assert all(p == join_keys for p in captured_registry_paths)



def test_RED_load_set_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        cs.load_set(["no_such_substrate_anywhere"], tenant_id="walk-test")
    with pytest.raises(ValueError, match="tenant is required"):
        cs.load_set(["no_such_substrate_anywhere"], tenant=None, tenant_id="walk-test")


def test_GREEN_load_set_declared_tenant_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    mesh = cs.load_set(["fastapi"], tenant=tenant, tenant_id="walk-test")
    assert mesh.stats.nodes > 0



def test_RED_load_set_absent_tenant_id_refuses_naming_tenant_id(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.load_set(["fastapi"], tenant=tenant)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.load_set(["fastapi"], tenant=tenant, tenant_id=None)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.load_set(["fastapi"], tenant=tenant, tenant_id="")
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.load_set(["fastapi"], tenant=tenant, tenant_id="   ")


def test_GREEN_load_set_declared_tenant_id_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    mesh = cs.load_set(["fastapi"], tenant=tenant, tenant_id="walk-test")
    assert mesh.stats.nodes > 0



def test_RED_derive_roster_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        cs.derive_roster("fastapi://module/fastapi")


def test_GREEN_derive_roster_declared_tenant_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    roster, _dropped = cs.derive_roster(
        "fastapi://module/fastapi", tenant=tenant, tenant_id="walk-test", radius=1)
    assert "fastapi" in roster


def test_RED_derive_roster_absent_tenant_id_refuses_naming_tenant_id(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.derive_roster("fastapi://module/fastapi", tenant=tenant)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.derive_roster("fastapi://module/fastapi", tenant=tenant, tenant_id="")
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.derive_roster("fastapi://module/fastapi", tenant=tenant, tenant_id="   ")


def test_GREEN_derive_roster_declared_tenant_id_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    roster, _dropped = cs.derive_roster(
        "fastapi://module/fastapi", tenant=tenant, tenant_id="walk-test", radius=1)
    assert "fastapi" in roster


def test_GREEN_derive_roster_live_path_reaches_index_rows_and_presence_check(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    roster, dropped = cs.derive_roster(
        "fastapi://module/fastapi", tenant=tenant, tenant_id="walk-test", radius=1)
    assert "widgets" in roster
    assert dropped == []

    import shutil as _sh
    _sh.rmtree(Path(tenant.data_home) / "widgets_graph")
    roster2, dropped2 = cs.derive_roster(
        "fastapi://module/fastapi", tenant=tenant, tenant_id="walk-test", radius=1)
    assert "widgets" not in roster2
    assert "widgets" in dropped2



def test_GREEN_load_literal_join_schemes_seam_runs_inside_load_set(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    cs.load_set(["fastapi"], tenant=tenant, tenant_id="walk-test")


def test_RED_load_literal_join_schemes_seam_refuses_when_absent(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs.load_set(["fastapi"], tenant=tenant)
    join_keys = Path(tenant.join_keys)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs._load_literal_join_schemes(join_keys)
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs._load_literal_join_schemes(join_keys, tenant_id="")
    with pytest.raises(ValueError, match="tenant_id is required"):
        cs._load_literal_join_schemes(join_keys, tenant_id=None)


def test_GREEN_load_literal_join_schemes_declared_identity_proceeds(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    schemes = cs._load_literal_join_schemes(Path(tenant.join_keys), tenant_id="walk-test")
    assert "termtype" in schemes
    assert "cwe" in schemes



def test_receipts_carry_exactly_the_declared_tenant_id(tmp_path):
    tenant, _ = _walk_fixture(tmp_path)
    real = cs.load_override_ir
    captured: list[tuple[str, tuple]] = []
    def spy(registry_path, *, tenant_id):
        ir = real(registry_path, tenant_id=tenant_id)
        captured.append((tenant_id, ir.records))
        return ir
    cs.load_override_ir = spy
    try:
        cs.load_set(["fastapi"], tenant=tenant, tenant_id="tenant-alpha")
        cs.load_set(["fastapi"], tenant=tenant, tenant_id="tenant-beta")
    finally:
        cs.load_override_ir = real

    alpha = [recs for tid, recs in captured if tid == "tenant-alpha"]
    beta = [recs for tid, recs in captured if tid == "tenant-beta"]
    assert alpha and beta, f"expected both ids captured, got {[(t, len(r)) for t, r in captured]}"

    assert alpha[0]
    assert beta[0]
    assert all(r.tenant_id == "tenant-alpha" for r in alpha[0])
    assert all(r.tenant_id == "tenant-beta" for r in beta[0])
    assert {r.tenant_id for r in alpha[0]} == {"tenant-alpha"}
    assert {r.tenant_id for r in beta[0]} == {"tenant-beta"}
    assert alpha[0][0].tenant_id != beta[0][0].tenant_id
