
from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
from collections import deque
from pathlib import Path
from typing import Any, Iterator

from graphy.adapters._receipt import Receipt
from graphy.ir import PYTHON_AST_VOCABULARY

__all__ = ["build_ir", "mint_records", "walk_files", "walk_files_naming_skips", "read_source",
           "is_package_dir", "PYTHON_AST_VOCABULARY"]

_DEFAULT_EXCLUDES = (
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    "build", "dist", ".pytest_cache", ".mypy_cache", ".ruff_cache",
)
_PACKAGE_EXCLUDES = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")


class _NodeRecords(dict):

    def __iter__(self):  # type: ignore[override]
        return iter(self.values())




def _dotted_for(file: Path, root: Path, package: str) -> str:
    rel = file.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".pyi").removesuffix(".py")
    if parts == [package]:
        return package
    return ".".join([package] + parts) if parts else package


def _scheme_of(dotted: str) -> str:
    return dotted.split(".", 1)[0] if dotted else "unknown"


def _node_id(kind: str, dotted: str) -> str:
    return f"{_scheme_of(dotted)}://{kind}/{dotted}"




def _expr_repr(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_expr_repr(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _expr_repr(node.func) + "(...)"
    try:
        return ast.unparse(node)[:120]
    except Exception:
        return f"<{type(node).__name__}>"


_COMPOUND = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)
if hasattr(ast, "TryStar"):
    _COMPOUND = _COMPOUND + (ast.TryStar,)
# the nodes _defs_in descends through on its way to a definition: a module, a class body, a
# compound statement and its handlers — a definition under anything else is not tracked
_SCOPE = _COMPOUND + (ast.Module, ast.ClassDef, ast.ExceptHandler)
_FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)

# The leaves the scan never queues: a Constant, an expression context, an operator — none holds an
# import, a call or a scope, and on sqlalchemy they are 56 % of every node (RECON.md §60). ``_VISITED``
# is every other AST class: one set lookup on a child's type decides the push. The fields that never
# hold a visited node — the identifiers and ints of the grammar, ``ctx`` · ``op`` · ``ops`` — are
# left out of a class's child fields, computed once per class with its kind.
_LEAF = frozenset(c for c in vars(ast).values() if isinstance(c, type)
                  and issubclass(c, (ast.expr_context, ast.operator, ast.boolop, ast.unaryop, ast.cmpop))) | {ast.Constant}
_VISITED = frozenset(c for c in vars(ast).values() if isinstance(c, type) and issubclass(c, ast.AST)) - _LEAF
_NEVER_CHILD = frozenset({"ctx", "op", "ops", "type_comment", "id", "arg", "attr", "name", "asname", "module",
                          "level", "is_async", "conversion", "kind", "simple"})
_CALL, _IMPORT, _FUNC_KIND, _SCOPE_KIND, _OTHER = 0, 1, 2, 3, 4
_CLASS_INFO: dict[type, tuple[int, tuple[str, ...]]] = {}


def _class_info(cls: type) -> tuple[int, tuple[str, ...]]:
    """What the scan does at a node of this class and which of its fields can hold a visited node —
    computed once per class, so the loop pays one dict lookup where it paid four class tests."""
    info = _CLASS_INFO.get(cls)
    if info is None:
        kind = (_CALL if cls is ast.Call else _IMPORT if cls in (ast.Import, ast.ImportFrom)
                else _FUNC_KIND if cls in _FUNC else _SCOPE_KIND if issubclass(cls, _SCOPE) else _OTHER)
        info = _CLASS_INFO[cls] = (kind, tuple(f for f in cls._fields if f not in _NEVER_CHILD))
    return info


def _module_bindings(body: list) -> set[str]:
    """The names the module's own scope binds to something the resolver can reach: a def or class
    ``_defs_in`` tracks, and every name a module-level import statement binds (``import a.b`` binds
    ``a``; ``from x import y as z`` binds ``z``) — descending through the same compound statements
    ``_defs_in`` does and never into a function body. These are the only heads a reference may
    carry: a local, a parameter, a global assigned at module level is not a definition."""
    out: set[str] = set()
    for stmt in body:
        if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(stmt.name)
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                if alias.name != "*":
                    out.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(stmt, _COMPOUND):
            out |= _module_bindings(stmt.body)
            out |= _module_bindings(getattr(stmt, "orelse", []) or [])
            for handler in getattr(stmt, "handlers", []) or []:
                out |= _module_bindings(handler.body)
            out |= _module_bindings(getattr(stmt, "finalbody", []) or [])
    return out


