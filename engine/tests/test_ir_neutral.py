"""The IR is the overlay: a shard whose nodes carry no `.py` path and no Python name gives
pillars, arms, the doors and the bridge the same answers as its Python-shaped twin, because every
consumer reads the producer's `module` and `role` fields and the scheme index's `standard` list —
never a filename, never the running interpreter. A floor for issue 18."""
from __future__ import annotations

import json
from pathlib import Path

import graphy.arms as arms
import graphy.bridge as bridge
import graphy.doors as doors
import graphy.fanout as fanout
import graphy.federated_store as fs
import graphy.pillars as pillars
from graphy.tenant import Tenant


def _twin(root: Path, name: str, ext: str, srcdir: str, std: str) -> tuple[Tenant, list[str]]:
    """A package `pkg` with a hub, a base and a test, and a ring shard `lib` it inherits from;
    `std://` is the ecosystem's standard library. Only the file shapes and the standard scheme
    differ between the twins."""
    def file_of(mod: str) -> str:
        return srcdir + "/" + mod.replace(".", "/") + ext

    def node(nid: str, node_type: str, role: str | None = None) -> dict:
        dotted = nid.split("/", 3)[-1]
        mod = dotted if node_type == "module" else dotted.rsplit(".", 1)[0]
        if node_type == "method":
            mod = mod.rsplit(".", 1)[0]
        rec = {"kind": "node", "node_type": node_type, "id": nid, "name": dotted.rsplit(".", 1)[-1],
               "dotted": dotted, "module": mod, "file": file_of(mod), "line": 1}
        if role:
            rec["role"] = role
        return rec

    data_home = root / "data"
    data_home.mkdir(parents=True)
    pkg = [node("pkg://module/pkg", "module"), node("pkg://module/pkg.hub", "module"),
           node("pkg://class/pkg.hub.Hub", "class"), node("pkg://method/pkg.hub.Hub.run", "method"),
           node("pkg://func/pkg.hub.spin", "func"), node("pkg://module/pkg.base", "module"),
           node("pkg://class/pkg.base.Base", "class"), node("pkg://func/pkg.base.prim", "func"),
           node("pkg://module/pkg.tests.test_hub", "module"),
           node("pkg://func/pkg.tests.test_hub.test_spin", "func", role="test")]
    pkg_edges = [
        {"kind": "edge", "edge_type": "contains", "src": "pkg://module/pkg.hub", "dst": "pkg://class/pkg.hub.Hub"},
        {"kind": "edge", "edge_type": "contains", "src": "pkg://module/pkg.hub", "dst": "pkg://func/pkg.hub.spin"},
        {"kind": "edge", "edge_type": "contains", "src": "pkg://module/pkg.base", "dst": "pkg://func/pkg.base.prim"},
        {"kind": "edge", "edge_type": "inherits", "src": "pkg://class/pkg.hub.Hub", "dst": "pkg://class/pkg.base.Base"},
        {"kind": "edge", "edge_type": "inherits", "src": "pkg://class/pkg.base.Base", "dst": "lib://class/lib.core.Thing"},
        {"kind": "edge", "edge_type": "calls", "src": "pkg://func/pkg.hub.spin", "dst": "pkg://func/pkg.base.prim"},
        {"kind": "edge", "edge_type": "calls", "src": "pkg://func/pkg.hub.spin", "dst": "pkg://func/pkg.base.prim"},
        {"kind": "edge", "edge_type": "calls", "src": "pkg://func/pkg.tests.test_hub.test_spin", "dst": "pkg://func/pkg.hub.spin"},
        {"kind": "edge", "edge_type": "imports", "src": "pkg://module/pkg.hub", "dst": f"{std}://module/{std}"},
    ]
    lib = [node("lib://module/lib.core", "module"), node("lib://class/lib.core.Thing", "class")]
    for slug, nodes, edges in (("pkg", pkg, pkg_edges), ("lib", lib, [])):
        d = data_home / f"{slug}_graph"
        d.mkdir()
        (d / "nodes.json").write_text(json.dumps({n["id"]: n for n in nodes}), encoding="utf-8")
        (d / "edges.json").write_text(json.dumps(edges), encoding="utf-8")
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {"standard": [std]}, "pkg": {"own": ["pkg"], "out": ["lib", std]}, "lib": {"own": ["lib"], "out": []},
    }), encoding="utf-8")
    join_keys = data_home / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    tenant = Tenant(root=root, data_home=data_home, adapters=(), join_keys=join_keys, journal=data_home / "journal",
                    build_lanes={"pkg_graph": (None, "static-dep"), "lib_graph": (None, "static-dep")},
                    cursor="sha256:" + "0" * 64, policy="refuse")
    roster = ["lib", "pkg"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id=name)
    return tenant, roster


