"""The shard index: a shard pushed is the shard pulled, byte for byte, or the pull refuses.
Over a directory and over an http base with the same layout; and a `pulled` lane carries the
pull as its command."""
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

import graphy.cli as cli
from graphy import index as shard_index
from graphy.tenant import LANE_KINDS, Tenant

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fastapi_graph"


def _shard(tmp_path: Path, name: str = "alpha_graph", *, version: str = "1.2.3", salt: str = "") -> Path:
    d = tmp_path / name
    d.mkdir(parents=True)
    nodes = {"alpha://module/alpha": {"id": "alpha://module/alpha", "node_type": "module", "salt": salt}}
    edges = [{"src": "alpha://module/alpha", "dst": "beta://module/beta", "edge_type": "imports"}]
    (d / "nodes.json").write_bytes(json.dumps(nodes, indent=2).encode())
    (d / "edges.json").write_bytes(json.dumps(edges, indent=2).encode())
    prov = {
        "surface": f"{name}.records", "oracle_commit": "sha256:" + "a" * 64,
        "corpus": {"scheme": "alpha", "distribution": "alpha", "version": version, "license": "MIT"},
        "counts": {"node_count": 1, "edge_count": 1},
        "files": {f: {"bytes": (d / f).stat().st_size, "sha256": hashlib.sha256((d / f).read_bytes()).hexdigest()}
                  for f in ("nodes.json", "edges.json")},
    }
    (d / "PROVENANCE.json").write_bytes(json.dumps(prov, indent=2).encode())
    return d


def _bytes(d: Path) -> dict[str, bytes]:
    return {f: (d / f).read_bytes() for f in shard_index.SHARD_FILES}


def test_push_pull_round_trip_is_byte_identical(tmp_path: Path) -> None:
    shard = _shard(tmp_path)
    idx = tmp_path / "index"
    m = shard_index.push(shard, idx)
    assert m["name"] == "alpha==1.2.3" and m["state"] == "pushed"
    assert (idx / "shards" / m["address"] / "NOTICE").read_text().startswith("shard alpha==1.2.3")
    assert json.loads((idx / "catalog.json").read_text()) == {"alpha==1.2.3": m["address"]}

    out = tmp_path / "pulled" / "alpha_graph"
    p = shard_index.pull("alpha==1.2.3", str(idx), out)
    assert p["address"] == m["address"] and p["out"] == str(out)
    assert _bytes(out) == _bytes(shard)
    # by address too
    out2 = tmp_path / "pulled2"
    shard_index.pull(m["address"], str(idx), out2)
    assert _bytes(out2) == _bytes(shard)
    # a second push of the same bytes is a no-op the manifest reports
    assert shard_index.push(shard, idx)["state"] == "already indexed"


def test_two_mints_are_two_entries_and_the_name_moves(tmp_path: Path) -> None:
    idx = tmp_path / "index"
    a = shard_index.push(_shard(tmp_path / "one"), idx)
    b = shard_index.push(_shard(tmp_path / "two", salt="x"), idx)
    assert a["address"] != b["address"]
    assert shard_index.catalog(str(idx)) == {"alpha==1.2.3": b["address"]}
    assert (idx / "shards" / a["address"] / "nodes.json").is_file()  # the old entry is still addressable


def test_pull_refuses_tampered_bytes_and_lands_nothing(tmp_path: Path) -> None:
    idx = tmp_path / "index"
    m = shard_index.push(_shard(tmp_path), idx)
    entry = idx / "shards" / m["address"] / "edges.json"
    entry.write_bytes(entry.read_bytes().replace(b"imports", b"IMPORTS"))
    out = tmp_path / "out"
    with pytest.raises(shard_index.IndexError_, match="does not match the manifest"):
        shard_index.pull("alpha==1.2.3", str(idx), out)
    assert not out.exists()
    assert [r[2] is not None for r in shard_index.verify_index(str(idx))] == [True]
    # the manifest rewritten to fit the tampered bytes still fails: the address is the content
    man = idx / "shards" / m["address"] / shard_index.MANIFEST_NAME
    row = json.loads(man.read_text())
    row["files"]["edges.json"]["sha256"] = hashlib.sha256(entry.read_bytes()).hexdigest()
    man.write_text(json.dumps(row))
    with pytest.raises(shard_index.IndexError_, match="do not hash to their address"):
        shard_index.pull("alpha==1.2.3", str(idx), out)
    assert not out.exists()


def test_push_refuses_a_shard_edited_after_its_mint(tmp_path: Path) -> None:
    shard = _shard(tmp_path)
    (shard / "nodes.json").write_bytes(b"{}")
    with pytest.raises(shard_index.IndexError_, match="edited after the mint"):
        shard_index.push(shard, tmp_path / "index")


