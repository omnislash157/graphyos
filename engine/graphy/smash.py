"""The minting lane. ``smash`` turns one installed or checked-out package into a
``<scheme>_graph`` shard (nodes.json + edges.json + PROVENANCE.json) with the python_ast
producer, then follows the shard's resolved ``imports`` edges into every package they name until
the ring closes: a dependency found under ``--site-packages`` is minted beside the root as a
sibling shard, the standard library is skipped by name, and what cannot be found is reported,
never guessed. ``ring.json`` is the receipt. ``parity`` proves a minted shard against a golden
one record for record."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from email.parser import HeaderParser
from pathlib import Path

from graphy.adapters import _receipt, python_ast
from graphy.adapters import typescript_ast
from graphy.ir import IRError, validate_graph
from graphy.parity import Golden, Harness, ParityError, json_equal

__all__ = ["SmashError", "smash", "mint", "parity", "locate", "distributions", "portable",
           "stdlib_names", "RING_NAME", "PROVENANCE_NAME", "SOURCES_KEY", "PRODUCERS", "Producer"]

RING_NAME = "ring.json"
PROVENANCE_NAME = "PROVENANCE.json"
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")
_NOTE = ("Verbatim producer output. Re-mint, never hand-edit — a shard edited to fit a schema "
         "proves the schema, not the engine.")


class SmashError(RuntimeError):
    pass


class Producer:
    """One ecosystem's door: how a corpus becomes records, where a scheme's corpus lives beside
    its dependencies, what the ecosystem's standard library is. The minting loop is the same for
    every producer; only this table differs."""

    def __init__(self, name: str, build_ir, vocabulary, is_package_dir, locate, distributions, standard,
                 corpus_arg: str, missing_site_packages_ok: bool = False):
        self.name = name
        self.build_ir = build_ir
        self.vocabulary = vocabulary
        self.is_package_dir = is_package_dir
        self.locate = locate
        self.distributions = distributions
        self.standard = standard
        self.corpus_arg = corpus_arg
        self.missing_site_packages_ok = missing_site_packages_ok


def stdlib_names() -> frozenset[str]:
    return frozenset(getattr(sys, "stdlib_module_names", ())) | {"__future__", "builtins", "__main__"}


def slug_for(scheme: str) -> str | None:
    """A shard is ``<slug>_graph`` and the grammar is ``[a-z0-9_]+``; a scheme that cannot be a
    slug cannot be a shard."""
    slug = scheme.lower()
    return slug if _SLUG_RE.match(slug) else None


def locate(scheme: str, site_packages: Path) -> Path | None:
    """A scheme's corpus under site-packages: its package directory, else its one-file module."""
    d = site_packages / scheme
    if d.is_dir() and next(d.rglob("*.py"), None) is not None:
        return d
    f = site_packages / f"{scheme}.py"
    return f if f.is_file() else None


_NODE_DIRS: dict[Path, dict[str, Path]] = {}


def node_dirs_of(node_modules: Path) -> dict[str, Path]:
    """slug → package directory for every entry of a node_modules, read once and cached by path:
    the ring asks for one scheme at a time and used to scan every entry per ask — 86 schemes ×
    343 entries and 37,000 ``relative_to`` calls on express, 432 ms of a 2.2 s eat (RECON.md §65).
    The first directory in sorted order wins a slug, as the scan did."""
    key = node_modules.resolve()
    dirs = _NODE_DIRS.get(key)
    if dirs is None:
        dirs = {}
        if key.is_dir():
            entries = [(d.name, d) for d in sorted(key.glob("*"))] + \
                      [(f"{d.parent.name}/{d.name}", d) for d in sorted(key.glob("@*/*"))]
            for spec, d in entries:
                if d.is_dir() and not d.name.startswith("."):
                    slug = slug_for_specifier(spec)
                    if slug is not None:
                        dirs.setdefault(slug, d)
        _NODE_DIRS[key] = dirs
    return dirs


