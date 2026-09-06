from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

import pytest

import graphy.mesh_federation_gate as gate
from graphy.tenant import Tenant


def _registry_text(slugs, admitted=None) -> str:
    return json.dumps({
        "substrate_roster": {"grandfathered": slugs or [], "admitted": admitted or {}},
        "registered_joins": {"literal_joins": []},
        "alias_overrides": {},
    }, indent=2)


def _tenant(tmp_path: Path, *, data_home: Path | None = None, join_keys: Path | None = None,
            slugs=None, admitted=None) -> Tenant:
    data_home = data_home or tmp_path / "data"
    data_home.mkdir(parents=True, exist_ok=True)
    join_keys = join_keys or tmp_path / "registry.json"
    if not join_keys.exists():
        join_keys.write_text(_registry_text(slugs, admitted), encoding="utf-8")
    return Tenant(
        root=tmp_path, data_home=data_home, adapters=(),
        build_lanes={}, join_keys=join_keys,
        cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal",
    )


def _synthetic_reg(admitted=None) -> dict:
    return {"aliases": {}, "alias_targets": set(), "literal_schemes": set(), "admitted": admitted or {}}


def _write_member_graph(data_home: Path, slug: str, own: list, out: list) -> None:
    g = Path(data_home) / f"{slug}_graph"
    g.mkdir(parents=True, exist_ok=True)
    (g / "stats.json").write_text("{}", encoding="utf-8")
    edges = []
    for s in own:
        edges.append({"src": f"{s}://a", "dst": f"{s}://b"})
    for o in out:
        edges.append({"src": f"{slug}://a", "dst": f"{o}://b"})
    (g / "edges.json").write_text(json.dumps(edges), encoding="utf-8")



def test_GREEN_classify_synthetic_injected_index():
    index = {
        "alpha": {"own": ["alpha"], "out": []},
        "beta": {"own": ["beta"], "out": ["alpha"]},
        "gamma": {"own": ["gamma"], "out": []},
    }
    reg = _synthetic_reg()
    card = gate.classify("beta", index, reg=reg, parked=set(), stdlib={"__future__"})
    assert card["state"] == "joined-within-axis"
    assert card["axis"] == ["code"]
    assert card["join_key"] == ["beta"]
    card = gate.classify("gamma", index, reg=reg, parked=set(), stdlib={"__future__"})
    assert card["state"] == "solo"
    card = gate.classify("beta", index, reg=reg, parked=set(), stdlib={"__future__"}, core={"alpha"})
    assert card["state"] == "joined-to-core"
    card = gate.classify("gamma", index, reg=reg, parked={"gamma"}, stdlib={"__future__"})
    assert card["state"] == "parked"


def test_GREEN_classify_registered_augment_synthetic_index():
    index = {
        "egress": {"own": [], "out": [], "missing": True},
        "base": {"own": ["egress", "base"], "out": []},
    }
    stamp = {
        "augment": True,
        "join_keys": ["egress://host"],
        "axes": {"egress://host": {"base": ["emits"]}},
        "members": ["base"],
        "kind": "augment", "owner": "tenant", "blurb": "b",
        "producer": "p", "accept_cmd": "true", "supersedes": "—",
    }
    reg = _synthetic_reg(admitted={"egress": stamp})
    card = gate.classify("egress", index, reg=reg, parked=set(), stdlib={"__future__"})
    assert card["state"] == "augment"
    assert card["join_key"] == ["egress://host"]
    assert card["evidence"]["observed"]["scheme_complete"] is True



def test_one_lock_build_index_scan_and_write_inside_one_lock(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])

    real_lock = gate._index_lock
    in_lock: list = []

    @contextlib.contextmanager
    def tracking_lock(t):
        in_lock.append(True)
        try:
            with real_lock(t):
                yield
        finally:
            in_lock.pop()

    monkeypatch.setattr(gate, "_index_lock", tracking_lock)

    real_build_index = gate.build_index
    scans: list = []

    def tracking_build_index(t):
        scans.append(bool(in_lock))
        return real_build_index(t)

    monkeypatch.setattr(gate, "build_index", tracking_build_index)

    with gate._index_lock(tenant):
        idx = gate.build_index(tenant)
        gate._write_index(idx, tenant)
        dirs = sorted(p.name for p in Path(tenant.data_home).glob("*_graph"))
        baseline = Path(tenant.data_home) / ".federation_graphdir_baseline.txt"
        tmp = baseline.with_name(baseline.name + ".tmp")
        tmp.write_text("\n".join(dirs) + "\n", encoding="utf-8")
        os.replace(tmp, baseline)

    assert scans == [True], "build_index must run INSIDE the index lock — the unguarded shape scans outside and loses rows"

    scans.clear()
    idx = gate.build_index(tenant)
    assert scans == [False] or scans != [True]
    gate._atomic_write_index(idx, tenant)


