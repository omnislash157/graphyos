"""typescript_ast — the second producer: TypeScript (and TSX) onto the nine words.

tree-sitter parses; this module maps. A file is a module (``src/router/index.ts`` folds to
``pkg.router`` the way ``__init__.py`` does), ``class`` · ``abstract class`` · ``interface`` are
class, a ``function`` declaration or a ``const x = (…) => …`` / ``const x = function`` at module
level is func, a method or accessor inside a class body is method. ``import``/``export … from``
are ``imports`` edges — a relative specifier resolved to the module it names, a bare one to the
package it names (``pkg://module/pkg``, a wormhole literal once that package is minted; Node's
built-ins are the ecosystem's standard library); ``extends`` and ``implements`` are ``inherits``
with the target left as text for the resolver; decorators are ``decorates``; every call and
``new`` inside a function or method body is ``calls`` with the callee as text; a function or
class read as a value (``app.get('/', handler)``, ``{ handler }``, a default, a decorator's
argument, a route table at the module's top level) is ``references``, its head bound by the
module's own declarations and imports and never by a name match. Every node
carries ``module`` and, when the file is a test by this producer's rule, ``role: test``.

No consumer downstream knows any of this: the store, the walk, the doors, pillars and arms read
only the vocabulary. tree-sitter is an optional extra (``pip install 'graphyos[typescript]'``);
without it this producer refuses by name and the core is untouched.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator

from graphy.adapters._receipt import Receipt
from graphy.ir import DEPENDS, PYTHON_AST_RELATIONS, REACHES, EDGE_TYPES, NODE_TYPES, Vocabulary

__all__ = ["build_ir", "mint_records", "walk_files", "is_package_dir", "TYPESCRIPT_AST_VOCABULARY", "NODE_STANDARD",
           "ProducerUnavailable", "slug_of_specifier"]

# The same nine words, so the same meanings: a consumer must not be able to tell the language
# from the door it opens (graphyos #68). Two more, declared here and nowhere else: a reactive
# binding is a `state` node, and an assignment to one is `writes` — blast on the state names every
# writer, descend from a writer arrives at the state (graphyos #85).
TYPESCRIPT_AST_VOCABULARY = Vocabulary(node_types=tuple(NODE_TYPES) + ("state",),
                                       edge_types=tuple(EDGE_TYPES) + ("writes",),
                                       producer="typescript_ast",
                                       relations={**PYTHON_AST_RELATIONS, "writes": (DEPENDS, REACHES)})

# Svelte 5's runes: compiler keywords, never imported, so no scope can bind them — the producer
# names them, exactly, the way NODE_STANDARD names Node's built-ins. A `state` or `derived` rune's
# declarator is a state node; the rest are calls like any other. Lifecycle functions (onMount,
# onDestroy) are imports from `svelte`, resolved by the ring, and never belong here. Svelte 4's
# `$:` statements and `$store` subscriptions are another syntax and are not read.
SVELTE_RUNES = {
    "$state": "state", "$state.raw": "state",
    "$derived": "derived", "$derived.by": "derived",
    "$props": "props", "$bindable": "props",
    "$effect": "effect", "$effect.pre": "effect", "$effect.root": "effect",
    "$inspect": "debug", "$host": "host",
}
_STATE_RUNES = ("state", "derived")

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
# A single-file component is a module whose script blocks are TypeScript or JavaScript: the blocks
# are walked by the same pass, the markup around them is blanked byte for byte so every line and
# offset is the file's own. The template is markup, not a program, and is not read (graphyos #85).
_COMPONENT_SUFFIXES = (".svelte", ".vue")
_READ_SUFFIXES = _SOURCE_SUFFIXES + _COMPONENT_SUFFIXES
TEST_FILE = re.compile(r"(^|/)(__tests__|tests?|test-utils?)/|\.(test|spec)\.(ts|tsx|mts|cts|js|jsx|mjs|cjs|svelte|vue)$")
_SCRIPT_BLOCK = re.compile(
    rb"<!--.*?-->|(?m:^)[ \t]*<script\b((?:\"[^\"]*\"|'[^']*'|[^'\">])*)>(.*?)</script\s*>", re.S | re.I)
_TS_LANG = re.compile(rb"""\blang\s*=\s*["']?(ts|typescript)\b""", re.I)
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
    return path.is_dir() and next((f for f in path.rglob("*") if f.suffix in _READ_SUFFIXES), None) is not None


def component_script(src: bytes) -> tuple[bytes, bool]:
    """A single-file component's script blocks in place: every byte outside a ``<script>`` body
    becomes a space (newlines kept), so the parse sees one program at the file's own lines and
    offsets. A ``<script>`` inside an HTML comment, or one that does not open its line
    (``{@html '<script>'}``), is markup. Returns (bytes, is_typescript)."""
    out = bytearray(b if b == 0x0A else 0x20 for b in src)
    is_ts = False
    for m in _SCRIPT_BLOCK.finditer(src):
        if m.group(2) is None:
            continue                                            # a comment
        out[m.start(2):m.end(2)] = m.group(2)
        is_ts = is_ts or bool(_TS_LANG.search(m.group(1)))
    return bytes(out), is_ts


