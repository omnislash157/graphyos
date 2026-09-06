"""The refresh lane. A synthetic tenant minted from one site-packages is refreshed against a
second site-packages that holds the same root one release newer: the sibling substrate lands
beside the current one, proven, and the journal says what was born and what died. PyPI is a
fixture here; the live lookup is the FastAPI run in RECON."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

import graphy.cli as cli
from graphy import refresh
from graphy import smash

from test_smash import _dist, _site


def _site_v2(tmp_path: Path) -> Path:
    """alpha 1.3.0: a function born in alpha.types, alpha.types.kinds died, beta unchanged."""
    (tmp_path / "v2").mkdir(parents=True, exist_ok=True)
    sp = _site(tmp_path / "v2")
    (sp / "alpha" / "types.py").write_text("import types\n\n\ndef shapes():\n    return types.SimpleNamespace()\n",
                                          encoding="utf-8")
    info = sp / "alpha-1.2.3.dist-info"
    info.rename(sp / "alpha-1.3.0.dist-info")
    meta = sp / "alpha-1.3.0.dist-info" / "METADATA"
    meta.write_text(meta.read_text(encoding="utf-8").replace("Version: 1.2.3", "Version: 1.3.0"), encoding="utf-8")
    return sp


def _tenant(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The current tenant: alpha 1.2.3 and its ring minted into <root>/data, declared, built."""
    (tmp_path / "v1").mkdir(parents=True, exist_ok=True)
    sp = _site(tmp_path / "v1")
    root = tmp_path / "tenant"
    root.mkdir()
    home = root / "data"
    ring = smash.smash("alpha", site_packages=sp, out=home)
    lanes = [f"--lane={m['slug']}_graph:static-dep" for m in ring["minted"].values()]
    desc = root / "tenant.json"
    cursor = "sha256:" + hashlib.sha256((home / "alpha_graph" / "edges.json").read_bytes()).hexdigest()
    assert cli.main(["init", "--tenant", str(desc), "--root", str(root), "--data-home", str(home),
                     "--join-keys", str(home / "registry.json"), "--journal", str(home / "journal"),
                     "--cursor", cursor, "--policy", "refuse", "--adapter", "python_ast", *lanes]) == 0
    return desc, home, sp


def _digest(home: Path) -> dict[str, str]:
    return {str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(home.rglob("*")) if p.is_file()}


def test_GREEN_parse_version_orders_releases_pre_releases_and_garbage():
    assert refresh.is_newer("0.141.1", "0.139.0")
    assert refresh.is_newer("1.0.0", "1.0.0rc1")
    assert refresh.is_newer("1.0.0rc1", "1.0.0b2")
    assert refresh.is_newer("1.0.0.post1", "1.0.0")
    assert refresh.is_newer("1.0.0", "1.0.0.dev3")
    assert not refresh.is_newer("1.0", "1.0.0")
    assert not refresh.is_newer("0.139.0", "0.139.0")
    assert not refresh.is_newer("not-a-version", "0.1")


def test_GREEN_is_final_refuses_dev_and_pre_releases_and_latest_release_skips_them():
    assert refresh.is_final("1.100.0") and refresh.is_final("1.0.0.post1")
    assert not refresh.is_final("1.101.0.dev1") and not refresh.is_final("1.101.0rc1")
    assert not refresh.is_final("1.0.0b2") and not refresh.is_final("garbage")
    data = {"releases": {"1.100.0": [{"size": 1}], "1.101.0.dev1": [{"size": 1}], "1.101.0.dev2": [{"size": 1}],
                         "1.101.0rc1": [{"size": 1}]}}
    assert refresh.latest_release("litellm", fetch=lambda url: data) == "1.100.0"
    only_dev = {"releases": {"0.1.dev1": [{"size": 1}]}}
    with pytest.raises(refresh.RefreshError, match="no final"):
        refresh.latest_release("devonly", fetch=lambda url: only_dev)


def test_GREEN_latest_release_reads_pypi_and_skips_pre_releases_and_yanked():
    data = {"releases": {"0.139.0": [{"yanked": False}], "0.141.1": [{"yanked": False}],
                         "0.142.0rc1": [{"yanked": False}], "0.141.2": [{"yanked": True}], "0.150.0": []}}
    assert refresh.latest_release("fastapi", fetch=lambda url: data) == "0.141.1"


def test_RED_latest_release_refuses_an_unreachable_index():
    def down(url):
        raise OSError("no route")
    with pytest.raises(refresh.RefreshError, match="unreachable"):
        refresh.latest_release("fastapi", fetch=down)
    with pytest.raises(refresh.RefreshError, match="no releases"):
        refresh.latest_release("fastapi", fetch=lambda url: {"releases": {}})


