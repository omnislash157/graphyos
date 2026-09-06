
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from graphy.adapters.outline import (
    OUTLINE_VOCABULARY,
    build_ir as build_outline,
)
from graphy.adapters.python_ast import (
    PYTHON_AST_VOCABULARY,
    build_ir as build_ast,
)
from graphy.ir import IRError, validate_graph
from graphy.native_json_graph_ir import validate_shard

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = HERE / "fixtures" / "lightning_corpus"
FASTAPI = HERE / "fixtures" / "fastapi_graph"
GRAPHOS = HERE.parent




def test_python_ast_ingests_two_corpora_and_anchors_source():
    ast_n, ast_e = build_ast(str(GRAPHOS / "graphy"))
    alt_n, alt_e = build_ast(str(CORPUS))
    assert ast_n != alt_n, "python-ast returned identical nodes for different corpora"
    assert any("resolve_graph" in str(x.get("id", "")) for x in ast_n), \
        "no source-derived anchor: graphy/ defines resolve_graph and the adapter never saw it"
    assert any("resolve_widget" in str(x.get("id", "")) for x in alt_n), \
        "no source-derived anchor: the lightning corpus defines resolve_widget"


def test_python_ast_validates_under_own_vocabulary():
    ast_n, ast_e = build_ast(str(GRAPHOS / "graphy"))
    assert validate_graph(ast_n, ast_e, PYTHON_AST_VOCABULARY) > 0


def test_python_ast_refused_under_foreign_vocabulary():
    ast_n, ast_e = build_ast(str(GRAPHOS / "graphy"))
    with pytest.raises(IRError):
        validate_graph(ast_n, ast_e, OUTLINE_VOCABULARY)




def test_outline_ingests_two_documents_and_anchors_source():
    out_n, out_e = build_outline(str(CORPUS / "transcript.md"))
    out2_n, out2_e = build_outline(str(CORPUS / "doctrine.md"))
    assert out_n != out2_n, "outline returned identical nodes for different documents"
    assert out_n, "outline produced NO nodes from a real document"


def test_outline_validates_under_own_vocabulary():
    out_n, out_e = build_outline(str(CORPUS / "transcript.md"))
    assert validate_graph(out_n, out_e, OUTLINE_VOCABULARY) > 0


def test_outline_refused_under_foreign_vocabulary():
    out_n, out_e = build_outline(str(CORPUS / "transcript.md"))
    with pytest.raises(IRError):
        validate_graph(out_n, out_e, PYTHON_AST_VOCABULARY)




@pytest.mark.parametrize(
    ("label", "build", "vocab"),
    [
        ("ast", build_ast, PYTHON_AST_VOCABULARY),
        ("outline", build_outline, OUTLINE_VOCABULARY),
    ],
)
def test_validate_shard_round_trips_each_producer(label, build, vocab):
    nodes, edges = build(str(CORPUS / "transcript.md")) if label == "outline" \
        else build(str(CORPUS))
    d = pathlib.Path(tempfile.mkdtemp()) / f"{label}_graph"
    d.mkdir(parents=True)
    (d / "nodes.json").write_text(json.dumps({x["id"]: x for x in nodes}), encoding="utf-8")
    (d / "edges.json").write_text(json.dumps(list(edges)), encoding="utf-8")
    assert validate_shard(str(d), vocab) > 0


def test_vendored_fastapi_shard_speaks_python_ast_dialect():
    assert validate_shard(str(FASTAPI), PYTHON_AST_VOCABULARY) > 0


def test_vendored_fastapi_shard_refused_under_outline_dialect():
    with pytest.raises(IRError):
        validate_shard(str(FASTAPI), OUTLINE_VOCABULARY)




