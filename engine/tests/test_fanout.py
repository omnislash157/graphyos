
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import graphy.cli as cli




def _write_shard(dirpath: Path, nodes: dict, edges: list) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (dirpath / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def _two_group_shard() -> tuple[dict, list]:
    nodes = {
        "alpha://module/alpha": {
            "kind": "node", "node_type": "module", "id": "alpha://module/alpha",
            "dotted": "alpha", "file": "alpha/__init__.py",
        },
        "alpha://func/alpha.util": {
            "kind": "node", "node_type": "func", "id": "alpha://func/alpha.util",
            "dotted": "alpha.util", "file": "alpha/util.py",
        },
        "beta://module/beta": {
            "kind": "node", "node_type": "module", "id": "beta://module/beta",
            "dotted": "beta", "file": "beta/__init__.py",
        },
    }
    edges = [
        {"kind": "edge", "edge_type": "imports", "src": "alpha://module/alpha",
         "dst": "alpha://func/alpha.util", "line": 1},
        {"kind": "edge", "edge_type": "imports", "src": "alpha://module/alpha",
         "dst": "beta://module/beta", "line": 2},
    ]
    return nodes, edges


def _emitted_files(out_dir: Path) -> dict[str, bytes]:
    return {
        p.relative_to(out_dir).as_posix(): p.read_bytes()
        for p in sorted(out_dir.rglob("*"))
        if p.is_file()
    }




def test_fanout_rerun_byte_identical(tmp_path, capsys):
    graph = tmp_path / "graph"
    _write_shard(graph, *_two_group_shard())

    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out_a)]) == 0
    capsys.readouterr()
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out_b)]) == 0
    capsys.readouterr()

    files_a = _emitted_files(out_a)
    files_b = _emitted_files(out_b)
    assert files_a.keys() == files_b.keys()
    for rel in sorted(files_a):
        assert files_a[rel] == files_b[rel], f"drifted bytes in {rel}"


def test_fanout_receipt_names_drift(tmp_path, capsys):
    nodes, edges = _two_group_shard()

    graph_a = tmp_path / "graph_a"
    _write_shard(graph_a, nodes, edges)
    out_a = tmp_path / "out_a"
    assert cli.main(["fanout", "--graph-dir", str(graph_a), "--out", str(out_a)]) == 0
    capsys.readouterr()
    receipt_a = json.loads((out_a / "receipt.json").read_text(encoding="utf-8"))

    graph_b = tmp_path / "graph_b"
    edges_b = copy.deepcopy(edges)
    edges_b[0]["edge_type"] = "calls"
    _write_shard(graph_b, nodes, edges_b)
    out_b = tmp_path / "out_b"
    assert cli.main(["fanout", "--graph-dir", str(graph_b), "--out", str(out_b)]) == 0
    capsys.readouterr()
    receipt_b = json.loads((out_b / "receipt.json").read_text(encoding="utf-8"))

    assert receipt_a["input"]["edges.json"] != receipt_b["input"]["edges.json"]
    assert receipt_a["input"]["nodes.json"] == receipt_b["input"]["nodes.json"]

    changed = {
        rel for rel in receipt_a["outputs"]
        if receipt_a["outputs"][rel] != receipt_b["outputs"].get(rel)
    }
    assert "alpha.md" in changed, f"drifted file not named; changed={changed}"
    assert "beta.md" not in changed
    assert "TOC.md" not in changed


def test_fanout_refuses_missing_graph_dir(tmp_path, capsys):
    missing = tmp_path / "no_such_graph"
    out = tmp_path / "out"
    rc = cli.main(["fanout", "--graph-dir", str(missing), "--out", str(out)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert rc == 2
    assert "FANOUT REFUSED:" in combined
    assert "graph dir" in combined
    assert "Traceback" not in combined
    assert not out.exists(), "a refused fan-out must emit nothing"


def test_fanout_renders_residual_repr_edges(tmp_path, capsys):
    nodes, edges = _two_group_shard()
    edges.append({"kind": "edge", "edge_type": "calls",
                  "src": "alpha://module/alpha", "dst_repr": "os.path.join",
                  "line": 3})
    graph = tmp_path / "graph"
    _write_shard(graph, nodes, edges)
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    total_edges = sum(g["edges"] for g in receipt["groups"].values())
    assert total_edges == 3, f"repr edge dropped from the receipt: {receipt['groups']}"
    section = (out / "alpha.md").read_text(encoding="utf-8")
    assert "os.path.join" in section, "repr edge dropped from the rendered section"


def test_fanout_refuses_malformed_residual(tmp_path, capsys):
    nodes, edges = _two_group_shard()
    edges.append({"garbage": True})
    graph = tmp_path / "graph"
    _write_shard(graph, nodes, edges)
    out = tmp_path / "out"
    rc = cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert rc == 2
    assert "FANOUT REFUSED:" in combined
    assert "malformed" in combined
    assert "Traceback" not in combined
    assert not out.exists(), "a refused fan-out must emit nothing"


def test_fanout_toc_group_does_not_overwrite_index(tmp_path, capsys):
    nodes = {
        "toc://module/TOC": {
            "kind": "node", "node_type": "module", "id": "toc://module/TOC",
            "dotted": "TOC.intro",
        },
    }
    graph = tmp_path / "graph"
    _write_shard(graph, nodes, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    index = (out / "TOC.md").read_text(encoding="utf-8")
    assert index.startswith("# Fan-out TOC"), "the product index was overwritten"
    section = (out / "TOC__2.md").read_text(encoding="utf-8")
    assert section.startswith("# TOC"), "the TOC group lost its section file"
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert {"TOC.md", "TOC__2.md"} <= set(receipt["outputs"])


def test_fanout_regeneration_retires_stale_sections(tmp_path, capsys):
    nodes, edges = _two_group_shard()
    graph_ab = tmp_path / "graph_ab"
    _write_shard(graph_ab, nodes, edges)
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph_ab), "--out", str(out)]) == 0
    capsys.readouterr()
    assert (out / "beta.md").is_file()

    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph_a = tmp_path / "graph_a"
    _write_shard(graph_a, alpha_only, [edges[0]])
    assert cli.main(["fanout", "--graph-dir", str(graph_a), "--out", str(out)]) == 0
    capsys.readouterr()

    assert not (out / "beta.md").exists(), "retired section survived regeneration"
    assert not (out / "receipt.json.prev").exists(), "transient prior receipt not reaped"
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert "beta.md" not in receipt["outputs"]