_CHECKOUT_NOISE = ("examples", "example", "benchmarks", "benchmark", "docs", "doc", "scripts", "fixtures", "__mocks__")


def excludes_for(root: Path) -> tuple[str, ...]:
    """A checkout (a ``src/`` with sources, or a ``.git``) is read from its source: build output
    and the folders that are not the package — examples, benchmarks, docs — are skipped, and its
    tests are read but marked. A shipped package (what node_modules holds) is read from what it
    ships, ``dist/`` and ``lib/`` included, because that is the package."""
    src = root / "src"
    if src.is_dir() and any(f.suffix in _READ_SUFFIXES for f in src.rglob("*") if f.is_file()):
        return _CHECKOUT_EXCLUDES + _CHECKOUT_NOISE
    if (root / ".git").exists():
        return _CHECKOUT_EXCLUDES + _CHECKOUT_NOISE
    return _SHIPPED_EXCLUDES


def walk_files(root: Path, exclude: tuple[str, ...] | None = None) -> Iterator[Path]:
    excluded = set(excludes_for(root) if exclude is None else exclude)
    depth = len(root.parts)                  # rglob yields under root: the prefix is cut by parts, never relative_to
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in _READ_SUFFIXES or f.name.endswith((".d.ts", ".d.mts", ".d.cts", ".min.js")):
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
    for suf in _READ_SUFFIXES:
        if stem.endswith(suf):
            stem = stem[:-len(suf)]
            break
    parts[-1] = stem
    if parts[-1] == "index" and file.suffix not in _COMPONENT_SUFFIXES:
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


def _calls_in(body, src: bytes, anonymous: bool = False) -> Iterator[tuple[str, int]]:
    """Every call and ``new`` inside a body, not descending into nested function or class
    definitions (those are their own nodes). ``anonymous`` descends into function expressions and
    arrows, for a component's top level, where ``onMount(() => load())`` is the component's own call."""
    skip = {"function_declaration", "class_declaration", "abstract_class_declaration",
            "method_definition", "generator_function_declaration"}
    if not anonymous:
        skip |= {"function_expression", "arrow_function"}
    stack = list(body.named_children)
    while stack:
        n = stack.pop()
        if n.type in skip:
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


_REF_SKIP_TYPES = frozenset({"type_annotation", "type_arguments", "type_parameters", "type_predicate",
                             "asserts", "export_clause", "type_alias_declaration", "interface_declaration"})


