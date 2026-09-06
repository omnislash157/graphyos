"""The container. Without duckdb the JSON path is the reader and every door says so by name;
with it, two parquets and a receipt land beside each shard, the estate is one view, and a
container older than its shard reads as stale."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.cli as cli
from graphy import container
from graphy import smash
from test_smash import _site

HAVE = container.have_duckdb()
needs_duckdb = pytest.mark.skipif(not HAVE, reason="duckdb not installed: pip install 'graphyos[estate]'")


def _ring(tmp_path: Path):
    sp = _site(tmp_path)
    home = tmp_path / "home"
    receipt = smash.smash("alpha", site_packages=sp, out=home)
    return home, sorted(m["slug"] for m in receipt["minted"].values())


def _tenant(tmp_path: Path, home: Path, slugs: list[str]) -> Path:
    desc = tmp_path / "tenant.json"
    rc = cli.main(["init", "--tenant", str(desc), "--root", str(tmp_path), "--data-home", str(home),
                   "--join-keys", str(home / "registry.json"), "--journal", str(home / "journal"),
                   "--cursor", "sha256:" + "0" * 64, "--policy", "refuse", "--adapter", "python_ast"]
                  + [f"--lane={s}_graph:static-dep" for s in slugs])
    assert rc == 0
    (home / ".federation_scheme_index.json").write_text(json.dumps(
        {"_meta": {}, **{s: {"own": [s], "out": []} for s in slugs}}), encoding="utf-8")
    return desc


def test_node_forms_come_from_the_id_alone():
    assert container.node_forms("t://class/pkg.Foo") == ("pkg.Foo", "Foo", "class")
    assert container.node_forms("t://module/pkg") == ("pkg", "pkg", "module")
    assert container.node_forms("bare") == ("bare", "bare", "")


def test_verify_says_absent_before_anything_is_emitted(tmp_path):
    home, slugs = _ring(tmp_path)
    assert container.verify(home / "alpha_graph") == "absent"


@pytest.mark.skipif(HAVE, reason="this is the no-duckdb path")
def test_RED_without_duckdb_emit_refuses_with_the_install_line_and_build_says_skipped(tmp_path, capsys):
    home, slugs = _ring(tmp_path)
    with pytest.raises(container.ContainerError, match="graphyos\\[estate\\]"):
        container.emit(home / "alpha_graph")
    desc = _tenant(tmp_path, home, slugs)
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    out = capsys.readouterr().out
    assert "BUILD OK" in out and "CONTAINER SKIPPED: duckdb is not installed" in out
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    assert "no container" in capsys.readouterr().out
    assert cli.main(["estate", "--tenant", str(desc), "--tenant-id", "t"]) == 2
    assert "ESTATE REFUSED" in capsys.readouterr().err


@needs_duckdb
def test_GREEN_emit_writes_both_parquets_and_a_receipt_that_pins_the_shard(tmp_path):
    home, slugs = _ring(tmp_path)
    gd = home / "alpha_graph"
    receipt = container.emit(gd)
    assert {p.name for p in gd.iterdir()} >= {"adjacency.parquet", "nodes.parquet", "container.json"}
    assert receipt["files"]["adjacency.parquet"]["rows"] == len(json.loads((gd / "edges.json").read_text()))
    assert receipt["files"]["nodes.parquet"]["rows"] == len(json.loads((gd / "nodes.json").read_text()))
    assert receipt["input_digest"] == container.shard_digest(gd)
    assert container.verify(gd) == "fresh"
    # the shard moves under the container: a resolver sidecar appears
    (gd / "wormhole_edges.json").write_text(json.dumps({"edges": [
        {"kind": "edge", "edge_type": "calls", "src": "alpha://module/alpha", "dst": "beta://module/beta",
         "via": "resolver:import", "label": "beta"}]}), encoding="utf-8")
    assert container.verify(gd) == "stale"
    again = container.emit(gd)
    assert again["files"]["adjacency.parquet"]["rows"] == receipt["files"]["adjacency.parquet"]["rows"] + 1
    assert container.verify(gd) == "fresh"


@needs_duckdb
def test_GREEN_the_rows_carry_the_shard_and_the_three_forms(tmp_path):
    import duckdb
    home, slugs = _ring(tmp_path)
    gd = home / "alpha_graph"
    container.emit(gd)
    con = duckdb.connect()
    rows = con.execute(f"SELECT id, kind, body, last, node_type, file, loc, attrs FROM read_parquet('{gd / 'nodes.parquet'}') "
                       "WHERE id = 'alpha://class/alpha.Root'").fetchall()
    assert rows == [("alpha://class/alpha.Root", "class", "alpha.Root", "Root", "class", "alpha/__init__.py", None,
                     json.dumps({"docstring": "The root class.", "line": 9, "name": "Root"}, sort_keys=True))]
    edge = con.execute(f"SELECT src, dst, edge_type, attrs, dst_repr FROM read_parquet('{gd / 'adjacency.parquet'}') "
                       "WHERE edge_type = 'imports' AND dst = 'beta://module/beta'").fetchall()
    assert edge == [("alpha://module/alpha", "beta://module/beta", "imports", json.dumps({"alias": None, "line": 4}), None)]
    label = con.execute(f"SELECT dst, dst_repr FROM read_parquet('{gd / 'adjacency.parquet'}') "
                        "WHERE edge_type = 'calls' AND dst_repr = 'beta.helper'").fetchall()
    assert label == [(None, "beta.helper")]


@needs_duckdb
def test_GREEN_build_emits_the_estate_and_one_query_spans_every_shard(tmp_path, capsys):
    home, slugs = _ring(tmp_path)
    desc = _tenant(tmp_path, home, slugs)
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    out = capsys.readouterr().out
    assert "CONTAINER OK: 3 shard(s)" in out
    for s in slugs:
        assert container.verify(home / f"{s}_graph") == "fresh"
    assert cli.main(["check", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    assert "container fresh for 3/3" in capsys.readouterr().out
    assert cli.main(["estate", "--tenant", str(desc), "--tenant-id", "t",
                     "--sql", "SELECT corpus, count(*) AS n FROM nodes GROUP BY corpus ORDER BY corpus"]) == 0
    out = capsys.readouterr().out
    assert "alpha_graph\t" in out and "beta_graph\t" in out and "gamma_graph\t" in out
    assert "ESTATE OK: 3 row(s) over 3 shard(s)" in out
    con = container.estate([home / f"{s}_graph" for s in slugs])
    cross = con.execute("SELECT count(*) FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus").fetchone()[0]
    con.close()
    assert cross == 3, "alpha's three import edges into beta and gamma are the wormholes, visible in SQL"


@needs_duckdb
def test_RED_a_stale_container_fails_check_and_the_estate_refuses_by_name(tmp_path, capsys):
    home, slugs = _ring(tmp_path)
    desc = _tenant(tmp_path, home, slugs)
    assert cli.main(["build", "--tenant", str(desc), "--tenant-id", "t"]) == 0
    capsys.readouterr()
    gd = home / "beta_graph"
    edges = json.loads((gd / "edges.json").read_text())
    edges.append({"kind": "edge", "edge_type": "calls", "src": "beta://func/beta.helper", "dst_repr": "print", "line": 3})
    (gd / "edges.json").write_text(json.dumps(edges), encoding="utf-8")
    assert container.verify(gd) == "stale"
    rc = cli.main(["container", "--tenant", str(desc), "--tenant-id", "t"])
    assert rc == 1 and "CONTAINER STALE: 2/3 fresh" in capsys.readouterr().out
    rc = cli.main(["estate", "--tenant", str(desc), "--tenant-id", "t"])
    assert rc == 2 and "beta_graph" in capsys.readouterr().err
    assert cli.main(["container", "--tenant", str(desc), "--tenant-id", "t", "--emit"]) == 0
    assert container.verify(gd) == "fresh"