def test_fanout_receipt_hashes_match_disk_bytes(tmp_path, capsys, monkeypatch):
    import hashlib
    from pathlib import Path as _P

    graph = tmp_path / "graph"
    _write_shard(graph, *_two_group_shard())

    real_write_text = _P.write_text

    def _crlf_write_text(self, data, *args, **kwargs):
        return real_write_text(self, data.replace("\n", "\r\n"), *args, **kwargs)

    monkeypatch.setattr(_P, "write_text", _crlf_write_text)

    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    for rel, recorded in receipt["outputs"].items():
        on_disk = hashlib.sha256((out / rel).read_bytes()).hexdigest()
        assert on_disk == recorded, f"{rel}: receipt hash does not describe disk bytes"
    assert b"\r" not in (out / "receipt.json").read_bytes()


def test_fanout_receipt_and_content_share_one_pin(tmp_path, capsys, monkeypatch):
    import hashlib

    import graphy.fanout as fanout_mod

    nodes_v1 = {"alpha://module/alpha": {
        "kind": "node", "node_type": "module", "id": "alpha://module/alpha",
        "dotted": "alpha"}}
    nodes_v2 = {"gamma://module/gamma": {
        "kind": "node", "node_type": "module", "id": "gamma://module/gamma",
        "dotted": "gamma"}}
    v1 = tmp_path / "v1"
    v2 = tmp_path / "v2"
    _write_shard(v1, nodes_v1, [])
    _write_shard(v2, nodes_v2, [])
    link = tmp_path / "graph"
    link.symlink_to(v1, target_is_directory=True)

    real_load = fanout_mod.load_graph_ir

    def _flip_then_load(graph_dir):
        link.unlink()
        link.symlink_to(v2, target_is_directory=True)
        return real_load(graph_dir)

    monkeypatch.setattr(fanout_mod, "load_graph_ir", _flip_then_load)

    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(link), "--out", str(out)]) == 0
    capsys.readouterr()

    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    v1_nodes_sha = hashlib.sha256((v1 / "nodes.json").read_bytes()).hexdigest()
    assert receipt["input"]["nodes.json"] == v1_nodes_sha, "receipt hashed the wrong pin"
    assert "alpha" in receipt["groups"], f"content came from the flipped target: {receipt['groups']}"
    assert "gamma" not in receipt["groups"], "receipt and content split across two snapshots"


def test_fanout_refuses_structurally_empty_records(tmp_path, capsys):
    base_nodes, base_edges = _two_group_shard()
    flawed = [
        ("bare-kind-edge", [{"kind": "edge"}]),
        ("empty-edge-type", [{"kind": "edge", "edge_type": "",
                              "src": "alpha://module/alpha",
                              "dst": "beta://module/beta"}]),
        ("present-empty-src", [{"kind": "edge", "edge_type": "calls",
                                "src": "", "dst": "beta://module/beta"}]),
        ("empty-src-beside-valid-repr", [{"kind": "edge", "edge_type": "calls",
                                          "src": "", "src_repr": "os.walk",
                                          "dst": "beta://module/beta"}]),
        ("main-lane-empty-edge-type", [{"src": "alpha://module/alpha",
                                        "dst": "beta://module/beta",
                                        "edge_type": ""}]),
    ]
    for tag, extra in flawed:
        graph = tmp_path / f"graph_{tag}"
        _write_shard(graph, base_nodes, base_edges + extra)
        out = tmp_path / f"out_{tag}"
        rc = cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)])
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert rc == 2, f"{tag}: structurally empty record admitted"
        assert "FANOUT REFUSED:" in combined, tag
        assert "malformed" in combined, tag
        assert "Traceback" not in combined, tag
        assert not out.exists(), f"{tag}: a refused fan-out must emit nothing"

    for tag, node in [
        ("empty-node-id", {"kind": "node", "id": "", "node_type": "module",
                           "dotted": "zeta"}),
        ("missing-node-type", {"kind": "node", "id": "zeta://module/zeta",
                               "dotted": "zeta"}),
    ]:
        graph = tmp_path / f"graph_{tag}"
        nodes = dict(base_nodes)
        nodes["zeta-key"] = node
        _write_shard(graph, nodes, base_edges)
        out = tmp_path / f"out_{tag}"
        rc = cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)])
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert rc == 2, f"{tag}: structurally empty node admitted"
        assert "malformed" in combined and "Traceback" not in combined, tag
        assert not out.exists(), tag

    graph = tmp_path / "graph_clean"
    _write_shard(graph, base_nodes, base_edges)
    out = tmp_path / "out_clean"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()


