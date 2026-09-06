"""The shard index: content-addressed shards, pushed and pulled byte-identical.

A shard is producer output — ``nodes.json`` + ``edges.json`` + ``PROVENANCE.json`` — and the
PROVENANCE carries the sha256 of the two payload files. The index addresses a shard by the
sha256 over all three files (``<name>\\0<sha256>\\n`` lines, sorted), so two mints that differ
in anything, the minted_at included, are two entries and a name pointer moves between them.

The layout is a directory, so it publishes as whatever hosts a directory — a git repo, a static
site, an object bucket::

    <index>/shards/<address>/nodes.json · edges.json · PROVENANCE.json · NOTICE · MANIFEST.json
    <index>/names/<name>.json      one name -> one address (``pydantic==2.11.7`` by default)
    <index>/catalog.json           every name -> address, regenerated on every push

Push is local (a directory). Pull reads a directory or an ``http(s)://`` base with the same
layout, and verifies every byte before the shard lands: each file against the manifest, the
payload against the PROVENANCE, and the whole against the address. A mismatch refuses and
nothing lands.

Nothing here decides an edge. The shard pulled is the shard pushed, or it is refused.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["IndexError_", "SHARD_FILES", "address_of", "verify_shard", "push", "pull",
           "catalog", "verify_index", "default_name", "MANIFEST_NAME"]

SHARD_FILES = ("nodes.json", "edges.json", "PROVENANCE.json")
PAYLOAD_FILES = ("nodes.json", "edges.json")
MANIFEST_NAME = "MANIFEST.json"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+=@-]{0,199}$")
_ADDRESS_RE = re.compile(r"^[0-9a-f]{64}$")


class IndexError_(RuntimeError):
    """Raised for every refusal: the index, the name, the shard, or the bytes did not hold."""


# ── the shard side ─────────────────────────────────────────────────────────────────────────────

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipts(files: dict[str, bytes]) -> dict[str, dict]:
    return {name: {"bytes": len(data), "sha256": _sha(data)} for name, data in files.items()}


def address_of(receipts: dict[str, dict]) -> str:
    """The content address: sha256 over sorted ``<file>\\0<sha256>\\n`` lines of the three files."""
    h = hashlib.sha256()
    for name in sorted(SHARD_FILES):
        h.update(name.encode())
        h.update(b"\0")
        h.update(receipts[name]["sha256"].encode())
        h.update(b"\n")
    return h.hexdigest()


def _read_shard(shard_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name in SHARD_FILES:
        p = shard_dir / name
        if not p.is_file():
            raise IndexError_(f"{shard_dir} is not a shard: no {name}")
        files[name] = p.read_bytes()
    return files


def verify_shard(files: dict[str, bytes]) -> dict:
    """The PROVENANCE must be JSON and its file receipts must match the payload bytes. Returns
    the provenance. A shard whose PROVENANCE disagrees with its bytes was edited after the mint."""
    try:
        prov = json.loads(files["PROVENANCE.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndexError_(f"PROVENANCE.json is not valid JSON: {exc}") from exc
    if not isinstance(prov, dict) or not isinstance(prov.get("files"), dict):
        raise IndexError_("PROVENANCE.json carries no 'files' receipts — nothing to verify the payload against")
    for name in PAYLOAD_FILES:
        want = prov["files"].get(name, {}).get("sha256")
        if not isinstance(want, str):
            raise IndexError_(f"PROVENANCE.json has no sha256 for {name}")
        got = _sha(files[name])
        if got != want:
            raise IndexError_(f"{name} does not match its PROVENANCE: sha256 {got[:12]}… vs declared "
                              f"{want[:12]}… — the shard was edited after the mint; re-mint, never hand-edit")
    return prov


def default_name(prov: dict) -> str | None:
    """``<distribution>==<version>`` when the PROVENANCE names both; else None and --name is required."""
    corpus = prov.get("corpus") if isinstance(prov.get("corpus"), dict) else {}
    dist, ver = corpus.get("distribution"), corpus.get("version")
    if isinstance(dist, str) and isinstance(ver, str) and dist and ver:
        return f"{dist}=={ver}"
    return None


def _check_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise IndexError_(f"name {name!r} does not fit the grammar [A-Za-z0-9][A-Za-z0-9_.+=@-]* — "
                          "a name is one path segment")
    if _ADDRESS_RE.match(name):
        raise IndexError_(f"name {name!r} is shaped like an address — a name never impersonates one")
    return name


# ── the index side ─────────────────────────────────────────────────────────────────────────────

def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _notice(prov: dict, name: str) -> str:
    corpus = prov.get("corpus") if isinstance(prov.get("corpus"), dict) else {}
    lines = [f"shard {name}",
             f"derived work of {corpus.get('distribution') or corpus.get('scheme') or prov.get('surface', '?')}"
             + (f" {corpus['version']}" if corpus.get("version") else ""),
             f"license: {corpus.get('license') or 'see the upstream distribution'}",
             f"oracle: {prov.get('oracle_commit', '?')}",
             "node docstrings are verbatim upstream text; attribution belongs to the upstream authors.",
             "the graph is structure — every edge is AST, a wormhole, or an admitted weld; no model decided one."]
    return "\n".join(lines) + "\n"


def _rewrite_catalog(index: Path) -> dict[str, str]:
    names_dir = index / "names"
    cat: dict[str, str] = {}
    for p in sorted(names_dir.glob("*.json")) if names_dir.is_dir() else ():
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexError_(f"name pointer {p} is unreadable: {exc}") from exc
        cat[row["name"]] = row["address"]
    _write_atomic(index / "catalog.json", (json.dumps(cat, indent=1, sort_keys=True) + "\n").encode())
    return cat


def push(shard_dir: str | Path, index: str | Path, *, name: str | None = None) -> dict:
    """Push one shard into a directory index. Returns the manifest. Refuses a shard whose bytes
    disagree with its PROVENANCE, a name that does not fit, or a foreign entry at the same
    address (impossible unless the index itself was edited)."""
    shard_dir = Path(shard_dir).resolve()
    index = Path(index)
    if not index.is_absolute():
        raise IndexError_(f"--index must be absolute, got {index} — a relative index is an ambient fallback")
    files = _read_shard(shard_dir)
    prov = verify_shard(files)
    name = name or default_name(prov)
    if not name:
        raise IndexError_("the PROVENANCE names no distribution==version — --name is required "
                          "(e.g. <scheme>@<oracle commit>)")
    name = _check_name(name)
    receipts = _receipts(files)
    address = address_of(receipts)

    entry = index / "shards" / address
    manifest_path = entry / MANIFEST_NAME
    if manifest_path.is_file():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old.get("files") != receipts:
            raise IndexError_(f"the index already holds a different shard at {address[:12]}… — the index was "
                              "edited; an address is its content or the index is a lie")
        manifest = old
        state = "already indexed"
    else:
        manifest = {
            "address": address, "files": receipts, "surface": prov.get("surface"),
            "oracle_commit": prov.get("oracle_commit"), "counts": prov.get("counts"),
            "corpus": {k: prov.get("corpus", {}).get(k) for k in ("scheme", "distribution", "version", "license")
                       if isinstance(prov.get("corpus"), dict)},
            "producer": prov.get("producer"),
            "pushed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        tmp = index / "shards" / f".{address}.{os.getpid()}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for fname, data in files.items():
            (tmp / fname).write_bytes(data)
        (tmp / "NOTICE").write_text(_notice(prov, name), encoding="utf-8")
        (tmp / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, entry)
        state = "pushed"

    names_dir = index / "names"
    names_dir.mkdir(parents=True, exist_ok=True)
    pointer = {"name": name, "address": address, "surface": prov.get("surface"),
               "pointed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _write_atomic(names_dir / f"{name}.json", (json.dumps(pointer, indent=1, sort_keys=True) + "\n").encode())
    _rewrite_catalog(index)
    return {**manifest, "name": name, "state": state}


# ── reading: a directory or an http(s) base, one layout ────────────────────────────────────────

class _Source:
    def __init__(self, base: str) -> None:
        self.base = base
        self.remote = base.startswith(("http://", "https://"))
        if not self.remote:
            p = Path(base)
            if not p.is_absolute():
                raise IndexError_(f"--index must be absolute or an http(s) URL, got {base}")
            if not p.is_dir():
                raise IndexError_(f"no index at {p}")

    def read(self, rel: str) -> bytes | None:
        if self.remote:
            url = self.base.rstrip("/") + "/" + urllib.parse.quote(rel)
            try:
                with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 — the operator named the base
                    return r.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None
                raise IndexError_(f"{url}: HTTP {exc.code}") from exc
            except (urllib.error.URLError, OSError) as exc:
                raise IndexError_(f"{url}: {exc}") from exc
        p = Path(self.base) / rel
        return p.read_bytes() if p.is_file() else None


def _resolve(src: _Source, ref: str) -> tuple[str, str | None]:
    """A 64-hex ref is an address; anything else is a name looked up in names/."""
    if _ADDRESS_RE.match(ref):
        return ref, None
    _check_name(ref)
    raw = src.read(f"names/{ref}.json")
    if raw is None:
        raise IndexError_(f"{ref!r} is not in the index at {src.base} — `graphy index --index …` lists what is")
    try:
        row = json.loads(raw.decode("utf-8"))
        address = row["address"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise IndexError_(f"name pointer for {ref!r} is unreadable: {exc}") from exc
    if not isinstance(address, str) or not _ADDRESS_RE.match(address):
        raise IndexError_(f"name pointer for {ref!r} carries no address")
    return address, ref


def _fetch_entry(src: _Source, address: str) -> tuple[dict, dict[str, bytes]]:
    raw = src.read(f"shards/{address}/{MANIFEST_NAME}")
    if raw is None:
        raise IndexError_(f"no shard at address {address[:12]}… in {src.base}")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndexError_(f"manifest at {address[:12]}… is unreadable: {exc}") from exc
    files: dict[str, bytes] = {}
    for name in SHARD_FILES:
        data = src.read(f"shards/{address}/{name}")
        if data is None:
            raise IndexError_(f"shard {address[:12]}… is missing {name} in {src.base}")
        files[name] = data
    return manifest, files


def _verify_entry(address: str, manifest: dict, files: dict[str, bytes]) -> dict:
    receipts = _receipts(files)
    for name in SHARD_FILES:
        want = (manifest.get("files") or {}).get(name, {}).get("sha256")
        if receipts[name]["sha256"] != want:
            raise IndexError_(f"{name} at {address[:12]}… does not match the manifest — the bytes in transit or "
                              "at rest were altered; refusing to land it")
    if address_of(receipts) != address:
        raise IndexError_(f"the files at {address[:12]}… do not hash to their address — refusing to land it")
    return verify_shard(files)


def pull(ref: str, index: str, out: str | Path) -> dict:
    """Pull a shard by name or address into ``out`` (an absolute directory that must not exist).
    Every byte is verified before anything lands. Returns the manifest with the name and out."""
    out_dir = Path(out)
    if not out_dir.is_absolute():
        raise IndexError_(f"--out must be absolute, got {out_dir}")
    if out_dir.exists():
        raise IndexError_(f"--out {out_dir} already exists — pull never overwrites a live path")
    src = _Source(index)
    address, name = _resolve(src, ref)
    manifest, files = _fetch_entry(src, address)
    prov = _verify_entry(address, manifest, files)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        for fname, data in files.items():
            (tmp / fname).write_bytes(data)
        os.replace(tmp, out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return {**manifest, "name": name, "out": str(out_dir), "surface": prov.get("surface")}


def catalog(index: str) -> dict[str, str]:
    """Every name the index holds -> its address."""
    src = _Source(index)
    raw = src.read("catalog.json")
    if raw is None:
        return {}
    try:
        cat = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndexError_(f"catalog.json at {index} is unreadable: {exc}") from exc
    if not isinstance(cat, dict):
        raise IndexError_(f"catalog.json at {index} is not an object")
    return cat


def verify_index(index: str) -> list[tuple[str, str, str | None]]:
    """Re-hash every named entry. Returns (name, address, problem-or-None) rows."""
    src = _Source(index)
    rows: list[tuple[str, str, str | None]] = []
    for name, address in sorted(catalog(index).items()):
        try:
            manifest, files = _fetch_entry(src, address)
            _verify_entry(address, manifest, files)
            rows.append((name, address, None))
        except IndexError_ as exc:
            rows.append((name, address, str(exc)))
    return rows