def _refs_in(body, src: bytes, bound: frozenset, shadow=frozenset(), anonymous: bool = False) -> Iterator[tuple[str, int]]:
    """Every name READ AS A VALUE under ``body`` whose head the module binds (``bound``: a top-level
    function, class or import) and no scope between the reader and the module rebinds, as (label, line)
    — ``app.get('/', handler)`` · ``{ handler }`` · ``ns.handler`` · ``@d(handler)`` (graphyos #94).
    The shadow is lexical, the way ``_writes_in`` keeps it: ``shadow`` is the enclosing function's
    (its parameters and hoisted names), a block adds its own ``let``/``const``/declarations, a ``for``
    its loop variables, a ``catch`` its parameter, a function expression or arrow (when descended) its
    parameters and hoisted names — each for its own subtree only (review round 1: a module-level
    ``for (const helper of …)`` read the loop variable as the import it shadows). The same descent rules
    as ``_calls_in``: never into a nested declaration, into a function expression or arrow only when
    ``anonymous``. A callee is the ``calls`` edge and not a reference; a member chain is one label and
    its inner names are not their own; a property name, a type (an annotation, a type alias, an
    interface), a declared name and a shorthand pattern are never values. ``this`` binds nothing here."""
    skip = {"function_declaration", "class_declaration", "abstract_class_declaration",
            "method_definition", "generator_function_declaration"}
    if not anonymous:
        skip |= {"function_expression", "arrow_function"}
    stack = [(c, False, frozenset(shadow)) for c in body.named_children]
    while stack:
        n, callee, sh = stack.pop()
        t = n.type
        if t in skip or t in _REF_SKIP_TYPES:
            continue
        if t in ("identifier", "shorthand_property_identifier"):
            if not callee:
                name = _text(n, src)
                if name in bound and name not in sh:
                    yield name, n.start_point[0] + 1
            continue
        if t == "member_expression":
            if _pure_chain(n):                             # `a.b.c`: one label, its inner names are the chain's own
                r = _expr_repr(n, src)
                head = r.split(".", 1)[0] if r else None
                if head and not callee and head in bound and head not in sh:
                    yield r, n.start_point[0] + 1
                continue
            # `f(1).prop` · `f[0].prop` · `(x as T).prop`: no name spells this chain — `_expr_repr` would
            # flatten it to `f.prop`, a label nothing binds, from a head that is the call's callee (review
            # round 2). Descend: the call keeps its callee flag, a bare name inside is its own value.
            stack.extend((c, False, sh) for c in n.named_children)
            continue
        if t in ("call_expression", "new_expression"):
            fn = n.child_by_field_name("function") if t == "call_expression" else n.child_by_field_name("constructor")
            stack.extend((c, fn is not None and c == fn, sh) for c in n.named_children)   # a tree-sitter node has no identity
            continue
        if t in ("as_expression", "satisfies_expression"):   # `x as T`: the value, never the type
            if n.named_children:
                stack.append((n.named_children[0], False, sh))
            continue
        if t == "decorator":                               # a bare decorator is `decorates`; its call's arguments are values
            inner = n.named_children[0] if n.named_children else None
            if inner is not None and inner.type in ("call_expression", "new_expression"):
                stack.append((inner, False, sh))
            continue
        if t in ("variable_declarator", "required_parameter", "optional_parameter", "rest_parameter",
                 "assignment_pattern", "object_assignment_pattern"):
            for field in ("value", "right"):                # the declared name is a binding, its value a value
                v = n.child_by_field_name(field)
                if v is not None:
                    stack.append((v, False, sh))
            continue
        if t == "pair":                                     # `{ key: value }`: the key is a name, never a value
            v = n.child_by_field_name("value")
            if v is not None:
                stack.append((v, False, sh))
            continue
        if t in _FUNCTION_LIKE:                             # descended only when anonymous: its own scope
            sh = sh | _hoisted(n, src) | {x for p in (n.child_by_field_name("parameters"),) if p is not None
                                          for c in p.named_children for x in _bound_names(c.child_by_field_name("pattern") or c, src)}
        elif t in ("statement_block", "switch_body"):
            sh = sh | _block_names(n, src)
        elif t == "for_statement":
            init = n.child_by_field_name("initializer")
            if init is not None and init.type in ("lexical_declaration", "variable_declaration"):
                sh = sh | {x for d in init.named_children if d.type == "variable_declarator"
                           for x in _bound_names(d.child_by_field_name("name"), src)}
        elif t == "for_in_statement":                       # `for (const x of xs)`: x is bound, never read here
            left = n.child_by_field_name("left")
            if left is not None:
                sh = sh | set(_bound_names(left, src))
                stack.extend((c, False, sh) for c in n.named_children if c != left)
                continue
        elif t == "catch_clause":
            param = n.child_by_field_name("parameter")
            if param is not None:
                sh = sh | set(_bound_names(param, src))
                stack.extend((c, False, sh) for c in n.named_children if c != param)
                continue
        stack.extend((c, False, sh) for c in n.named_children)


def _pure_chain(node) -> bool:
    """``a.b.c`` and nothing else: every link of the object spine is a member expression and the base is
    a name (or ``this``/``super``). A call, a ``new``, a subscript, a cast or a parenthesis anywhere in
    the spine makes it an expression, not a name a scope can bind."""
    n = node
    while n.type == "member_expression":
        n = n.child_by_field_name("object")
        if n is None:
            return False
    return n.type in ("identifier", "this", "super")


def _module_bound(tree, src: bytes) -> frozenset[str]:
    """The names the module's own top level binds to something the resolver can reach: a function,
    class or interface declaration, a ``const x = () => …``, a CommonJS ``exports.x = function``
    whose name is one identifier, and every name an ``import`` or a ``require`` binds. The only
    heads a reference may carry (graphyos #94); a local or a parameter is never one."""
    out: set[str] = set()
    for raw in tree.root_node.named_children:
        stmt = _unwrap_export(raw)
        t = stmt.type
        if t == "import_statement":
            for c in stmt.named_children:
                if c.type != "import_clause":
                    continue
                for cc in c.named_children:
                    if cc.type == "identifier":
                        out.add(_text(cc, src))
                    elif cc.type == "namespace_import":
                        ident = next((x for x in cc.named_children if x.type == "identifier"), None)
                        if ident is not None:
                            out.add(_text(ident, src))
                    elif cc.type == "named_imports":
                        for spec_node in cc.named_children:
                            if spec_node.type != "import_specifier":
                                continue
                            n = spec_node.child_by_field_name("name")
                            a = spec_node.child_by_field_name("alias")
                            if a is not None:
                                out.add(_text(a, src))
                            elif n is not None:
                                out.add(_text(n, src))
        elif t in ("class_declaration", "abstract_class_declaration", "interface_declaration",
                   "function_declaration", "generator_function_declaration"):
            name_node = stmt.child_by_field_name("name")
            if name_node is not None:
                out.add(_text(name_node, src))
        elif t in ("lexical_declaration", "variable_declaration", "expression_statement"):
            for _spec, names, _line in _requires_in(stmt, src):
                for name, alias in names:
                    if alias:
                        out.add(alias)
                    elif name:
                        out.add(name)
            if t == "expression_statement":
                for name, _fn in _assigned_functions(stmt, src):
                    if name.isidentifier():
                        out.add(name)
            else:
                for name_node, _fn in _func_of_lexical(stmt):
                    out.add(_text(name_node, src))
    return frozenset(out)


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


