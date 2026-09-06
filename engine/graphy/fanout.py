
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

try:
    import msvcrt
except ImportError:
    msvcrt = None

from graphy._portable_flock import fcntl
from graphy.cartograph import resolve_graph
from graphy.native_json_graph_ir import load_graph_ir

__all__ = ["FanoutError", "Cut", "load_partition", "compile_fanout", "verify_fanout"]

_NO_DOTTED_GROUP = "(no-dotted-path)"
_DEFAULT_REST = "(unpartitioned)"
_MAX_DEPTH = 32
_SECTION_SUFFIX = ".md"
_LOCK_NAME = ".fanout.lock"
_RECEIPT_NAME = "receipt.json"
_RECEIPT_PREV = "receipt.json.prev"
_RECEIPT_TMP = "receipt.json.tmp"
_RESERVED_FILENAMES = frozenset({
    "TOC.md", _RECEIPT_NAME, _RECEIPT_PREV, _RECEIPT_TMP, _LOCK_NAME,
})
_EMITTABLE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.md$")
_PAYLOAD_TMP_SUFFIX = ".part"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_LOCKING = msvcrt is not None


class FanoutError(Exception):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _acquire_publish_lock(lock_f) -> None:
    if _WINDOWS_LOCKING:
        while True:
            lock_f.seek(0)
            try:
                msvcrt.locking(lock_f.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError as exc:
                if exc.errno != errno.EDEADLK:
                    raise
                continue
    else:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)