def test_GREEN_refresh_mints_a_sibling_proves_it_and_the_journal_says_born_and_died(tmp_path, capsys):
    desc, home, _ = _tenant(tmp_path)
    before = _digest(home)
    sp2 = _site_v2(tmp_path)
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha",
                   "--site-packages", str(sp2)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "UPSTREAM: alpha 1.2.3 -> 1.3.0" in out
    assert "CHECK OK" in out and "REFRESH OK: alpha 1.2.3 -> 1.3.0" in out
    # never in place: the current substrate is byte-identical
    assert _digest(home) == before
    sibling = home.with_name("data.1.3.0")
    sib_desc = desc.with_name("tenant.1.3.0.json")
    assert sibling.is_dir() and sib_desc.is_file()
    declared = json.loads(sib_desc.read_text(encoding="utf-8"))
    assert declared["data_home"] == str(sibling) and declared["policy"] == "refuse"
    assert set(declared["build_lanes"]) == {"alpha_graph", "beta_graph", "gamma_graph"}
    assert (sibling / ".federation_scheme_index.json").is_file()
    # the journal says
    receipt = json.loads((sibling / refresh.RECEIPT_NAME).read_text(encoding="utf-8"))
    assert receipt["verdict"] == "OK" and receipt["release_source"].startswith("read off ")
    by = {d["shard"]: d for d in receipt["diff"]}
    assert by["alpha_graph"]["n_born"] == 1 and by["alpha_graph"]["n_died"] == 1
    assert by["beta_graph"] == {**by["beta_graph"], "n_born": 0, "n_died": 0, "presence": "both"}
    page = [json.loads(l) for l in (sibling / "journal" / "alpha_graph.journal.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert page["born"] == ["alpha://func/alpha.types.shapes"]
    assert page["died"] == ["alpha://func/alpha.types.kinds"]
    assert page["cursor"] == "1.3.0" and page["prev_cursor"] == "1.2.3"
    assert "born  func/alpha.types.shapes" in out and "died  func/alpha.types.kinds" in out
    # the sibling is a tenant in its own right
    assert cli.main(["check", "--tenant", str(sib_desc), "--tenant-id", "t"]) == 0


def test_GREEN_a_current_release_is_reported_and_nothing_is_minted(tmp_path, capsys):
    desc, home, sp = _tenant(tmp_path)
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha", "--release", "1.2.3"])
    assert rc == 0
    assert "REFRESH CURRENT: alpha 1.2.3" in capsys.readouterr().out
    assert not home.with_name("data.1.2.3").exists()
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha", "--release", "9.0", "--check"])
    assert rc == 0 and "REFRESH NEWER: alpha 1.2.3 -> 9.0" in capsys.readouterr().out
    assert not home.with_name("data.9.0").exists()


def test_RED_refresh_refuses_without_a_provenance_or_over_a_previous_sibling(tmp_path, capsys):
    desc, home, _ = _tenant(tmp_path)
    (home / "alpha_graph" / smash.PROVENANCE_NAME).unlink()
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha", "--release", "2.0"])
    assert rc == 2 and "no PROVENANCE.json" in capsys.readouterr().err
    desc, home, _ = _tenant(tmp_path / "again")
    home.with_name("data.1.3.0").mkdir()
    sp2 = _site_v2(tmp_path / "again")
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha", "--site-packages", str(sp2)])
    assert rc == 2 and "--force" in capsys.readouterr().err
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha", "--site-packages", str(sp2), "--force"])
    assert rc == 0
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha", "--site-packages", str(sp2), "--release", "1.4"])
    assert rc == 2 and "holds alpha 1.3.0" in capsys.readouterr().err


def test_RED_refresh_refuses_to_guess(capsys):
    assert cli.main(["refresh", "--tenant", "x.json"]) == 2
    assert "REFRESH REFUSED" in capsys.readouterr().err


def test_GREEN_fixture_is_re_minted_by_the_engine_after_a_green_check(tmp_path, capsys):
    desc, home, _ = _tenant(tmp_path)
    sp2 = _site_v2(tmp_path)
    fixture = tmp_path / "fixtures" / "alpha_graph"
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha",
                   "--site-packages", str(sp2), "--fixture", str(fixture)])
    assert rc == 0, capsys.readouterr().out
    prov = json.loads((fixture / smash.PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert prov["corpus"]["version"] == "1.3.0"
    assert prov["mint_command"].endswith("--no-ring") and "--package alpha" in prov["mint_command"]
    assert not (fixture.parent / smash.RING_NAME).exists()
    assert "alpha://func/alpha.types.shapes" in json.loads((fixture / "nodes.json").read_text(encoding="utf-8"))
    # the pin closes: the new ring passes parity against the re-minted fixture
    ring_out = tmp_path / "again"
    smash.smash("alpha", site_packages=sp2, out=ring_out, ring=False)
    smash.parity(ring_out / "alpha_graph", fixture)
    # a fixture dir that is not the root's shard is refused before anything is minted
    rc = cli.main(["refresh", "--tenant", str(desc), "--tenant-id", "t", "--package", "alpha",
                   "--site-packages", str(sp2), "--fixture", str(tmp_path / "wrong_name"), "--force"])
    assert rc == 2 and "--fixture must be" in capsys.readouterr().err