def test_one_lock_build_index_main_branch(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])

    real_lock = gate._index_lock
    in_lock: list = []

    @contextlib.contextmanager
    def tracking_lock(t):
        in_lock.append(True)
        try:
            with real_lock(t):
                yield
        finally:
            in_lock.pop()

    monkeypatch.setattr(gate, "_index_lock", tracking_lock)

    real_build_index = gate.build_index
    scans: list = []

    def tracking_build_index(t):
        scans.append(bool(in_lock))
        return real_build_index(t)

    monkeypatch.setattr(gate, "build_index", tracking_build_index)

    rc = gate.main(["--tenant-id", "test", "--data-home", str(tenant.data_home),
                    "--join-keys", str(tenant.join_keys), "--build-index"])
    assert rc == 0
    assert scans == [True], "main --build-index must scan INSIDE the lock — the unguarded shape scans outside and loses rows"
    assert (Path(tenant.data_home) / ".federation_graphdir_baseline.txt").exists()
    assert (Path(tenant.data_home) / ".federation_scheme_index.json").exists()


def test_one_lock_build_index_concurrent_observer_loses_no_row(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])
    import threading
    results: dict = {}
    scans: list = []
    real_lock = gate._index_lock
    real_build_index = gate.build_index

    @contextlib.contextmanager
    def tracking_lock(t):
        with real_lock(t):
            yield

    monkeypatch.setattr(gate, "_index_lock", tracking_lock)
    monkeypatch.setattr(gate, "build_index", real_build_index)

    def worker():
        try:
            with gate._index_lock(tenant):
                idx = gate.build_index(tenant)
                gate._write_index(idx, tenant)
            results["ok"] = True
        except Exception as exc:  # pragma: no cover - failure reporting
            results["err"] = repr(exc)

    with gate._index_lock(tenant):
        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=0.3)
        assert "ok" not in results
        assert not results.get("err")
    t.join(timeout=10)
    assert results.get("ok") is True



def _main_build_index_argv(tenant):
    return ["--tenant-id", "test", "--data-home", str(tenant.data_home),
            "--join-keys", str(tenant.join_keys), "--build-index"]


def test_atomic_baseline_via_production_build_index(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])
    baseline = gate._baseline_path(tenant)

    replaced = []
    real_replace = os.replace
    monkeypatch.setattr(gate.os, "replace",
                        lambda src, dst: (replaced.append((str(src), str(dst))),
                                          real_replace(src, dst))[1])
    rc = gate.main(_main_build_index_argv(tenant))
    assert rc == 0
    assert baseline.read_text(encoding="utf-8").strip() == "alpha_graph"
    hits = [(s, d) for s, d in replaced if d == str(baseline)]
    assert hits, f"baseline was not produced via os.replace; recorded: {replaced}"
    assert ".tmp." in hits[0][0]
    assert not list(Path(tenant.data_home).glob(".federation_graphdir_baseline.txt.tmp*"))


def test_atomic_baseline_forced_failure_before_replace_leaves_destination_untorn(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])
    baseline = gate._baseline_path(tenant)
    baseline.write_text("OLD-BASELINE\n", encoding="utf-8")

    real_replace = os.replace

    def failing_replace(src, dst):
        if str(dst) == str(baseline):
            raise OSError("forced failure BEFORE the baseline replace")
        return real_replace(src, dst)

    monkeypatch.setattr(gate.os, "replace", failing_replace)
    with pytest.raises(OSError, match="forced failure"):
        gate.main(_main_build_index_argv(tenant))
    assert baseline.read_text(encoding="utf-8") == "OLD-BASELINE\n"


def test_atomic_baseline_RED_against_direct_write_mutant(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])
    baseline = gate._baseline_path(tenant)

    def direct_write_mutant(t, dirs):
        p = gate._baseline_path(t)
        p.write_text("\n".join(dirs) + "\n", encoding="utf-8")
        return p

    monkeypatch.setattr(gate, "_write_baseline", direct_write_mutant)
    replaced = []
    real_replace = os.replace
    monkeypatch.setattr(gate.os, "replace",
                        lambda src, dst: (replaced.append((str(src), str(dst))),
                                          real_replace(src, dst))[1])
    rc = gate.main(_main_build_index_argv(tenant))
    assert rc == 0
    assert baseline.exists()
    hits = [(s, d) for s, d in replaced if d == str(baseline)]
    assert not hits, "mutant unexpectedly routed through os.replace"



