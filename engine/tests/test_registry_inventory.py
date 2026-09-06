from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.augment_registry as ar
import graphy.inventory as inv
from graphy.tenant import Tenant


def _admitted_entry(slug: str, stamp: dict) -> str:
    inner = json.dumps({slug: stamp}, indent=2, ensure_ascii=False).split("\n")[1:-1]
    return "\n".join("    " + ln for ln in inner)


def _registry_text(admitted=None, grandfathered=None) -> str:
    admitted = admitted or {}
    gf = grandfathered or []
    lines = ["{"]
    lines.append('  "substrate_roster": {')
    lines.append('    "grandfathered": [')
    for i, s in enumerate(sorted(gf)):
        lines.append(f"      {json.dumps(s)}" + ("," if i < len(gf) - 1 else ""))
    lines.append("    ],")
    lines.append('    "admitted": {')
    for i, (slug, stamp) in enumerate(sorted(admitted.items())):
        lines.append(_admitted_entry(slug, stamp) + ("," if i < len(admitted) - 1 else ""))
    lines.append("    }")
    lines.append("  },")
    lines.append('  "registered_joins": {"literal_joins": []},')
    lines.append('  "alias_overrides": {}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _tenant(tmp_path: Path, *, data_home: Path | None = None, join_keys: Path | None = None,
            admitted=None, grandfathered=None) -> Tenant:
    data_home = data_home or tmp_path / "data"
    data_home.mkdir(parents=True, exist_ok=True)
    join_keys = join_keys or tmp_path / "registry.json"
    if not join_keys.exists():
        join_keys.write_text(_registry_text(admitted, grandfathered), encoding="utf-8")
    return Tenant(
        root=tmp_path, data_home=data_home, adapters=(),
        build_lanes={}, join_keys=join_keys,
        cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal",
    )


def _descriptor(slug: str = "egress") -> dict:
    return ar.normalize_descriptor(
        slug=slug, kind="augment", owner="tenant", blurb="test augment",
        members=["base"], axes={"egress://host": {"base": ["emits"]}},
        producer="test-producer", accept_cmd="true",
    )


def _preexisting_stamp() -> dict:
    return {
        "augment": True, "kind": "augment", "owner": "tenant", "supersedes": "—",
        "blurb": "pre-existing", "members": ["base"],
        "join_keys": ["preexisting://x"],
        "axes": {"preexisting://x": {"base": ["emits"]}},
        "declared_members": {"base": ["emits"]},
        "producer": "p", "accept_cmd": "true",
        "freshness_policy": "member cursors",
        "descriptor_digest": "1" * 16,
        "admitted_via": "test",
    }



def test_GREEN_register_verify_roundtrip_locked_atomic_byte_clean(tmp_path):
    tenant = _tenant(tmp_path, admitted={"preexisting": _preexisting_stamp()})
    desc = _descriptor()
    result = ar.register("egress", desc, tenant=tenant, admission_predicate=lambda s: True)
    assert result["registered"] is True
    assert result["op"] == "insert"
    ar.verify_registration("egress", desc, tenant=tenant)
    reg = json.loads(Path(tenant.join_keys).read_text(encoding="utf-8"))
    stamp = reg["substrate_roster"]["admitted"]["egress"]
    assert stamp == ar.stamp_from_descriptor(desc)
    result2 = ar.register("egress", desc, tenant=tenant, admission_predicate=lambda s: True)
    assert result2["registered"] is False
    assert "byte-idempotent" in result2["reason"]


def test_GREEN_register_replace_updates_stamp_in_place(tmp_path):
    tenant = _tenant(tmp_path, admitted={"preexisting": _preexisting_stamp()})
    desc1 = _descriptor()
    ar.register("egress", desc1, tenant=tenant, admission_predicate=lambda s: True)
    desc2 = _descriptor()
    desc2 = {**desc2, "blurb": "changed blurb"}
    result = ar.register("egress", desc2, tenant=tenant, admission_predicate=lambda s: True)
    assert result["op"] == "replace"
    ar.verify_registration("egress", desc2, tenant=tenant)
    with pytest.raises(RuntimeError, match="stamp != descriptor"):
        ar.verify_registration("egress", desc1, tenant=tenant)



def test_GREEN_admission_predicate_injected_and_used(tmp_path):
    tenant = _tenant(tmp_path, admitted={"preexisting": _preexisting_stamp()})
    desc = _descriptor()
    calls = []

    def pred(slug: str) -> bool:
        calls.append(slug)
        return True

    ar.register("egress", desc, tenant=tenant, admission_predicate=pred)
    assert calls == ["egress"]