# The fields whose subtree is a type, never a value: a name there is an annotation, and an
# annotation is not a reference (graphyos #94 mints a function or class USED, not named as a type).
_TYPE_FIELDS = frozenset({"annotation", "returns"})
# The lists whose bare names are already an edge of their own: a decorator is `decorates`, a base is
# `inherits`. A call among them (`@retry(on=fn)`, `class K(make_base(fn))`) still carries values.
_BOUND_LISTS = frozenset({"decorator_list", "bases"})
_NAME_KINDS = (ast.Name, ast.Attribute)


def _scan(tree: ast.AST) -> tuple[list[ast.AST], dict[ast.AST, list[tuple[str, int]]],
                                  dict[ast.AST | None, list[tuple[str, int]]]]:
    """One level-order pass over every node of a file — the order ``ast.walk`` yields them, so the
    records read the same — visiting no node twice. It collects the import statements wherever
    they sit and, keyed by the tracked definition that owns them, every call: a definition is
    tracked when ``_defs_in`` reaches it (never inside a function body), and a call belongs to the
    outermost tracked function around it, the one whose subtree the old per-definition walk read.
    The children come straight off each class's child fields (``_class_info``, once per class) —
    the generator ``ast.iter_child_nodes`` builds costs three times the walk — and a leaf
    (``_LEAF``) is never queued: it has nothing the scan reads and no children.

    The same pass collects every REFERENCE (graphyos #94): a name read as a value — ``handler=fn``,
    ``{"x": fn}``, ``@d(fn)``, ``def f(x=fn)``, ``mod.fn`` — whose head the module's own scope binds
    (``_module_bindings``: a tracked def or class, a module-level import) and that no scope between the
    reader and the module rebinds — the module's own top level (``_shadow_in``: a for target, a comprehension
    target, a lambda's parameter, a walrus, an assignment), the class body around a class-level reference,
    and the owning function (a parameter, an assignment, a nested def's name — ``_rebound_names``). It is
    keyed by the tracked def or class that holds it, ``None`` for the module's own top level. A call's
    callee is a ``calls`` edge already and is not a reference; a bare decorator is ``decorates``; a bare or
    subscripted base is ``inherits``; a name under an annotation is a type, not a value; the inner names of
    a dotted chain are the chain's, not their own. Every push is unchanged: a node the old pass visited is
    visited once, with two more flags. ``rebound`` — each function's own rebindings, computed once here and
    handed to ``_bindable_annotations`` — is returned beside the records."""
    imports: list[ast.AST] = []
    calls: dict[ast.AST, list[tuple[str, int]]] = {}
    refs: dict[ast.AST | None, list[tuple[str, int]]] = {}
    body = getattr(tree, "body", []) or []
    bound = _module_bindings(body)
    module_shadow = _shadow_in(body)
    shadows: dict[ast.AST | None, set[str]] = {None: module_shadow}
    rebound: dict[ast.AST, set[str]] = {}
    # (node, owner: the tracked function whose calls these are, tracked, holder: the tracked def or class
    #  a reference belongs to, ref_ok: a name here is a value and not a callee, a decorator or a type)
    todo: deque[tuple[ast.AST, ast.AST | None, bool, ast.AST | None, bool]] = deque([(tree, None, True, None, True)])
    pop, push = todo.popleft, todo.append
    visited, cached, class_info = _VISITED, _CLASS_INFO.get, _class_info
    while todo:
        node, owner, tracked, holder, ref_ok = pop()
        cls = type(node)
        kind, fields = cached(cls) or class_info(cls)
        callee: ast.AST | None = None
        if kind == _CALL:
            if owner is not None:
                calls.setdefault(owner, []).append((_expr_repr(node.func), getattr(node, "lineno", 0)))
            if type(node.func) in _NAME_KINDS:
                callee = node.func                      # the callee is the calls edge, never a reference
        elif kind == _IMPORT:
            imports.append(node)
        elif kind == _FUNC_KIND:
            if owner is None and tracked:
                owner = node
                holder = node
            tracked = False
        elif kind == _SCOPE_KIND:
            if cls is ast.ClassDef and tracked:
                holder = node
        elif kind == _OTHER:
            tracked = False
            if ref_ok and cls in _NAME_KINDS:
                label = node.id if cls is ast.Name else _name_chain(node)
                if label is not None:
                    ref_ok = False                      # the chain's inner names are the chain's own
                    head = label.split(".", 1)[0]
                    if head in bound and isinstance(node.ctx, ast.Load) and head not in module_shadow:
                        shadow = shadows.get(holder)
                        if shadow is None:                  # a class body's own rebindings, once per class
                            shadow = shadows[holder] = _shadow_in(holder.body) if isinstance(holder, ast.ClassDef) else set()
                        if head not in shadow and owner is not None:
                            own = rebound.get(owner)
                            if own is None:
                                own = rebound[owner] = _rebound_names(owner)
                            if head in own or head in _param_names(owner):
                                shadow = None               # the function's own scope rebinds it
                        if shadow is not None and head not in shadow:
                            refs.setdefault(holder, []).append((label, getattr(node, "lineno", 0)))
        values = node.__dict__
        for name in fields:
            value = values.get(name)
            if value is None:
                continue
            ok = ref_ok and name not in _TYPE_FIELDS
            if type(value) is list:
                if name in _BOUND_LISTS:
                    for child in value:
                        if type(child) in visited:  # a bare decorator or base is its own edge; a call's arguments are values
                            push((child, owner, tracked, holder, ok and not _is_bound_shape(child)))
                    continue
                for child in value:
                    if type(child) in visited:
                        push((child, owner, tracked, holder, ok))
            elif type(value) in visited:
                push((value, owner, tracked, holder, ok and value is not callee))
    return imports, calls, refs, rebound