def _walk_class(cls, class_dotted: str, class_id: str, file_rel: str, src: bytes, runes: bool = False,
                bound: frozenset = frozenset()) -> Iterator[dict]:
    body = cls.child_by_field_name("body")
    if body is None:
        return
    pending: list = []                                     # the decorators the grammar lays before a member, not under it
    for m in body.named_children:
        if m.type == "decorator":
            pending.append(m)
            continue
        decorators, pending = pending, []
        if m.type == "public_field_definition":            # `static handler = fn`: the class's own reference
            value = m.child_by_field_name("value")
            if value is not None and not (runes and _state_rune(value, src)):
                for label, line in _refs_in(_Wrap([value]), src, bound):
                    yield {"kind": "edge", "edge_type": "references", "src": class_id, "dst_repr": label, "line": line}
        if runes and m.type == "public_field_definition":
            name_node, rune = m.child_by_field_name("name"), _state_rune(m.child_by_field_name("value"), src)
            if name_node is not None and rune:
                dotted = f"{class_dotted}.{_text(name_node, src)}"
                sid = _node_id("state", dotted)
                yield {"kind": "node", "node_type": "state", "id": sid, "name": _text(name_node, src), "dotted": dotted,
                       "file": file_rel, "line": m.start_point[0] + 1, "docstring": "", "rune": rune,
                       "container_class": class_dotted.rsplit(".", 1)[-1]}
                yield {"kind": "edge", "edge_type": "contains", "src": class_id, "dst": sid}
            continue
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
            for label, line in _refs_in(_Wrap(decorators + list(m.named_children)), src, bound, frozenset(_scope_of(m, src))):
                yield {"kind": "edge", "edge_type": "references", "src": mid, "dst_repr": label, "line": line}
            if runes:
                for label, line in _writes_in(_Wrap([mbody]), src, frozenset(_scope_of(m, src))):
                    yield {"kind": "edge", "edge_type": "writes", "src": mid, "dst_repr": label, "line": line}


def _walk_module(tree, module_id: str, module_dotted: str, file_rel: str, src: bytes,
                 resolve_import, component: bool = False, runes: bool = False) -> Iterator[dict]:
    bound = _module_bound(tree, src)
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
            yield from _walk_class(stmt, dotted, cid, file_rel, src, runes, bound)
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
        if runes and t in ("lexical_declaration", "variable_declaration"):
            for d in stmt.named_children:
                if d.type != "variable_declarator":
                    continue
                name_node, rune = d.child_by_field_name("name"), _state_rune(d.child_by_field_name("value"), src)
                if rune and name_node is not None and name_node.type == "identifier":
                    name = _text(name_node, src)
                    sid = _node_id("state", f"{module_dotted}.{name}")
                    yield {"kind": "node", "node_type": "state", "id": sid, "name": name, "dotted": f"{module_dotted}.{name}",
                           "file": file_rel, "line": stmt.start_point[0] + 1, "docstring": "", "rune": rune,
                           "container_class": None}
                    yield {"kind": "edge", "edge_type": "contains", "src": module_id, "dst": sid}
        if runes and not funcs and t not in ("function_declaration", "generator_function_declaration",
                                              "import_statement", "class_declaration", "abstract_class_declaration"):
            for label, line in _writes_in(_Wrap([stmt]), src):
                yield {"kind": "edge", "edge_type": "writes", "src": module_id, "dst_repr": label, "line": line}
        if component and not funcs and t not in ("function_declaration", "generator_function_declaration"):
            # A component's top level runs per instance: its calls are the component's own, the way a
            # function body's are the function's — `onMount(() => load())` included.
            for call, line in _calls_in(_Wrap([stmt]), src, anonymous=True):
                yield {"kind": "edge", "edge_type": "calls", "src": module_id, "dst_repr": call, "line": line}
        if not funcs and t not in ("function_declaration", "generator_function_declaration", "import_statement"):
            # the module's own top level: a route table, a registry, `app.get('/', handler)` (graphyos #94)
            for label, line in _refs_in(_Wrap([raw]), src, bound, anonymous=component):
                yield {"kind": "edge", "edge_type": "references", "src": module_id, "dst_repr": label, "line": line}
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
                if runes:
                    for label, line in _writes_in(_Wrap([body]), src, frozenset(_scope_of(fn, src))):
                        yield {"kind": "edge", "edge_type": "writes", "src": fid, "dst_repr": label, "line": line}
                if body.type == "statement_block":
                    for call, line in _calls_in(body, src):
                        yield {"kind": "edge", "edge_type": "calls", "src": fid, "dst_repr": call, "line": line}
                else:                                   # an arrow function's expression body
                    for call, line in _calls_in(_Wrap([body]), src):
                        yield {"kind": "edge", "edge_type": "calls", "src": fid, "dst_repr": call, "line": line}
                # the parameters' defaults and the body; never the function's own name (a binding, not a value)
                for label, line in _refs_in(_Wrap([c for c in (params, body) if c is not None]), src, bound,
                                            frozenset(_scope_of(fn, src))):
                    yield {"kind": "edge", "edge_type": "references", "src": fid, "dst_repr": label, "line": line}