def _release_publish_lock(lock_f) -> None:
    if _WINDOWS_LOCKING:
        lock_f.seek(0)
        msvcrt.locking(lock_f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _endpoint_flaw(record: dict[str, Any], resolved_key: str) -> str | None:
    repr_key = f"{resolved_key}_repr"
    has_resolved = resolved_key in record
    has_repr = repr_key in record
    if not has_resolved and not has_repr:
        return f"carries neither {resolved_key} nor {repr_key}"
    if has_resolved and (not isinstance(record[resolved_key], str)
                        or not record[resolved_key]):
        return f"{resolved_key} must be a non-empty string"
    if has_repr and (not isinstance(record[repr_key], str)
                     or not record[repr_key]):
        return f"{repr_key} must be a non-empty string"
    return None


def _node_flaw(record: dict[str, Any]) -> str | None:
    if record.get("kind") != "node":
        return f"expected kind 'node', got {record.get('kind')!r}"
    if not isinstance(record.get("id"), str) or not record["id"]:
        return "id must be a non-empty string"
    if not isinstance(record.get("node_type"), str) or not record["node_type"]:
        return "node_type must be a non-empty string"
    return None


def _edge_flaw(record: dict[str, Any]) -> str | None:
    if record.get("kind") != "edge":
        return f"expected kind 'edge', got {record.get('kind')!r}"
    if not isinstance(record.get("edge_type"), str) or not record["edge_type"]:
        return "edge_type must be a non-empty string"
    return _endpoint_flaw(record, "src") or _endpoint_flaw(record, "dst")


class Cut:
    """How a shard's dotted paths become groups.

    A depth cut keeps the first N dotted segments (`fastapi.routing.APIRouter.get` at depth 2 is
    `fastapi.routing`). A partition names its groups and the dotted prefixes each claims, matched
    at segment boundaries, the longest prefix winning; a dotted path no prefix claims lands in
    `rest`. A partition is the one curated input a fan-out takes, and the receipt pins its bytes.
    """

    def __init__(self, depth: int = 1, groups: dict[str, list[str]] | None = None,
                 rest: str = _DEFAULT_REST, source: str | None = None,
                 sha256: str | None = None) -> None:
        if groups is None:
            if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1 or depth > _MAX_DEPTH:
                raise FanoutError(f"depth must be an integer in 1..{_MAX_DEPTH}, got {depth!r}")
        self.depth = depth
        self.groups = groups
        self.rest = rest
        self.source = source
        self.sha256 = sha256
        self._by_prefix: dict[str, str] = {}
        if groups is not None:
            for name, prefixes in groups.items():
                for prefix in prefixes:
                    self._by_prefix[prefix] = name

    @property
    def kind(self) -> str:
        return "depth" if self.groups is None else "partition"

    def group_of(self, dotted: str) -> str:
        if self.groups is None:
            return ".".join(dotted.split(".")[: self.depth])
        parts = dotted.split(".")
        for n in range(len(parts), 0, -1):
            name = self._by_prefix.get(".".join(parts[:n]))
            if name is not None:
                return name
        return self.rest

    def prefixes_of(self, group: str) -> list[str]:
        if self.groups is None:
            return []
        return list(self.groups.get(group, []))

    def receipt(self) -> dict[str, Any]:
        if self.groups is None:
            return {"kind": "depth", "depth": self.depth}
        return {"kind": "partition", "sha256": self.sha256,
                "groups": len(self.groups), "rest": self.rest}


_PREFIX_RE = re.compile(r"^[A-Za-z0-9_~-]+(\.[A-Za-z0-9_~-]+)*$")


def load_partition(path: str | Path) -> Cut:
    """A partition file: {"groups": {NAME: [dotted prefix, …]}, "rest": NAME}."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise FanoutError(f"cannot read the partition at {p}: {exc}") from exc
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise FanoutError(f"partition at {p} is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("groups"), dict) or not doc["groups"]:
        raise FanoutError(f"partition at {p} must carry a non-empty 'groups' map")
    rest = doc.get("rest", _DEFAULT_REST)
    if not isinstance(rest, str) or not rest:
        raise FanoutError(f"partition at {p}: 'rest' must be a non-empty group name")
    groups: dict[str, list[str]] = {}
    claimed: dict[str, str] = {}
    for name, prefixes in doc["groups"].items():
        if not isinstance(name, str) or not name:
            raise FanoutError(f"partition at {p}: a group name must be a non-empty string")
        if name == rest:
            raise FanoutError(f"partition at {p}: group {name!r} is also the rest group")
        if not isinstance(prefixes, list) or not prefixes:
            raise FanoutError(f"partition at {p}: group {name!r} must list at least one dotted prefix")
        clean: list[str] = []
        for prefix in prefixes:
            if not isinstance(prefix, str) or not _PREFIX_RE.match(prefix):
                raise FanoutError(f"partition at {p}: group {name!r} carries a non-dotted prefix {prefix!r}")
            if prefix in claimed:
                raise FanoutError(f"partition at {p}: prefix {prefix!r} is claimed by both "
                                  f"{claimed[prefix]!r} and {name!r}")
            claimed[prefix] = name
            clean.append(prefix)
        groups[name] = clean
    return Cut(groups=groups, rest=rest, source=str(p), sha256=_sha256(raw))


def _node_group(node: dict[str, Any], cut: Cut) -> str:
    dotted = node.get("dotted")
    if isinstance(dotted, str) and dotted:
        return cut.group_of(dotted)
    return _NO_DOTTED_GROUP


def _edge_endpoint(edge: dict[str, Any], key: str) -> str:
    val = edge.get(key)
    if isinstance(val, str) and val:
        return val
    rep = edge.get(f"{key}_repr")
    if isinstance(rep, str) and rep:
        return f"repr:{rep}"
    return ""


def _section_filename(key: str, used_folded: set[str]) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", key)
    if not stem or stem in (".", ".."):
        stem = "_group"
    candidate = stem + _SECTION_SUFFIX
    n = 2
    while candidate.casefold() in used_folded:
        candidate = f"{stem}__{n}{_SECTION_SUFFIX}"
        n += 1
    used_folded.add(candidate.casefold())
    return candidate


def _render_toc(group_keys: list[str], group_nodes: dict[str, int],
                group_edges: dict[str, int], filenames: dict[str, str]) -> str:
    lines = ["# Fan-out TOC", ""]
    for key in group_keys:
        lines.append(f"- {key}: {group_nodes.get(key, 0)} nodes / "
                     f"{group_edges.get(key, 0)} edges -> {filenames[key]}")
    lines.append("")
    return "\n".join(lines)


def _render_node_line(node: dict[str, Any]) -> str:
    parts = [f"node_type={node.get('node_type', '')}",
             f"dotted={node.get('dotted', '')}"]
    file_val = node.get("file")
    if isinstance(file_val, str) and file_val and not os.path.isabs(file_val):
        parts.append(f"file={file_val}")
    return f"- {node['id']}  ({', '.join(parts)})"


def _render_section(key: str, nodes: list[dict[str, Any]],
                    edges: list[dict[str, Any]], prefixes: list[str] = ()) -> str:
    lines = [f"# {key}", ""]
    if prefixes:
        lines += ["prefixes: " + " · ".join(prefixes), ""]
    lines.append("## nodes")
    if nodes:
        for n in nodes:
            lines.append(_render_node_line(n))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## edges")
    if edges:
        for e in edges:
            lines.append(f"- {_edge_endpoint(e, 'src')} -> "
                         f"{_edge_endpoint(e, 'dst')} [{e.get('edge_type', '')}]")
    else:
        lines.append("(none)")
    lines.append("")
    return "\n".join(lines)


def compile_fanout(graph_dir: str | Path, out_dir: str | Path,
                   cut: Cut | None = None) -> dict[str, Any]:
    cut = cut if cut is not None else Cut()
    gd = Path(graph_dir)
    if not gd.is_dir():
        raise FanoutError(f"graph dir does not exist at {gd}")

    resolved = resolve_graph(gd)
    try:
        nodes_bytes = (resolved / "nodes.json").read_bytes()
        edges_bytes = (resolved / "edges.json").read_bytes()
    except OSError as exc:
        raise FanoutError(f"cannot read the shard at {gd}: {exc}") from exc

    try:
        shard = load_graph_ir(resolved)
    except (OSError, ValueError) as exc:
        raise FanoutError(f"cannot load the shard at {gd}: {exc}") from exc

    nodes_by_id: dict[str, dict[str, Any]] = {}
    all_edges: list[dict[str, Any]] = []
    flaws: list[str] = []
    for n in shard.nodes:
        flaw = _node_flaw(n)
        if flaw:
            flaws.append(f"node {n.get('id')!r}: {flaw}")
        else:
            nodes_by_id[n["id"]] = n
    for e in shard.edges:
        flaw = _edge_flaw(e)
        if flaw:
            flaws.append(f"edge {e.get('src') or e.get('src_repr')!r}: {flaw}")
        else:
            all_edges.append(e)
    for res in shard.residuals:
        if isinstance(res, dict) and res.get("kind") == "node":
            flaw = _node_flaw(res)
            if flaw:
                flaws.append(f"residual node {res.get('id')!r}: {flaw}")
            else:
                nodes_by_id.setdefault(res["id"], res)
        elif isinstance(res, dict) and res.get("kind") == "edge":
            flaw = _edge_flaw(res)
            if flaw:
                flaws.append(f"residual edge: {flaw}")
            else:
                all_edges.append(res)
        else:
            flaws.append("record with no kind: node/edge shape")
    if flaws:
        shown = "; ".join(flaws[:3]) + ("; …" if len(flaws) > 3 else "")
        raise FanoutError(
            f"shard at {gd} carries {len(flaws)} genuinely malformed record(s) "
            f"({shown}) — nothing was written")

    group_nodes: dict[str, list[dict[str, Any]]] = {}
    for node in nodes_by_id.values():
        group_nodes.setdefault(_node_group(node, cut), []).append(node)
    for nodes in group_nodes.values():
        nodes.sort(key=lambda n: n["id"])

    node_group_of = {nid: _node_group(n, cut) for nid, n in nodes_by_id.items()}
    group_edges: dict[str, list[dict[str, Any]]] = {}
    for edge in all_edges:
        src = edge.get("src", "")
        dst = edge.get("dst", "")
        if src in node_group_of:
            key = node_group_of[src]
        elif dst in node_group_of:
            key = node_group_of[dst]
        else:
            key = _NO_DOTTED_GROUP
        group_edges.setdefault(key, []).append(edge)
    for edges in group_edges.values():
        edges.sort(key=lambda e: (_edge_endpoint(e, "src"),
                                  _edge_endpoint(e, "dst"),
                                  e.get("edge_type", "")))

    group_keys = sorted(set(group_nodes) | set(group_edges))
    filenames: dict[str, str] = {}
    used_folded: set[str] = {name.casefold() for name in _RESERVED_FILENAMES}
    for key in group_keys:
        filenames[key] = _section_filename(key, used_folded)

    files: dict[str, str] = {}
    files["TOC.md"] = _render_toc(
        group_keys,
        {k: len(v) for k, v in group_nodes.items()},
        {k: len(v) for k, v in group_edges.items()},
        filenames,
    )
    for key in group_keys:
        files[filenames[key]] = _render_section(
            key, group_nodes.get(key, []), group_edges.get(key, []), cut.prefixes_of(key))

    payloads: dict[str, bytes] = {relpath: content.encode("utf-8")
                                  for relpath, content in files.items()}
    outputs = {relpath: _sha256(buf) for relpath, buf in sorted(payloads.items())}
    receipt = {
        "input": {
            "nodes.json": _sha256(nodes_bytes),
            "edges.json": _sha256(edges_bytes),
        },
        "cut": cut.receipt(),
        "groups": {key: {
            "nodes": len(group_nodes.get(key, [])),
            "edges": len(group_edges.get(key, [])),
        } for key in group_keys},
        "outputs": outputs,
    }
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")

    out = Path(out_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
        lock_path = out / _LOCK_NAME
        if lock_path.is_symlink():
            raise FanoutError(
                f"lock file at {lock_path} is a symlink — refusing to lock "
                "through a redirected entry")
        with open(lock_path, "a+b") as lock_f:
            _acquire_publish_lock(lock_f)
            try:
                receipt_path = out / _RECEIPT_NAME
                prev_path = out / _RECEIPT_PREV
                tmp_path = out / _RECEIPT_TMP
                if tmp_path.exists() or tmp_path.is_symlink():
                    tmp_path.unlink()
                for entry in sorted(out.iterdir()):
                    if entry.name.endswith(_PAYLOAD_TMP_SUFFIX):
                        entry.unlink()
                if receipt_path.exists():
                    os.replace(receipt_path, prev_path)
                for relpath, buf in payloads.items():
                    staged = out / (relpath + _PAYLOAD_TMP_SUFFIX)
                    staged.write_bytes(buf)
                    os.replace(staged, out / relpath)
                current_by_fold = {name.casefold(): name for name in payloads}
                for entry in sorted(out.iterdir()):
                    name = entry.name
                    if not _EMITTABLE_NAME.match(name) or name in _RESERVED_FILENAMES:
                        continue
                    if entry.is_symlink():
                        entry.unlink()
                        continue
                    if not entry.is_file():
                        continue
                    live = current_by_fold.get(name.casefold())
                    if live is not None and entry.samefile(out / live):
                        continue
                    entry.unlink()
                tmp_path.write_bytes(receipt_bytes)
                os.replace(tmp_path, receipt_path)
                if prev_path.exists():
                    prev_path.unlink()
            finally:
                _release_publish_lock(lock_f)
    except OSError as exc:
        raise FanoutError(f"cannot write the fan-out to {out_dir}: {exc}") from exc
    return receipt


def _read_pinned_entry(path: Path) -> tuple[bytes | None, str | None]:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    nonblock = getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, os.O_RDONLY | nofollow | nonblock)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return None, "redirected entry (symlink)"
        if exc.errno == errno.ENOENT:
            return None, "missing"
        return None, f"unreadable (errno {exc.errno})"
    flaw: str | None = None
    data: bytes | None = None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            flaw = "not a regular file"
        elif not nofollow:
            try:
                lst = os.lstat(path)
            except OSError:
                flaw = "entry vanished during verification"
            else:
                if stat.S_ISLNK(lst.st_mode):
                    flaw = "redirected entry (symlink)"
                elif (lst.st_dev, lst.st_ino) != (st.st_dev, st.st_ino):
                    flaw = "entry replaced during verification"
        if flaw is None:
            if nonblock and os.name != "nt":
                os.set_blocking(fd, True)
            fh = os.fdopen(fd, "rb")
            fd = -1
            try:
                data = fh.read()
            except OSError as exc:
                flaw = f"unreadable after open (errno {exc.errno})"
                data = None
            finally:
                try:
                    fh.close()
                except OSError as exc:
                    if flaw is None:
                        flaw = f"descriptor cleanup failed (errno {exc.errno})"
                        data = None
    except OSError as exc:
        flaw = f"unreadable after open (errno {exc.errno})"
        data = None
    if fd >= 0:
        try:
            os.close(fd)
        except OSError as exc:
            if flaw is None:
                flaw = f"descriptor cleanup failed (errno {exc.errno})"
                data = None
    if flaw is not None:
        return None, flaw
    return data, None


def _cut_flaw(cut: Any) -> str | None:
    if not isinstance(cut, dict):
        return "cut must be a map"
    if cut.get("kind") == "depth":
        d = cut.get("depth")
        if (set(cut) != {"kind", "depth"} or not isinstance(d, int)
                or isinstance(d, bool) or d < 1 or d > _MAX_DEPTH):
            return f"a depth cut must carry depth 1..{_MAX_DEPTH}"
        return None
    if cut.get("kind") == "partition":
        if (set(cut) != {"kind", "sha256", "groups", "rest"}
                or not isinstance(cut["sha256"], str) or not _SHA256_HEX.match(cut["sha256"])
                or not isinstance(cut["groups"], int) or isinstance(cut["groups"], bool)
                or cut["groups"] < 1
                or not isinstance(cut["rest"], str) or not cut["rest"]):
            return "a partition cut must carry its sha256, its group count and its rest group"
        return None
    return "cut kind must be depth or partition"


def _receipt_flaw(pinned: Any) -> str | None:
    if not isinstance(pinned, dict) or set(pinned) != {"input", "cut", "groups", "outputs"}:
        return "root must carry exactly input/cut/groups/outputs"
    cut_flaw = _cut_flaw(pinned["cut"])
    if cut_flaw is not None:
        return cut_flaw
    inp = pinned["input"]
    if (not isinstance(inp, dict) or set(inp) != {"nodes.json", "edges.json"}
            or not all(isinstance(v, str) and _SHA256_HEX.match(v)
                       for v in inp.values())):
        return "input must hash exactly nodes.json and edges.json"
    groups = pinned["groups"]
    if not isinstance(groups, dict) or not all(
            isinstance(k, str) and isinstance(v, dict)
            and set(v) == {"nodes", "edges"}
            and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0
                    for n in v.values())
            for k, v in groups.items()):
        return "groups must map names to nodes/edges counts"
    outputs = pinned["outputs"]
    if not isinstance(outputs, dict) or not outputs:
        return "outputs must be a nonempty map"
    for k, v in outputs.items():
        if not isinstance(k, str) or not _EMITTABLE_NAME.match(k):
            return f"output key {k!r} is not a compiler filename"
        if not isinstance(v, str) or not _SHA256_HEX.match(v):
            return f"output {k} carries a non-sha256 digest"
    used_folded = {name.casefold() for name in _RESERVED_FILENAMES}
    expected = {"TOC.md"}
    for key in sorted(groups):
        expected.add(_section_filename(key, used_folded))
    if set(outputs) != expected:
        return ("outputs do not match the deterministic filename set the "
                "compiler assigns to these groups")
    return None


def verify_fanout(out_dir: str | Path,
                  receipt_bytes: bytes | None = None,
                  read_set: dict[str, bytes] | None = None) -> dict[str, Any]:
    if receipt_bytes is not None and read_set is None:
        raise ValueError(
            "a pinned receipt needs the bytes read under it — pass read_set; "
            "re-reading disk against an old pin can be ABA-fooled by a "
            "republish of the pinned generation")
    out = Path(out_dir)
    if receipt_bytes is None:
        receipt_bytes, flaw = _read_pinned_entry(out / _RECEIPT_NAME)
        if flaw is not None:
            return {"status": "INCOMPLETE", "mismatched": [], "receipt": None,
                    "detail": f"receipt.json: {flaw} — a publish is in "
                              "flight, a crashed run never completed, or the "
                              "entry is not the compiler's; do not trust reads"}
    try:
        pinned = json.loads(receipt_bytes)
    except ValueError:
        return {"status": "INCOMPLETE", "mismatched": [], "receipt": None,
                "detail": "receipt.json is not valid JSON — foreign or "
                          "truncated; do not trust reads"}
    receipt_flaw = _receipt_flaw(pinned)
    if receipt_flaw is not None:
        return {"status": "INCOMPLETE", "mismatched": [],
                "receipt": pinned if isinstance(pinned, dict) else None,
                "detail": f"foreign receipt shape ({receipt_flaw}) — "
                          "do not trust reads"}
    outputs = pinned["outputs"]

    if read_set is None:
        read_set = {}
        mismatched: list[str] = []
        for relpath in sorted(outputs):
            buf, flaw = _read_pinned_entry(out / relpath)
            if flaw is not None:
                mismatched.append(f"{relpath}: {flaw}")
            else:
                read_set[relpath] = buf
    else:
        mismatched = []
        if not read_set:
            return {"status": "INCOMPLETE", "mismatched": [], "receipt": pinned,
                    "detail": "read_set is empty — verifying zero read "
                              "records proves nothing; do not trust reads"}
    for relpath, buf in sorted(read_set.items()):
        if not isinstance(relpath, str) or not _EMITTABLE_NAME.match(relpath):
            mismatched.append(f"{relpath!r}: not a compiler filename")
            continue
        want = outputs.get(relpath)
        if want is None:
            mismatched.append(f"{relpath}: not in the pinned receipt")
        elif _sha256(buf) != want:
            mismatched.append(f"{relpath}: hash mismatch")
    if mismatched:
        return {"status": "IN-FLIGHT", "mismatched": mismatched,
                "receipt": pinned,
                "detail": "a publish overlapped this read set — re-pin the "
                          "receipt and re-read"}
    return {"status": "COHERENT", "mismatched": [], "receipt": pinned,
            "detail": f"{len(read_set)} read record(s) match the pinned "
                      "receipt"}