def node_dir_for(scheme: str, node_modules: Path) -> Path | None:
    """The package directory under node_modules whose name slugs to ``scheme``, TypeScript or not."""
    return node_dirs_of(node_modules).get(scheme)


def locate_node(scheme: str, node_modules: Path) -> Path | None:
    """A scheme's TypeScript source under node_modules: the package's ``source`` entry or a ``src/``
    that carries ``.ts`` files, else the package directory itself when it ships JavaScript (``lib/``,
    ``dist/`` — what the package is). A package with neither is reported unresolved, never guessed."""
    d = node_dir_for(scheme, node_modules)
    if d is not None:
        pj = d / "package.json"
        src = None
        try:
            meta = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(meta.get("source"), str):
                cand = d / meta["source"]
                src = cand.parent if cand.is_file() else cand
        except (OSError, ValueError):
            pass
        for cand in ([src] if src else []) + [d / "src", d]:
            if cand is not None and cand.is_dir() and typescript_ast.is_package_dir(cand):
                return cand          # the package dir itself: what it ships, dist/ and lib/ included
    return None


def slug_for_specifier(spec: str) -> str | None:
    return typescript_ast.slug_of_specifier(spec)


def distributions_node(node_modules: Path) -> dict[str, dict]:
    """scheme → the package.json that installed it (name, version, license), one per package dir."""
    out: dict[str, dict] = {}
    if not node_modules.is_dir():
        return out
    for pj in sorted(node_modules.glob("*/package.json")) + sorted(node_modules.glob("@*/*/package.json")):
        try:
            meta = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = meta.get("name")
        if not isinstance(name, str):
            continue
        slug = slug_for_specifier(name)
        if slug:
            lic = meta.get("license")
            out.setdefault(slug, {"distribution": name, "version": str(meta.get("version") or "") or None,
                                  "license": lic if isinstance(lic, str) else None})
    return out


def _license_of(msg) -> str | None:
    expr = msg.get("License-Expression")
    if expr:
        return expr.strip()
    for cls in msg.get_all("Classifier") or ():
        if cls.startswith("License ::"):
            return cls.split("::")[-1].strip()
    raw = msg.get("License")
    if raw:
        return raw.strip().splitlines()[0][:80]
    return None


def distributions(site_packages: Path) -> dict[str, dict]:
    """Top-level import name → the distribution that installed it, read from every
    ``*.dist-info`` on disk (RECORD names the files, METADATA the name, version and license)."""
    out: dict[str, dict] = {}
    for info in sorted(site_packages.glob("*.dist-info")):
        try:
            msg = HeaderParser().parsestr((info / "METADATA").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        meta = {"distribution": (msg.get("Name") or "").strip() or None,
                "version": (msg.get("Version") or "").strip() or None,
                "license": _license_of(msg)}
        names: set[str] = set()
        record = info / "RECORD"
        if record.is_file():
            for line in record.read_text(encoding="utf-8", errors="replace").splitlines():
                path = line.split(",", 1)[0]
                if not path or path.startswith(("..", "/")) or path.split("/", 1)[0].endswith((".dist-info", ".data")):
                    continue
                if "/" in path:
                    if "__pycache__" not in path:
                        names.add(path.split("/", 1)[0])
                elif path.endswith(".py"):
                    names.add(path[:-3])
        top = info / "top_level.txt"
        if top.is_file():
            names |= {ln.strip() for ln in top.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()}
        for name in names:
            out.setdefault(name, meta)
    return out


PRODUCERS: dict[str, Producer] = {
    "python_ast": Producer("python_ast", python_ast.build_ir, python_ast.PYTHON_AST_VOCABULARY,
                           python_ast.is_package_dir, locate, distributions, stdlib_names, "--site-packages"),
    "typescript_ast": Producer("typescript_ast", typescript_ast.build_ir, typescript_ast.TYPESCRIPT_AST_VOCABULARY,
                               typescript_ast.is_package_dir, locate_node, distributions_node,
                               lambda: typescript_ast.NODE_STANDARD, "--site-packages (node_modules)",
                               missing_site_packages_ok=True),
}


def corpus_digest(corpus: Path, walk=None, hashes: dict[str, str] | None = None) -> tuple[str, int]:
    """Content address of exactly the files the producer reads: sha256 over sorted
    ``<relpath>\\0<sha256(file)>\\n`` lines. ``hashes`` (relpath under the corpus → sha256, the
    producer's receipt) spares the second read of every file."""
    files = list((walk or python_ast.walk_files)(corpus))
    base = corpus.parent
    root = corpus if corpus.is_dir() else corpus.parent
    h = hashlib.sha256()
    for f in files:
        h.update(str(f.relative_to(base)).encode())
        h.update(b"\0")
        sha = (hashes or {}).get(str(f.relative_to(root))) or hashlib.sha256(f.read_bytes()).hexdigest()
        h.update(sha.encode())
        h.update(b"\n")
    return h.hexdigest(), len(files)


def git_head(corpus: Path) -> str | None:
    """The commit a checkout is at, or None. A corpus that git ignores (a venv inside a repo) has
    no commit: the enclosing repo's HEAD says nothing about the wheel."""
    cwd = corpus if corpus.is_dir() else corpus.parent

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)

    try:
        if run("check-ignore", "-q", str(corpus)).returncode != 1:
            return None
        head = run("rev-parse", "HEAD")
    except (OSError, subprocess.TimeoutExpired):
        return None
    return head.stdout.strip() if head.returncode == 0 and head.stdout.strip() else None