class _Wrap:
    def __init__(self, children):
        self.named_children = children


def _state_rune(value, src: bytes) -> str | None:
    """The rune a declarator's value calls, when it declares state (``$state(0)``, ``$derived.by(f)``)."""
    v = value
    while v is not None and v.type in ("parenthesized_expression", "as_expression", "satisfies_expression",
                                        "non_null_expression") and v.named_children:
        v = v.named_children[0]
    if v is None or v.type != "call_expression":
        return None
    fn = v.child_by_field_name("function")
    r = _expr_repr(fn, src) if fn is not None else None
    return r if r is not None and SVELTE_RUNES.get(r) in _STATE_RUNES else None


_FUNCTION_LIKE = ("function_declaration", "generator_function_declaration", "function_expression", "function",
                  "arrow_function", "generator_function", "method_definition")


def _bound_names(pattern, src: bytes) -> Iterator[str]:
    """Every identifier a parameter or declarator pattern binds (``{a, b: c}``, ``[x, ...y]``, ``z = 1``)."""
    stack = [pattern]
    while stack:
        n = stack.pop()
        if n.type in ("identifier", "shorthand_property_identifier_pattern"):
            yield _text(n, src)
        elif n.type == "pair_pattern":
            v = n.child_by_field_name("value")
            if v is not None:
                stack.append(v)
        elif n.type not in _FUNCTION_LIKE and n.type not in ("type_annotation", "property_identifier"):
            if n.type in ("assignment_pattern", "object_assignment_pattern"):
                left = n.child_by_field_name("left")
                if left is not None:
                    stack.append(left)
                continue
            stack.extend(n.named_children)


def _kind(node) -> str | None:
    """The declaration keyword a ``for … in/of`` carries (``let`` · ``const`` · ``var``), or None."""
    for i, c in enumerate(node.children):
        if node.field_name_for_child(i) == "kind":
            return c.type
    return None


def _hoisted(fn, src: bytes) -> set[str]:
    """The names a function binds for its whole body: its parameters and every ``var`` under it,
    nested functions left to their own scope. ``let``, ``const``, a class or a function declaration
    belongs to its block, and `_block_names` adds it where that block opens."""
    names: set[str] = set()
    if fn.type in ("function_expression", "function", "generator_function"):
        own = fn.child_by_field_name("name")                # `function count() { count = 8 }`: count is the function
        if own is not None:
            names.add(_text(own, src))
    params = fn.child_by_field_name("parameters") or fn.child_by_field_name("parameter")
    if params is not None:
        for p in (params.named_children if params.type == "formal_parameters" else [params]):
            pat = p.child_by_field_name("pattern") or p
            names.update(_bound_names(pat, src))
    body = fn.child_by_field_name("body")
    stack = list(body.named_children) if body is not None and body.type == "statement_block" else []
    while stack:
        n = stack.pop()
        if n.type in _FUNCTION_LIKE or n.type in ("class_declaration", "class", "abstract_class_declaration"):
            continue
        if n.type == "variable_declaration":
            for d in n.named_children:
                pat = d.child_by_field_name("name") if d.type == "variable_declarator" else None
                if pat is not None:
                    names.update(_bound_names(pat, src))
        elif n.type == "for_in_statement" and _kind(n) == "var":
            left = n.child_by_field_name("left")
            if left is not None:
                names.update(_bound_names(left, src))
        stack.extend(n.named_children)
    return names


def _block_names(block, src: bytes) -> set[str]:
    """The names a block binds for itself: its own ``let``/``const`` declarators, classes and function
    declarations (a module is strict, so a function declared in a block belongs to the block)."""
    names: set[str] = set()
    items = list(block.named_children)
    if block.type == "switch_body":                      # `case 1: let z` belongs to the switch body
        items = [c for case in block.named_children for c in case.named_children]
    for n in items:
        if n.type == "lexical_declaration":
            for d in n.named_children:
                pat = d.child_by_field_name("name") if d.type == "variable_declarator" else None
                if pat is not None:
                    names.update(_bound_names(pat, src))
        elif n.type in ("class_declaration", "abstract_class_declaration", "function_declaration",
                        "generator_function_declaration"):
            nm = n.child_by_field_name("name")
            if nm is not None:
                names.add(_text(nm, src))
    return names


