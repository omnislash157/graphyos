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


def test_GREEN_the_records_are_compact_and_the_receipts_are_indented_and_parity_reads_both(tmp_path, capsys):
    """nodes.json and edges.json are the machine's: one line, compact separators — a third of the
    bytes of the indented form. PROVENANCE.json and ring.json are a human's: indented. A golden
    written in the old indented form still proves a compact re-mint, record for record."""
    sp = _site(tmp_path)
    out = tmp_path / "home"
    smash.smash("alpha", site_packages=sp, out=out)
    shard = out / "alpha_graph"
    for name in ("nodes.json", "edges.json"):
        text = (shard / name).read_text(encoding="utf-8")
        assert text.count("\n") == 1 and '": ' not in text and '", "' not in text
        assert len(text) < len(json.dumps(json.loads(text), indent=2)) * 0.8
    assert (shard / "PROVENANCE.json").read_text().startswith("{\n  ")
    assert (out / smash.RING_NAME).read_text().startswith("{\n  ")
    golden = tmp_path / "golden_graph"
    shutil.copytree(shard, golden)
    for name in ("nodes.json", "edges.json"):  # the old form, as every shard already in an index carries it
        (golden / name).write_text(json.dumps(json.loads((golden / name).read_text()), indent=2) + "\n")
    assert validate_shard(str(golden), PYTHON_AST_VOCABULARY) == validate_shard(str(shard), PYTHON_AST_VOCABULARY)
    rc = cli.main(["smash", "--package", "alpha", "--site-packages", str(sp), "--out", str(tmp_path / "again"),
                   "--parity", str(golden)])
    assert rc == 0 and "PARITY OK: alpha_graph.records@" in capsys.readouterr().out


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


def _shard_bytes(shard: Path) -> tuple[bytes, bytes]:
    return (shard / "nodes.json").read_bytes(), (shard / "edges.json").read_bytes()


def test_GREEN_a_remint_parses_only_the_files_whose_bytes_moved_and_equals_a_full_mint(tmp_path, monkeypatch):
    """The per-file receipt in PROVENANCE (`sources`): a re-mint over the previous shard hashes
    every file, parses the one that changed and splices the rest's records in; the shard is
    byte-identical to a full mint of the same tree — on a touched file, an added one, a deleted one."""
    import ast
    sp = _site(tmp_path)
    corpus = sp / "alpha"
    live, fresh = tmp_path / "live", tmp_path / "fresh"
    prov = smash.mint(corpus, live, mint_command="m")
    src = prov[smash.SOURCES_KEY]
    assert src["spliceable"] and src["parsed"] == 2 and src["reused"] == 0
    assert set(src["files"]) == {"__init__.py", "types.py"}
    assert all(set(f) == {"sha256", "nodes", "edges"} for f in src["files"].values())
    real = ast.parse
    parsed: list[int] = []
    monkeypatch.setattr(ast, "parse", lambda *a, **k: (parsed.append(1), real(*a, **k))[1])

    # nothing moved: nothing parsed, the bytes the same
    before = _shard_bytes(live)
    prov = smash.mint(corpus, live, mint_command="m")
    assert parsed == [] and prov[smash.SOURCES_KEY]["parsed"] == 0 and prov[smash.SOURCES_KEY]["reused"] == 2
    assert _shard_bytes(live) == before

    # one file touched: exactly one parse, and the shard equals a full mint
    (corpus / "types.py").write_text("import types\nimport os\n\n\ndef kinds():\n    return os.name\n"
                                     "\n\nclass Kind:\n    pass\n", encoding="utf-8")
    parsed.clear()
    smash.mint(corpus, live, mint_command="m")
    assert len(parsed) == 1
    parsed.clear()
    shutil.rmtree(fresh, ignore_errors=True)
    smash.mint(corpus, fresh, mint_command="m")
    assert len(parsed) == 2
    assert _shard_bytes(live) == _shard_bytes(fresh)

    # a file added, then one deleted: the splice still equals the full mint
    (corpus / "extra.py").write_text("from .types import Kind\n\n\nclass Extra(Kind):\n    pass\n", encoding="utf-8")
    parsed.clear()
    smash.mint(corpus, live, mint_command="m")
    assert len(parsed) == 1
    shutil.rmtree(fresh)
    smash.mint(corpus, fresh, mint_command="m")
    assert _shard_bytes(live) == _shard_bytes(fresh)
    (corpus / "types.py").unlink()
    parsed.clear()
    smash.mint(corpus, live, mint_command="m")
    assert parsed == []
    shutil.rmtree(fresh)
    smash.mint(corpus, fresh, mint_command="m")
    assert _shard_bytes(live) == _shard_bytes(fresh)
    validate_shard(live, PYTHON_AST_VOCABULARY)