RECORD_SEPARATORS = (",", ":")


def _write_json(path: Path, obj) -> None:
    """A file a human opens — PROVENANCE.json, ring.json, a receipt: indented."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _write_records(path: Path, obj) -> None:
    """A file the machine reads — nodes.json, edges.json, the wormhole sidecar: compact separators,
    no indent. A third of the bytes of the indented form, and the encode is a fraction of the
    mint; every pull, digest and parse downstream reads the same records for fewer bytes."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, separators=RECORD_SEPARATORS) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _file_receipt(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _counts(nodes: dict, edges: list) -> dict:
    node_types: dict[str, int] = {}
    edge_types: dict[str, int] = {}
    for rec in nodes.values():
        node_types[rec.get("node_type", "?")] = node_types.get(rec.get("node_type", "?"), 0) + 1
    for rec in edges:
        edge_types[rec.get("edge_type", "?")] = edge_types.get(rec.get("edge_type", "?"), 0) + 1
    return {"node_count": len(nodes), "edge_count": len(edges),
            "node_types": dict(sorted(node_types.items())), "edge_types": dict(sorted(edge_types.items()))}


SOURCES_KEY = "sources"


def _reuse_from(shard_dir: Path, producer_block: dict):
    """The splice over the shard already at ``shard_dir``: a callable the producer asks per file,
    ``(pin, relpath, sha256) -> (node_records, edge_records) | None``, and the receipt it reads.
    None when the shard has no receipt, the receipt is not spliceable, or the producer that wrote
    it (adapter · graphy · python) is not this one — a record minted by another producer version
    is not this producer's output, and a full mint runs. The previous records are read once, on
    the first file that matches; a file whose bytes moved, or a pin that moved, returns None.

    Returns ``(reuse, refusal)``. The receipt hashes the *sources*, not the records, so before a
    single record is reused the payload itself — nodes.json and edges.json bytes — must hash to
    ``PROVENANCE.files``, the digests the mint wrote (the same check ``index.verify_shard`` runs).
    A shard whose bytes disagree with its receipt was edited after the mint: a planted edge with
    matching source hashes would otherwise survive the splice into the store. Such a shard is
    named in ``refusal`` and nothing of it is reused — the full mint runs."""
    try:
        prov = json.loads((shard_dir / PROVENANCE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    src = prov.get(SOURCES_KEY) if isinstance(prov, dict) else None
    if (not isinstance(src, dict) or not src.get("spliceable") or not isinstance(src.get("files"), dict)
            or prov.get("producer") != producer_block):
        return None, None
    receipts = prov.get("files") if isinstance(prov.get("files"), dict) else {}
    raw: dict[str, bytes] = {}
    for name in ("nodes.json", "edges.json"):
        want = receipts.get(name, {}).get("sha256") if isinstance(receipts.get(name), dict) else None
        try:
            data = (shard_dir / name).read_bytes()
        except OSError:
            return None, None
        got = hashlib.sha256(data).hexdigest()
        if not isinstance(want, str):
            return None, f"SPLICE REFUSED: {shard_dir.name} PROVENANCE carries no sha256 for {name} — minted fresh"
        if got != want:
            return None, (f"SPLICE REFUSED: {shard_dir.name} {name} does not match its PROVENANCE "
                          f"(sha256 {got[:12]}… vs declared {want[:12]}…) — the shard was edited after the mint; "
                          "nothing of it is reused, minted fresh")
        raw[name] = data
    spans: dict[str, tuple[str, int, int, int, int]] = {}
    n_off = e_off = 0
    for rel, f in src["files"].items():
        if not isinstance(f, dict):
            return None
        spans[rel] = (f.get("sha256"), n_off, f.get("nodes", 0), e_off, f.get("edges", 0))
        n_off += f.get("nodes", 0)
        e_off += f.get("edges", 0)
    loaded: list = []

    def reuse(pin: str, rel: str, sha: str):
        if pin != src.get("pin"):
            return None
        span = spans.get(rel)
        if span is None or span[0] != sha:
            return None
        if not loaded:
            try:
                nodes = json.loads(raw["nodes.json"].decode("utf-8"))
                edges = json.loads(raw["edges.json"].decode("utf-8"))
            except ValueError:
                nodes, edges = None, None
            if not isinstance(nodes, dict) or not isinstance(edges, list) or len(nodes) != n_off or len(edges) != e_off:
                loaded.append(None)          # the records disagree with the receipt: the receipt is discarded
            else:
                loaded.append((list(nodes.values()), edges))
        if loaded[0] is None:
            return None
        node_list, edge_list = loaded[0]
        _, n0, nn, e0, ne = span
        return _receipt.splice(node_list[n0:n0 + nn], edge_list[e0:e0 + ne], src["files"][rel])

    return reuse, None


def mint(corpus: str | Path, shard_dir: str | Path, *, mint_command: str,
         distribution: dict | None = None, producer: Producer | str = "python_ast",
         package: str | None = None) -> dict:
    """Mint one corpus into ``shard_dir``: nodes.json (keyed by id), edges.json, PROVENANCE.json.
    Returns the provenance. Raises IRError when the producer's output fails its own vocabulary.

    A shard already at ``shard_dir`` is the splice: its PROVENANCE carries the per-file receipt
    (``sources``: file → sha256 of bytes → the records it produced), and a re-mint hashes every
    file, parses only the ones whose bytes moved, and takes the rest's records from the previous
    nodes.json and edges.json. The shard written is byte-identical to a full mint of the same
    tree; a receipt that does not fit the tree, the producer or the records is discarded and the
    full mint runs. No cache lives outside the shard's own directory."""
    corpus = Path(corpus).resolve()
    shard_dir = Path(shard_dir).resolve()
    prod = PRODUCERS[producer] if isinstance(producer, str) else producer
    producer_block = {"adapter": prod.name, "graphy": _graphy_version(), "python": platform.python_version()}
    reuse, refusal = _reuse_from(shard_dir, producer_block) if shard_dir.is_dir() else (None, None)
    if refusal:
        print(refusal, file=sys.stderr)
    if prod.name == "python_ast":
        nodes, edges, sources = python_ast.mint_records(corpus, reuse=reuse)
    else:
        nodes, edges, sources = typescript_ast.mint_records(corpus, package, reuse=reuse)
    validate_graph(nodes, edges, prod.vocabulary)
    node_map = {k: v for k, v in nodes.items()}
    shard_dir.mkdir(parents=True, exist_ok=True)
    _write_records(shard_dir / "nodes.json", node_map)
    _write_records(shard_dir / "edges.json", edges)
    digest, n_files = corpus_digest(corpus, walk=python_ast.walk_files if prod.name == "python_ast" else typescript_ast.walk_files,
                                    hashes={rel: f["sha256"] for rel, f in sources["files"].items()})
    head = git_head(corpus)
    kind = "file" if corpus.is_file() else ("package" if prod.is_package_dir(corpus) else "tree")
    prov = {
        "surface": f"{shard_dir.name}.records",
        "oracle_commit": head or f"sha256:{digest}",
        "mint_command": mint_command,
        "producer": producer_block,
        "minted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {"scheme": package or (corpus.stem if corpus.is_file() else corpus.name), "kind": kind,
                   "path": portable(corpus), "files": n_files, "sha256": digest, "git_head": head,
                   **(distribution or {})},
        "counts": _counts(node_map, edges),
        "files": {name: _file_receipt(shard_dir / name) for name in ("nodes.json", "edges.json")},
        SOURCES_KEY: {**sources, **({"splice_refused": refusal} if refusal else {})},
        "note": _NOTE,
    }
    _write_json(shard_dir / PROVENANCE_NAME, prov)
    return prov


def _graphy_version() -> str:
    from graphy import __version__
    return __version__


def _schemes(edges: list) -> tuple[set[str], set[str]]:
    src: set[str] = set()
    dst: set[str] = set()
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if isinstance(s, str) and "://" in s:
            src.add(s.split("://", 1)[0])
        if isinstance(d, str) and "://" in d:
            dst.add(d.split("://", 1)[0])
    return src, dst


def _import_schemes(edges: list) -> set[str]:
    return {e["dst"].split("://", 1)[0] for e in edges
            if e.get("edge_type") == "imports" and isinstance(e.get("dst"), str) and "://" in e["dst"]}


def portable(path: Path) -> str:
    """A path as a shard records it: relative to the directory the mint ran from when it lies
    under that directory or its parent (the repo and its siblings), absolute otherwise. A shard
    is tracked and travels; the box it was minted on does not."""
    path = Path(path).resolve()
    cwd = Path.cwd().resolve()
    for base in (cwd, cwd.parent):
        try:
            path.relative_to(base)
        except ValueError:
            continue
        return os.path.relpath(path, cwd)
    return str(path)


def mint_command_for(package: str, site_packages: Path, out: Path, *, corpus: Path | None,
                     ring: bool, producer: str = "python_ast") -> str:
    cmd = (f"python3 -m graphy smash --package {package} --site-packages {portable(site_packages)} "
           f"--out {portable(out)}")
    if corpus is not None:
        cmd += f" --corpus {portable(corpus)}"
    if not ring:
        cmd += " --no-ring"
    if producer != "python_ast":
        cmd += f" --producer {producer}"
    return cmd


def smash(package: str, *, site_packages: str | Path, out: str | Path,
          corpus: str | Path | None = None, ring: bool = True,
          log=None, producer: str = "python_ast") -> dict:
    """Mint ``package`` (from ``corpus`` when given, else from site-packages) and, unless
    ``ring`` is off, every package its resolved imports name that site-packages holds, until no
    new scheme appears. Writes ``<out>/<slug>_graph/`` per package and ``<out>/ring.json``."""
    if producer not in PRODUCERS:
        raise SmashError(f"unknown producer {producer!r} — one of {', '.join(PRODUCERS)}")
    prod = PRODUCERS[producer]
    sp = Path(site_packages).resolve()
    out_dir = Path(out).resolve()
    if not sp.is_dir() and not (prod.missing_site_packages_ok and corpus):
        raise SmashError(f"{prod.corpus_arg} is not a directory: {sp}")
    root_corpus = Path(corpus).resolve() if corpus else prod.locate(package, sp)
    if root_corpus is None or not root_corpus.exists():
        raise SmashError(f"package {package!r} not found: no {sp / package}/ with .py files and no "
                         f"{sp / (package + '.py')}" if corpus is None
                         else f"--corpus does not exist: {root_corpus}")
    if slug_for(package) is None:
        raise SmashError(f"package {package!r} cannot name a shard: the slug grammar is [a-z0-9_]+")
    command = mint_command_for(package, sp, out_dir, corpus=Path(corpus).resolve() if corpus else None, ring=ring,
                               producer=producer)
    dists = prod.distributions(sp)
    if producer != "python_ast" and package not in dists and corpus:
        pj = Path(corpus).resolve() / "package.json"
        if not pj.is_file():
            pj = Path(corpus).resolve().parent / "package.json"
        try:
            meta = json.loads(pj.read_text(encoding="utf-8"))
            dists[package] = {"distribution": meta.get("name"), "version": str(meta.get("version") or "") or None,
                              "license": meta.get("license") if isinstance(meta.get("license"), str) else None}
        except (OSError, ValueError):
            pass
    stdlib = prod.standard()
    minted: dict[str, dict] = {}
    scheme_index: dict[str, dict] = {}
    imports: dict[str, list[str]] = {}
    skipped_stdlib: set[str] = set()
    unresolved: dict[str, str] = {}
    queue: list[tuple[str, Path]] = [(package, root_corpus)]
    while queue:
        scheme, c = queue.pop(0)
        if scheme in minted:
            continue
        slug = slug_for(scheme)
        shard = out_dir / f"{slug}_graph"
        try:
            prov = mint(c, shard, mint_command=command, distribution=dists.get(scheme), producer=prod,
                        package=scheme)
        except IRError as exc:
            raise SmashError(f"{scheme}: producer output failed its own vocabulary — {exc}") from exc
        edges = json.loads((shard / "edges.json").read_text(encoding="utf-8"))
        own, dst = _schemes(edges)
        outs = _import_schemes(edges) - {scheme}
        imports[scheme] = sorted(outs)
        scheme_index[slug] = {"own": sorted(own), "out": sorted(dst - own)}
        minted[scheme] = {"slug": slug, "shard": str(shard), "corpus": str(c),
                          "kind": prov["corpus"]["kind"],
                          "distribution": prov["corpus"].get("distribution"),
                          "version": prov["corpus"].get("version"),
                          "nodes": prov["counts"]["node_count"], "edges": prov["counts"]["edge_count"],
                          "parsed": prov[SOURCES_KEY]["parsed"], "reused": prov[SOURCES_KEY]["reused"]}
        if log:
            src = prov[SOURCES_KEY]
            log(f"MINT OK: {scheme} {prov['counts']['node_count']} nodes / {prov['counts']['edge_count']} edges -> {shard}"
                f"  (parsed {src['parsed']} of {src['parsed'] + src['reused']} files)")
        if not ring:
            break
        for s in sorted(outs):
            if s in minted or s in unresolved or any(q[0] == s for q in queue):
                continue
            if s in stdlib:
                skipped_stdlib.add(s)
                continue
            if slug_for(s) is None:
                unresolved[s] = "not a slug: the shard grammar is [a-z0-9_]+"
                continue
            loc = prod.locate(s, sp) if sp.is_dir() else None
            if loc is None:
                shipped = node_dir_for(s, sp) if producer != "python_ast" else None
                unresolved[s] = (f"{shipped} ships no TypeScript or JavaScript source" if shipped
                                 else f"not under {sp}")
            else:
                queue.append((s, loc))
    receipt = {
        "root": package, "producer": producer, "site_packages": str(sp), "out": str(out_dir), "mint_command": command,
        "minted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "minted": minted, "imports": imports, "scheme_index": scheme_index,
        "stdlib": sorted(skipped_stdlib), "standard": sorted(stdlib),
        "unresolved": dict(sorted(unresolved.items())),
    }
    _write_json(out_dir / RING_NAME, receipt)
    return receipt


def shard_payload(shard_dir: str | Path) -> dict:
    d = Path(shard_dir)
    return {"nodes": json.loads((d / "nodes.json").read_text(encoding="utf-8")),
            "edges": json.loads((d / "edges.json").read_text(encoding="utf-8"))}


def golden_from_shard(golden_dir: str | Path) -> Golden:
    """A shard directory with a PROVENANCE.json is a golden: its provenance is the pin, its
    nodes and edges the payload."""
    d = Path(golden_dir)
    try:
        prov = json.loads((d / PROVENANCE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParityError(f"golden shard has no {PROVENANCE_NAME}: {d}") from exc
    except json.JSONDecodeError as exc:
        raise ParityError(f"golden {d / PROVENANCE_NAME} is not valid JSON: {exc}") from exc
    if not isinstance(prov, dict):
        raise ParityError(f"golden {d / PROVENANCE_NAME} must be a JSON object")
    fields = {k: prov.get(k) for k in ("surface", "oracle_commit", "mint_command")}
    for k, v in fields.items():
        if not isinstance(v, str):
            raise ParityError(f"golden {d / PROVENANCE_NAME} field {k!r} must be a string, got {type(v).__name__}")
    try:
        payload = shard_payload(d)
    except FileNotFoundError as exc:
        raise ParityError(f"golden shard is missing a record file: {exc}") from exc
    return Golden(surface=fields["surface"], oracle_commit=fields["oracle_commit"],
                  mint_command=fields["mint_command"], payload=payload)


def divergence(produced: dict, golden: dict) -> list[str]:
    """A bounded, human-sized account of how two payloads differ; empty when they do not."""
    lines: list[str] = []
    pn, gn = produced.get("nodes") or {}, golden.get("nodes") or {}
    pe, ge = produced.get("edges") or [], golden.get("edges") or []
    missing = sorted(set(gn) - set(pn))
    extra = sorted(set(pn) - set(gn))
    changed = [k for k in gn if k in pn and not json_equal(gn[k], pn[k])]
    if missing or extra or changed:
        lines.append(f"nodes: {len(pn)} produced vs {len(gn)} golden · missing {len(missing)} · "
                     f"extra {len(extra)} · changed {len(changed)}")
        for k in missing[:3]:
            lines.append(f"  missing  {k}")
        for k in extra[:3]:
            lines.append(f"  extra    {k}")
        for k in changed[:3]:
            fields = sorted(f for f in set(gn[k]) | set(pn[k]) if not json_equal(gn[k].get(f), pn[k].get(f)))
            lines.append(f"  changed  {k}  fields {fields}")
    if not json_equal(pe, ge):
        lines.append(f"edges: {len(pe)} produced vs {len(ge)} golden")
        for i, (a, b) in enumerate(zip(pe, ge)):
            if not json_equal(a, b):
                lines.append(f"  first divergence at edge {i}:")
                lines.append(f"    golden   {json.dumps(b, sort_keys=True)}")
                lines.append(f"    produced {json.dumps(a, sort_keys=True)}")
                break
    return lines


def parity(shard_dir: str | Path, golden_dir: str | Path) -> Golden:
    """Prove the minted shard equals the golden record for record. Raises ParityError naming
    the divergence and the re-mint command."""
    golden = golden_from_shard(golden_dir)
    produced = shard_payload(shard_dir)
    diff = divergence(produced, golden.payload)
    if diff:
        raise ParityError(f"parity FAILED on surface {golden.surface!r} (oracle {golden.oracle_commit}).\n"
                          + "\n".join(f"  {ln}" for ln in diff)
                          + f"\n  re-mint with: {golden.mint_command}")
    harness = Harness()
    harness.register(golden.surface, lambda: produced)
    harness.check(golden)
    return golden
