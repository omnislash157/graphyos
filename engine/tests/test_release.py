"""The version-identity law at the seam: a node id is a name, the roster is the resolution, two
releases of one scheme refuse in build, check and the bridge. A floor for issue 19."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.bridge as bridge
import graphy.cli as cli
import graphy.federated_store as fs
import graphy.release as release
from graphy.tenant import Tenant


def _shard(d: Path, scheme: str, version: str | None, extra_nodes: dict | None = None) -> None:
    d.mkdir(parents=True)
    nodes = {f"{scheme}://module/{scheme}": {"kind": "node", "node_type": "module", "id": f"{scheme}://module/{scheme}",
                                             "dotted": scheme, "module": scheme, "file": f"{scheme}/__init__.py"}}
    nodes.update(extra_nodes or {})
    (d / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (d / "edges.json").write_text(json.dumps([]), encoding="utf-8")
    if version is not None:
        (d / "PROVENANCE.json").write_text(json.dumps({
            "corpus": {"scheme": scheme, "distribution": scheme, "version": version}}), encoding="utf-8")


def _tenant(root: Path, lanes: dict[str, list[str]], std_version: str | None) -> tuple[Tenant, Path, list[str]]:
    """A tenant whose `app` imports `std`; `std_graph` is pinned to std_version (None: unpinned)."""
    home = root / "data"
    _shard(home / "app_graph", "app", "1.0", {
        "app://func/app.entry": {"kind": "node", "node_type": "func", "id": "app://func/app.entry", "dotted": "app.entry",
                                 "module": "app", "file": "app/__init__.py"}})
    (home / "app_graph" / "edges.json").write_text(json.dumps([
        {"kind": "edge", "edge_type": "imports", "src": "app://module/app", "dst": "std://module/std"}]), encoding="utf-8")
    _shard(home / "std_graph", "std", std_version)
    index = {"_meta": {}, "app": {"own": ["app"], "out": ["std"]}, "std": {"own": ["std"], "out": []}}
    for extra in lanes:
        if extra not in ("app_graph", "std_graph"):
            index[extra[:-len("_graph")]] = {"own": lanes[extra], "out": []}
    (home / ".federation_scheme_index.json").write_text(json.dumps(index), encoding="utf-8")
    jk = home / "registry.json"
    jk.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    bl = {k: (None, "static-dep") for k in lanes}
    t = Tenant(root=root, data_home=home, adapters=(), build_lanes=bl, join_keys=jk, cursor="sha256:" + "0" * 64,
               policy="refuse", journal=home / "journal")
    desc = root / "tenant.json"
    desc.write_text(json.dumps({"root": str(root), "data_home": str(home), "adapters": [],
                                "build_lanes": {k: [None, "static-dep"] for k in lanes}, "join_keys": str(jk),
                                "cursor": "sha256:" + "0" * 64, "policy": "refuse", "journal": str(home / "journal")}),
                    encoding="utf-8")
    return t, desc, sorted(k[:-len("_graph")] for k in lanes)


def test_GREEN_release_of_reads_the_provenance_or_says_unpinned(tmp_path):
    _shard(tmp_path / "x_graph", "x", "2.1")
    r = release.release_of(tmp_path / "x_graph")
    assert (r.slug, r.scheme, r.pin) == ("x", "x", "x==2.1")
    _shard(tmp_path / "y_graph", "y", None)
    assert release.release_of(tmp_path / "y_graph") is None
    assert release.release_of(tmp_path / "nowhere_graph") is None


def test_RED_build_and_check_refuse_two_releases_of_one_scheme(tmp_path, capsys):
    lanes = {"app_graph": ["app"], "std_graph": ["std"], "std_old_graph": ["std"]}
    t, desc, roster = _tenant(tmp_path, lanes, "4.16")
    _shard(t.data_home / "std_old_graph", "std", "4.12")
    rel = release.roster_releases(t.data_home, roster)
    assert release.collisions(rel) == [("std", {"std": "std==4.16", "std_old": "std==4.12"})]
    with pytest.raises(release.ReleaseError, match="std_graph=std==4.16, std_old_graph=std==4.12"):
        release.require_one_release(t.data_home, roster)
    rc = cli.main(["build", "--tenant", str(desc), "--tenant-id", "t"])
    assert rc == 2 and "BUILD REFUSED: two releases of one scheme" in capsys.readouterr().err
    rc = cli.main(["check", "--tenant", str(desc), "--tenant-id", "t"])
    err = capsys.readouterr().err
    assert rc == 1 and "CHECK RED: release lane: scheme 'std' is owned under two releases" in err
    # an unpinned shard beside a pinned one is a collision too: the roster cannot say which release the literal means
    (t.data_home / "std_old_graph" / "PROVENANCE.json").unlink()
    assert release.collisions(release.roster_releases(t.data_home, roster)) == [
        ("std", {"std": "std==4.16", "std_old": "unpinned"})]


def test_GREEN_one_release_per_scheme_builds(tmp_path, capsys):
    t, desc, roster = _tenant(tmp_path, {"app_graph": ["app"], "std_graph": ["std"]}, "4.16")
    assert release.collisions(release.roster_releases(t.data_home, roster)) == []
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    assert "BUILD OK" in capsys.readouterr().out


def _two(tmp_path, a_version, b_version):
    ta, da, ra = _tenant(tmp_path / "a", {"app_graph": ["app"], "std_graph": ["std"]}, a_version)
    tb, db, rb = _tenant(tmp_path / "b", {"app_graph": ["app"], "std_graph": ["std"]}, b_version)
    for t, r, n in ((ta, ra, "a"), (tb, rb, "b")):
        fs.compile_store(r, fs.store_path_for(r, tenant=t), tenant=t, tenant_id=n)
    sides = bridge.open_sides([(ta, "a"), (tb, "b")], roster_of=lambda t: ra)
    return sides, da, db


def test_GREEN_bridge_receipt_prints_each_side_release(tmp_path):
    sides, _, _ = _two(tmp_path, "4.16", "4.16")
    receipt = bridge.verify_joins(sides, ["std"], roster_of=lambda t: ["app", "std"])
    assert receipt["std"]["a"] == {"nodes": 1, "release": "std==4.16", "skew": False}
    assert receipt["std"]["b"]["release"] == "std==4.16"
    text, _ = bridge.render(bridge.cross(sides, ["std"], "app://module/app", "app://func/app.entry"), receipt)
    assert "JOIN std: a holds 1 node(s) at std==4.16 · b holds 1 node(s) at std==4.16" in text


def test_RED_bridge_refuses_release_skew_unless_carried(tmp_path, capsys):
    sides, da, db = _two(tmp_path, "4.16", "4.12")
    with pytest.raises(bridge.BridgeError, match=r"pin different releases \(a std==4.16 · b std==4.12\)"):
        bridge.verify_joins(sides, ["std"], roster_of=lambda t: ["app", "std"])
    receipt = bridge.verify_joins(sides, ["std"], roster_of=lambda t: ["app", "std"], allow_skew=True)
    assert receipt["std"]["a"]["skew"] and receipt["std"]["b"]["skew"]
    text, rc = bridge.render(bridge.cross(sides, ["std"], "app://func/app.entry", "app://module/app"), receipt)
    assert "JOIN std SKEW: the sides pin different releases and the operator carries it" in text
    base = ["bridge", "--tenant", str(da), "--tenant-id", "a", "--tenant", str(db), "--tenant-id", "b", "--join", "std",
            "--seed", "app://module/app", "--target", "std://module/std"]
    assert cli.main(base) == 2 and "pin different releases" in capsys.readouterr().err
    assert cli.main(base + ["--allow-release-skew"]) == 0 and "JOIN std SKEW" in capsys.readouterr().out
    # an unpinned side against a pinned one is not a skew the law can rule on: it is printed as unpinned and crosses
    sides, _, _ = _two(tmp_path / "u", "4.16", None)
    receipt = bridge.verify_joins(sides, ["std"], roster_of=lambda t: ["app", "std"])
    assert receipt["std"]["b"]["release"] == "unpinned" and not receipt["std"]["a"]["skew"]
