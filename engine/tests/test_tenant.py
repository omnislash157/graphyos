
from __future__ import annotations

from dataclasses import fields

import pytest

from graphy import REQUIRED_FIELDS, Tenant, TenantError


def _valid_kwargs(tmp_path):
    return {
        "root": tmp_path / "root",
        "data_home": tmp_path / "data",
        "adapters": ("python-ast", "outline", "native-json"),
        "build_lanes": {
            "CODE": ("scripts/graph_rebuild.sh", "walk-time-auto"),
            "SCRAPE": (None, "scrape"),
        },
        "join_keys": tmp_path / "join_keys.json",
        "cursor": "sha256:" + "0" * 64,
        "policy": "refuse",
        "journal": tmp_path / "journal",
    }



def test_GREEN_REQUIRED_FIELDS_is_the_eight_literal_names():
    assert REQUIRED_FIELDS == (
        "root",
        "data_home",
        "adapters",
        "build_lanes",
        "join_keys",
        "cursor",
        "policy",
        "journal",
    )


def test_GREEN_REQUIRED_FIELDS_matches_the_dataclass_fields():
    assert REQUIRED_FIELDS == tuple(f.name for f in fields(Tenant))


def test_GREEN_two_tenants_in_one_process_both_work(tmp_path):
    a_root = tmp_path / "a_root"
    a_data = tmp_path / "a_data"
    b_root = tmp_path / "b_root"
    b_data = tmp_path / "b_data"
    for d in (a_root, a_data, b_root, b_data):
        d.mkdir(parents=True, exist_ok=True)

    a = Tenant(
        root=a_root,
        data_home=a_data,
        adapters=("python-ast", "outline", "native-json"),
        build_lanes={"CODE": ("scripts/graph_rebuild.sh", "walk-time-auto")},
        join_keys=tmp_path / "a_join_keys.json",
        cursor="sha256:" + "a" * 64,
        policy="refuse",
        journal=tmp_path / "a_journal",
    )
    b = Tenant(
        root=b_root,
        data_home=b_data,
        adapters=("python-ast", "outline", "native-json"),
        build_lanes={"CODE": ("scripts/graph_rebuild.sh", "walk-time-auto")},
        join_keys=tmp_path / "b_join_keys.json",
        cursor="sha256:" + "b" * 64,
        policy="warn",
        journal=tmp_path / "b_journal",
    )

    assert a.resolve("src/main.py") == (a_root / "src/main.py").resolve()
    assert b.resolve("src/main.py") == (b_root / "src/main.py").resolve()
    assert a.resolve("tenant_a_graph", base="data_home") == (
        a_data / "tenant_a_graph"
    ).resolve()
    assert b.resolve("tenant_b_graph", base="data_home") == (
        b_data / "tenant_b_graph"
    ).resolve()

    with pytest.raises(TenantError):
        a.resolve(b.data_home / "tenant_a_graph", base="data_home")
    with pytest.raises(TenantError):
        b.resolve(a.data_home / "tenant_b_graph", base="data_home")

    with pytest.raises(AttributeError):
        a.root = a_root / "elsewhere"


def test_GREEN_absolute_path_inside_the_tenant_resolves(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    kwargs = _valid_kwargs(tmp_path)
    kwargs["root"] = root
    tenant = Tenant(**kwargs)
    target = root / "main.py"
    assert tenant.resolve(target) == target.resolve()



@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_RED_absent_field_is_refused(tmp_path, field):
    kwargs = _valid_kwargs(tmp_path)
    del kwargs[field]
    with pytest.raises(TypeError):
        Tenant(**kwargs)



def test_RED_policy_outside_refuse_or_warn_raises(tmp_path):
    for bad in ("heal", "auto", "refuse-by-default", ""):
        kwargs = _valid_kwargs(tmp_path)
        kwargs["policy"] = bad
        with pytest.raises(TenantError, match="policy"):
            Tenant(**kwargs)


def test_GREEN_policy_refuse_and_warn_are_accepted(tmp_path):
    for policy in ("refuse", "warn"):
        kwargs = _valid_kwargs(tmp_path)
        kwargs["policy"] = policy
        tenant = Tenant(**kwargs)
        assert tenant.policy == policy



def test_RED_malformed_build_lanes_entry_raises_TenantError(tmp_path):
    for bad in ("scripts/graph_rebuild.sh", ("walk-time-auto",),
                ("cmd", "walk-time-auto", "extra"), None):
        kwargs = _valid_kwargs(tmp_path)
        kwargs["build_lanes"] = {"CODE": bad}
        with pytest.raises(TenantError, match="build_lanes"):
            Tenant(**kwargs)


def test_RED_malformed_build_lanes_CONTAINER_raises_TenantError(tmp_path):
    for bad in (None, ["CODE", ("cmd", "walk-time-auto")], "CODE", 42, ("cmd", "walk-time-auto")):
        kwargs = _valid_kwargs(tmp_path)
        kwargs["build_lanes"] = bad
        with pytest.raises(TenantError, match="build_lanes"):
            Tenant(**kwargs)


def test_RED_build_lanes_command_must_be_a_string_or_None(tmp_path):
    kwargs = _valid_kwargs(tmp_path)
    kwargs["build_lanes"] = {"CODE": (42, "walk-time-auto")}
    with pytest.raises(TenantError, match="command"):
        Tenant(**kwargs)


def test_GREEN_build_lanes_command_may_be_None(tmp_path):
    kwargs = _valid_kwargs(tmp_path)
    kwargs["build_lanes"] = {
        "DEP": (None, "static-dep"),
        "SECURITY_MESH": (None, "parked"),
        "SCRAPE": (None, "scrape"),
        "UNCLASSIFIED": (None, "ORPHANED"),
    }
    tenant = Tenant(**kwargs)
    assert tenant.build_lanes["DEP"] == (None, "static-dep")



def test_RED_isolation_neither_tenant_reads_the_other_data_home(tmp_path):
    a_kwargs = _valid_kwargs(tmp_path)
    a_kwargs["root"] = tmp_path / "a_root"
    a_kwargs["data_home"] = tmp_path / "a_data"
    b_kwargs = _valid_kwargs(tmp_path)
    b_kwargs["root"] = tmp_path / "b_root"
    b_kwargs["data_home"] = tmp_path / "b_data"
    a = Tenant(**a_kwargs)
    b = Tenant(**b_kwargs)

    with pytest.raises(TenantError):
        a.resolve(b.data_home / "graph", base="data_home")
    with pytest.raises(TenantError):
        b.resolve(a.data_home / "graph", base="data_home")


def test_RED_traversal_climbing_out_raises(tmp_path):
    tenant = Tenant(**_valid_kwargs(tmp_path))
    with pytest.raises(TenantError):
        tenant.resolve("../outside")
    with pytest.raises(TenantError):
        tenant.resolve("sub/../../../outside")


def test_RED_absolute_path_outside_the_tenant_raises(tmp_path):
    tenant = Tenant(**_valid_kwargs(tmp_path))
    outside = tmp_path.parent / "absolute_outside"
    with pytest.raises(TenantError):
        tenant.resolve(outside)


def test_RED_symlink_whose_target_lands_outside_raises(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "escape").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"this platform cannot create a symlink: {exc}")

    kwargs = _valid_kwargs(tmp_path)
    kwargs["root"] = root
    tenant = Tenant(**kwargs)
    with pytest.raises(TenantError):
        tenant.resolve("escape")
    with pytest.raises(TenantError):
        tenant.resolve(root / "escape" / "graph")