def test_fanout_retires_unreceipted_strays(tmp_path, capsys, monkeypatch):
    nodes, edges = _two_group_shard()
    graph_ab = tmp_path / "graph_ab"
    _write_shard(graph_ab, nodes, edges)
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph_a = tmp_path / "graph_a"
    _write_shard(graph_a, alpha_only, [edges[0]])

    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph_ab), "--out", str(out)]) == 0
    capsys.readouterr()
    (out / "orphan.md").write_bytes(b"# unreceipted stray from an older producer\n")
    assert cli.main(["fanout", "--graph-dir", str(graph_a), "--out", str(out)]) == 0
    capsys.readouterr()
    assert not (out / "orphan.md").exists(), "unreceipted stray survived the publish"
    assert not (out / "beta.md").exists(), "retired section survived regeneration"
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    disk_md = {p.name for p in out.iterdir() if p.name.endswith(".md")}
    assert disk_md == set(receipt["outputs"]), (
        f"disk and receipt disagree: {disk_md} vs {set(receipt['outputs'])}")

    out2 = tmp_path / "out2"
    real_write = Path.write_bytes
    armed = {"on": True}

    def _crash_before_receipt(self, data):
        if armed["on"] and self.name == "receipt.json.tmp":
            raise OSError("forced crash before the receipt")
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", _crash_before_receipt)
    rc = cli.main(["fanout", "--graph-dir", str(graph_ab), "--out", str(out2)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.out + captured.err
    assert not (out2 / "receipt.json").exists(), "a crashed run must leave no receipt"
    assert (out2 / "beta.md").is_file(), "the probe needs the in-flight litter on disk"

    armed["on"] = False
    assert cli.main(["fanout", "--graph-dir", str(graph_a), "--out", str(out2)]) == 0
    capsys.readouterr()
    assert not (out2 / "beta.md").exists(), "interrupted-generation litter survived"
    receipt = json.loads((out2 / "receipt.json").read_text(encoding="utf-8"))
    assert "beta.md" not in receipt["outputs"]
    disk_md = {p.name for p in out2.iterdir() if p.name.endswith(".md")}
    assert disk_md == set(receipt["outputs"])


def test_fanout_prior_receipt_never_an_unlink_oracle(tmp_path, capsys):
    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])

    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"outside the compiler's namespace\n")
    out = tmp_path / "out"
    out.mkdir()
    hostile = {"outputs": {"../victim.txt": "00", str(victim): "00"}}
    (out / "receipt.json").write_text(json.dumps(hostile), encoding="utf-8")
    (out / "stale_gen.md").write_bytes(b"# genuine stale artifact inside --out\n")
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()
    assert victim.is_file(), "a receipt key escaped --out and deleted the sentinel"
    assert not (out / "stale_gen.md").exists(), "genuine stale artifact survived"
    assert not (out / "receipt.json.prev").exists(), "prior marker not reaped"
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert "alpha.md" in receipt["outputs"]

    out2 = tmp_path / "out2"
    out2.mkdir()
    (out2 / "receipt.json").write_text("[]", encoding="utf-8")
    rc = cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out2)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Traceback" not in captured.out + captured.err
    receipt = json.loads((out2 / "receipt.json").read_text(encoding="utf-8"))
    assert "alpha.md" in receipt["outputs"]


def test_fanout_windows_seat_lock_serializes(tmp_path, monkeypatch):
    import hashlib
    import threading

    import graphy.fanout as fanout_mod

    nodes_a = {"alpha://module/alpha": {"kind": "node", "node_type": "module",
                                        "id": "alpha://module/alpha",
                                        "dotted": "alpha"}}
    nodes_b = {"gamma://module/gamma": {"kind": "node", "node_type": "module",
                                        "id": "gamma://module/gamma",
                                        "dotted": "gamma"}}
    real_write = Path.write_bytes

    class _ShimMsvcrt:
        LK_LOCK = 1
        LK_UNLCK = 0

        def __init__(self, real: bool):
            self._real = real

        def locking(self, fd, mode, nbytes):
            if not self._real:
                return
            import fcntl as _f
            _f.flock(fd, _f.LOCK_EX if mode == self.LK_LOCK else _f.LOCK_UN)

    def _overlap(tag: str, real_lock: bool):
        graph_a = tmp_path / f"graph_a_{tag}"
        graph_b = tmp_path / f"graph_b_{tag}"
        _write_shard(graph_a, nodes_a, [])
        _write_shard(graph_b, nodes_b, [])
        out = tmp_path / f"out_{tag}"
        monkeypatch.setattr(fanout_mod, "msvcrt", _ShimMsvcrt(real_lock))
        monkeypatch.setattr(fanout_mod, "_WINDOWS_LOCKING", True)
        paused = threading.Event()
        release = threading.Event()

        def _pausing_write(self, data):
            if (threading.current_thread().name == "writer-a"
                    and self.name == "receipt.json.tmp"):
                paused.set()
                release.wait(timeout=30)
            return real_write(self, data)

        monkeypatch.setattr(Path, "write_bytes", _pausing_write)
        real_acquire = fanout_mod._acquire_publish_lock
        b_acquired = threading.Event()
        order: list[str] = []

        def _noting_acquire(lock_f):
            real_acquire(lock_f)
            if threading.current_thread().name == "writer-b":
                order.append("b-acquired")
                b_acquired.set()

        monkeypatch.setattr(fanout_mod, "_acquire_publish_lock", _noting_acquire)
        done: dict[str, dict] = {}
        ta = threading.Thread(
            name="writer-a",
            target=lambda: done.update(a=fanout_mod.compile_fanout(graph_a, out)))
        ta.start()
        assert paused.wait(timeout=30), "writer A never reached its receipt"
        tb = threading.Thread(
            name="writer-b",
            target=lambda: done.update(b=fanout_mod.compile_fanout(graph_b, out)))
        tb.start()
        # B says when it holds the lock; a no-op lock admits it at once, a real one
        # not until A releases — 0.2 s is the ceiling on "still blocked", never a sleep
        b_acquired_inside_window = b_acquired.wait(timeout=0.2)
        if b_acquired_inside_window:
            tb.join(timeout=30)  # B's publish lands inside A's window — the overlap the control wants
        order.append("a-released")
        release.set()
        ta.join(timeout=30)
        tb.join(timeout=30)
        assert not ta.is_alive() and not tb.is_alive(), "a writer never finished"
        assert b_acquired.is_set(), "writer B never took the lock"
        b_published_inside_window = b_acquired_inside_window or order.index("b-acquired") < order.index("a-released")
        assert "a" in done and "b" in done, "a writer died instead of returning"
        receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
        lies = []
        for rel, want in receipt["outputs"].items():
            p = out / rel
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != want:
                lies.append(rel)
        return b_published_inside_window, lies

    b_inside, lies = _overlap("noop", real_lock=False)
    assert b_inside, "control failed: the no-op lock did not admit the overlap"
    assert lies, "control failed: the no-op overlap left a truthful receipt"

    b_inside, lies = _overlap("real", real_lock=True)
    assert not b_inside, "writer B published inside writer A's locked window"
    assert lies == [], f"the receipt lies about disk: {lies}"