def test_RED_register_refused_when_predicate_refuses(tmp_path):
    tenant = _tenant(tmp_path, admitted={"preexisting": _preexisting_stamp()})
    desc = _descriptor()
    with pytest.raises(RuntimeError, match="refused by the admission predicate"):
        ar.register("egress", desc, tenant=tenant, admission_predicate=lambda s: False)
    reg = json.loads(Path(tenant.join_keys).read_text(encoding="utf-8"))
    assert "egress" not in reg["substrate_roster"]["admitted"]


def test_RED_register_no_predicate_refuses_naming_it(tmp_path):
    tenant = _tenant(tmp_path, admitted={"preexisting": _preexisting_stamp()})
    desc = _descriptor()
    with pytest.raises(ValueError, match="admission_predicate"):
        ar.register("egress", desc, tenant=tenant)
    with pytest.raises(ValueError, match="admission_predicate"):
        ar.register("egress", desc, tenant=tenant, admission_predicate=None)
    reg = json.loads(Path(tenant.join_keys).read_text(encoding="utf-8"))
    assert "egress" not in reg["substrate_roster"]["admitted"]



def test_GREEN_inventory_renders_to_tenant_report_path(tmp_path):
    tenant = _tenant(tmp_path)
    data_home = Path(tenant.data_home)
    graph_dir = data_home / "widgets_graph"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.json").write_text(json.dumps({"widgets://m/w": {"id": "widgets://m/w"}}), encoding="utf-8")
    (graph_dir / "edges.json").write_text("[]", encoding="utf-8")
    (graph_dir / "stats.json").write_text(json.dumps(
        {"node_count": 1, "edge_count": 0, "cluster_count": 1}), encoding="utf-8")

    inv.main(tenant=tenant)

    report = data_home / ".SUBSTRATES.report.md"
    assert report.exists()
    md = report.read_text(encoding="utf-8")
    assert "# Substrate Inventory" in md
    assert "widgets" in md
    assert not (data_home.parent / "registries").exists()


def test_GREEN_render_markdown_includes_augment_overlay(tmp_path):
    admitted = {
        "egress": {
            "augment": True, "kind": "augment", "owner": "tenant", "blurb": "b",
            "members": ["base"], "join_keys": ["egress://host"],
            "axes": {"egress://host": {"base": ["emits"]}},
            "declared_members": {"base": ["emits"]}, "producer": "p", "accept_cmd": "true",
            "supersedes": "—", "freshness_policy": "member cursors",
            "descriptor_digest": "0" * 16, "admitted_via": "test",
        },
    }
    tenant = _tenant(tmp_path, admitted=admitted)
    index = {"base": {"own": ["egress", "base"], "out": []}}
    md = inv.render_markdown([], index=index, head_sha="abc1234", tenant=tenant)
    assert "Augments / no standalone graph" in md
    assert "egress" in md
    assert "scheme_complete" in md



def test_no_write_path_to_tracked_catalog():
    src = Path(inv.__file__).read_text(encoding="utf-8")
    assert "--write-registry" not in src
    assert "agent_data_home" not in src
    assert "registries" not in src



def test_RED_register_absent_tenant_refuses_naming_tenant(tmp_path):
    desc = _descriptor()
    with pytest.raises(ValueError, match="tenant is required"):
        ar.register("egress", desc, admission_predicate=lambda s: True)


def test_GREEN_register_declared_tenant_proceeds(tmp_path):
    tenant = _tenant(tmp_path, admitted={"preexisting": _preexisting_stamp()})
    desc = _descriptor()
    result = ar.register("egress", desc, tenant=tenant, admission_predicate=lambda s: True)
    assert result["registered"] is True


def test_RED_verify_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        ar.verify_registration("egress", _descriptor())


def test_RED_inventory_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        inv.render_markdown([], tenant=None)


def test_GREEN_inventory_declared_tenant_proceeds(tmp_path):
    tenant = _tenant(tmp_path)
    assert inv.main(tenant=tenant) == 0



def test_removal_audit_registry_host_lanes_absent():
    src = Path(ar.__file__).read_text(encoding="utf-8")
    assert "_DESCRIPTOR_MODULES" not in src
    assert "_has_admit_ledger" not in src
    assert "admits_ledger" not in src
    assert "_LEDGER" not in src
    assert "subprocess" not in src
    assert "name_gate" not in src


def test_removal_audit_inventory_host_tables_absent():
    src = Path(inv.__file__).read_text(encoding="utf-8")
    for symbol in ("CODE_GRAPHS", "SUBSTRATE_BLURBS", "SUBSTRATE_DISPATCHER", "PARKED_SUBMESH"):
        assert symbol not in src, f"{symbol} must not travel"
