"""The bridge: two tenants in one process, neither reading the other's data_home, and a walk that
crosses between them only on a declared join. A floor, never the proof — the proof is the
FastAPI → SQLAlchemy run in RECON."""
from __future__ import annotations

import builtins
import json
import sqlite3
from pathlib import Path

import pytest

import graphy.bridge as bridge
import graphy.cli as cli
import graphy.federated_store as fs
from graphy.tenant import Tenant

SHARED = "shared://module/shared"            # the literal both tenants carry
SHARED_FN = "shared://func/shared.helper"
PRIVATE = "twin://module/twin"               # spelled the same on both sides, never declared


def _write_graph(dirpath: Path, nodes: dict, edges: list) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (dirpath / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def _node(nid: str, node_type: str = "func") -> dict:
    dotted = nid.split("/", 3)[-1]
    return {"kind": "node", "node_type": node_type, "id": nid, "name": dotted.rsplit(".", 1)[-1],
            "dotted": dotted, "file": dotted.replace(".", "/") + ".py", "line": 1}


def _tenant(root: Path, name: str, own: str) -> tuple[Tenant, Path, list[str]]:
    """A tenant whose package `own` imports the shared package and the twin package; every file
    of it lives under its own root/data_home."""
    data_home = root / "data"
    data_home.mkdir(parents=True)
    _write_graph(data_home / f"{own}_graph", {
        f"{own}://module/{own}": _node(f"{own}://module/{own}", "module"),
        f"{own}://func/{own}.entry": _node(f"{own}://func/{own}.entry"),
    }, [
        {"kind": "edge", "edge_type": "contains", "src": f"{own}://module/{own}", "dst": f"{own}://func/{own}.entry"},
        {"kind": "edge", "edge_type": "calls", "src": f"{own}://func/{own}.entry", "dst": SHARED_FN, "line": 2},
        {"kind": "edge", "edge_type": "imports", "src": f"{own}://module/{own}", "dst": PRIVATE, "line": 1},
    ])
    _write_graph(data_home / "shared_graph", {SHARED: _node(SHARED, "module"), SHARED_FN: _node(SHARED_FN)},
                 [{"kind": "edge", "edge_type": "contains", "src": SHARED, "dst": SHARED_FN}])
    _write_graph(data_home / "twin_graph", {PRIVATE: _node(PRIVATE, "module")}, [])
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, own: {"own": [own], "out": ["shared", "twin"]},
        "shared": {"own": ["shared"], "out": []}, "twin": {"own": ["twin"], "out": []},
    }), encoding="utf-8")
    join_keys = data_home / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    lanes = {f"{own}_graph": (None, "static-dep"), "shared_graph": (None, "static-dep"), "twin_graph": (None, "static-dep")}
    tenant = Tenant(root=root, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=data_home / "journal")
    roster = sorted([own, "shared", "twin"])
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id=name)
    desc = root / "tenant.json"
    desc.write_text(json.dumps({
        "root": str(root), "data_home": str(data_home), "adapters": [],
        "build_lanes": {k: [None, v[1]] for k, v in lanes.items()}, "join_keys": str(join_keys),
        "cursor": "sha256:" + "0" * 64, "policy": "refuse", "journal": str(data_home / "journal")}), encoding="utf-8")
    return tenant, desc, roster


@pytest.fixture
def two(tmp_path):
    a = _tenant(tmp_path / "a", "alpha", "alpha")
    b = _tenant(tmp_path / "b", "beta", "beta")
    return a, b


class _Recorder:
    """Every path the process opens — builtins.open and sqlite3.connect — labelled by the side
    ``open_for`` was serving when it happened."""

    def __init__(self, monkeypatch):
        self.paths: list[tuple[str, Path]] = []
        self.phase = "-"
        real_open, real_connect, real_open_for = builtins.open, sqlite3.connect, fs.open_for

        def rec_open(file, *a, **k):
            if isinstance(file, (str, Path)):
                self.paths.append((self.phase, Path(file)))
            return real_open(file, *a, **k)

        def rec_connect(db, *a, **k):
            s = str(db)
            if s.startswith("file:"):
                s = s[5:].split("?", 1)[0]
            self.paths.append((self.phase, Path(s)))
            return real_connect(db, *a, **k)

        def rec_open_for(substrates, *, tenant=None, tenant_id=None, **k):
            self.phase = tenant_id
            try:
                return real_open_for(substrates, tenant=tenant, tenant_id=tenant_id, **k)
            finally:
                self.phase = "-"

        monkeypatch.setattr(builtins, "open", rec_open)
        monkeypatch.setattr(sqlite3, "connect", rec_connect)
        monkeypatch.setattr(fs, "open_for", rec_open_for)

    def of(self, phase: str) -> list[Path]:
        return [p for ph, p in self.paths if ph == phase]


def _under(p: Path, home: Path) -> bool:
    home = home.resolve()
    return p.resolve() == home or home in p.resolve().parents


