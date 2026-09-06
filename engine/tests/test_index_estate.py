"""The estate over an index: every named shard as one view, pinned to the catalog; stale when the
catalog moves. A floor — the proof is the 521-shard run in RECON. Skipped by name without duckdb."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.cli as cli
from graphy import container, index as shard_index, index_estate, smash
from test_smash import _site

pytestmark = pytest.mark.skipif(not container.have_duckdb(), reason=container.INSTALL_HINT)


def _index(tmp_path: Path) -> Path:
    sp = _site(tmp_path)
    out = tmp_path / "out"
    smash.smash("alpha", site_packages=sp, out=out)
    idx = tmp_path / "index"
    for shard in sorted(out.glob("*_graph")):
        shard_index.push(shard, idx, name=f"{shard.name[:-6]}==0.1")
    return idx


def test_GREEN_emit_query_and_stale(tmp_path, capsys):
    idx = _index(tmp_path)
    assert index_estate.verify_index_estate(idx)[0] == "absent"
    r = index_estate.emit_index(idx)
    assert r["shards"] == 3 and r["nodes"] > 0 and r["edges"] > 0
    assert index_estate.verify_index_estate(idx)[0] == "fresh"
    con, receipt = index_estate.estate_index(idx)
    rows = con.execute("SELECT name, count(*) FROM adj WHERE edge_type='imports' AND dst LIKE 'beta://%' GROUP BY 1").fetchall()
    con.close()
    assert sorted(rows) == [("alpha==0.1", 1), ("gamma==0.1", 1)]
    rc = cli.main(["estate", "--index", str(idx), "--sql", "SELECT count(DISTINCT name) AS n FROM nodes"])
    out = capsys.readouterr().out
    assert rc == 0 and "\n3\n" in out and "ESTATE OK: 1 row(s) over 3 shard(s)" in out
    # the catalog moves: a fourth name lands
    shard_index.push(next(iter(sorted((tmp_path / "out").glob("*_graph")))), idx, name="again==0.2")
    assert index_estate.verify_index_estate(idx)[0] == "stale"
    with pytest.raises(container.ContainerError, match="STALE"):
        index_estate.estate_index(idx)
    rc = cli.main(["estate", "--index", str(idx), "--sql", "SELECT 1"])
    assert rc == 2 and "STALE" in capsys.readouterr().err
    rc = cli.main(["estate", "--index", str(idx), "--emit"])
    assert rc == 0 and "ESTATE EMITTED: 4 shard(s)" in capsys.readouterr().out


def test_RED_refusals(tmp_path, capsys):
    rc = cli.main(["estate", "--index", "relative/index", "--sql", "SELECT 1"])
    assert rc == 2 and "must be absolute" in capsys.readouterr().err
    rc = cli.main(["estate", "--index", str(tmp_path), "--sql", "SELECT 1"])
    assert rc == 2 and "not an index" in capsys.readouterr().err