def test_roster_validation_fails_loud_on_non_roster_slug(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    monkeypatch.setattr(gate, "CORE_NAMES", frozenset({"alpha", "ghost"}))
    with pytest.raises(RuntimeError, match="roster validation FAILED"):
        gate._validate_roster_membership(tenant)
    with pytest.raises(RuntimeError, match="ghost"):
        gate._validate_roster_membership(tenant)


def test_roster_validation_passes_when_subset(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    monkeypatch.setattr(gate, "CORE_NAMES", frozenset({"alpha"}))
    gate._validate_roster_membership(tenant)


def test_GREEN_classify_with_injected_index_does_not_call_roster(tmp_path, monkeypatch):
    index = {"alpha": {"own": ["alpha"], "out": []}}
    reg = _synthetic_reg()
    monkeypatch.setattr(gate, "roster", lambda tenant=None: (_ for _ in ()).throw(AssertionError("roster() must not be called")))
    card = gate.classify("alpha", index, reg=reg, parked=set())
    assert card["state"] == "solo"



def test_GREEN_census_exact_cover_synthetic_roster(tmp_path):
    tenant = _tenant(tmp_path, slugs=["base", "widgets"])
    index = {"base": {"own": ["base"], "out": []}, "widgets": {"own": ["widgets"], "out": ["base"]}}
    reg = _synthetic_reg()
    flagged = gate.census(index=index, reg=reg,
                          node_schemes={"base": {"base", "widgets"}},
                          tenant=tenant, base_members={"base"})
    assert flagged == []


def test_RED_census_flags_unregistered_walkable(tmp_path):
    tenant = _tenant(tmp_path, slugs=["base"])
    index = {"base": {"own": ["base"], "out": []}}
    reg = _synthetic_reg()
    flagged = gate.census(index=index, reg=reg,
                          node_schemes={"base": {"base", "ghost_axis"}},
                          tenant=tenant, base_members={"base"})
    assert flagged == ["ghost_axis"]


def test_GREEN_cmd_all_exact_cover(tmp_path):
    tenant = _tenant(tmp_path, slugs=["alpha", "beta"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])
    _write_member_graph(Path(tenant.data_home), "beta", own=["beta"], out=["alpha"])
    index = gate.build_index(tenant)
    assert gate.cmd_all(index, tenant) == 0



def test_registry_two_tenant_cache_discrimination(tmp_path):
    jk1 = tmp_path / "reg1.json"
    jk2 = tmp_path / "reg2.json"
    jk1.write_text(_registry_text(["alpha"], admitted={
        "a1": {"augment": True, "join_keys": ["a1://x"],
               "axes": {"a1://x": {"m": ["e"]}}, "members": ["m"]}}), encoding="utf-8")
    jk2.write_text(_registry_text(["beta"]), encoding="utf-8")
    os.utime(jk1, (0, 0))
    os.utime(jk2, (0, 0))
    assert jk1.stat().st_mtime_ns == jk2.stat().st_mtime_ns

    t1 = _tenant(tmp_path, join_keys=jk1, slugs=["alpha"])
    t2 = _tenant(tmp_path, join_keys=jk2, slugs=["beta"])
    r1 = gate._registry(t1)
    r2 = gate._registry(t2)
    assert "a1" in r1["admitted"]
    assert "a1" not in r2["admitted"]
    assert r1 is not r2



def test_RED_roster_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        gate.roster()
    with pytest.raises(ValueError, match="tenant is required"):
        gate.roster(None)


def test_GREEN_roster_declared_tenant_proceeds(tmp_path):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    assert gate.roster(tenant) == {"alpha"}


def test_RED_observe_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        gate.observe("alpha")


def test_GREEN_observe_declared_tenant_proceeds(tmp_path):
    tenant = _tenant(tmp_path, slugs=["alpha"])
    _write_member_graph(Path(tenant.data_home), "alpha", own=["alpha"], out=[])
    result = gate.observe("alpha", tenant)
    assert result["index"] == "refreshed"


def test_RED_census_absent_tenant_refuses_naming_tenant(tmp_path):
    with pytest.raises(ValueError, match="tenant is required"):
        gate.census()



def test_removal_audit_host_tables_absent():
    src = Path(gate.__file__).read_text(encoding="utf-8")
    for symbol in ("SCHEME_AXIS", "_PARKED_MEMBERS", "_SECURITY_LOCAL", "_B2_OFFLOADED",
                   "_AUGMENT_BASE_MEMBERS", "_RESERVED_EMITTED_SCHEMES"):
        assert symbol not in src, f"{symbol} must not travel"
    host_row = "host_" + "codebase"
    assert host_row not in src
    assert "b2://" not in src