def test_fanout_case_folded_filename_identity(tmp_path, capsys):
    nodes = {
        "toc://module/toc": {"kind": "node", "node_type": "module",
                             "id": "toc://module/toc", "dotted": "toc.intro"},
        "a://module/Alpha": {"kind": "node", "node_type": "module",
                             "id": "a://module/Alpha", "dotted": "Alpha.x"},
        "a://module/alpha": {"kind": "node", "node_type": "module",
                             "id": "a://module/alpha", "dotted": "alpha.y"},
    }
    graph = tmp_path / "graph"
    _write_shard(graph, nodes, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    outputs = set(receipt["outputs"])
    assert len({n.casefold() for n in outputs}) == len(outputs), (
        f"case-aliased artifact set: {sorted(outputs)}")
    assert (out / "TOC.md").read_text(encoding="utf-8").startswith("# Fan-out TOC"), (
        "the product index was overwritten through a case alias")
    assert "toc__2.md" in outputs, "the toc group was not deflected off the index"
    assert (out / "toc__2.md").read_text(encoding="utf-8").startswith("# toc")
    assert {"Alpha.md", "alpha__2.md"} <= outputs, (
        f"case-colliding groups did not allocate distinct names: {sorted(outputs)}")
    assert (out / "Alpha.md").read_text(encoding="utf-8").startswith("# Alpha")
    assert (out / "alpha__2.md").read_text(encoding="utf-8").startswith("# alpha")


def test_fanout_refuses_main_lane_kind_mismatch(tmp_path, capsys):
    base_nodes, base_edges = _two_group_shard()

    for tag, nodes, edges in [
        ("node-labeled-edge",
         {**base_nodes, "zeta://module/zeta": {
             "kind": "edge", "node_type": "module", "id": "zeta://module/zeta",
             "dotted": "zeta"}},
         base_edges),
        ("node-missing-kind",
         {**base_nodes, "zeta://module/zeta": {
             "node_type": "module", "id": "zeta://module/zeta",
             "dotted": "zeta"}},
         base_edges),
        ("edge-labeled-node",
         base_nodes,
         base_edges + [{"kind": "node", "edge_type": "calls",
                        "src": "alpha://module/alpha",
                        "dst": "beta://module/beta"}]),
    ]:
        graph = tmp_path / f"graph_{tag}"
        _write_shard(graph, nodes, edges)
        out = tmp_path / f"out_{tag}"
        rc = cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)])
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert rc == 2, f"{tag}: a kind-mismatched record was published"
        assert "FANOUT REFUSED:" in combined and "malformed" in combined, tag
        assert "Traceback" not in combined, tag
        assert not out.exists(), tag

    graph = tmp_path / "graph_kind_correct"
    _write_shard(graph, base_nodes, base_edges)
    out = tmp_path / "out_kind_correct"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()


def test_fanout_retires_legacy_reserved_case_alias(tmp_path, capsys):
    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    legacy = out / "toc.md"
    legacy.write_bytes(b"# legacy lowercase toc section from an older producer\n")
    assert not legacy.samefile(out / "TOC.md"), (
        "probe needs a case-sensitive seat: toc.md must be a distinct file")
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    assert not (out / "toc.md").exists(), "legacy reserved-name alias survived"
    assert (out / "TOC.md").read_text(encoding="utf-8").startswith("# Fan-out TOC")
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    disk_md = {p.name for p in out.iterdir() if p.name.endswith(".md")}
    assert disk_md == set(receipt["outputs"])
    assert len({n.casefold() for n in disk_md}) == len(disk_md)


def test_fanout_symlinked_output_entry_never_redirects_bytes(tmp_path, capsys):
    import hashlib

    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])

    sentinel_toc = tmp_path / "sentinel_toc.txt"
    sentinel_alpha = tmp_path / "sentinel_alpha.txt"
    sentinel_tmp = tmp_path / "sentinel_tmp.txt"
    for s in (sentinel_toc, sentinel_alpha, sentinel_tmp):
        s.write_bytes(b"outside --out; the compiler must never write here\n")

    out = tmp_path / "out"
    out.mkdir()
    (out / "TOC.md").symlink_to(sentinel_toc)
    (out / "alpha.md").symlink_to(sentinel_alpha)
    (out / "receipt.json.tmp").symlink_to(sentinel_tmp)
    assert (out / "TOC.md").is_symlink() and (out / "alpha.md").is_symlink(), (
        "probe setup: the hostile entries must exist before the publish")

    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    for s in (sentinel_toc, sentinel_alpha, sentinel_tmp):
        assert s.read_bytes() == b"outside --out; the compiler must never write here\n", (
            f"compiler bytes escaped --out into {s.name}")
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    for rel in ("TOC.md", "alpha.md"):
        p = out / rel
        assert not p.is_symlink() and p.is_file(), f"{rel} is still a redirected entry"
        on_disk = hashlib.sha256(p.read_bytes()).hexdigest()
        assert on_disk == receipt["outputs"][rel]


