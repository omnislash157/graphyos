"""typescript_ast — the second producer: TypeScript (and TSX) onto the nine words.

tree-sitter parses; this module maps. A file is a module (``src/router/index.ts`` folds to
``pkg.router`` the way ``__init__.py`` does), ``class`` · ``abstract class`` · ``interface`` are
class, a ``function`` declaration or a ``const x = (…) => …`` / ``const x = function`` at module
level is func, a method or accessor inside a class body is method. ``import``/``export … from``
are ``imports`` edges — a relative specifier resolved to the module it names, a bare one to the
package it names (``pkg://module/pkg``, a wormhole literal once that package is minted; Node's
built-ins are the ecosystem's standard library); ``extends`` and ``implements`` are ``inherits``
with the target left as text for the resolver; decorators are ``decorates``; every call and
``new`` inside a function or method body is ``calls`` with the callee as text. Every node
carries ``module`` and, when the file is a test by this producer's rule, ``role: test``.

No consumer downstream knows any of this: the store, the walk, the doors, pillars and arms read
only the vocabulary. tree-sitter is an optional extra (``pip install 'graphyos[typescript]'``);
without it this producer refuses by name and the core is untouched.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterator

from graphy.adapters._receipt import Receipt
from graphy.ir import EDGE_TYPES, NODE_TYPES, Vocabulary

__all__ = ["build_ir", "mint_records", "walk_files", "is_package_dir", "TYPESCRIPT_AST_VOCABULARY", "NODE_STANDARD",
           "ProducerUnavailable", "slug_of_specifier"]

TYPESCRIPT_AST_VOCABULARY = Vocabulary(node_types=NODE_TYPES, edge_types=EDGE_TYPES, producer="typescript_ast")

# Node's built-in modules: the ecosystem's standard library, the producer's to name.
NODE_STANDARD = frozenset({
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto",
    "dgram", "diagnostics_channel", "dns", "domain", "events", "fs", "http", "http2", "https",
    "inspector", "module", "net", "os", "path", "perf_hooks", "process", "punycode", "querystring",
    "readline", "repl", "stream", "string_decoder", "sys", "timers", "tls", "trace_events", "tty",
    "url", "util", "v8", "vm", "wasi", "worker_threads", "zlib", "test", "sea", "sqlite",
})

_CHECKOUT_EXCLUDES = ("node_modules", ".git", "dist", "build", "coverage", ".next", "out")
_SHIPPED_EXCLUDES = ("node_modules", ".git")
_DEFAULT_EXCLUDES = _CHECKOUT_EXCLUDES
_TS_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")
_JS_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")
_SOURCE_SUFFIXES = _TS_SUFFIXES + _JS_SUFFIXES
TEST_FILE = re.compile(r"(^|/)(__tests__|tests?|test-utils?)/|\.(test|spec)\.(ts|tsx|mts|cts|js|jsx|mjs|cjs)$")
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class ProducerUnavailable(RuntimeError):
    pass


def _parsers():
    try:
        import tree_sitter
        import tree_sitter_typescript as tst
    except ImportError as exc:
        raise ProducerUnavailable(
            "the typescript_ast producer needs tree-sitter — pip install 'graphyos[typescript]' "
            f"({exc})") from exc
    ts = tree_sitter.Parser(tree_sitter.Language(tst.language_typescript()))
    tsx = tree_sitter.Parser(tree_sitter.Language(tst.language_tsx()))
    return ts, tsx


def slug_of_specifier(spec: str) -> str | None:
    """The scheme a bare import specifier names: ``hono`` → ``hono``; ``@hono/node-server/x`` →
    ``hono__node_server`` (a scoped name and its subpath fold to the package); ``node:fs`` → ``fs``.
    None when the name cannot be a slug."""
    s = spec.strip()
    if not s or s.startswith((".", "/")):
        return None                      # a relative or absolute path is a file, never a package
    if s.startswith("node:"):
        s = s[5:]
    parts = s.split("/")
    name = "/".join(parts[:2]) if s.startswith("@") and len(parts) >= 2 else parts[0]
    slug = name.lstrip("@").replace("/", "__").replace("-", "_").replace(".", "_").lower()
    return slug if _SLUG_RE.match(slug) else None


def is_package_dir(path: Path) -> bool:
    return path.is_dir() and next((f for f in path.rglob("*") if f.suffix in _SOURCE_SUFFIXES), None) is not None


_CHECKOUT_NOISE = ("examples", "example", "benchmarks", "benchmark", "docs", "doc", "scripts", "fixtures", "__mocks__")


def excludes_for(root: Path) -> tuple[str, ...]:
    """A checkout (a ``src/`` with sources, or a ``.git``) is read from its source: build output
    and the folders that are not the package — examples, benchmarks, docs — are skipped, and its
    tests are read but marked. A shipped package (what node_modules holds) is read from what it
    ships, ``dist/`` and ``lib/`` included, because that is the package."""
    src = root / "src"
    if src.is_dir() and any(f.suffix in _SOURCE_SUFFIXES for f in src.rglob("*") if f.is_file()):
        return _CHECKOUT_EXCLUDES + _CHECKOUT_NOISE
    if (root / ".git").exists():
        return _CHECKOUT_EXCLUDES + _CHECKOUT_NOISE
    return _SHIPPED_EXCLUDES


def walk_files(root: Path, exclude: tuple[str, ...] | None = None) -> Iterator[Path]:
    excluded = set(excludes_for(root) if exclude is None else exclude)
    depth = len(root.parts)                  # rglob yields under root: the prefix is cut by parts, never relative_to
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in _SOURCE_SUFFIXES or f.name.endswith((".d.ts", ".d.mts", ".d.cts", ".min.js")):
            continue
        if excluded.intersection(f.parts[depth:]):
            continue
        yield f


def _node_id(kind: str, dotted: str) -> str:
    return f"{dotted.split('.', 1)[0]}://{kind}/{dotted}"


def _dotted_for(file: Path, root: Path, package: str) -> str:
    rel = file.relative_to(root)
    parts = list(rel.parts)
    stem = parts[-1]
    for suf in _SOURCE_SUFFIXES:
        if stem.endswith(suf):
            stem = stem[:-len(suf)]
            break
    parts[-1] = stem
    if parts[-1] == "index":
        parts = parts[:-1]
    parts = [p.replace("-", "_").replace(".", "_") for p in parts]
    return ".".join([package] + parts) if parts else package


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _expr_repr(node, src: bytes) -> str | None:
    """A dotted repr for the callees and bases the resolver can bind: identifiers, member chains,
    ``this.x``, ``super.x``, ``new X`` and generic instantiations. Anything else is not a label."""
    t = node.type
    if t in ("identifier", "type_identifier", "this", "super", "property_identifier", "private_property_identifier"):
        return _text(node, src)
    if t == "member_expression":
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        if obj is None or prop is None:
            return None
        o = _expr_repr(obj, src)
        return f"{o}.{_text(prop, src)}" if o else None
    if t == "nested_type_identifier":
        return _text(node, src)
    if t == "generic_type":
        inner = node.child_by_field_name("name")
        return _expr_repr(inner, src) if inner is not None else None
    if t == "new_expression":
        ctor = node.child_by_field_name("constructor")
        return _expr_repr(ctor, src) if ctor is not None else None
    if t in ("parenthesized_expression", "non_null_expression", "as_expression", "satisfies_expression"):
        for c in node.named_children:
            r = _expr_repr(c, src)
            if r:
                return r
    if t == "call_expression":
        fn = node.child_by_field_name("function")
        return _expr_repr(fn, src) if fn is not None else None
    return None


def _calls_in(body, src: bytes) -> Iterator[tuple[str, int]]:
    """Every call and ``new`` inside a body, not descending into nested function or class
    definitions (those are their own nodes)."""
    stack = list(body.named_children)
    while stack:
        n = stack.pop()
        if n.type in ("function_declaration", "class_declaration", "abstract_class_declaration",
                      "method_definition", "function_expression", "arrow_function", "generator_function_declaration"):
            continue
        if n.type in ("call_expression", "new_expression"):
            fn = n.child_by_field_name("function") if n.type == "call_expression" else n.child_by_field_name("constructor")
            if fn is not None:
                r = _expr_repr(fn, src)
                if r == "require":
                    pass                                      # a binding, not a call: _requires_in reads it
                elif r and r not in ("super",):
                    yield (r + "(...)"), n.start_point[0] + 1
                elif r == "super":
                    yield "super(...)", n.start_point[0] + 1
        stack.extend(n.named_children)


def _unwrap_export(stmt):
    """``export [default] <declaration>`` → the declaration; anything else → itself."""
    if stmt.type == "export_statement":
        decl = stmt.child_by_field_name("declaration")
        if decl is not None:
            return decl
        for c in stmt.named_children:
            if c.type in ("class_declaration", "abstract_class_declaration", "function_declaration",
                          "interface_declaration", "lexical_declaration", "generator_function_declaration"):
                return c
    return stmt


def _func_of_lexical(decl):
    """``const x = (…) => …`` / ``const x = function …``: (name node, function node) per declarator."""
    for d in decl.named_children:
        if d.type != "variable_declarator":
            continue
        name = d.child_by_field_name("name")
        value = d.child_by_field_name("value")
        if name is None or value is None or name.type != "identifier":
            continue
        v = value
        while v.type in ("parenthesized_expression", "as_expression", "satisfies_expression", "non_null_expression") and v.named_children:
            v = v.named_children[0]
        if v.type in ("arrow_function", "function_expression", "function", "generator_function"):
            yield name, v


def _require_spec(value, src: bytes):
    """``require('x')``, or ``require('x')(…)`` (a call on what require returned): the specifier."""
    v = value
    while v is not None and v.type in ("parenthesized_expression", "non_null_expression", "as_expression"):
        v = v.named_children[0] if v.named_children else None
    if v is None or v.type != "call_expression":
        return None
    fn = v.child_by_field_name("function")
    if fn is not None and fn.type == "call_expression":          # require('debug')('express')
        return _require_spec(fn, src)
    if fn is None or fn.type != "identifier" or _text(fn, src) != "require":
        return None
    args = v.child_by_field_name("arguments")
    if args is None or not args.named_children or args.named_children[0].type != "string":
        return None
    return _text(args.named_children[0], src).strip("'\"`")


def _requires_in(stmt, src: bytes) -> Iterator[tuple[str, list, int]]:
    """CommonJS bindings at module level: ``const x = require('y')`` binds x to the module,
    ``const {a, b: c} = require('y')`` binds names, ``module.exports.X = require('y')`` and
    ``exports.X = require('y')`` re-export the module as X. Each yields (specifier, names, line)."""
    line = stmt.start_point[0] + 1
    if stmt.type in ("lexical_declaration", "variable_declaration"):
        for d in stmt.named_children:
            if d.type != "variable_declarator":
                continue
            spec = _require_spec(d.child_by_field_name("value"), src)
            if spec is None:
                continue
            pat = d.child_by_field_name("name")
            if pat is None:
                continue
            if pat.type == "identifier":
                yield spec, [(None, _text(pat, src))], line
            elif pat.type == "object_pattern":
                names = []
                for c in pat.named_children:
                    if c.type == "shorthand_property_identifier_pattern":
                        names.append((_text(c, src), None))
                    elif c.type == "pair_pattern":
                        k, v = c.child_by_field_name("key"), c.child_by_field_name("value")
                        if k is not None and v is not None and v.type == "identifier":
                            names.append((_text(k, src), _text(v, src)))
                yield spec, names, line
    elif stmt.type == "expression_statement" and stmt.named_children:
        e = stmt.named_children[0]
        while e.type == "assignment_expression":
            left, right = e.child_by_field_name("left"), e.child_by_field_name("right")
            if left is not None and right is not None:
                spec = _require_spec(right, src)
                if spec is not None:
                    lt = _text(left, src)
                    if lt.startswith(("module.exports.", "exports.")):
                        yield spec, [(None, lt.rsplit(".", 1)[-1])], line
                    elif lt in ("module.exports", "exports"):
                        yield spec, [], line
                    break
                e = right
            else:
                break


def _assigned_functions(stmt, src: bytes) -> Iterator[tuple[str, Any]]:
    """The CommonJS idiom: a function assigned to a member at module level is a definition.
    ``app.listen = function () {…}`` is ``app.listen``; ``exports.query = function …`` and
    ``module.exports.Route = …`` are ``query`` and ``Route``; ``module.exports = function name…``
    is ``name``; an anonymous function assigned to ``module.exports`` has no name and is no node."""
    e = stmt.named_children[0] if stmt.named_children else None
    if e is None or e.type != "assignment_expression":
        return
    left, right = e.child_by_field_name("left"), e.child_by_field_name("right")
    if left is None or right is None:
        return
    v = right
    while v.type == "assignment_expression":               # exports = module.exports = fn
        v = v.child_by_field_name("right")
    while v is not None and v.type in ("parenthesized_expression", "as_expression") and v.named_children:
        v = v.named_children[0]
    if v is None or v.type not in ("function_expression", "function", "arrow_function", "generator_function"):
        return
    lt = _text(left, src)
    if lt.startswith("module.exports."):
        name = lt[len("module.exports."):]
    elif lt.startswith("exports."):
        name = lt[len("exports."):]
    elif lt in ("module.exports", "exports"):
        nn = v.child_by_field_name("name")
        if nn is None:
            return
        name = _text(nn, src)
    elif left.type in ("member_expression", "identifier") and all(p.isidentifier() for p in lt.split(".")):
        name = lt
    else:
        return
    yield name, v


def _heritage(cls_node, src: bytes) -> Iterator[str]:
    for c in cls_node.named_children:
        if c.type == "class_heritage":
            for h in c.named_children:
                if h.type in ("extends_clause", "implements_clause"):
                    for v in h.named_children:
                        r = _expr_repr(v, src)
                        if r:
                            yield r
        elif c.type == "extends_type_clause":          # interface X extends Y, Z
            for v in c.named_children:
                r = _expr_repr(v, src)
                if r:
                    yield r


def _decorators(node, src: bytes) -> Iterator[str]:
    for c in node.named_children:
        if c.type == "decorator":
            inner = c.named_children[0] if c.named_children else None
            r = _expr_repr(inner, src) if inner is not None else None
            if r:
                yield r


def _walk_class(cls, class_dotted: str, class_id: str, file_rel: str, src: bytes) -> Iterator[dict]:
    body = cls.child_by_field_name("body")
    if body is None:
        return
    for m in body.named_children:
        if m.type not in ("method_definition", "method_signature", "abstract_method_signature"):
            continue
        name_node = m.child_by_field_name("name")
        if name_node is None:
            continue
        name = _text(name_node, src)
        dotted = f"{class_dotted}.{name}"
        mid = _node_id("method", dotted)
        params = m.child_by_field_name("parameters")
        yield {"kind": "node", "node_type": "method", "id": mid, "name": name, "dotted": dotted, "file": file_rel,
               "line": m.start_point[0] + 1, "is_async": any(c.type == "async" for c in m.children),
               "args": [_text(p.child_by_field_name("pattern") or p, src) for p in (params.named_children if params else [])
                        if p.type in ("required_parameter", "optional_parameter", "rest_parameter")],
               "returns": None, "docstring": "", "container_class": class_dotted.rsplit(".", 1)[-1]}
        yield {"kind": "edge", "edge_type": "contains", "src": class_id, "dst": mid}
        for d in _decorators(m, src):
            yield {"kind": "edge", "edge_type": "decorates", "src_repr": d, "dst": mid, "line": m.start_point[0] + 1}
        mbody = m.child_by_field_name("body")
        if mbody is not None:
            for call, line in _calls_in(mbody, src):
                yield {"kind": "edge", "edge_type": "calls", "src": mid, "dst_repr": call, "line": line}


def _walk_module(tree, module_id: str, module_dotted: str, file_rel: str, src: bytes,
                 resolve_import) -> Iterator[dict]:
    for raw in tree.root_node.named_children:
        stmt = _unwrap_export(raw)
        t = stmt.type
        if t in ("import_statement",) or (t == "export_statement" and stmt.child_by_field_name("source") is not None):
            source = stmt.child_by_field_name("source")
            if source is None:
                continue
            spec = _text(source, src).strip("'\"`")
            dst = resolve_import(spec)
            if dst is None:
                continue
            names: list[tuple[str | None, str | None]] = []
            for c in stmt.named_children:
                if c.type == "import_clause":
                    for cc in c.named_children:
                        if cc.type == "identifier":                       # default import
                            names.append(("default", _text(cc, src)))
                        elif cc.type == "namespace_import":
                            ident = next((x for x in cc.named_children if x.type == "identifier"), None)
                            if ident is not None:
                                names.append((None, _text(ident, src)))     # import * as ns → binds ns to the module
                        elif cc.type == "named_imports":
                            for spec_node in cc.named_children:
                                if spec_node.type != "import_specifier":
                                    continue
                                n = spec_node.child_by_field_name("name")
                                a = spec_node.child_by_field_name("alias")
                                if n is not None:
                                    names.append((_text(n, src), _text(a, src) if a is not None else None))
                elif c.type == "export_clause":
                    for spec_node in c.named_children:
                        if spec_node.type != "export_specifier":
                            continue
                        n = spec_node.child_by_field_name("name")
                        a = spec_node.child_by_field_name("alias")
                        if n is not None:
                            names.append((_text(n, src), _text(a, src) if a is not None else None))
                elif c.type == "namespace_export":
                    ident = next((x for x in c.named_children if x.type == "identifier"), None)
                    names.append((None, _text(ident, src) if ident is not None else None))
            line = stmt.start_point[0] + 1
            if not names:
                yield {"kind": "edge", "edge_type": "imports", "src": module_id, "dst": dst, "line": line}
            for name, alias in names:
                e = {"kind": "edge", "edge_type": "imports", "src": module_id, "dst": dst, "line": line}
                if name is not None:
                    e["name"] = name
                    if alias and alias != name:
                        e["alias"] = alias
                elif alias:
                    e["alias"] = alias
                yield e
            continue
        if t in ("class_declaration", "abstract_class_declaration", "interface_declaration"):
            name_node = stmt.child_by_field_name("name")
            if name_node is None:
                continue
            name = _text(name_node, src)
            dotted = f"{module_dotted}.{name}"
            cid = _node_id("class", dotted)
            yield {"kind": "node", "node_type": "class", "id": cid, "name": name, "dotted": dotted, "file": file_rel,
                   "line": stmt.start_point[0] + 1, "docstring": "",
                   "interface": t == "interface_declaration"}
            yield {"kind": "edge", "edge_type": "contains", "src": module_id, "dst": cid}
            for base in _heritage(stmt, src):
                yield {"kind": "edge", "edge_type": "inherits", "src": cid, "dst_repr": base, "line": stmt.start_point[0] + 1}
            for d in _decorators(raw, src):
                yield {"kind": "edge", "edge_type": "decorates", "src_repr": d, "dst": cid, "line": stmt.start_point[0] + 1}
            yield from _walk_class(stmt, dotted, cid, file_rel, src)
            continue
        if t in ("lexical_declaration", "variable_declaration", "expression_statement"):
            for spec, names, line in _requires_in(stmt, src):
                dst = resolve_import(spec)
                if dst is None:
                    continue
                if not names:
                    yield {"kind": "edge", "edge_type": "imports", "src": module_id, "dst": dst, "line": line}
                for name, alias in names:
                    e = {"kind": "edge", "edge_type": "imports", "src": module_id, "dst": dst, "line": line}
                    if name is not None:
                        e["name"] = name
                        if alias and alias != name:
                            e["alias"] = alias
                    elif alias:
                        e["alias"] = alias
                    yield e
        funcs: list[tuple[str, Any, Any]] = []
        if t == "expression_statement":
            for name, fn in _assigned_functions(stmt, src):
                funcs.append((name, fn, stmt))
        if t in ("function_declaration", "generator_function_declaration"):
            name_node = stmt.child_by_field_name("name")
            if name_node is not None:
                funcs.append((_text(name_node, src), stmt, stmt))
        elif t in ("lexical_declaration", "variable_declaration"):
            for name_node, fn in _func_of_lexical(stmt):
                funcs.append((_text(name_node, src), fn, stmt))
        for name, fn, anchor in funcs:
            dotted = f"{module_dotted}.{name}"
            fid = _node_id("func", dotted)
            params = fn.child_by_field_name("parameters")
            yield {"kind": "node", "node_type": "func", "id": fid, "name": name, "dotted": dotted, "file": file_rel,
                   "line": anchor.start_point[0] + 1, "is_async": any(c.type == "async" for c in fn.children),
                   "args": [_text(p.child_by_field_name("pattern") or p, src) for p in (params.named_children if params else [])
                            if p.type in ("required_parameter", "optional_parameter", "rest_parameter")],
                   "returns": None, "docstring": "", "container_class": None}
            yield {"kind": "edge", "edge_type": "contains", "src": module_id, "dst": fid}
            body = fn.child_by_field_name("body")
            if body is not None:
                if body.type == "statement_block":
                    for call, line in _calls_in(body, src):
                        yield {"kind": "edge", "edge_type": "calls", "src": fid, "dst_repr": call, "line": line}
                else:                                   # an arrow function's expression body
                    for call, line in _calls_in(_Wrap([body]), src):
                        yield {"kind": "edge", "edge_type": "calls", "src": fid, "dst_repr": call, "line": line}


class _Wrap:
    def __init__(self, children):
        self.named_children = children


def _module_for_specifier(spec: str, file: Path, root: Path, package: str, modules: dict[str, str]) -> str | None:
    """A relative specifier → the module id it names (``./x`` → x.ts | x/index.ts | x.tsx …);
    a bare one → the package's module id (the scheme a slug can carry) or None."""
    if spec.startswith("."):
        base = (file.parent / spec).resolve()
        cands = [base]
        for suf in _SOURCE_SUFFIXES:
            cands.append(base.with_name(base.name + suf))
        for suf in _SOURCE_SUFFIXES:
            cands.append(base / f"index{suf}")
        if base.suffix in (".js", ".mjs", ".cjs"):        # `./x.js` in ESM-style TS names ./x.ts
            stem = base.with_suffix("")
            for suf in _SOURCE_SUFFIXES:
                cands.append(stem.with_name(stem.name + suf))
        for c in cands:
            key = str(c)
            if key in modules:
                return modules[key]
        return None
    slug = slug_of_specifier(spec)
    if slug is None:
        return None
    if slug == package:
        sub = spec.split("/", 2 if spec.startswith("@") else 1)[-1] if "/" in spec else ""
        return _node_id("module", ".".join([package] + [p.replace("-", "_") for p in sub.split("/") if p]) if sub else package)
    return _node_id("module", slug)


