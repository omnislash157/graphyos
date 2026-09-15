
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


@pytest.fixture(scope="module")
def engine_ir():
    """The engine's own package minted once for the module: three tests read the same mint, which
    cost the floor a second apiece when each minted it again (graphyos #61)."""
    return build_ast(str(GRAPHOS / "graphy"))


def test_python_ast_ingests_two_corpora_and_anchors_source(engine_ir):
    ast_n, ast_e = engine_ir
    alt_n, alt_e = build_ast(str(CORPUS))
    assert ast_n != alt_n, "python-ast returned identical nodes for different corpora"
    assert any("resolve_graph" in str(x.get("id", "")) for x in ast_n), \
        "no source-derived anchor: graphy/ defines resolve_graph and the adapter never saw it"
    assert any("resolve_widget" in str(x.get("id", "")) for x in alt_n), \
        "no source-derived anchor: the lightning corpus defines resolve_widget"


def test_python_ast_validates_under_own_vocabulary(engine_ir):
    ast_n, ast_e = engine_ir
    assert validate_graph(ast_n, ast_e, PYTHON_AST_VOCABULARY) > 0


def test_python_ast_refused_under_foreign_vocabulary(engine_ir):
    ast_n, ast_e = engine_ir
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


def test_python_ast_visits_every_node_of_a_file_exactly_once(tmp_path, monkeypatch):
    """The producer is one level-order pass per file (graphyos #14): every AST node that can hold
    an import, a call or a scope is popped once — the count of pops is the count of nodes minus the
    leaves (a Constant, an expression context, an operator: never queued, graphyos #24) — and no
    subtree is read twice. The pass keeps
    the old attribution: an import inside a function body is the module's; a call inside a
    nested def belongs to the outermost tracked function; a class body's own calls are nobody's;
    a def under a statement ``_defs_in`` does not descend (``match``) is not a node and its calls
    are not edges."""
    import ast
    from collections import deque
    from graphy.adapters import python_ast

    mod = tmp_path / "sample.py"
    mod.write_text(
        "import os\n"
        "def outer():\n"
        "    import json\n"
        "    def inner():\n"
        "        return json.dumps(1)\n"
        "    return inner()\n"
        "class K(object):\n"
        "    field = make()\n"
        "    def m(self):\n"
        "        return helper(self)\n"
        "match os.name:\n"
        "    case 'nt':\n"
        "        def gated():\n"
        "            return hidden()\n",
        encoding="utf-8",
    )
    pops = {"n": 0}

    class Counting(deque):
        def popleft(self):
            pops["n"] += 1
            return super().popleft()

    monkeypatch.setattr(python_ast, "deque", Counting)
    records = list(python_ast._emit_records_for_file(mod, tmp_path, "sample"))
    nodes = list(ast.walk(ast.parse(mod.read_text(encoding="utf-8"))))
    leaves = sum(1 for n in nodes if type(n) in python_ast._LEAF)
    assert leaves and pops["n"] == len(nodes) - leaves, (pops["n"], len(nodes), leaves)

    calls = {(r["src"].rsplit("/", 1)[1], r["dst_repr"]) for r in records if r.get("edge_type") == "calls"}
    assert calls == {("sample.outer", "json.dumps"), ("sample.outer", "inner"), ("sample.K.m", "helper")}
    imports = sorted(r["dst"].rsplit("/", 1)[1] for r in records if r.get("edge_type") == "imports")
    assert imports == ["json", "os"]
    assert {r["dotted"] for r in records if r["kind"] == "node"} == {"sample", "sample.outer", "sample.K", "sample.K.m"}