def _is_bound_shape(node: ast.AST) -> bool:
    """A decorator or a base the producer already spells as its own edge: a name, a dotted chain, or a
    subscripted one (`Generic[T]`, `Mapping[str, int]`) — the `inherits` label is the whole text, so
    its head is not a second edge; a call among them still carries values (`@retry(on=fn)`)."""
    if type(node) in _NAME_KINDS:
        return True
    return isinstance(node, ast.Subscript) and type(node.value) in _NAME_KINDS




def _resolve_module_dst(raw: str, package: str, local_packages: frozenset[str]) -> str:
    first = raw.split(".", 1)[0]
    if first == package:
        return raw
    if first in local_packages:
        return f"{package}.{raw}"
    return raw


def _emit_import_edges(
    imports: list[ast.AST],
    module_id: str,
    module_dotted: str,
    package: str,
    local_packages: frozenset[str],
    is_package: bool = False,
) -> Iterator[dict]:
    for node in imports:
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield {
                    "kind": "edge",
                    "edge_type": "imports",
                    "src": module_id,
                    "dst": _node_id(
                        "module",
                        _resolve_module_dst(alias.name, package, local_packages),
                    ),
                    "alias": alias.asname,
                    "line": node.lineno,
                }
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:
                drop = node.level - 1 if is_package else node.level
                base = module_dotted.split(".")
                base = base[: max(0, len(base) - drop)] if drop else base
                pieces = [p for p in base + ([mod] if mod else []) if p]
                mod = ".".join(pieces)
            elif mod:
                mod = _resolve_module_dst(mod, package, local_packages)
            for alias in node.names:
                dst = _node_id("module", mod) if mod else _node_id("module", alias.name)
                yield {
                    "kind": "edge",
                    "edge_type": "imports",
                    "src": module_id,
                    "dst": dst,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                }




def _defs_in(body: list) -> Iterator[ast.AST]:
    """The def and class statements a body defines, descending through the compound statements a
    module or class guards them with — ``if``/``else``, ``try``/``except``/``finally``, ``with``,
    ``for``, ``while`` — and never into a function body. A version-gated backport
    (``if hasattr(typing, X): ... else: class X``) defines X on the module; the module is its parent."""
    for stmt in body:
        if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield stmt
        elif isinstance(stmt, _COMPOUND):
            yield from _defs_in(stmt.body)
            yield from _defs_in(getattr(stmt, "orelse", []) or [])
            for handler in getattr(stmt, "handlers", []) or []:
                yield from _defs_in(handler.body)
            yield from _defs_in(getattr(stmt, "finalbody", []) or [])