def build_ir(corpus_root: str | Path, package: str | None = None) -> tuple[dict, list]:
    nodes, edges, _ = mint_records(corpus_root, package)
    return nodes, edges


def mint_records(corpus_root: str | Path, package: str | None = None, *, reuse=None) -> tuple[dict, list, dict]:
    """``build_ir`` with the per-file receipt (see ``python_ast.mint_records``). A file's records
    are a function of its bytes, its path, the package name and the corpus's file list — a
    relative specifier resolves against the files that exist — so the ``pin`` carries the sorted
    file list's digest; ``reuse(pin, relpath, sha256)`` hands back a file's records or None."""
    root = Path(corpus_root).resolve()
    package = package or root.name.replace("-", "_")
    ts, tsx = _parsers()
    files = list(walk_files(root))
    modules: dict[str, str] = {}
    dotted_of: dict[Path, str] = {}
    rels: dict[Path, str] = {}
    for f in files:
        d = _dotted_for(f, root, package)
        dotted_of[f] = d
        modules[str(f.resolve())] = _node_id("module", d)
        rels[f] = str(f.relative_to(root)).replace("\\", "/")
    listing = hashlib.sha256("\n".join(sorted(rels.values())).encode("utf-8")).hexdigest()
    pin = f"typescript_ast:{package}:{listing}"
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    receipt = Receipt("first")
    for f in files:
        rel = rels[f]
        try:
            src = f.read_bytes()
        except OSError as exc:
            receipt.unreadable(rel, f"unreadable: {exc.strerror or exc.__class__.__name__}")
            continue
        sha = hashlib.sha256(src).hexdigest()
        cached = reuse(pin, rel, sha) if reuse is not None else None
        if cached is None:
            tree = (ts if f.suffix in (".ts", ".mts", ".cts") else tsx).parse(src)   # JSX-safe for everything else
            module_dotted = dotted_of[f]
            module_id = modules[str(f.resolve())]
            file_rel = str(f.relative_to(root.parent))
            role = "test" if TEST_FILE.search(str(f.relative_to(root)).replace("\\", "/")) else None
            mod_rec = {"kind": "node", "node_type": "module", "id": module_id, "dotted": module_dotted, "file": file_rel,
                       "loc": src.count(b"\n") + 1, "docstring": ""}
            records = [mod_rec] + list(_walk_module(
                tree, module_id, module_dotted, file_rel, src,
                lambda spec, _f=f: _module_for_specifier(spec, _f, root, package, modules)))
            n_recs, e_recs = [], []
            for rec in records:
                if rec["kind"] == "node":
                    rec["module"] = module_dotted
                    if role:
                        rec["role"] = role
                    n_recs.append(rec)
                else:
                    e_recs.append(rec)
        else:
            n_recs, e_recs = cached
        receipt.file(rel, sha, n_recs, e_recs, nodes, parsed=cached is None)
        edges.extend(e_recs)
    return nodes, edges, receipt.finish(pin)