def _cut(tmp_path: Path) -> fanout.Cut:
    p = tmp_path / "partition.json"
    p.write_text(json.dumps({"groups": {"HUB": ["pkg.hub"], "BASE": ["pkg.base"]}, "rest": "EDGE"}), encoding="utf-8")
    return fanout.load_partition(p)


def test_GREEN_a_non_python_shard_reads_the_same_through_every_consumer(tmp_path):
    py_t, py_r = _twin(tmp_path / "py", "py", ".py", "pkg", "os")
    ts_t, ts_r = _twin(tmp_path / "ts", "ts", ".ts", "src", "node:fs".replace(":", "_"))
    py = fs.open_for(py_r, tenant=py_t, tenant_id="py")
    ts = fs.open_for(ts_r, tenant=ts_t, tenant_id="ts")

    # the standard library is what the scheme index says: the import lands as a wire node, not an unresolved edge
    assert py.membership("os://module/os") == "wire" and ts.membership("node_fs://module/node_fs") == "wire"

    # pillars: the same module graph, ruled from `module`, never from a path
    gpy, gts = pillars.module_graph(py, "pkg"), pillars.module_graph(ts, "pkg")
    assert (gpy.size, gpy.weight, gpy.modules) == (gts.size, gts.weight, gts.modules)

    # arms: byte-identical regions (the body names symbols and modules, never files)
    cut = _cut(tmp_path)
    rpy = arms.render_all(py, "pkg", cut, tenant_dir="tenants/pkg", tenant_id="pkg")
    rts = arms.render_all(ts, "pkg", cut, tenant_dir="tenants/pkg", tenant_id="pkg")
    assert {k: v.body for k, v in rpy.items()} == {k: v.body for k, v in rts.items()}
    assert "- `base.Base` ──inherits──▶ `lib.core.Thing` lib" in rts["BASE"].body

    # doors: what a test is comes from the producer's `role`, not a filename
    for store in (py, ts):
        e = doors.explain(store, "pkg://func/pkg.hub.spin")
        assert [t.node for t in e.tests] == ["pkg://func/pkg.tests.test_hub.test_spin"]

    # the bridge: two twins in one process, crossing on the ring literal both minted
    sides = bridge.open_sides([(py_t, "py"), (ts_t, "ts")], roster_of=lambda t: py_r)
    bridge.verify_joins(sides, ["lib"])
    res = bridge.cross(sides, ["lib"], "pkg://func/pkg.hub.spin", "pkg://class/pkg.base.Base")
    assert res.found and res.crossings == 0            # home first: the same package on the near side
    res = bridge.cross(sides, ["lib"], "lib://class/lib.core.Thing", "pkg://class/pkg.hub.Hub")
    assert res.found


def test_RED_a_record_without_module_is_skipped_never_derived(tmp_path):
    assert pillars._module_of({"node_type": "func", "dotted": "pkg.hub.spin", "file": "pkg/hub.py"}, "pkg://func/pkg.hub.spin") is None
    assert pillars._module_of({"module": "pkg.hub"}, "x") == "pkg.hub"
    assert pillars._module_of(None, "x") is None