def test_fanout_reader_protocol_detects_torn_generation(tmp_path, capsys, monkeypatch):
    import pytest

    nodes_v1 = {"alpha://module/alpha": {
        "kind": "node", "node_type": "module", "id": "alpha://module/alpha",
        "dotted": "alpha"}}
    nodes_v2 = {**nodes_v1, "alpha://func/alpha.util": {
        "kind": "node", "node_type": "func", "id": "alpha://func/alpha.util",
        "dotted": "alpha.util"}}
    graph_v1 = tmp_path / "graph_v1"
    graph_v2 = tmp_path / "graph_v2"
    _write_shard(graph_v1, nodes_v1, [])
    _write_shard(graph_v2, nodes_v2, [])
    out = tmp_path / "out"

    import graphy.fanout as fanout_mod

    assert cli.main(["fanout", "--graph-dir", str(graph_v1), "--out", str(out)]) == 0
    capsys.readouterr()
    pinned = (out / "receipt.json").read_bytes()
    toc_a = (out / "TOC.md").read_bytes()

    assert cli.main(["fanout", "--graph-dir", str(graph_v2), "--out", str(out)]) == 0
    capsys.readouterr()
    section_b = (out / "alpha.md").read_bytes()

    assert cli.main(["fanout", "--graph-dir", str(graph_v1), "--out", str(out)]) == 0
    capsys.readouterr()

    with pytest.raises(ValueError, match="ABA"):
        fanout_mod.verify_fanout(out, receipt_bytes=pinned)

    tear = fanout_mod.verify_fanout(
        out, receipt_bytes=pinned,
        read_set={"TOC.md": toc_a, "alpha.md": section_b})
    assert tear["status"] == "IN-FLIGHT", "the ABA-hidden tear went undetected"
    assert any("alpha.md" in m for m in tear["mismatched"]), tear["mismatched"]

    coherent = fanout_mod.verify_fanout(
        out, receipt_bytes=pinned,
        read_set={"TOC.md": toc_a, "alpha.md": (out / "alpha.md").read_bytes()})
    assert coherent["status"] == "COHERENT", coherent
    assert cli.main(["fanout", "--verify", "--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert "FANOUT VERIFY: COHERENT" in captured.out + captured.err

    hostile_dir = tmp_path / "hostile"
    hostile_dir.mkdir()
    (hostile_dir / "receipt.json").write_text('{"outputs": {}}\n', encoding="utf-8")
    empty_receipt = fanout_mod.verify_fanout(hostile_dir)
    assert empty_receipt["status"] == "INCOMPLETE", empty_receipt
    assert cli.main(["fanout", "--verify", "--out", str(hostile_dir)]) == 1
    captured = capsys.readouterr()
    assert "INCOMPLETE" in captured.out + captured.err
    empty_reads = fanout_mod.verify_fanout(out, receipt_bytes=pinned, read_set={})
    assert empty_reads["status"] == "INCOMPLETE", empty_reads

    hostile = json.dumps({"outputs": {"../victim.txt": "00"}}).encode("utf-8")
    verdict = fanout_mod.verify_fanout(out, receipt_bytes=hostile,
                                       read_set={"TOC.md": toc_a})
    assert verdict["status"] == "INCOMPLETE"
    assert "foreign receipt shape" in verdict["detail"]

    out2 = tmp_path / "out2"
    real_write = Path.write_bytes
    armed = {"on": True}

    def _crash_before_receipt(self, data):
        if armed["on"] and self.name == "receipt.json.tmp":
            raise OSError("forced crash before the receipt")
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", _crash_before_receipt)
    assert cli.main(["fanout", "--graph-dir", str(graph_v1), "--out", str(out2)]) == 2
    capsys.readouterr()
    armed["on"] = False
    incomplete = fanout_mod.verify_fanout(out2)
    assert incomplete["status"] == "INCOMPLETE", incomplete
    assert cli.main(["fanout", "--verify", "--out", str(out2)]) == 1
    captured = capsys.readouterr()
    assert "INCOMPLETE" in captured.out + captured.err


def test_fanout_verify_refuses_noncompiler_receipts(tmp_path, capsys):
    import hashlib

    import graphy.fanout as fanout_mod

    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()
    real_receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    toc_bytes = (out / "TOC.md").read_bytes()

    foreign_dir = tmp_path / "foreign"
    foreign_dir.mkdir()
    payload = b"# not a compiler artifact\n"
    (foreign_dir / "foreign.md").write_bytes(payload)
    (foreign_dir / "receipt.json").write_text(json.dumps(
        {"outputs": {"foreign.md": hashlib.sha256(payload).hexdigest()}}),
        encoding="utf-8")
    verdict = fanout_mod.verify_fanout(foreign_dir)
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "foreign receipt shape" in verdict["detail"]
    assert cli.main(["fanout", "--verify", "--out", str(foreign_dir)]) == 1
    captured = capsys.readouterr()
    assert "INCOMPLETE" in captured.out + captured.err

    smuggled = dict(real_receipt["outputs"])
    smuggled["../outside.md"] = "00" * 32
    hostile = json.dumps({"input": real_receipt["input"],
                          "groups": real_receipt["groups"],
                          "outputs": smuggled}).encode("utf-8")
    verdict = fanout_mod.verify_fanout(out, receipt_bytes=hostile,
                                       read_set={"TOC.md": toc_bytes})
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "foreign receipt shape" in verdict["detail"]

    for tag, mutate in [
        ("missing-input", lambda r: {k: v for k, v in r.items() if k != "input"}),
        ("bad-digest", lambda r: {**r, "outputs": {**r["outputs"], "TOC.md": "xyz"}}),
        ("case-alias", lambda r: {**r, "outputs": {**r["outputs"],
                                                   "ALPHA.md": r["outputs"]["alpha.md"]}}),
        ("count-break", lambda r: {**r, "groups": {**r["groups"],
                                                   "ghost": {"nodes": 0, "edges": 0}}}),
    ]:
        verdict = fanout_mod.verify_fanout(
            out, receipt_bytes=json.dumps(mutate(real_receipt)).encode("utf-8"),
            read_set={"TOC.md": toc_bytes})
        assert verdict["status"] == "INCOMPLETE", f"{tag}: {verdict}"

    foreign_sub = {**real_receipt,
                   "outputs": {"TOC.md": real_receipt["outputs"]["TOC.md"],
                               "foreign.md": real_receipt["outputs"]["alpha.md"]}}
    verdict = fanout_mod.verify_fanout(
        out, receipt_bytes=json.dumps(foreign_sub).encode("utf-8"),
        read_set={"TOC.md": toc_bytes})
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "foreign receipt shape" in verdict["detail"]

    assert fanout_mod.verify_fanout(out)["status"] == "COHERENT"
    toc_group_nodes = {"toc://module/TOC": {
        "kind": "node", "node_type": "module", "id": "toc://module/TOC",
        "dotted": "TOC.intro"}}
    graph_toc = tmp_path / "graph_toc"
    _write_shard(graph_toc, toc_group_nodes, [])
    out_toc = tmp_path / "out_toc"
    assert cli.main(["fanout", "--graph-dir", str(graph_toc), "--out", str(out_toc)]) == 0
    capsys.readouterr()
    assert fanout_mod.verify_fanout(out_toc)["status"] == "COHERENT"


def test_fanout_verify_contains_post_open_errors(tmp_path, capsys, monkeypatch):
    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    import errno as errno_mod

    import graphy.fanout as fanout_mod

    real_set_blocking = os.set_blocking
    calls = {"n": 0, "fail_at": 1}

    def _eio_set_blocking(fd, blocking):
        calls["n"] += 1
        if calls["n"] >= calls["fail_at"]:
            raise OSError(errno_mod.EIO, "forced post-open I/O error")
        return real_set_blocking(fd, blocking)

    monkeypatch.setattr(os, "set_blocking", _eio_set_blocking)

    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "unreadable after open" in verdict["detail"]
    assert cli.main(["fanout", "--verify", "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    assert "unreadable after open" in captured.out + captured.err

    calls["n"], calls["fail_at"] = 0, 2
    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] == "IN-FLIGHT", verdict
    assert any("unreadable after open" in m for m in verdict["mismatched"])

    calls["fail_at"] = 10**9
    real_fstat, real_close = os.fstat, os.close
    state = {"fd": None, "close_raised": False, "armed": True}

    def _eio_fstat(fd):
        if state["armed"]:
            state["fd"] = fd
            raise OSError(errno_mod.EIO, "forced fstat EIO")
        return real_fstat(fd)

    def _eio_close(fd):
        if state["armed"] and fd == state["fd"] and not state["close_raised"]:
            state["close_raised"] = True
            real_close(fd)
            raise OSError(errno_mod.EIO, "forced close EIO")
        return real_close(fd)

    monkeypatch.setattr(os, "fstat", _eio_fstat)
    monkeypatch.setattr(os, "close", _eio_close)
    verdict = fanout_mod.verify_fanout(out)
    assert state["close_raised"], "the probe never exercised the cleanup path"
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "unreadable after open" in verdict["detail"], (
        "the cleanup error overrode the classified flaw")
    state["armed"] = True
    state["fd"] = None
    state["close_raised"] = False
    assert cli.main(["fanout", "--verify", "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err

    state["armed"] = False
    calls["n"] = 0
    real_fdopen = os.fdopen
    dual = {"armed": True, "close_raised": False}

    class _DualFailWrapper:
        def __init__(self, real):
            self._real = real

        def read(self):
            raise OSError(errno_mod.EIO, "forced read EIO")

        def close(self):
            self._real.close()
            dual["close_raised"] = True
            raise OSError(errno_mod.ENOSPC, "forced wrapper-close ENOSPC")

    def _dual_fdopen(fd, *args, **kwargs):
        real = real_fdopen(fd, *args, **kwargs)
        if dual["armed"]:
            return _DualFailWrapper(real)
        return real

    monkeypatch.setattr(os, "fdopen", _dual_fdopen)
    verdict = fanout_mod.verify_fanout(out)
    assert dual["close_raised"], "the probe never exercised the wrapper close"
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "errno 5" in verdict["detail"], (
        f"the cleanup errno overrode the operational failure: {verdict['detail']}")

    class _CloseOnlyFail(_DualFailWrapper):
        def read(self):
            return self._real.read()

    def _close_fail_fdopen(fd, *args, **kwargs):
        real = real_fdopen(fd, *args, **kwargs)
        if dual["armed"]:
            return _CloseOnlyFail(real)
        return real

    monkeypatch.setattr(os, "fdopen", _close_fail_fdopen)
    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "descriptor cleanup failed" in verdict["detail"], verdict

    dual["armed"] = False
    assert fanout_mod.verify_fanout(out)["status"] == "COHERENT"


def test_fanout_verify_never_follows_redirected_entries(tmp_path, capsys):
    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    import graphy.fanout as fanout_mod

    outside_copy = tmp_path / "outside_alpha.md"
    outside_copy.write_bytes((out / "alpha.md").read_bytes())
    (out / "alpha.md").unlink()
    (out / "alpha.md").symlink_to(outside_copy)
    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] != "COHERENT", "a redirected entry certified green"
    assert any("alpha.md" in m and "redirected" in m
               for m in verdict["mismatched"]), verdict
    assert cli.main(["fanout", "--verify", "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert "redirected" in captured.out + captured.err

    (out / "alpha.md").unlink()
    os.mkfifo(out / "alpha.md")
    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] != "COHERENT"
    assert any("alpha.md" in m and "regular" in m
               for m in verdict["mismatched"]), verdict

    (out / "alpha.md").unlink()
    receipt_copy = tmp_path / "outside_receipt.json"
    receipt_copy.write_bytes((out / "receipt.json").read_bytes())
    (out / "receipt.json").unlink()
    (out / "receipt.json").symlink_to(receipt_copy)
    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] == "INCOMPLETE", verdict
    assert "redirected" in verdict["detail"]

    (out / "receipt.json").unlink()
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()
    assert fanout_mod.verify_fanout(out)["status"] == "COHERENT"


def test_fanout_verify_fallback_branch_is_race_safe(tmp_path, capsys, monkeypatch):
    nodes, _ = _two_group_shard()
    alpha_only = {k: v for k, v in nodes.items() if k.startswith("alpha")}
    graph = tmp_path / "graph"
    _write_shard(graph, alpha_only, [])
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    capsys.readouterr()

    import graphy.fanout as fanout_mod

    outside = tmp_path / "outside.md"
    outside.write_bytes((out / "alpha.md").read_bytes())
    (out / "alpha.md").unlink()
    (out / "alpha.md").symlink_to(outside)

    monkeypatch.setattr(fanout_mod.os, "O_NOFOLLOW", 0)
    verdict = fanout_mod.verify_fanout(out)
    assert verdict["status"] != "COHERENT", (
        "the forced-fallback branch certified a redirected entry")
    assert any("alpha.md" in m and ("redirected" in m or "replaced" in m)
               for m in verdict["mismatched"]), verdict

    (out / "alpha.md").unlink()
    (out / "alpha.md").write_bytes(outside.read_bytes())
    assert fanout_mod.verify_fanout(out)["status"] == "COHERENT"


def test_fanout_no_type_vocabulary(tmp_path, capsys):
    nodes = {
        "alpha://module/alpha": {
            "kind": "node", "node_type": "module", "id": "alpha://module/alpha",
            "dotted": "alpha",
        },
        "alpha://widget/alpha.sparkle": {
            "kind": "node", "node_type": "sparkle", "id": "alpha://widget/alpha.sparkle",
            "dotted": "alpha.sparkle", "file": "alpha/sparkle.py",
        },
    }
    graph = tmp_path / "graph"
    _write_shard(graph, nodes, [])
    out = tmp_path / "out"
    rc = cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert rc == 0
    assert "FANOUT OK:" in combined
    assert "Traceback" not in combined

    section = (out / "alpha.md").read_text(encoding="utf-8")
    assert "sparkle" in section
    assert "node_type=sparkle" in section


# ── the cut: a single package partitioned into its pillars (issue 9) ──────────

FASTAPI_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fastapi_graph"
FASTAPI_PARTITION = Path(__file__).resolve().parent.parent / "tenants" / "fastapi" / "partition.json"


def _receipt(out_dir: Path) -> dict:
    return json.loads((out_dir / "receipt.json").read_text(encoding="utf-8"))


def test_fanout_partition_cuts_fastapi_into_its_pillars(tmp_path, capsys):
    """One package, four named pillars and the edge — the counts the tenant's walk reports."""
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(FASTAPI_FIXTURE), "--out", str(out),
                     "--partition", str(FASTAPI_PARTITION)]) == 0
    line = capsys.readouterr().out
    assert "FANOUT OK: 5 group(s) by partition" in line, line
    receipt = _receipt(out)
    assert set(receipt["groups"]) == {"ROUTING", "DEPENDENCIES", "COMPAT", "OPENAPI", "EDGE"}
    assert receipt["cut"]["kind"] == "partition"
    assert receipt["cut"]["sha256"] == hashlib.sha256(FASTAPI_PARTITION.read_bytes()).hexdigest()
    assert receipt["cut"]["rest"] == "EDGE"
    nodes = json.loads((FASTAPI_FIXTURE / "nodes.json").read_text(encoding="utf-8"))
    edges = json.loads((FASTAPI_FIXTURE / "edges.json").read_text(encoding="utf-8"))
    nodes = nodes if isinstance(nodes, dict) else {n["id"]: n for n in nodes}
    assert sum(g["nodes"] for g in receipt["groups"].values()) == len(nodes)
    assert sum(g["edges"] for g in receipt["groups"].values()) == len(edges)
    # every node of a routing module is in ROUTING, none of a dependencies module is
    routing_ids = {nid for nid, n in nodes.items()
                   if str(n.get("dotted", "")).split(".")[:2] in (["fastapi", "routing"],
                                                                   ["fastapi", "applications"],
                                                                   ["fastapi", "sse"])}
    section = (out / "ROUTING.md").read_text(encoding="utf-8")
    assert all(f"- {nid}  (" in section for nid in routing_ids)
    assert receipt["groups"]["ROUTING"]["nodes"] == len(routing_ids)
    assert "fastapi://func/fastapi.dependencies.utils.solve_dependencies" not in section
    assert "prefixes: fastapi.routing · fastapi.applications · fastapi.sse" in section
    assert cli.main(["fanout", "--verify", "--out", str(out)]) == 0
    assert "COHERENT" in capsys.readouterr().out
    # the default cut still says what the issue said: one group
    one = tmp_path / "one"
    assert cli.main(["fanout", "--graph-dir", str(FASTAPI_FIXTURE), "--out", str(one)]) == 0
    assert set(_receipt(one)["groups"]) == {"fastapi"}
    assert _receipt(one)["cut"] == {"kind": "depth", "depth": 1}


def test_fanout_depth_cut_on_fastapi(tmp_path, capsys):
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(FASTAPI_FIXTURE), "--out", str(out),
                     "--depth", "2"]) == 0
    receipt = _receipt(out)
    assert receipt["cut"] == {"kind": "depth", "depth": 2}
    assert {"fastapi.routing", "fastapi.openapi", "fastapi._compat", "fastapi"} <= set(receipt["groups"])
    assert len(receipt["groups"]) > 20
    assert (out / "fastapi.routing.md").is_file()