def _scope_of(fn, src: bytes) -> set[str]:
    """The names bound for a function's whole body: the hoisted ones and its body block's own."""
    body = fn.child_by_field_name("body")
    own = _block_names(body, src) if body is not None and body.type == "statement_block" else set()
    return _hoisted(fn, src) | own


def _write_targets(target) -> Iterator[Any]:
    """The assignable leaves of an assignment's left side: a destructuring pattern
    (``[a, this.b] = …`` · ``({a, b: o.c, d = 1, ...e} = …)``) yields each element it writes."""
    stack = [target]
    while stack:
        n = stack.pop()
        if n.type in ("array_pattern", "object_pattern", "rest_pattern"):
            stack.extend(n.named_children)
        elif n.type in ("assignment_pattern", "object_assignment_pattern"):
            left = n.child_by_field_name("left")
            if left is not None:
                stack.append(left)
        elif n.type == "pair_pattern":
            value = n.child_by_field_name("value")
            if value is not None:
                stack.append(value)
        else:
            yield n


def _write_label(target, src: bytes, shadow) -> str | None:
    """The binding an assignment target writes: ``x`` · ``x.a.b`` and ``x[0]`` write ``x`` ·
    ``this.count.n`` writes ``this.count``. A name the enclosing scope rebinds writes nothing here."""
    chain = []
    n = target
    while n.type in ("member_expression", "subscript_expression", "parenthesized_expression", "non_null_expression"):
        if n.type == "member_expression":
            prop = n.child_by_field_name("property")
            chain.append(_text(prop, src) if prop is not None else None)
            n = n.child_by_field_name("object")
        elif n.type == "subscript_expression":
            chain.append(None)
            n = n.child_by_field_name("object")
        else:
            n = n.named_children[0] if n.named_children else None
        if n is None:
            return None
    if n.type == "this":
        return f"this.{chain[-1]}" if chain and chain[-1] and "this" not in shadow else None
    if n.type in ("identifier", "shorthand_property_identifier_pattern"):
        name = _text(n, src)
        return None if name in shadow else name
    return None


def _writes_in(node, src: bytes, shadow=frozenset()) -> Iterator[tuple[str, int]]:
    """Every assignment, compound assignment, ``++``/``--`` and bare ``for (x of …)`` target under
    ``node``, as (label, line). The shadow is lexical: a function adds its parameters and hoisted
    ``var``s, a block its own ``let``/``const``/declarations, a ``for`` its loop variables and a
    ``catch`` its parameter, each for its own subtree only (graphyos #85)."""
    stack = [(c, frozenset(shadow)) for c in node.named_children]
    while stack:
        n, sh = stack.pop()
        t = n.type
        if t in ("class_declaration", "class", "abstract_class_declaration"):
            continue                                        # a class's methods are their own nodes
        targets = []
        if t in _FUNCTION_LIKE:
            sh = sh | _hoisted(n, src)
            if t != "arrow_function" and not (t == "method_definition" and n.parent is not None
                                              and n.parent.type == "class_body"):
                sh = sh | {"this"}                          # a function or object method rebinds `this`
        elif t in ("statement_block", "switch_body"):
            sh = sh | _block_names(n, src)
        elif t == "for_statement":
            init = n.child_by_field_name("initializer")
            if init is not None and init.type in ("lexical_declaration", "variable_declaration"):
                sh = sh | {x for d in init.named_children if d.type == "variable_declarator"
                           for x in _bound_names(d.child_by_field_name("name"), src)}
        elif t == "for_in_statement":
            left = n.child_by_field_name("left")
            if left is not None:
                if _kind(n):
                    sh = sh | set(_bound_names(left, src))
                else:
                    targets.append(left)                    # for (x of xs): every turn writes x
        elif t == "catch_clause":
            param = n.child_by_field_name("parameter")
            if param is not None:
                sh = sh | set(_bound_names(param, src))
        elif t in ("assignment_expression", "augmented_assignment_expression"):
            targets.append(n.child_by_field_name("left"))
        elif t == "update_expression":
            targets.append(n.child_by_field_name("argument"))
        for target in targets:
            if target is None:
                continue
            for leaf in _write_targets(target):
                label = _write_label(leaf, src, sh)
                if label:
                    yield label, n.start_point[0] + 1
        stack.extend((c, sh) for c in n.named_children)