def test_fixture_shard_names_itself_and_pulls_identical(tmp_path: Path) -> None:
    idx = tmp_path / "index"
    m = shard_index.push(FIXTURE, idx)  # the PROVENANCE carries distribution==version: no --name needed
    assert m["name"] == "fastapi==0.139.0"
    out = tmp_path / "fastapi_graph"
    shard_index.pull("fastapi==0.139.0", str(idx), out)
    assert _bytes(out) == _bytes(FIXTURE)
    assert m["counts"]["node_count"] == 507


def test_refusals(tmp_path: Path) -> None:
    idx = tmp_path / "index"
    shard_index.push(_shard(tmp_path), idx)
    with pytest.raises(shard_index.IndexError_, match="not in the index"):
        shard_index.pull("nothing==1.0", str(idx), tmp_path / "x")
    with pytest.raises(shard_index.IndexError_, match="must be absolute"):
        shard_index.pull("alpha==1.2.3", str(idx), "relative/out")
    with pytest.raises(shard_index.IndexError_, match="must be absolute"):
        shard_index.pull("alpha==1.2.3", "relative/index", tmp_path / "x")
    (tmp_path / "live").mkdir()
    with pytest.raises(shard_index.IndexError_, match="never overwrites"):
        shard_index.pull("alpha==1.2.3", str(idx), tmp_path / "live")
    with pytest.raises(shard_index.IndexError_, match="grammar"):
        shard_index.push(_shard(tmp_path / "s2"), idx, name="../escape")
    with pytest.raises(shard_index.IndexError_, match="impersonates"):
        shard_index.push(_shard(tmp_path / "s3"), idx, name="f" * 64)


def test_pull_over_http_is_byte_identical(tmp_path: Path) -> None:
    idx = tmp_path / "index"
    shard = _shard(tmp_path)
    m = shard_index.push(shard, idx)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(idx))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        out = tmp_path / "http_out"
        p = shard_index.pull("alpha==1.2.3", base, out)
        assert p["address"] == m["address"] and _bytes(out) == _bytes(shard)
        assert shard_index.catalog(base) == {"alpha==1.2.3": m["address"]}
        assert shard_index.verify_index(base) == [("alpha==1.2.3", m["address"], None)]
        with pytest.raises(shard_index.IndexError_, match="not in the index"):
            shard_index.pull("nothing==1.0", base, tmp_path / "y")
    finally:
        srv.shutdown()
        srv.server_close()


def test_cli_verbs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shard = _shard(tmp_path)
    idx = tmp_path / "index"
    assert cli.main(["push", str(shard), "--index", str(idx)]) == 0
    assert "PUSH OK: alpha==1.2.3" in capsys.readouterr().out
    assert cli.main(["index", "--index", str(idx)]) == 0
    assert "INDEX: 1 named shard(s)" in capsys.readouterr().out
    out = tmp_path / "out"
    assert cli.main(["pull", "alpha==1.2.3", "--index", str(idx), "--out", str(out)]) == 0
    assert "PULL OK" in capsys.readouterr().out and _bytes(out) == _bytes(shard)
    assert cli.main(["index", "--index", str(idx), "--verify"]) == 0
    assert "INDEX OK" in capsys.readouterr().out
    assert cli.main(["pull", "--index", str(idx)]) == 2
    assert "PULL REFUSED" in capsys.readouterr().err
    assert cli.main(["push", str(shard)]) == 2
    assert cli.main(["pull", "nothing", "--index", str(idx), "--out", str(tmp_path / "z")]) == 2


def test_pulled_lane_carries_its_command(tmp_path: Path) -> None:
    assert "pulled" in LANE_KINDS
    lanes = cli._parse_lanes(["a_graph:static-dep",
                              "b_graph:pulled=python3 -m graphy pull b==1.0 --index /idx --out {out}"])
    assert lanes == {"a_graph": (None, "static-dep"),
                     "b_graph": ("python3 -m graphy pull b==1.0 --index /idx --out {out}", "pulled")}
    t = Tenant(root=tmp_path, data_home=tmp_path / "sub", adapters=("python_ast",), build_lanes=lanes,
               join_keys=tmp_path / "r.json", cursor="sha256:" + "0" * 64, policy="refuse",
               journal=tmp_path / "j")
    assert t.build_lanes["b_graph"][1] == "pulled"
    with pytest.raises(ValueError, match="KEY:KIND"):
        cli._parse_lanes(["no-kind"])
