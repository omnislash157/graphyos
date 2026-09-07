"""The seam. A synthetic ring is minted with `smash`, then measured with `converge` and resolved
with `resolve`. Every resolution the tests assert is one the rules can reach structurally: a
local definition, an import, a re-export, self, super. A name no rule reaches stays text."""
from __future__ import annotations

import json
from pathlib import Path

import graphy.cli as cli
from graphy import converge as cv
from graphy import federated_store as fstore
from graphy import smash
from graphy.ir import PYTHON_AST_VOCABULARY
from graphy.native_json_graph_ir import WORMHOLE_SIDECAR, load_graph_ir, validate_shard
from test_smash import _dist


def _site(tmp_path: Path) -> Path:
    sp = tmp_path / "site-packages"
    sp.mkdir()
    alpha = sp / "alpha"
    alpha.mkdir()
    (alpha / "__init__.py").write_text(
        "import os\n"
        "import json as js\n"
        "import beta\n"
        "from gamma import Widget\n"          # a re-export: gamma/__init__ imports Widget from gamma.core
        "from gamma.core import make\n"
        "from typing import cast\n"
        "import nothere\n\n\n"
        "def local_helper(x):\n"
        "    return len(x)\n\n\n"
        "def run(x):\n"
        "    local_helper(x)\n"
        "    beta.helper(x)\n"
        "    js.dumps(x)\n"
        "    make(x)\n"
        "    cast(int, x)\n"
        "    os.path.join(x)\n"
        "    nothere.thing(x)\n"
        "    return x.unknown(x)\n\n\n"
        "class Root(Widget):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.go()\n\n"
        "    def go(self):\n"
        "        return self.go\n", encoding="utf-8")
    (sp / "beta.py").write_text("def helper(x):\n    return x\n", encoding="utf-8")
    gamma = sp / "gamma"
    gamma.mkdir()
    (gamma / "__init__.py").write_text("from .core import Widget, make\n", encoding="utf-8")
    (gamma / "core.py").write_text(
        "class Widget:\n    def __init__(self):\n        pass\n\n\ndef make(x):\n    return Widget()\n",
        encoding="utf-8")
    _dist(sp, "alpha", "1.0", ["alpha/__init__.py"])
    _dist(sp, "beta", "1.0", ["beta.py"])
    _dist(sp, "gamma", "1.0", ["gamma/__init__.py", "gamma/core.py"])
    return sp


def _ring(tmp_path: Path):
    sp = _site(tmp_path)
    home = tmp_path / "home"
    receipt = smash.smash("alpha", site_packages=sp, out=home)
    slugs = sorted(m["slug"] for m in receipt["minted"].values())
    return home, slugs


def test_GREEN_converge_counts_wormholes_per_shard_pair(tmp_path):
    home, slugs = _ring(tmp_path)
    assert slugs == ["alpha", "beta", "gamma"]
    report = cv.converge(cv.load_ring(home, slugs))
    pairs = {(r["from"], r["to"]): r for r in report["pairs"]}
    # alpha's imports edges land on beta and gamma nodes; gamma's re-export lands on gamma.core (own shard: not a pair)
    assert pairs[("alpha", "beta")]["edges"] == 1 and pairs[("alpha", "beta")]["by_type"] == {"imports": 1}
    assert pairs[("alpha", "gamma")]["edges"] == 2 and pairs[("alpha", "gamma")]["nodes"] == 2
    assert ("gamma", "beta") not in pairs and ("beta", "alpha") not in pairs
    assert report["shards"]["alpha"]["labels"] == 13   # len · 8 calls in run · Widget · super · super().__init__ · self.go
    assert report["wormholes"] == 3


def test_GREEN_resolve_walks_scope_not_names(tmp_path):
    home, slugs = _ring(tmp_path)
    ring = cv.load_ring(home, slugs)
    summary = cv.resolve(ring, "alpha", write=True)
    side = json.loads((home / "alpha_graph" / WORMHOLE_SIDECAR).read_text())
    by_label = {(e["src"].rsplit(".", 1)[-1], e["label"]): (e["dst"], e["via"]) for e in side["edges"]}
    assert by_label[("run", "local_helper")] == ("alpha://func/alpha.local_helper", "resolver:local")
    assert by_label[("run", "beta.helper")] == ("beta://func/beta.helper", "resolver:import")
    assert by_label[("run", "make")] == ("gamma://func/gamma.core.make", "resolver:import")
    assert by_label[("__init__", "self.go")] == ("alpha://method/alpha.Root.go", "resolver:self")
    # the base class came through gamma's re-export, and super() stands on it
    assert by_label[("Root", "Widget")] == ("gamma://class/gamma.core.Widget", "resolver:reexport")
    assert by_label[("__init__", "super(...).__init__")] == ("gamma://method/gamma.core.Widget.__init__", "resolver:super")
    left = {(q["label"]): (q["qualified"], q["kind"]) for q in side["qualified"]}
    assert left["js.dumps"] == ("json.dumps", "stdlib")
    assert left["cast"] == ("typing.cast", "stdlib")
    assert left["os.path.join"] == ("os.path.join", "stdlib")
    assert left["nothere.thing"] == ("nothere.thing", "unminted")
    assert summary["unresolved"]["builtin"] == 2          # len, and the bare super() call
    assert summary["unresolved"]["unresolved"] == 1       # x.unknown — a local, no rule reaches it
    assert summary["resolved"] == 6 and summary["cross_shard"] == 4
    assert validate_shard(str(home / "alpha_graph"), PYTHON_AST_VOCABULARY) > 0