def test_RED_a_receipt_that_does_not_fit_is_discarded_and_the_full_mint_runs(tmp_path, monkeypatch):
    """Three ways the receipt stops fitting: the records beside it were hand-edited, the producer
    that wrote it is not this one, the pin moved (a repo root's local package set). Each runs
    the full mint and the shard equals a fresh one; none is a guess."""
    import ast
    sp = _site(tmp_path)
    real = ast.parse
    parsed: list[int] = []
    monkeypatch.setattr(ast, "parse", lambda *a, **k: (parsed.append(1), real(*a, **k))[1])

    live = tmp_path / "live"
    smash.mint(sp / "alpha", live, mint_command="m")
    want = _shard_bytes(live)
    nodes = json.loads((live / "nodes.json").read_text(encoding="utf-8"))
    nodes.pop(next(iter(nodes)))
    (live / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")   # a hand inside the shard
    parsed.clear()
    smash.mint(sp / "alpha", live, mint_command="m")
    assert len(parsed) == 2 and _shard_bytes(live) == want

    prov = json.loads((live / smash.PROVENANCE_NAME).read_text(encoding="utf-8"))
    prov["producer"]["graphy"] = "0.0.0-other"
    (live / smash.PROVENANCE_NAME).write_text(json.dumps(prov), encoding="utf-8")
    parsed.clear()
    smash.mint(sp / "alpha", live, mint_command="m")
    assert len(parsed) == 2 and _shard_bytes(live) == want

    # a repo root: a new top-level package changes how every file's imports resolve — the pin moves
    root = tmp_path / "repo"
    shutil.copytree(sp / "alpha", root / "alpha")
    (root / "alpha" / "__init__.py").write_text("import helpers\n", encoding="utf-8")
    tree = tmp_path / "tree"
    smash.mint(root, tree, mint_command="m")
    first = json.loads((tree / smash.PROVENANCE_NAME).read_text(encoding="utf-8"))[smash.SOURCES_KEY]["pin"]
    (root / "helpers").mkdir()
    (root / "helpers" / "__init__.py").write_text("", encoding="utf-8")
    parsed.clear()
    smash.mint(root, tree, mint_command="m")
    prov = json.loads((tree / smash.PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert prov[smash.SOURCES_KEY]["pin"] != first and prov[smash.SOURCES_KEY]["parsed"] == 3
    edges = json.loads((tree / "edges.json").read_text(encoding="utf-8"))
    assert any(e["dst"] == "repo://module/repo.helpers" for e in edges if e.get("edge_type") == "imports")
    fresh = tmp_path / "tree_fresh"
    smash.mint(root, fresh, mint_command="m")
    assert _shard_bytes(tree) == _shard_bytes(fresh)


def test_GREEN_eat_again_keeps_the_shards_parses_nothing_and_prunes_a_shard_the_ring_dropped(tmp_path, capsys, monkeypatch):
    """A re-eat starts from the previous substrate's shards (nodes · edges · PROVENANCE kept, every
    build product wiped), so the mint splices and parses nothing; a ring shard the new ring no
    longer names is removed."""
    import ast
    sp = _site(tmp_path)
    repo = tmp_path / "repo"
    shutil.copytree(sp / "alpha", repo / "alpha")
    (repo / "pyproject.toml").write_text('[project]\nname="alpha"\nversion="0"\n', encoding="utf-8")
    assert cli.main(["eat", "--repo", str(repo), "--site-packages", str(sp)]) == 0
    out = capsys.readouterr().out
    assert "EAT OK: alpha + 2 ring shard(s)" in out and "(5 of 5 files parsed" in out
    sub = repo / ".graphy" / "substrate"
    assert sorted(d.name for d in sub.glob("*_graph")) == ["alpha_graph", "beta_graph", "gamma_graph"]
    before = {d.name: _shard_bytes(d) for d in sub.glob("*_graph")}
    assert (sub / "alpha_graph" / "wormhole_edges.json").is_file()
    real = ast.parse
    parsed: list[int] = []
    monkeypatch.setattr(ast, "parse", lambda *a, **k: (parsed.append(1), real(*a, **k))[1])
    assert cli.main(["eat", "--repo", str(repo), "--site-packages", str(sp)]) == 0
    out = capsys.readouterr().out
    assert parsed == [] and "(0 of " in out
    assert {d.name: _shard_bytes(d) for d in sub.glob("*_graph")} == before
    assert (sub / "alpha_graph" / "wormhole_edges.json").is_file()   # converge ran again over the kept shard
    # alpha stops importing gamma: the gamma shard is pruned, the ring names three
    (repo / "alpha" / "__init__.py").write_text("import beta\n\n\ndef run():\n    return beta.helper(1)\n", encoding="utf-8")
    parsed.clear()
    assert cli.main(["eat", "--repo", str(repo), "--site-packages", str(sp)]) == 0
    out = capsys.readouterr().out
    assert len(parsed) == 1 and "(1 of " in out
    assert not (sub / "gamma_graph").exists() and (sub / "beta_graph").is_dir()


def _full_and_spliced(corpus: Path, live: Path, fresh: Path, **kw) -> None:
    smash.mint(corpus, live, mint_command="m", **kw)
    shutil.rmtree(fresh, ignore_errors=True)
    smash.mint(corpus, fresh, mint_command="m", **kw)
    assert _shard_bytes(live) == _shard_bytes(fresh)


def test_GREEN_an_id_two_files_emit_is_stored_by_the_receipt_and_the_splice_stays_byte_identical(tmp_path):
    """`pkg/x.py` and `pkg/x/__init__.py` both spell `pkg://module/pkg.x`: under the python producer
    the later file's record wins the value and the earlier keeps the position. The receipt stores
    the two records a span cannot recover; touching or deleting either file re-mints to the
    bytes of a full mint. The same under the TypeScript producer's first-wins (`index.js` beside
    `index.mjs`), where the later file's record is the one stored."""
    pkg = tmp_path / "pkg"
    (pkg / "x").mkdir(parents=True)
    (pkg / "__init__.py").write_text("from . import x\n", encoding="utf-8")
    (pkg / "x.py").write_text('"""the file"""\n\n\ndef f():\n    return 1\n', encoding="utf-8")
    (pkg / "x" / "__init__.py").write_text('"""the package"""\n\n\ndef g():\n    return 2\n', encoding="utf-8")
    live, fresh = tmp_path / "live", tmp_path / "fresh"
    prov = smash.mint(pkg, live, mint_command="m")
    src = prov[smash.SOURCES_KEY]
    assert src["spliceable"] and src["cross_file"] == 1
    assert list(src["files"]) == ["__init__.py", "x/__init__.py", "x.py"]      # walk order: the package first
    assert "own" in src["files"]["x/__init__.py"] and "extra" in src["files"]["x.py"]
    nodes = json.loads((live / "nodes.json").read_text(encoding="utf-8"))
    assert nodes["pkg://module/pkg.x"]["docstring"] == "the file"      # the later file's value
    assert list(nodes).index("pkg://module/pkg.x") < list(nodes).index("pkg://func/pkg.x.g")   # the earlier file's position
    prov = smash.mint(pkg, live, mint_command="m")
    assert prov[smash.SOURCES_KEY]["parsed"] == 0 and _shard_bytes(live) == _shard_bytes(live)
    _full_and_spliced(pkg, live, fresh)
    (pkg / "x.py").write_text('"""the file, edited"""\n\n\ndef f():\n    return 3\n', encoding="utf-8")
    _full_and_spliced(pkg, live, fresh)
    (pkg / "x" / "__init__.py").unlink()
    (pkg / "x").rmdir()
    _full_and_spliced(pkg, live, fresh)
    assert json.loads((live / "nodes.json").read_text(encoding="utf-8"))["pkg://module/pkg.x"]["docstring"] == "the file, edited"
    (pkg / "x.py").unlink()
    (pkg / "x").mkdir()
    (pkg / "x" / "__init__.py").write_text('"""the package, back"""\n', encoding="utf-8")
    _full_and_spliced(pkg, live, fresh)

    pytest.importorskip("tree_sitter_javascript")
    js = tmp_path / "js"
    js.mkdir()
    (js / "package.json").write_text('{"name": "js", "version": "1.0.0"}', encoding="utf-8")
    (js / "index.js").write_text("function a() { return 1 }\nmodule.exports = a\n", encoding="utf-8")
    (js / "index.mjs").write_text("export function a() { return 2 }\nexport function b() { return 3 }\n", encoding="utf-8")
    live, fresh = tmp_path / "live_js", tmp_path / "fresh_js"
    prov = smash.mint(js, live, mint_command="m", producer="typescript_ast", package="js")
    src = prov[smash.SOURCES_KEY]
    assert src["cross_file"] >= 1 and "extra" in src["files"]["index.mjs"] and "own" not in src["files"]["index.js"]
    _full_and_spliced(js, live, fresh, producer="typescript_ast", package="js")
    (js / "index.js").unlink()
    _full_and_spliced(js, live, fresh, producer="typescript_ast", package="js")
    assert "js://func/js.index.b" in json.loads((live / "nodes.json").read_text(encoding="utf-8"))


def test_RED_a_planted_edge_in_a_shard_on_disk_does_not_survive_the_splice(tmp_path, capsys):
    """Red-team finding 3 (RECON §71, graphyos #36): the splice trusted a shard's records whenever
    PROVENANCE's per-source-file hashes matched, but the receipt hashes the sources, not the records
    — a hostile repo that commits `.graphy/substrate/<pkg>_graph/` with one planted edge and matching
    source hashes had it survive MINT OK · BUILD OK · CHECK OK. The payload must hash to
    `PROVENANCE.files` before a splice reuses anything: the planted shard is refused by name and
    minted fresh, the fresh shard carries no planted row and equals a full mint; an untouched shard
    splices exactly as before, byte-identical, parsing nothing."""
    import ast
    sp = _site(tmp_path)
    corpus = sp / "alpha"
    live, fresh = tmp_path / "live", tmp_path / "fresh"
    smash.mint(corpus, live, mint_command="m")
    smash.mint(corpus, fresh, mint_command="m")
    clean = _shard_bytes(live)

    # the plant: one imports edge re-pointed, the source hashes untouched
    edges = json.loads((live / "edges.json").read_text(encoding="utf-8"))
    victim = next(e for e in edges if e["edge_type"] == "imports")
    victim["dst"] = "alpha://module/alpha.PLANTED"
    (live / "edges.json").write_text(json.dumps(edges), encoding="utf-8")
    assert b"PLANTED" in (live / "edges.json").read_bytes()

    prov = smash.mint(corpus, live, mint_command="m")
    err = capsys.readouterr().err
    assert "SPLICE REFUSED: live edges.json does not match its PROVENANCE" in err
    assert "minted fresh" in err
    src = prov[smash.SOURCES_KEY]
    assert src["reused"] == 0 and src["parsed"] == 2
    assert src["splice_refused"].startswith("SPLICE REFUSED: live edges.json")
    assert b"PLANTED" not in (live / "edges.json").read_bytes()
    assert _shard_bytes(live) == clean == _shard_bytes(fresh)

    # a planted node, same law
    nodes = json.loads((live / "nodes.json").read_text(encoding="utf-8"))
    nodes["alpha://module/alpha.PLANTED"] = dict(next(iter(nodes.values())), id="alpha://module/alpha.PLANTED")
    (live / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    prov = smash.mint(corpus, live, mint_command="m")
    assert "SPLICE REFUSED: live nodes.json does not match its PROVENANCE" in capsys.readouterr().err
    assert prov[smash.SOURCES_KEY]["reused"] == 0
    assert b"PLANTED" not in (live / "nodes.json").read_bytes()
    assert _shard_bytes(live) == clean

    # the same answer: an untouched shard splices as before — nothing parsed, nothing refused, the bytes the same
    parsed: list[int] = []
    real = ast.parse
    try:
        ast.parse = lambda *a, **k: (parsed.append(1), real(*a, **k))[1]
        prov = smash.mint(corpus, live, mint_command="m")
    finally:
        ast.parse = real
    assert parsed == [] and prov[smash.SOURCES_KEY]["reused"] == 2
    assert "splice_refused" not in prov[smash.SOURCES_KEY]
    assert capsys.readouterr().err == ""
    assert _shard_bytes(live) == clean