def test_fanout_partition_on_a_second_producer(tmp_path, capsys):
    """The outline producer's dotted paths (`outline.<doc>.<slug>`) cut the same way."""
    from graphy.adapters.outline import build_ir
    corpus = Path(__file__).resolve().parent / "fixtures" / "lightning_corpus"
    nodes: dict = {}
    edges: list = []
    for doc in ("transcript.md", "doctrine.md"):
        n, e = build_ir(corpus / doc)
        nodes.update(n)
        edges.extend(e)
    assert len({n["dotted"].split(".")[1] for n in nodes.values()}) == 2
    graph = tmp_path / "graph"
    _write_shard(graph, nodes, edges)

    by_depth = tmp_path / "depth"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(by_depth), "--depth", "2"]) == 0
    assert set(_receipt(by_depth)["groups"]) == {"outline.transcript", "outline.doctrine"}
    assert sum(g["nodes"] for g in _receipt(by_depth)["groups"].values()) == len(nodes)

    partition = tmp_path / "partition.json"
    partition.write_text(json.dumps({
        "groups": {"TALK": ["outline.transcript"]}, "rest": "LAW"}), encoding="utf-8")
    by_part = tmp_path / "part"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(by_part),
                     "--partition", str(partition)]) == 0
    receipt = _receipt(by_part)
    assert set(receipt["groups"]) == {"TALK", "LAW"}
    assert receipt["groups"]["TALK"]["nodes"] == _receipt(by_depth)["groups"]["outline.transcript"]["nodes"]
    assert receipt["groups"]["LAW"]["nodes"] == _receipt(by_depth)["groups"]["outline.doctrine"]["nodes"]
    assert receipt["cut"]["sha256"] == hashlib.sha256(partition.read_bytes()).hexdigest()
    assert cli.main(["fanout", "--verify", "--out", str(by_part)]) == 0

    # a rerun under the same partition is byte-identical
    again = tmp_path / "again"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(again),
                     "--partition", str(partition)]) == 0
    assert _emitted_files(again) == _emitted_files(by_part)