def test_RED_an_unreadable_file_is_named_with_its_reason_and_a_coding_cookie_is_honoured(tmp_path):
    """Red-team finding 5 (RECON §71, graphyos #38): a syntax error, a latin-1 file or nesting past
    the interpreter's limit minted nothing and still counted as parsed — a codebase with one latin-1
    module lost it and the walk said "names no node" with no hint. Now every file the producer
    cannot read is named under ``unreadable`` with its reason, counted as neither parsed nor reused;
    a latin-1 module with its PEP 263 cookie (and a BOM-led utf-8 one) is decoded by the cookie and
    mints; a file symlink whose target lies outside the corpus is skipped and named, never read."""
    import os
    from graphy.adapters import python_ast
    pkg = tmp_path / "badpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "good.py").write_text("def ok():\n    pass\n", encoding="utf-8")
    (pkg / "broken.py").write_text("def top():\n    pass\n\ndef f(:\n    pass\n", encoding="utf-8")
    (pkg / "latin.py").write_bytes(b"# coding: latin-1\n# caf\xe9\ndef g(): pass\n")
    (pkg / "raw_latin.py").write_bytes(b"# caf\xe9\ndef h(): pass\n")
    (pkg / "deep.py").write_text("x = " + "(" * 300 + "1" + ")" * 300 + "\ndef d(): pass\n", encoding="utf-8")
    (pkg / "bom.py").write_bytes(b"\xef\xbb\xbfdef bom(): pass\n")
    (pkg / "nul.py").write_bytes(b"def n(): pass\n\x00")
    outside = tmp_path / "outside.py"
    outside.write_text("def secret(): pass\n", encoding="utf-8")
    try:                                   # Windows grants symlinks only to a privileged or developer-mode seat
        os.symlink(outside, pkg / "escaped.py")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"this seat cannot create a symlink, so the escape it proves cannot be staged: {exc}")
    os.symlink(pkg / "good.py", pkg / "inside.py")            # a link that stays inside is a module of the corpus
    os.symlink(tmp_path, pkg / "up")                          # a directory link is never descended

    files, skipped = python_ast.walk_files_naming_skips(pkg)
    assert skipped == {"escaped.py": f"symlink outside the corpus -> {outside.resolve()}"}
    assert [f.name for f in files] == ["__init__.py", "bom.py", "broken.py", "deep.py", "good.py", "inside.py",
                                       "latin.py", "nul.py", "raw_latin.py"]
    assert python_ast.walk_files(pkg) == files

    nodes, edges, sources = python_ast.mint_records(pkg)
    unreadable = sources["unreadable"]
    assert unreadable == {
        "escaped.py": f"symlink outside the corpus -> {outside.resolve()}",
        "broken.py": "syntax error line 4",
        "deep.py": "too deeply nested",
        "nul.py": "null bytes",
        "raw_latin.py": "not utf-8",
    }
    assert sources["parsed"] == 5 and sources["reused"] == 0
    assert set(sources["files"]) == {"__init__.py", "bom.py", "good.py", "inside.py", "latin.py"}
    dotted = {n["dotted"] for n in nodes.values() if n["node_type"] == "func"}
    assert dotted == {"badpkg.good.ok", "badpkg.latin.g", "badpkg.bom.bom", "badpkg.inside.ok"}
    assert not any("secret" in n["dotted"] or "escaped" in n["dotted"] for n in nodes.values())

    # the reader on its own: a readable file hands back its text and tree, an unreadable one its reason
    src, tree = python_ast.read_source(pkg / "latin.py")
    assert "café" in src and tree.body
    assert python_ast.read_source(pkg / "broken.py") == "syntax error line 4"
    assert python_ast.read_source(tmp_path / "missing.py").startswith("unreadable: ")
    (pkg / "cookie.py").write_bytes(b"# coding: nope-1\ndef c(): pass\n")
    assert python_ast.read_source(pkg / "cookie.py") == "unknown encoding: nope-1"

    # a readable file's records are the same whether the producer reads it or is handed the parse
    handed = list(python_ast._emit_records_for_file(pkg / "good.py", pkg, "badpkg", parsed=python_ast.read_source(pkg / "good.py")))
    assert handed == list(python_ast._emit_records_for_file(pkg / "good.py", pkg, "badpkg"))