def test_python_ast_package_mode_does_not_capture_stdlib_names_it_shadows(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""A package."""\nimport types\nfrom . import types as own\n', encoding="utf-8")
    (pkg / "types.py").write_text("X = 1\n", encoding="utf-8")
    nodes, edges = build_ast(str(pkg))
    dsts = [e["dst"] for e in edges if e["edge_type"] == "imports"]
    assert "types://module/types" in dsts and "pkg://module/pkg" in dsts
    assert nodes["pkg://module/pkg"]["file"] == "pkg/__init__.py"
    assert nodes["pkg://module/pkg"]["docstring"] == "A package."


def test_python_ast_repo_root_mode_prefixes_its_local_packages(tmp_path):
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "core.py").write_text("import os\n", encoding="utf-8")
    (repo / "main.py").write_text("from app.core import run\nimport os\n", encoding="utf-8")
    nodes, edges = build_ast(str(repo))
    dsts = {e["dst"] for e in edges if e["edge_type"] == "imports"}
    assert "repo://module/repo.app.core" in dsts and "os://module/os" in dsts
    assert nodes["repo://module/repo.main"]["file"] == "repo/main.py"


def test_python_ast_mints_a_one_file_distribution(tmp_path):
    mod = tmp_path / "solo.py"
    mod.write_text('"""Solo."""\nimport sys\n\n\ndef f():\n    """Doc."""\n    return sys.argv\n', encoding="utf-8")
    nodes, edges = build_ast(str(mod))
    assert nodes["solo://module/solo"]["file"] == "solo.py"
    assert nodes["solo://func/solo.f"]["docstring"] == "Doc."
    assert [e["dst"] for e in edges if e["edge_type"] == "imports"] == ["sys://module/sys"]


def test_python_ast_mints_defs_guarded_by_module_and_class_level_compound_statements(tmp_path):
    """A def or class under a module-level if/try/with/for is the module's — a version-gated
    backport defines the name on the module, so the module is its parent and the dotted path is
    unchanged. A def inside a function body is still not a node (issue 12)."""
    mod = tmp_path / "shim.py"
    mod.write_text(
        "import sys\n"
        "if sys.version_info >= (3, 12):\n"
        "    from typing import override\n"
        "else:\n"
        "    def override(f):\n"
        "        return f\n"
        "try:\n"
        "    from typing import Buffer\n"
        "except ImportError:\n"
        "    class Buffer:\n"
        "        def __buffer__(self):\n"
        "            pass\n"
        "finally:\n"
        "    def cleanup():\n"
        "        pass\n"
        "with open(__file__) as fh:\n"
        "    def reader():\n"
        "        return fh\n"
        "for _i in range(1):\n"
        "    def looped():\n"
        "        pass\n"
        "while False:\n"
        "    def never():\n"
        "        pass\n"
        "class Gated:\n"
        "    if sys.platform == 'win32':\n"
        "        def win(self):\n"
        "            pass\n"
        "    else:\n"
        "        def posix(self):\n"
        "            pass\n"
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
        "    return inner\n",
        encoding="utf-8",
    )
    nodes, edges = build_ast(str(mod))
    ids = set(nodes.keys())
    assert {"shim://func/shim.override", "shim://class/shim.Buffer", "shim://method/shim.Buffer.__buffer__",
            "shim://func/shim.cleanup", "shim://func/shim.reader", "shim://func/shim.looped",
            "shim://func/shim.never", "shim://class/shim.Gated", "shim://method/shim.Gated.win",
            "shim://method/shim.Gated.posix", "shim://func/shim.outer"} <= ids
    assert "shim://func/shim.outer.inner" not in ids and not any(n.get("name") == "inner" for n in nodes)
    contains = {(e["src"], e["dst"]) for e in edges if e["edge_type"] == "contains"}
    assert ("shim://module/shim", "shim://func/shim.override") in contains
    assert ("shim://module/shim", "shim://class/shim.Buffer") in contains
    assert ("shim://class/shim.Gated", "shim://method/shim.Gated.posix") in contains
    assert nodes["shim://method/shim.Gated.win"]["container_class"] == "Gated"