def _param_names(fn: ast.AST) -> list[str]:
    """Every named parameter, in signature order: positional-only, positional, *args, keyword-only, **kwargs."""
    a = fn.args
    return [p.arg for p in a.posonlyargs] + [p.arg for p in a.args] + ([a.vararg.arg] if a.vararg else []) \
        + [p.arg for p in a.kwonlyargs] + ([a.kwarg.arg] if a.kwarg else [])


def _name_chain(node: ast.AST) -> str | None:
    """`Name` or an `Attribute` chain of names, as dotted text; anything else (a subscript, a string, a
    union, a call) is None — the one shape a scope can bind."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _name_chain(node.value)
        return f"{head}.{node.attr}" if head else None
    return None


def _rebound_names(fn: ast.AST) -> set[str]:
    """Every name the function's body binds again, anywhere under it — an assignment or augmented
    assignment target, a for/with/except alias, a comprehension target, a walrus, a nested def or lambda's
    own parameter or name, an import, a global/nonlocal — so a parameter's annotation binds only a name that
    means one thing from the signature to the last line."""
    out: set[str] = set()
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(node.name); out.update(_param_names(node))
        elif isinstance(node, ast.Lambda):
            out.update(_param_names(node))
        elif isinstance(node, ast.ClassDef):
            out.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            out.update(node.names)
        elif isinstance(node, ast.alias):
            out.add((node.asname or node.name).split(".")[0])
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            out.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            out.add(node.rest)
    return out


def _shadow_in(body: list) -> set[str]:
    """Every name a module's or a class's own scope rebinds by anything but a def, a class or an
    import — an assignment, a for/with/except target, a comprehension target, a walrus, a lambda's
    parameter, a global — never descending into a function (its rebindings are its own,
    ``_rebound_names``) or a nested class (its own scope). A reference whose head is here is not the
    definition it spells, so it mints nothing (graphyos #94, review round 1)."""
    out: set[str] = set()
    todo = list(body)
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, ast.Lambda):
            out.update(_param_names(node))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            out.update(node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            out.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            out.add(node.rest)
        todo.extend(ast.iter_child_nodes(node))
    return out


def _bindable_annotations(fn: ast.AST, rebound: set[str] | None = None) -> dict[str, str] | None:
    a = fn.args
    rebound = _rebound_names(fn) if rebound is None else rebound
    out = {}
    for p in (*a.posonlyargs, *a.args, *a.kwonlyargs):
        if p.annotation is None or p.arg in rebound:
            continue
        text = _name_chain(p.annotation)
        if text:
            out[p.arg] = text
    return out or None


def _walk_stmt(
    stmt: ast.AST,
    parent_id: str,
    parent_dotted: str,
    file_rel: str,
    container_class: str | None = None,
    package: str = "",
    local_packages: frozenset[str] = frozenset(),
    calls: dict[ast.AST, list[tuple[str, int]]] | None = None,
    refs: dict[ast.AST | None, list[tuple[str, int]]] | None = None,
    rebound: dict[ast.AST, set[str]] | None = None,
) -> Iterator[dict]:
    calls = calls if calls is not None else {}
    refs = refs if refs is not None else {}
    rebound = rebound if rebound is not None else {}
    if isinstance(stmt, ast.ClassDef):
        class_dotted = f"{parent_dotted}.{stmt.name}"
        class_id = _node_id("class", class_dotted)
        yield {
            "kind": "node",
            "node_type": "class",
            "id": class_id,
            "name": stmt.name,
            "dotted": class_dotted,
            "file": file_rel,
            "line": stmt.lineno,
            "docstring": (ast.get_docstring(stmt) or "")[:200],
        }
        yield {"kind": "edge", "edge_type": "contains", "src": parent_id, "dst": class_id}
        for base in stmt.bases:
            yield {
                "kind": "edge",
                "edge_type": "inherits",
                "src": class_id,
                "dst_repr": _expr_repr(base),
                "line": stmt.lineno,
            }
        for dec in stmt.decorator_list:
            yield {
                "kind": "edge",
                "edge_type": "decorates",
                "src_repr": _expr_repr(dec),
                "dst": class_id,
                "line": stmt.lineno,
            }
        yield from _reference_edges(class_id, refs.get(stmt, ()))
        for sub in _defs_in(stmt.body):
            yield from _walk_stmt(sub, class_id, class_dotted, file_rel,
                                  container_class=stmt.name, package=package,
                                  local_packages=local_packages, calls=calls, refs=refs, rebound=rebound)
    elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        kind = "method" if container_class else "func"
        func_dotted = f"{parent_dotted}.{stmt.name}"
        func_id = _node_id(kind, func_dotted)
        yield {
            "kind": "node",
            "node_type": kind,
            "id": func_id,
            "name": stmt.name,
            "dotted": func_dotted,
            "file": file_rel,
            "line": stmt.lineno,
            "is_async": isinstance(stmt, ast.AsyncFunctionDef),
            "args": _param_names(stmt),
            # a parameter's annotation when it is a name the resolver can bind (graphyos #57): `ctx: Context`
            # makes `ctx.invoke` `Context.invoke` the way `self.` binds the container — by scope. Only a bare
            # or dotted name is kept, and only when the body never rebinds the parameter; the rest is text
            "annotations": _bindable_annotations(stmt, rebound.get(stmt)),
            "returns": _expr_repr(stmt.returns) if stmt.returns else None,
            "docstring": (ast.get_docstring(stmt) or "")[:200],
            "container_class": container_class,
        }
        yield {"kind": "edge", "edge_type": "contains", "src": parent_id, "dst": func_id}
        for dec in stmt.decorator_list:
            yield {
                "kind": "edge",
                "edge_type": "decorates",
                "src_repr": _expr_repr(dec),
                "dst": func_id,
                "line": stmt.lineno,
            }
        for call_repr, line in calls.get(stmt, ()):
            yield {
                "kind": "edge",
                "edge_type": "calls",
                "src": func_id,
                "dst_repr": call_repr,
                "line": line,
            }
        yield from _reference_edges(func_id, refs.get(stmt, ()))


def _reference_edges(src_id: str, refs) -> Iterator[dict]:
    """A ``references`` edge per value-use ``_scan`` keyed to this node, the target left as text for
    the resolver the way a call's is — one edge per site, like a call (graphyos #94)."""
    for label, line in refs:
        yield {"kind": "edge", "edge_type": "references", "src": src_id, "dst_repr": label, "line": line}


def _is_excluded(file: Path, exclude_patterns: tuple[str, ...], root: Path) -> bool:
    try:
        parts = set(file.relative_to(root).parts)
    except ValueError:
        parts = set(file.parts)
    return any(p in parts for p in exclude_patterns)


def _local_package_names(root: Path) -> frozenset[str]:
    names: set[str] = set()
    for entry in root.iterdir():
        if entry.name.startswith(".") or entry.name in _DEFAULT_EXCLUDES:
            continue
        if entry.is_dir() and next(entry.rglob("*.py"), None) is not None:
            names.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py":
            names.add(entry.stem)
    return frozenset(names)


def read_source(file: Path, raw: bytes | None = None) -> tuple[str, ast.AST] | str:
    """The file's text and its tree, or the one-line reason the producer cannot read it. The
    encoding is the file's own — the PEP 263 coding cookie or the BOM, ``tokenize.detect_encoding``
    — so a latin-1 module with its cookie mints; a file that decodes, parses and nests within the
    interpreter's limits is readable and nothing else is. ``raw`` spares a second read when the
    caller already holds the bytes (the mint hashes them first)."""
    try:
        if raw is None:
            raw = file.read_bytes()
    except OSError as exc:
        return f"unreadable: {exc.strerror or exc.__class__.__name__}"
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    except SyntaxError as exc:                    # a bad cookie, or a first line that is not utf-8
        msg = str(exc.msg if exc.msg else exc)
        return "not utf-8" if "encoding declaration" in msg else msg
    try:
        src = raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return f"not {'utf-8' if encoding.startswith('utf-8') else encoding}"
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        msg = exc.msg or ""
        if "nested" in msg or "too complex" in msg:
            return "too deeply nested"
        if "null bytes" in msg:
            return "null bytes"
        return f"syntax error line {exc.lineno}" if exc.lineno else "syntax error"
    except (RecursionError, MemoryError):
        return "too deeply nested"
    except ValueError as exc:                     # 3.10: null bytes are a ValueError
        return "null bytes" if "null bytes" in str(exc) else f"unparseable: {exc}"
    return src, tree


def _emit_raw_records_for_file(
    file: Path,
    root: Path,
    package: str,
    local_packages: frozenset[str] = frozenset(),
    rel_base: Path | None = None,
    parsed: tuple[str, ast.AST] | None = None,
) -> Iterator[dict]:
    if parsed is None:
        parsed = read_source(file)
        if isinstance(parsed, str):
            return
    src, tree = parsed

    module_dotted = _dotted_for(file, root, package)
    module_id = _node_id("module", module_dotted)
    file_rel = str(file.relative_to(rel_base if rel_base is not None else root.parent)).replace("\\", "/")
  # The separator is normalised HERE, where the record is built: a shard minted on Windows
    # carried `idna\\cli.py` where a Linux mint carried `idna/cli.py`, so the same tree at the same
    # commit produced two different shards and the generation digest, the golden fixtures and every
    # byte-identity check disagreed across hosts. Node IDS were always clean, so no walk was ever
    # wrong — this is parity, not correctness (graphyos #88, measured on a Windows production box:
    # 14,675 of 113,799 file fields, 0 of 177,281 ids).

    yield {
        "kind": "node",
        "node_type": "module",
        "id": module_id,
        "dotted": module_dotted,
        "file": file_rel,
        "loc": len(src.splitlines()),
        "docstring": (ast.get_docstring(tree) or "")[:200],
    }

    imports, calls, refs, rebound = _scan(tree)
    yield from _emit_import_edges(imports, module_id, module_dotted, package,
                                  local_packages,
                                  is_package=file.name == "__init__.py")
    yield from _reference_edges(module_id, refs.get(None, ()))     # the module's own top level: a table, a registry

    for stmt in _defs_in(tree.body):
        yield from _walk_stmt(stmt, module_id, module_dotted, file_rel,
                              package=package, local_packages=local_packages, calls=calls, refs=refs, rebound=rebound)





TEST_FILE = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_tests?\.py$|(^|/)conftest\.py$")


def _emit_records_for_file(
    file: Path,
    root: Path,
    package: str,
    local_packages: frozenset[str] = frozenset(),
    rel_base: Path | None = None,
    parsed: tuple[str, ast.AST] | None = None,
) -> Iterator[dict]:
    """Every node carries ``module`` (the dotted module that holds it) and, when the producer's
    own rule says the file is a test, ``role: test``. The consumers read those fields; no consumer
    derives a module from a ``.py`` path or decides what a test is."""
    module_dotted: str | None = None
    for rec in _emit_raw_records_for_file(file, root, package, local_packages, rel_base, parsed):
        if rec.get("kind") == "node":
            if rec["node_type"] == "module":
                module_dotted = rec["dotted"]
            rec["module"] = module_dotted if module_dotted is not None else rec["dotted"]
            if TEST_FILE.search(str(rec.get("file") or "")):
                rec["role"] = "test"
        yield rec

def is_package_dir(corpus_dir: str | Path) -> bool:
    """A corpus that carries its own ``__init__.py`` is one importable package: its name is the
    scheme, its siblings are other packages. Anything else is a repo root whose top-level
    directories are local packages that resolve under the root's name."""
    return (Path(corpus_dir) / "__init__.py").is_file()


def walk_files(corpus_dir: str | Path) -> list[Path]:
    """The exact files a corpus is minted from, in mint order. A package directory skips only
    caches; a repo root also skips build and vendored trees; a ``.py`` file is itself."""
    return walk_files_naming_skips(corpus_dir)[0]


def _escapes(file: Path, root: Path) -> str | None:
    """The reason a file symlink is skipped: its target lies outside the corpus root. A corpus
    is the tree under its root; a link to ``/etc/passwd`` is not a module of it. A directory
    symlink is never descended (``rglob``), so only file links are asked."""
    if not file.is_symlink():
        return None
    try:
        target = file.resolve(strict=True)
    except (OSError, RuntimeError):
        return "symlink to nothing"
    try:
        target.relative_to(root)
    except ValueError:
        return f"symlink outside the corpus -> {target}"
    return None


def walk_files_naming_skips(corpus_dir: str | Path) -> tuple[list[Path], dict[str, str]]:
    """``walk_files`` and, beside it, the files under the root the producer will not read by
    name (relative to the root) with the reason — a symlink that escapes the corpus."""
    root = Path(corpus_dir).resolve()
    if root.is_file():
        return ([root] if root.suffix == ".py" else []), {}
    if not root.is_dir():
        raise RuntimeError(f"path is not a directory or a .py file: {root}")
    excludes = _PACKAGE_EXCLUDES if is_package_dir(root) else _DEFAULT_EXCLUDES
    files: list[Path] = []
    skipped: dict[str, str] = {}
    for f in sorted(root.rglob("*.py")):
        if _is_excluded(f, excludes, root):
            continue
        why = _escapes(f, root)
        if why is None:
            files.append(f)
        else:
            skipped[str(f.relative_to(root)).replace("\\", "/")] = why
    return files, skipped


def build_ir(corpus_dir: str | Path) -> tuple[_NodeRecords, list[dict]]:
    """Mint the IR of one corpus. A directory is a package (``__init__.py`` present) or a repo
    root; a single ``.py`` file is a one-module distribution (``typing_extensions.py``) whose
    scheme is the file's stem. Files are named relative to the corpus's parent."""
    nodes, edges, _ = mint_records(corpus_dir)
    return nodes, edges


def mint_records(corpus_dir: str | Path, *, reuse=None) -> tuple[_NodeRecords, list[dict], dict]:
    """``build_ir`` with the per-file receipt: for every file the producer read, in mint order,
    the sha256 of its bytes and how many node slots and edge records it produced. A file's records are
    a function of its bytes, its path, the package name and the root's local package set — the
    ``pin`` — and nothing else, so a re-mint may take them from the previous shard instead of
    parsing: ``reuse(pin, relpath, sha256)`` returns ``(node_records, edge_records)`` or None,
    and the producer parses only what it returns None for. Each file's records are a contiguous
    span of the shard; an id two files emit is the one thing a span cannot recover, and the
    receipt stores exactly those records (``_receipt``)."""
    root = Path(corpus_dir).resolve()
    nodes: _NodeRecords = _NodeRecords()
    edges: list[dict] = []
    if root.is_file() and root.suffix == ".py":
        package, base, local_packages = root.stem, root.parent, frozenset()
        rel_base, rel_root = base, root.parent
    else:
        package, base = root.name, root
        local_packages = frozenset() if is_package_dir(root) else _local_package_names(root)
        rel_base, rel_root = base.parent, root
    # `references` is in the pin: a span a mint before graphyos #94 wrote holds no reference edge, and a
    # re-mint that spliced it would answer zero for every handler in the file it never re-read
    pin = f"python_ast:references:{package}:{'package' if is_package_dir(root) or root.is_file() else 'tree'}:" \
          + ",".join(sorted(local_packages))
    receipt = Receipt("last")
    files, skipped = walk_files_naming_skips(root)
    for rel, why in skipped.items():
        receipt.unreadable(rel, why)
    for file in files:
        rel = str(file.relative_to(rel_root)).replace("\\", "/")
        try:
            raw = file.read_bytes()
        except OSError as exc:
            receipt.unreadable(rel, f"unreadable: {exc.strerror or exc.__class__.__name__}")
            continue
        sha = hashlib.sha256(raw).hexdigest()
        cached = reuse(pin, rel, sha) if reuse is not None else None
        if cached is not None and not cached[0]:
            cached = None       # a readable file always emits its module node: an empty span is a file
            #                     an older mint could not read and counted anyway — read it, and name it
        if cached is None:
            parsed = read_source(file, raw)
            if isinstance(parsed, str):
                receipt.unreadable(rel, parsed)
                continue
            recs = list(_emit_records_for_file(file, base, package, local_packages=local_packages,
                                               rel_base=rel_base, parsed=parsed))
            n_recs = [r for r in recs if r.get("kind") == "node"]
            e_recs = [r for r in recs if r.get("kind") != "node"]
        else:
            n_recs, e_recs = cached
        receipt.file(rel, sha, n_recs, e_recs, nodes, parsed=cached is None)
        edges.extend(e_recs)
    return nodes, edges, receipt.finish(pin)