def test_GREEN_a_path_field_is_posix_whoever_minted_the_shard(tmp_path):
    """A shard minted on Windows carried `idna\\cli.py` where a Linux mint of the same bytes at the
    same commit carried `idna/cli.py`, so the generation digest, the golden fixtures and every
    byte-identity check disagreed across hosts. Node IDS were always clean — 0 of 177,281 on a real
    Windows roster — so no walk was ever wrong; this is parity, not correctness (graphyos #88).

    The first client proved the shape exactly: same corpus, same engine, 58 nodes / 395 edges on
    both hosts, 10 of 10 files parsed on both, and replacing `\\` with `/` in the file fields
    reproduced the Linux digest character for character. One normalisation is the whole fix.

    It is asserted at the TYPED RECORD, not only in graphy's own producers, because on that client's
    roster 21 of 23 file-bearing lanes carried backslashes and most were minted by emitters this
    engine never wrote. A producer that hands the IR a native path gets it normalised too."""
    from graphy.ir import PYTHON_AST_VOCABULARY, Node
    node = Node.from_mapping("x://func/x.f", {
        "kind": "node", "node_type": "func", "id": "x://func/x.f", "dotted": "x.f",
        "file": "x\\sub\\mod.py", "line": 1, "docstring": "",
    }, PYTHON_AST_VOCABULARY)
    assert node.file == "x/sub/mod.py"
    # a path that is already posix is untouched, and a record with no file stays None
    assert Node.from_mapping("x://func/x.g", {
        "kind": "node", "node_type": "func", "id": "x://func/x.g", "dotted": "x.g",
        "file": "x/sub/mod.py", "line": 1, "docstring": "",
    }, PYTHON_AST_VOCABULARY).file == "x/sub/mod.py"


def test_GREEN_the_producer_writes_a_posix_path_before_the_ir_ever_sees_it(tmp_path):
    """The typed record is the backstop; the producer is where the bytes are decided. Both matter:
    a shard's nodes.json is compared byte-for-byte across hosts by the golden fixtures, and that
    file is written by the producer, not by the IR."""
    pkg = tmp_path / "deep"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "sub" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "sub" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    from graphy.adapters import python_ast
    nodes, _edges, _sources = python_ast.mint_records(pkg)
    files = {r.get("file") for r in nodes.values() if r.get("file")}
    assert files, "the fixture minted no file-bearing node"
    assert not any("\\" in f for f in files), files
    assert "deep/sub/mod.py" in files