def test_GREEN_two_tenants_open_in_one_process_and_neither_reads_the_other(two, monkeypatch):
    (ta, _da, ra), (tb, _db, rb) = two
    rec = _Recorder(monkeypatch)
    sides = bridge.open_sides([(ta, "alpha"), (tb, "beta")], roster_of=lambda t: ra if t is ta else rb)
    alpha, beta = rec.of("alpha"), rec.of("beta")
    assert alpha and beta, "opening a store reads its inputs — nothing recorded means the recorder is off"
    assert all(_under(p, ta.data_home) for p in alpha), [p for p in alpha if not _under(p, ta.data_home)]
    assert all(_under(p, tb.data_home) for p in beta), [p for p in beta if not _under(p, tb.data_home)]
    assert not any(_under(p, tb.data_home) for p in alpha)
    assert not any(_under(p, ta.data_home) for p in beta)
    assert sides[0].store.membership("alpha://func/alpha.entry") == "alpha"
    assert sides[0].store.membership("beta://func/beta.entry") is None
    assert sides[1].store.membership("beta://func/beta.entry") == "beta"
    assert sides[1].store.membership("alpha://func/alpha.entry") is None


def test_GREEN_declared_join_crosses_on_the_literal_with_the_hops(two):
    (ta, _, ra), (tb, _, rb) = two
    sides = bridge.open_sides([(ta, "alpha"), (tb, "beta")], roster_of=lambda t: ra if t is ta else rb)
    receipt = bridge.verify_joins(sides, ["shared"])
    assert {tid: r["nodes"] for tid, r in receipt["shared"].items()} == {"alpha": 2, "beta": 2}
    assert {r["release"] for r in receipt["shared"].values()} == {"unpinned"}     # synthetic shards carry no PROVENANCE
    res = bridge.cross(sides, ["shared"], "alpha://func/alpha.entry", "beta://func/beta.entry")
    assert res.found and res.crossings == 1
    crossing = [h for h in res.hops if h.crossing][0]
    assert crossing.src == crossing.dst == SHARED_FN
    assert (crossing.side_src, crossing.side_dst) == ("alpha", "beta")
    assert crossing.direction == "shared"
    text, rc = bridge.render(res, receipt)
    assert rc == 0 and "==join shared==> [beta] shared://func/shared.helper" in text
    assert "JOIN shared: alpha holds 2 node(s) at unpinned · beta holds 2 node(s) at unpinned" in text


def test_RED_no_join_refuses_and_an_undeclared_twin_never_crosses(two):
    (ta, _, ra), (tb, _, rb) = two
    sides = bridge.open_sides([(ta, "alpha"), (tb, "beta")], roster_of=lambda t: ra if t is ta else rb)
    with pytest.raises(bridge.BridgeError, match="no --join declared"):
        bridge.verify_joins(sides, [])
    with pytest.raises(bridge.BridgeError, match="no node under pydantic://"):
        bridge.verify_joins(sides, ["pydantic"])
    with pytest.raises(bridge.BridgeError, match="not a scheme"):
        bridge.verify_joins(sides, ["shared://"])
    # twin:// is spelled the same on both sides; declared only `shared`, the walk cannot use it
    res = bridge.cross(sides, ["shared"], "alpha://module/alpha", "twin://module/twin")
    assert res.found and res.crossings == 0                      # alpha's own twin node
    res = bridge.cross(sides, ["twin"], "alpha://module/alpha", "beta://module/beta")
    assert res.found and res.crossings == 1 and res.hops[1].direction == "twin"
    # with a join declared but no route through it, the answer is NO-PATH, never a guess
    res = bridge.cross(sides, ["shared"], "alpha://module/alpha", "beta://module/beta", max_depth=1)
    assert not res.found and res.stopped_by == "max_depth"


def test_RED_one_tenant_twice_or_one_side_is_refused(two):
    (ta, _, ra), (tb, _, rb) = two
    with pytest.raises(bridge.BridgeError, match="share the data_home"):
        bridge.open_sides([(ta, "alpha"), (ta, "alpha-again")], roster_of=lambda t: ra)
    with pytest.raises(bridge.BridgeError, match="names two sides"):
        bridge.open_sides([(ta, "alpha"), (tb, "alpha")], roster_of=lambda t: ra if t is ta else rb)
    with pytest.raises(bridge.BridgeError, match="needs two tenants"):
        bridge.open_sides([(ta, "alpha")], roster_of=lambda t: ra)


def test_GREEN_cli_bridge_prints_the_hops_and_exits_by_verdict(two, capsys):
    (_, da, _), (_, db, _) = two
    base = ["bridge", "--tenant", str(da), "--tenant-id", "alpha", "--tenant", str(db), "--tenant-id", "beta"]
    rc = cli.main(base + ["--join", "shared", "--seed", "alpha://func/alpha.entry", "--target", "beta://func/beta.entry"])
    out = capsys.readouterr().out
    assert rc == 0 and "BRIDGE PATH:" in out and "crossings=1" in out and "BRIDGE: alpha reads=" in out
    rc = cli.main(base + ["--seed", "alpha://func/alpha.entry", "--target", "beta://func/beta.entry"])
    assert rc == 2 and "no --join declared" in capsys.readouterr().err
    rc = cli.main(base + ["--join", "shared", "--seed", "alpha://func/alpha.entry", "--target", "nowhere://x/y"])
    assert rc == 1 and "target nowhere://x/y absent" in capsys.readouterr().out
    rc = cli.main(["bridge", "--tenant", str(da), "--tenant-id", "alpha", "--join", "shared", "--seed", "a", "--target", "b"])
    assert rc == 2 and "exactly two --tenant" in capsys.readouterr().err
