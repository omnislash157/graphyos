
from __future__ import annotations

import ast
import hashlib
import re
from collections import deque
from pathlib import Path
from typing import Any, Iterator

from graphy.adapters._receipt import Receipt
from graphy.ir import PYTHON_AST_VOCABULARY

__all__ = ["build_ir", "mint_records", "walk_files", "is_package_dir", "PYTHON_AST_VOCABULARY"]

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


def _scan(tree: ast.AST) -> tuple[list[ast.AST], dict[ast.AST, list[tuple[str, int]]]]:
    """One level-order pass over every node of a file — the order ``ast.walk`` yields them, so the
    records read the same — visiting no node twice. It collects the import statements wherever
    they sit and, keyed by the tracked definition that owns them, every call: a definition is
    tracked when ``_defs_in`` reaches it (never inside a function body), and a call belongs to the
    outermost tracked function around it, the one whose subtree the old per-definition walk read.
    The children come straight off each class's ``_fields`` — the generator ``ast.iter_child_nodes``
    builds costs three times the walk."""
    imports: list[ast.AST] = []
    calls: dict[ast.AST, list[tuple[str, int]]] = {}
    todo: deque[tuple[ast.AST, ast.AST | None, bool]] = deque([(tree, None, True)])
    pop, push = todo.popleft, todo.append
    Call, Imports, Func, Scope, Node = ast.Call, (ast.Import, ast.ImportFrom), _FUNC, _SCOPE, ast.AST
    while todo:
        node, owner, tracked = pop()
        cls = type(node)
        if cls is Call:
            if owner is not None:
                calls.setdefault(owner, []).append((_expr_repr(node.func), getattr(node, "lineno", 0)))
        elif cls in Imports:
            imports.append(node)
        elif cls in Func:
            if owner is None and tracked:
                owner = node
            tracked = False
        elif not issubclass(cls, Scope):
            tracked = False
        for name in cls._fields:
            value = getattr(node, name, None)
            if isinstance(value, Node):
                push((value, owner, tracked))
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, Node):
                        push((child, owner, tracked))
    return imports, calls




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


def _walk_stmt(
    stmt: ast.AST,
    parent_id: str,
    parent_dotted: str,
    file_rel: str,
    container_class: str | None = None,
    package: str = "",
    local_packages: frozenset[str] = frozenset(),
    calls: dict[ast.AST, list[tuple[str, int]]] | None = None,
) -> Iterator[dict]:
    calls = calls if calls is not None else {}
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
        for sub in _defs_in(stmt.body):
            yield from _walk_stmt(sub, class_id, class_dotted, file_rel,
                                  container_class=stmt.name, package=package,
                                  local_packages=local_packages, calls=calls)
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
            "args": [a.arg for a in stmt.args.args],
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


def _emit_raw_records_for_file(
    file: Path,
    root: Path,
    package: str,
    local_packages: frozenset[str] = frozenset(),
    rel_base: Path | None = None,
) -> Iterator[dict]:
    try:
        src = file.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return

    module_dotted = _dotted_for(file, root, package)
    module_id = _node_id("module", module_dotted)
    file_rel = str(file.relative_to(rel_base if rel_base is not None else root.parent))

    yield {
        "kind": "node",
        "node_type": "module",
        "id": module_id,
        "dotted": module_dotted,
        "file": file_rel,
        "loc": len(src.splitlines()),
        "docstring": (ast.get_docstring(tree) or "")[:200],
    }

    imports, calls = _scan(tree)
    yield from _emit_import_edges(imports, module_id, module_dotted, package,
                                  local_packages,
                                  is_package=file.name == "__init__.py")

    for stmt in _defs_in(tree.body):
        yield from _walk_stmt(stmt, module_id, module_dotted, file_rel,
                              package=package, local_packages=local_packages, calls=calls)





TEST_FILE = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_tests?\.py$|(^|/)conftest\.py$")


def _emit_records_for_file(
    file: Path,
    root: Path,
    package: str,
    local_packages: frozenset[str] = frozenset(),
    rel_base: Path | None = None,
) -> Iterator[dict]:
    """Every node carries ``module`` (the dotted module that holds it) and, when the producer's
    own rule says the file is a test, ``role: test``. The consumers read those fields; no consumer
    derives a module from a ``.py`` path or decides what a test is."""
    module_dotted: str | None = None
    for rec in _emit_raw_records_for_file(file, root, package, local_packages, rel_base):
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
    root = Path(corpus_dir).resolve()
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    if not root.is_dir():
        raise RuntimeError(f"path is not a directory or a .py file: {root}")
    excludes = _PACKAGE_EXCLUDES if is_package_dir(root) else _DEFAULT_EXCLUDES
    return [f for f in sorted(root.rglob("*.py")) if not _is_excluded(f, excludes, root)]


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
    pin = f"python_ast:{package}:{'package' if is_package_dir(root) or root.is_file() else 'tree'}:" \
          + ",".join(sorted(local_packages))
    receipt = Receipt("last")
    for file in walk_files(root):
        rel = str(file.relative_to(rel_root)).replace("\\", "/")
        try:
            sha = hashlib.sha256(file.read_bytes()).hexdigest()
        except OSError:
            continue
        cached = reuse(pin, rel, sha) if reuse is not None else None
        if cached is None:
            recs = list(_emit_records_for_file(file, base, package, local_packages=local_packages,
                                               rel_base=rel_base))
            n_recs = [r for r in recs if r.get("kind") == "node"]
            e_recs = [r for r in recs if r.get("kind") != "node"]
        else:
            n_recs, e_recs = cached
        receipt.file(rel, sha, n_recs, e_recs, nodes, parsed=cached is None)
        edges.extend(e_recs)
    return nodes, edges, receipt.finish(pin)