def test_GREEN_a_foreign_shard_s_path_field_is_posix_by_the_time_the_STORE_reads_it(tmp_path):
    """The test the first #88 fix needed and did not have.

    That fix normalised in `ir.Node.from_mapping`, which LOOKS like the typed boundary every shard
    passes through. It is not: `from_mapping` is called only from `validate_graph`, which discards
    the Node it builds. The store's load path runs on raw dicts through
    `native_json_graph_ir._resolve_shard` and never constructs one — so a foreign shard's
    backslashes reached the compiled store untouched and the fix covered only the two producers
    that normalise at their own walk. 14.3% of a real roster's file-bearing nodes, not the 85.7%
    it claimed.

    So this asserts the fact at the surface that matters — what the STORE returns — rather than at
    the layer the fix happened to touch. An adversarial review found it by asking whether the code
    path a claim names is the code path that runs."""
    import json as _json
    from graphy.tenant import Tenant
    import graphy.federated_store as fs

    data = tmp_path / "data"
    (data / "foreign_graph").mkdir(parents=True)
    nid = "foreign://func/foreign.mod.f"
    (data / "foreign_graph" / "nodes.json").write_text(_json.dumps({nid: {
        "kind": "node", "node_type": "func", "id": nid, "dotted": "foreign.mod.f",
        "file": "foreign\\sub\\mod.py", "line": 1}}), encoding="utf-8")
    (data / "foreign_graph" / "edges.json").write_text("[]", encoding="utf-8")
    (data / "foreign_graph" / "PROVENANCE.json").write_text(
        _json.dumps({"counts": {"node_count": 1, "edge_count": 0}}), encoding="utf-8")
    (data / ".federation_scheme_index.json").write_text(
        _json.dumps({"_meta": {}, "foreign": {"own": ["foreign"], "out": []}}), encoding="utf-8")
    keys = tmp_path / "registry.json"
    keys.write_text(_json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    tenant = Tenant(root=tmp_path, data_home=data, adapters=(),
                    build_lanes={"foreign_graph": (None, "static-dep")}, join_keys=keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    fs.compile_store(["foreign"], fs.store_path_for(["foreign"], tenant=tenant), tenant=tenant,
                     tenant_id="x")
    store = fs.open_for(["foreign"], tenant=tenant, tenant_id="x")
    assert store.record(nid)["file"] == "foreign/sub/mod.py"


def test_GREEN_a_function_referenced_as_a_value_mints_a_references_edge_bound_through_scope(tmp_path):
    """A function reached through a dispatch table, a callback argument, a decorator's argument or a
    default had no inbound edge, so `blast` answered zero for all 26 CLI verbs (graphyos #94). The
    producer now mints `references` for a name read as a value whose head the module's own scope
    binds — a def, a class, an import — and the owning function never rebinds. Never a name match:
    a parameter or a local of the same name mints nothing; a callee is `calls`, a bare decorator
    `decorates`, a base `inherits`, an annotation a type — none is a reference."""
    from collections import Counter
    from graphy.adapters import python_ast
    mod = tmp_path / "sample.py"
    mod.write_text(
        "import json\n"
        "import os.path\n"
        "from functools import wraps as w\n"
        "def a(): pass\n"
        "def b(): pass\n"
        "class K(object):\n"
        "    field = a\n"                       # a class body's own reference
        "def register(p):\n"
        "    p.set_defaults(handler=a)\n"       # the callback argument — cli.py's shape, x26
        "    table = {'b': b, 'k': K}\n"        # the dispatch table
        "    return table\n"
        "@w(on=b)\n"                            # the decorator's argument; `w` itself is `decorates`
        "def c(x=a):\n"                         # the default
        "    b()\n"                             # a call, not a reference
        "    return json.dumps\n"               # an import's attribute, read as a value
        "def shadow(a):\n"
        "    return a\n"                        # the parameter shadows the def: nothing
        "def shadow2():\n"
        "    b = 1\n"
        "    return b\n"                        # a rebound local: nothing
        "def typed(k: K) -> K:\n"
        "    return os.path.join\n"             # the annotations are types; the chain is a value
        "DISPATCH = {'c': c}\n"                 # the module's own top level
        "if __name__ == '__main__':\n"
        "    c()\n"                             # a module-level call: never a reference
        # review round 1 of #94: the module's and a class body's own rebindings shadow too — a name match
        # minted from a comprehension target, a lambda's parameter, a for target, a class-level assignment
        "import email\n"
        "M = {raw: email for email, raw in ()}\n"
        "def la(): pass\n"
        "def fb(): pass\n"
        "L = lambda la: la\n"                  # the lambda's parameter shadows la on the module
        "for fb in ():\n    pass\n"           # the for target shadows fb on the module
        "USE = fb\n"
        "class C(Generic[K]):\n"               # a subscripted base is `inherits`, never a reference to its head
        "    a = 1\n"
        "    USES = a\n"
        "    OK = K\n"
        # review round 2 of #94: a match capture — a star or a mapping rest — binds too
        "match ():\n    case [*fb]:\n        pass\n    case {**la}:\n        pass\n",
        encoding="utf-8",
    )
    records = list(python_ast._emit_records_for_file(mod, tmp_path, "sample"))
    refs = Counter((r["src"].rsplit("/", 1)[1], r["dst_repr"]) for r in records if r.get("edge_type") == "references")
    assert refs == Counter({
        ("sample.K", "a"): 1,
        ("sample.register", "a"): 1, ("sample.register", "b"): 1, ("sample.register", "K"): 1,
        ("sample.c", "b"): 1, ("sample.c", "a"): 1, ("sample.c", "json.dumps"): 1,
        ("sample.typed", "os.path.join"): 1,
        ("sample", "c"): 1,
        ("sample.C", "K"): 1,                   # the class's own reference; `a` is rebound in the body, `email` on the module
    }), refs
    assert ("sample.C", "Generic") not in refs and {r["dst_repr"] for r in records if r.get("edge_type") == "inherits"} == {"object", "Generic[K]"}
    calls = {(r["src"].rsplit("/", 1)[1], r["dst_repr"]) for r in records if r.get("edge_type") == "calls"}
    assert calls == {("sample.register", "p.set_defaults"), ("sample.c", "w"), ("sample.c", "b")}
    for r in records:
        if r.get("edge_type") == "references":
            assert isinstance(r.get("line"), int) and r["line"] > 0 and "dst" not in r     # text for the resolver
    validate_graph({r["id"]: r for r in records if r["kind"] == "node"},
                   [r for r in records if r["kind"] == "edge"], PYTHON_AST_VOCABULARY)
    # the engine's own sharpest case: every `_cmd_*` handler is a value `_build_parser` binds
    cli = GRAPHOS / "graphy" / "cli.py"
    recs = list(python_ast._emit_records_for_file(cli, GRAPHOS / "graphy", "graphy"))
    binders = {r["src"].rsplit(".", 1)[1] for r in recs if r.get("edge_type") == "references" and r["dst_repr"] == "_cmd_check"}
    assert binders == {"_build_parser"}, binders


def test_GREEN_a_reference_and_an_annotation_read_the_scope_symtable_binds_not_a_hand_list(tmp_path):
    """Whether a name a scope reads is the definition it spells was two hand lists of Python's binders
    (`_rebound_names` · `_shadow_in`), holed twice in one rung (graphyos #141). One reader over CPython's
    `symtable` answers it: a def's decorator and defaults are the scope around the def, a comprehension
    cannot rebind a function's parameter, a file the interpreter's own scope analysis refuses mints
    nothing — and a name a def binds and an assignment binds again still shadows, as it did."""
    from graphy.adapters import python_ast
    mod = tmp_path / "sample.py"
    mod.write_text(
        "class Ctx: pass\n"
        "def helper(): pass\n"
        "def wrap(f): return f\n"
        "def reg(*a): return wrap\n"
        "@reg(lambda ctx: ctx)\n"                   # the lambda is the module's, not `run`'s
        "def run(ctx: Ctx):\n"
        "    return ctx.go\n"
        "def each(ctx: Ctx):\n"
        "    return [ctx for ctx in ()]\n"          # the comprehension's own ctx: the parameter still means Ctx
        "def again(ctx: Ctx):\n"
        "    ctx = 1\n"                             # a real rebinding: no annotation
        "@reg(helper := 1)\n"                       # a decorator's walrus rebinds helper on the module
        "def dec(): pass\n"
        "USE = helper\n"
        "def twice(): pass\n"
        "twice = wrap(twice)\n"                     # a def bound again by an assignment still shadows
        "T = twice\n"
        "class K:\n"
        "    def m(self, __p: Ctx):\n"
        "        __p = 1\n"                         # symtable spells it `_K__p`: still a rebinding
        "    def n(self, __q: Ctx):\n"
        "        return [__q for __q in ()]\n"
        "    W = [wrap for wrap in ()]\n"           # a class body's comprehension target
        "    V = wrap\n",
        encoding="utf-8",
    )
    records = list(python_ast._emit_records_for_file(mod, tmp_path, "sample"))
    ann = {r["dotted"]: r["annotations"] for r in records if r.get("node_type") in ("func", "method")}
    assert ann["sample.run"] == {"ctx": "Ctx"} and ann["sample.each"] == {"ctx": "Ctx"}, ann
    assert ann["sample.again"] is None and ann["sample.K.m"] is None and ann["sample.K.n"] == {"__q": "Ctx"}, ann
    refs = sorted((r["src"].rsplit("/", 1)[1], r["dst_repr"]) for r in records if r.get("edge_type") == "references")
    assert ("sample", "helper") not in refs and ("sample", "twice") not in refs and ("sample.K", "wrap") not in refs, refs
    # the interpreter's own scope analysis refuses a file ast.parse accepts: nothing is bound, nothing minted
    bad = tmp_path / "dup.py"
    bad.write_text("class Ctx: pass\ndef f(ctx: Ctx, ctx: Ctx):\n    return Ctx\nX = Ctx\n", encoding="utf-8")
    recs = list(python_ast._emit_records_for_file(bad, tmp_path, "dup"))
    assert [r for r in recs if r.get("edge_type") == "references"] == []
    assert [r["annotations"] for r in recs if r.get("node_type") == "func"] == [None]
    # the reader is the oracle's: every scope of the engine answers what symtable says it binds
    import symtable
    src = (GRAPHOS / "graphy" / "cli.py").read_text(encoding="utf-8")
    import ast as _ast
    *_, scopes = python_ast._scan(_ast.parse(src), src)
    table = symtable.symtable(src, "cli.py", "exec")
    assigned = {s.get_name() for s in table.get_symbols() if s.is_assigned() and not s.is_namespace()}
    assert assigned <= scopes.of(None), assigned - scopes.of(None)