def test_fanout_partition_longest_prefix_wins_at_segment_boundaries(tmp_path):
    from graphy.fanout import Cut, load_partition
    partition = tmp_path / "p.json"
    partition.write_text(json.dumps({"groups": {
        "A": ["pkg.a"], "AB": ["pkg.a.b"], "R": ["pkg.routing"]}}), encoding="utf-8")
    cut = load_partition(partition)
    assert cut.group_of("pkg.a.x") == "A"
    assert cut.group_of("pkg.a.b.Y.z") == "AB"
    assert cut.group_of("pkg.a") == "A"
    assert cut.group_of("pkg.routingx") == "(unpartitioned)"   # a segment boundary, not a string prefix
    assert cut.group_of("other") == "(unpartitioned)"
    assert Cut(depth=2).group_of("pkg.a.b.c") == "pkg.a"
    assert Cut(depth=5).group_of("pkg.a") == "pkg.a"


def test_fanout_partition_refusals(tmp_path, capsys):
    from graphy.fanout import FanoutError, load_partition
    import pytest
    cases = {
        "double-claim": {"groups": {"A": ["pkg.a"], "B": ["pkg.a"]}},
        "rest-collides": {"groups": {"A": ["pkg.a"]}, "rest": "A"},
        "empty-group": {"groups": {"A": []}},
        "no-groups": {"rest": "X"},
        "not-dotted": {"groups": {"A": ["pkg/a"]}},
    }
    for tag, doc in cases.items():
        p = tmp_path / f"{tag}.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(FanoutError):
            load_partition(p)
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(FanoutError):
        load_partition(bad)
    graph = tmp_path / "graph"
    _write_shard(graph, *_two_group_shard())
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out),
                     "--partition", str(bad)]) == 2
    assert "FANOUT REFUSED" in capsys.readouterr().err
    assert not (out / "receipt.json").exists()
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out),
                     "--partition", str(bad), "--depth", "2"]) == 2
    assert "two cuts" in capsys.readouterr().err
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out), "--depth", "0"]) == 2


def test_fanout_verify_pins_the_cut(tmp_path, capsys):
    import graphy.fanout as fanout_mod
    graph = tmp_path / "graph"
    _write_shard(graph, *_two_group_shard())
    out = tmp_path / "out"
    assert cli.main(["fanout", "--graph-dir", str(graph), "--out", str(out)]) == 0
    real = _receipt(out)
    toc = (out / "TOC.md").read_bytes()
    for tag, mutate in [
        ("no-cut", lambda r: {k: v for k, v in r.items() if k != "cut"}),
        ("bad-kind", lambda r: {**r, "cut": {"kind": "magic"}}),
        ("bad-depth", lambda r: {**r, "cut": {"kind": "depth", "depth": 0}}),
        ("bare-partition", lambda r: {**r, "cut": {"kind": "partition"}}),
    ]:
        verdict = fanout_mod.verify_fanout(
            out, receipt_bytes=json.dumps(mutate(real)).encode("utf-8"), read_set={"TOC.md": toc})
        assert verdict["status"] == "INCOMPLETE", f"{tag}: {verdict}"