# ── alias imports (graphyos #102): TypeScript's own `compilerOptions.paths`, and SvelteKit's documented `$lib` ──
# A specifier like `$lib/api.js` is neither relative nor a package: it is bound by the alias the language declares
# in tsconfig/jsconfig, read here by TypeScript's rules (exact key first, then the `*` pattern with the longest
# prefix; targets relative to `baseUrl`, else to the config that declares `paths`; `extends` followed, a missing
# target named). SvelteKit's `$lib` → `src/lib` is the framework's fixed default, applied only in a Kit project
# whose config declares no `$lib`; `kit.alias` lives in JavaScript and is named unread, never evaluated.

_JSON_STRING = re.compile(r'"(?:\\.|[^"\\])*"')


def _jsonc(text: str) -> Any:
    """tsconfig is JSON with comments and trailing commas: both stripped outside strings, then parsed."""
    out, pos = [], 0
    for m in _JSON_STRING.finditer(text):
        gap = re.sub(r"//[^\n]*|/\*.*?\*/", "", text[pos:m.start()], flags=re.S)
        out += [gap, m.group(0)]
        pos = m.end()
    out.append(re.sub(r"//[^\n]*|/\*.*?\*/", "", text[pos:], flags=re.S))
    body, parts = "".join(out), []
    pos = 0
    for m in _JSON_STRING.finditer(body):
        parts += [re.sub(r",(\s*[}\]])", r"\1", body[pos:m.start()]), m.group(0)]
        pos = m.end()
    parts.append(re.sub(r",(\s*[}\]])", r"\1", body[pos:]))
    return json.loads("".join(parts))