def test_GREEN_the_loader_admits_the_sidecar_and_the_store_digest_moves(tmp_path):
    home, slugs = _ring(tmp_path)
    before = len(load_graph_ir(home / "alpha_graph").edges)
    digest_before = fstore._shard_input_digest(home / "alpha_graph")
    cv.resolve(cv.load_ring(home, slugs), "alpha", write=True)
    after = load_graph_ir(home / "alpha_graph").edges
    assert len(after) == before + 6
    assert all(e.get("via", "").startswith("resolver:") for e in after[before:])
    assert fstore._shard_input_digest(home / "alpha_graph") != digest_before, \
        "a store compiled before the sidecar existed must read as stale"
    # a second resolve over the same ring sees the sidecar's edges as edges, not as labels, and is idempotent
    again = cv.resolve(cv.load_ring(home, slugs), "alpha", write=True)
    assert again["resolved"] == 6 and len(load_graph_ir(home / "alpha_graph").edges) == before + 6


def test_GREEN_converge_after_resolve_counts_the_new_wormholes(tmp_path):
    home, slugs = _ring(tmp_path)
    ring = cv.load_ring(home, slugs)
    for s in slugs:
        cv.resolve(ring, s, write=True)
    report = cv.converge(cv.load_ring(home, slugs))
    pairs = {(r["from"], r["to"]): r for r in report["pairs"]}
    assert pairs[("alpha", "beta")]["by_type"] == {"calls": 1, "imports": 1}
    assert pairs[("alpha", "gamma")]["by_type"] == {"calls": 2, "imports": 2, "inherits": 1}


def test_GREEN_the_cli_measures_and_resolves_a_tenant(tmp_path, capsys):
    home, slugs = _ring(tmp_path)
    desc = tmp_path / "tenant.json"
    rc = cli.main(["init", "--tenant", str(desc), "--root", str(tmp_path), "--data-home", str(home),
                   "--join-keys", str(home / "registry.json"), "--journal", str(home / "journal"),
                   "--cursor", "sha256:" + "0" * 64, "--policy", "refuse", "--adapter", "python_ast"]
                  + [f"--lane={s}_graph:static-dep" for s in slugs])
    assert rc == 0
    rc = cli.main(["converge", "--tenant", str(desc), "--tenant-id", "t", "--resolve"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "RESOLVE OK: alpha 13 label(s) -> 6 edge(s)" in out
    assert "CONVERGE: 3 shard(s)" in out and "alpha -> gamma" in out
    assert "RESOLVED: rebuild the store" in out
    assert (home / "gamma_graph" / WORMHOLE_SIDECAR).is_file()


def test_RED_converge_refuses_without_a_tenant(capsys):
    assert cli.main(["converge", "--tenant-id", "t"]) == 2
    assert "CONVERGE REFUSED" in capsys.readouterr().err


def test_GREEN_the_sidecar_carries_the_ring_digest_never_a_clock_and_two_resolves_are_the_same_bytes(tmp_path):
    """The sidecar used to stamp ``resolved_at`` — a wall clock — so no two rebuilds were byte-identical
    on it. It carries ``resolved_over`` now: the digest of every ring shard's nodes.json and edges.json,
    what the resolve is a function of, so two resolves over the same shards write the same bytes and a
    byte moved in any ring shard moves the stamp (graphyos #27)."""
    from graphy.native_json_graph_ir import ring_source_digest
    home, slugs = _ring(tmp_path)
    first = cv.resolve(cv.load_ring(home, slugs), "alpha", write=True)
    sidecar = home / "alpha_graph" / "wormhole_edges.json"
    bytes_one = sidecar.read_bytes()
    assert "resolved_at" not in first and first["resolved_over"] == ring_source_digest(home, slugs)
    assert len(first["resolved_over"]) == 16 and json.loads(bytes_one)["summary"]["resolved_over"] == first["resolved_over"]
    second = cv.resolve(cv.load_ring(home, slugs), "alpha", write=True)
    assert sidecar.read_bytes() == bytes_one and second["resolved_over"] == first["resolved_over"]
    edges = home / "beta_graph" / "edges.json"
    edges.write_bytes(edges.read_bytes().replace(b"\n", b" \n", 1) if b"\n" in edges.read_bytes() else edges.read_bytes() + b" ")
    assert ring_source_digest(home, slugs) != first["resolved_over"], "a byte moved in a ring shard moves the stamp"
