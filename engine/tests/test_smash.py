"""The minting lane. A synthetic site-packages stands in for a real one: a root package that
imports a one-file distribution, a sibling package, the standard library, and one name nothing
installed provides. The FastAPI parity proof against the vendored fixture runs when a corpus
site-packages is named by GRAPHY_CORPUS_SITE_PACKAGES and is skipped loudly otherwise."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

import graphy.cli as cli
from graphy import smash
from graphy.ir import PYTHON_AST_VOCABULARY
from graphy.native_json_graph_ir import validate_shard
from graphy.parity import ParityError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fastapi_graph"


def _dist(sp: Path, name: str, version: str, files: list[str]) -> None:
    info = sp / f"{name}-{version}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\nLicense-Expression: MIT\n\nthe body\n",
        encoding="utf-8")
    (info / "RECORD").write_text("".join(f"{f},sha256=x,1\n" for f in files)
                                 + f"{name}-{version}.dist-info/METADATA,,\n", encoding="utf-8")


def _site(tmp_path: Path) -> Path:
    sp = tmp_path / "site-packages"
    sp.mkdir()
    alpha = sp / "alpha"
    alpha.mkdir()
    (alpha / "__init__.py").write_text(
        '"""Alpha, the root."""\n'
        "import os\n"
        "from typing import Any\n"
        "import beta\n"
        "from gamma.core import Widget\n"
        "import delta\n\n\n"
        "class Root(Widget):\n"
        '    """The root class."""\n\n'
        "    def run(self) -> Any:\n"
        "        return beta.helper(self)\n", encoding="utf-8")
    (alpha / "types.py").write_text("import types\n\n\ndef kinds():\n    return types.SimpleNamespace()\n",
                                    encoding="utf-8")
    (sp / "beta.py").write_text('"""Beta, a one-file distribution."""\nimport os\n\n\n'
                                "def helper(x):\n    return os.getcwd()\n", encoding="utf-8")
    gamma = sp / "gamma"
    gamma.mkdir()
    (gamma / "__init__.py").write_text("from .core import Widget\n", encoding="utf-8")
    (gamma / "core.py").write_text("import beta\n\n\nclass Widget:\n    pass\n", encoding="utf-8")
    _dist(sp, "alpha", "1.2.3", ["alpha/__init__.py", "alpha/types.py"])
    _dist(sp, "beta", "0.9", ["beta.py"])
    _dist(sp, "gamma", "2.0", ["gamma/__init__.py", "gamma/core.py"])
    return sp


def test_GREEN_smash_mints_the_root_and_closes_the_ring(tmp_path):
    sp = _site(tmp_path)
    out = tmp_path / "home"
    receipt = smash.smash("alpha", site_packages=sp, out=out)
    assert set(receipt["minted"]) == {"alpha", "beta", "gamma"}
    assert receipt["unresolved"] == {"delta": f"not under {sp}"}
    assert {"os", "typing", "types"} <= set(receipt["stdlib"])
    assert receipt["imports"]["alpha"] == ["beta", "delta", "gamma", "os", "types", "typing"]
    assert receipt["imports"]["gamma"] == ["beta"]
    for scheme, row in receipt["minted"].items():
        shard = Path(row["shard"])
        assert shard == out / f"{scheme}_graph"
        assert {p.name for p in shard.iterdir()} == {"nodes.json", "edges.json", "PROVENANCE.json"}
        assert validate_shard(str(shard), PYTHON_AST_VOCABULARY) > 0
        prov = json.loads((shard / "PROVENANCE.json").read_text())
        assert prov["surface"] == f"{scheme}_graph.records"
        assert prov["mint_command"] == receipt["mint_command"]
        assert prov["oracle_commit"] == "sha256:" + prov["corpus"]["sha256"]
        for name in ("nodes.json", "edges.json"):
            assert prov["files"][name]["bytes"] == (shard / name).stat().st_size
    alpha = json.loads((out / "alpha_graph" / "PROVENANCE.json").read_text())
    assert alpha["corpus"]["version"] == "1.2.3" and alpha["corpus"]["license"] == "MIT"
    assert alpha["corpus"]["kind"] == "package" and alpha["corpus"]["files"] == 2
    beta = json.loads((out / "beta_graph" / "PROVENANCE.json").read_text())
    assert beta["corpus"]["version"] == "0.9" and beta["corpus"]["kind"] == "file"
    assert (out / smash.RING_NAME).is_file()
    assert receipt["scheme_index"]["alpha"] == {"own": ["alpha"],
                                                "out": ["beta", "delta", "gamma", "os", "types", "typing"]}


def test_GREEN_the_producer_speaks_the_fixture_dialect(tmp_path):
    sp = _site(tmp_path)
    out = tmp_path / "home"
    smash.smash("alpha", site_packages=sp, out=out)
    nodes = json.loads((out / "alpha_graph" / "nodes.json").read_text())
    edges = json.loads((out / "alpha_graph" / "edges.json").read_text())
    assert isinstance(nodes, dict) and isinstance(edges, list)
    mod = nodes["alpha://module/alpha"]
    assert mod["file"] == "alpha/__init__.py" and mod["docstring"] == "Alpha, the root."
    assert nodes["alpha://class/alpha.Root"]["docstring"] == "The root class."
    assert nodes["alpha://method/alpha.Root.run"]["container_class"] == "Root"
    imports = {e["dst"] for e in edges if e["edge_type"] == "imports"}
    assert "types://module/types" in imports, \
        "a package's own types.py must not capture the stdlib import (the fixture's dialect)"
    assert "beta://module/beta" in imports and "gamma://module/gamma.core" in imports
    beta_nodes = json.loads((out / "beta_graph" / "nodes.json").read_text())
    assert beta_nodes["beta://module/beta"]["file"] == "beta.py"


def test_GREEN_no_ring_mints_only_the_root(tmp_path):
    sp = _site(tmp_path)
    out = tmp_path / "home"
    receipt = smash.smash("alpha", site_packages=sp, out=out, ring=False)
    assert list(receipt["minted"]) == ["alpha"]
    assert not (out / "beta_graph").exists()
    assert receipt["mint_command"].endswith(" --no-ring")


def test_GREEN_corpus_override_mints_the_root_from_a_checkout(tmp_path):
    sp = _site(tmp_path)
    checkout = tmp_path / "checkout" / "alpha"
    shutil.copytree(sp / "alpha", checkout)
    (checkout / "extra.py").write_text("def more():\n    return 1\n", encoding="utf-8")
    out = tmp_path / "home"
    receipt = smash.smash("alpha", site_packages=sp, out=out, corpus=checkout)
    assert receipt["minted"]["alpha"]["corpus"] == str(checkout)
    assert set(receipt["minted"]) == {"alpha", "beta", "gamma"}
    nodes = json.loads((out / "alpha_graph" / "nodes.json").read_text())
    assert "alpha://func/alpha.extra.more" in nodes
    prov = json.loads((out / "alpha_graph" / "PROVENANCE.json").read_text())
    assert Path(prov["corpus"]["path"]).resolve() == checkout.resolve() and prov["corpus"]["version"] == "1.2.3"
    assert f"--corpus {smash.portable(checkout)}" in prov["mint_command"]


def test_RED_a_missing_package_is_refused(tmp_path, capsys):
    sp = _site(tmp_path)
    rc = cli.main(["smash", "--package", "omega", "--site-packages", str(sp), "--out", str(tmp_path / "home")])
    assert rc == 2
    assert "SMASH REFUSED" in capsys.readouterr().err
    rc = cli.main(["smash", "--package", "alpha", "--site-packages", str(tmp_path / "nope"),
                   "--out", str(tmp_path / "home")])
    assert rc == 2


def test_RED_smash_refuses_to_guess_its_arguments(capsys):
    assert cli.main(["smash", "--package", "alpha"]) == 2
    assert "--site-packages is required" in capsys.readouterr().err


def test_GREEN_parity_proves_a_remint_and_RED_names_a_divergence(tmp_path, capsys):
    sp = _site(tmp_path)
    first = tmp_path / "first"
    assert cli.main(["smash", "--package", "alpha", "--site-packages", str(sp), "--out", str(first)]) == 0
    golden = first / "alpha_graph"
    second = tmp_path / "second"
    rc = cli.main(["smash", "--package", "alpha", "--site-packages", str(sp), "--out", str(second),
                   "--parity", str(golden)])
    out = capsys.readouterr().out
    assert rc == 0 and "PARITY OK: alpha_graph.records@sha256:" in out and "SMASH OK" in out
    (sp / "alpha" / "types.py").write_text("import types\n\n\ndef kinds():\n    return 1\n\n\ndef more():\n    pass\n",
                                           encoding="utf-8")
    third = tmp_path / "third"
    rc = cli.main(["smash", "--package", "alpha", "--site-packages", str(sp), "--out", str(third),
                   "--parity", str(golden)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "PARITY FAILED" in err and "extra    alpha://func/alpha.types.more" in err
    assert "re-mint with: python3 -m graphy smash --package alpha" in err


def test_RED_a_golden_without_provenance_is_refused(tmp_path):
    sp = _site(tmp_path)
    out = tmp_path / "home"
    smash.smash("alpha", site_packages=sp, out=out, ring=False)
    (out / "alpha_graph" / "PROVENANCE.json").unlink()
    with pytest.raises(ParityError, match="no PROVENANCE.json"):
        smash.parity(out / "alpha_graph", out / "alpha_graph")


def test_GREEN_corpus_digest_is_content_addressed(tmp_path):
    sp = _site(tmp_path)
    a, n = smash.corpus_digest(sp / "alpha")
    assert n == 2 and len(a) == 64
    (sp / "alpha" / "types.py").write_text("# moved\nimport types\n", encoding="utf-8")
    b, _ = smash.corpus_digest(sp / "alpha")
    assert a != b


def test_GREEN_distributions_map_import_names_to_wheels(tmp_path):
    sp = _site(tmp_path)
    d = smash.distributions(sp)
    assert d["alpha"] == {"distribution": "alpha", "version": "1.2.3", "license": "MIT"}
    assert d["beta"]["version"] == "0.9" and d["gamma"]["version"] == "2.0"
    assert "omega" not in d


@pytest.mark.skipif(not os.environ.get("GRAPHY_CORPUS_SITE_PACKAGES"),
                    reason="GRAPHY_CORPUS_SITE_PACKAGES not set: the FastAPI parity proof needs a "
                           "site-packages holding fastapi==0.139.0 (RECON.md §13 names the venv)")
def test_GREEN_fastapi_minted_from_the_pinned_wheel_equals_the_vendored_fixture(tmp_path):
    sp = Path(os.environ["GRAPHY_CORPUS_SITE_PACKAGES"])
    out = tmp_path / "home"
    receipt = smash.smash("fastapi", site_packages=sp, out=out, ring=False)
    golden = smash.parity(receipt["minted"]["fastapi"]["shard"], FIXTURE)
    assert golden.surface == "fastapi_graph.records"
    assert receipt["minted"]["fastapi"]["nodes"] == 507 and receipt["minted"]["fastapi"]["edges"] == 3715