def alias_config(root: Path) -> dict:
    """The aliases a corpus's imports are bound by: ``{"config", "patterns": [[key, [target, …]], …], "missing"}``,
    every path POSIX and relative to the project (the directory holding package.json), so the receipt a shard
    carries is the same bytes on every host and names no box path (graphyos #88). ``project`` rides beside it
    for the match and is never written. The nearest tsconfig.json or jsconfig.json at or above ``root``, up to
    the first directory holding a package.json."""
    root = Path(root).resolve()
    project, cfg, d = root, None, root
    for _ in range(8):
        cfg = next((d / n for n in ("tsconfig.json", "jsconfig.json") if (d / n).is_file()), None)
        if (d / "package.json").is_file():
            project = d
        if cfg is not None or (d / "package.json").is_file() or d.parent == d:
            break
        d = d.parent
    missing: list[str] = []

    def rel(p: Path) -> str:
        """POSIX and relative to the project; a target outside it keeps its `..` hops, never an absolute path."""
        return Path(os.path.relpath(p.resolve(), project)).as_posix()

    def target_of(at: Path, ext: str) -> Path | None:
        if ext.startswith("."):
            t = (at / ext)
            return t if t.is_file() or t.suffix == ".json" else t.with_name(t.name + ".json")
        t = project / "node_modules" / ext
        return t if t.suffix == ".json" else (t / "tsconfig.json" if t.is_dir() else t.with_name(t.name + ".json"))

    def load(c: Path, seen: frozenset) -> tuple[tuple | None, Path | None]:
        try:
            data = _jsonc(c.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            missing.append(f"{rel(c)}: unreadable ({exc.__class__.__name__})")
            return None, None
        paths, base = None, None
        ext = data.get("extends") if isinstance(data, dict) else None
        for e in ([ext] if isinstance(ext, str) else [x for x in (ext or []) if isinstance(x, str)]):
            t = target_of(c.parent, e)
            if t is None or not t.is_file():
                missing.append(f"{rel(c)} extends {e}: {rel(t) if t is not None else e} does not exist")
                continue
            if t.resolve() in seen:
                continue
            p, b = load(t, seen | {t.resolve()})
            paths, base = (p if p is not None else paths), (b if b is not None else base)
        co = data.get("compilerOptions") if isinstance(data, dict) else None
        if isinstance(co, dict):
            if isinstance(co.get("baseUrl"), str):
                base = (c.parent / co["baseUrl"]).resolve()
            if isinstance(co.get("paths"), dict):
                paths = (co["paths"], c.parent.resolve())
        return paths, base

    table: dict[str, list[str]] = {}
    if cfg is not None:
        paths, base = load(cfg, frozenset({cfg.resolve()}))
        if paths is not None:
            declared, anchor = paths
            anchor = base or anchor
            for key, targets in declared.items():
                if isinstance(key, str) and isinstance(targets, list):
                    table[key] = [rel(anchor / t) for t in targets if isinstance(t, str)]
    kit = next((project / n for n in ("svelte.config.js", "svelte.config.ts") if (project / n).is_file()), None)
    pkg = project / "package.json"
    if kit is not None and pkg.is_file() and "@sveltejs/kit" in pkg.read_text(encoding="utf-8", errors="replace"):
        if "$lib" not in table and "$lib/*" not in table:
            table["$lib"], table["$lib/*"] = ["src/lib"], ["src/lib/*"]
        if re.search(r"\balias\s*:", kit.read_text(encoding="utf-8", errors="replace")):
            missing.append(f"{rel(kit)}: kit.alias is JavaScript and is not read")
    return {"config": rel(cfg) if cfg is not None else None,
            "patterns": [[k, table[k]] for k in sorted(table)], "missing": missing, "project": project}


def _alias_targets(spec: str, aliases: dict) -> list[Path]:
    """TypeScript's matching: an exact key wins; else the `*` pattern whose prefix is longest, the star's match
    substituted into each target. A key binds the whole specifier (`$lib/*` never binds `$library/x`)."""
    project = aliases.get("project") or Path(".")
    best: tuple[int, list[str]] | None = None
    for key, targets in aliases.get("patterns", ()):
        if "*" not in key:
            if spec == key:
                return [(project / t).resolve() for t in targets]
            continue
        pre, _, suf = key.partition("*")
        if spec.startswith(pre) and spec.endswith(suf) and len(spec) >= len(pre) + len(suf):
            star = spec[len(pre):len(spec) - len(suf)]
            if best is None or len(pre) > best[0]:
                best = (len(pre), [t.replace("*", star, 1) for t in targets])
    return [(project / t).resolve() for t in best[1]] if best else []


def _module_at(base: Path, modules: dict[str, str]) -> str | None:
    """A path a specifier names → its module id: the file, the file with a source suffix, the directory's index,
    and `x.js` naming `x.ts` in ESM-style TypeScript."""
    cands = [base]
    for suf in _SOURCE_SUFFIXES:
        cands.append(base.with_name(base.name + suf))
    for suf in _SOURCE_SUFFIXES:
        cands.append(base / f"index{suf}")
    if base.suffix in (".js", ".mjs", ".cjs"):
        stem = base.with_suffix("")
        for suf in _SOURCE_SUFFIXES:
            cands.append(stem.with_name(stem.name + suf))
    for c in cands:
        key = str(c)
        if key in modules:
            return modules[key]
    return None


def _module_for_specifier(spec: str, file: Path, root: Path, package: str, modules: dict[str, str],
                          aliases: dict | None = None) -> str | None:
    """A relative specifier → the module id it names (``./x`` → x.ts | x/index.ts | x.tsx …); an alias
    (``$lib/x``) → the module its target names; a bare one → the package's module id (the scheme a slug
    can carry) or None."""
    if spec.startswith("."):
        return _module_at((file.parent / spec).resolve(), modules)
    for target in _alias_targets(spec, aliases or {}):
        found = _module_at(target, modules)
        if found is not None:
            return found
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
        dotted_of[f] = _dotted_for(f, root, package)
    claims: dict[str, int] = {}
    for d in dotted_of.values():
        claims[d] = claims.get(d, 0) + 1
    for f in files:
        d = dotted_of[f]
        if f.suffix in _COMPONENT_SUFFIXES and claims[d] > 1:           # and Foo.svelte beside Foo.vue
            d = dotted_of[f] = f"{d}_{f.suffix[1:]}"             # +page.svelte beside +page.ts: both modules stand
        modules[str(f.resolve())] = _node_id("module", d)
        rels[f] = str(f.relative_to(root)).replace("\\", "/")
    listing = hashlib.sha256("\n".join(sorted(rels.values())).encode("utf-8")).hexdigest()
    aliases = alias_config(root)                                # an alias edit re-resolves every import (graphyos #102)
    alias_key = hashlib.sha256(json.dumps(aliases["patterns"], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    pin = f"typescript_ast:references:{package}:{listing}:aliases:{alias_key}"   # a pre-#94 span holds no reference edge: never spliced
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
            component = f.suffix in _COMPONENT_SUFFIXES
            if component:
                code, is_ts = component_script(src)
                tree = (ts if is_ts else tsx).parse(code)
            else:
                code = src
                tree = (ts if f.suffix in (".ts", ".mts", ".cts") else tsx).parse(src)   # JSX-safe for everything else
            module_dotted = dotted_of[f]
            module_id = modules[str(f.resolve())]
            file_rel = str(f.relative_to(root.parent)).replace("\\", "/")   # posix on every host (graphyos #88)
            role = "test" if TEST_FILE.search(str(f.relative_to(root)).replace("\\", "/")) else None
            mod_rec = {"kind": "node", "node_type": "module", "id": module_id, "dotted": module_dotted, "file": file_rel,
                       "loc": src.count(b"\n") + 1, "docstring": ""}
            records = [mod_rec] + list(_walk_module(
                tree, module_id, module_dotted, file_rel, code,
                lambda spec, _f=f: _module_for_specifier(spec, _f, root, package, modules, aliases), component,
                component or f.name.endswith((".svelte.ts", ".svelte.js"))))
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
    done = receipt.finish(pin)
    done["aliases"] = {k: v for k, v in aliases.items() if k != "project"}   # the config, the patterns, what was not found
    return nodes, edges, done
