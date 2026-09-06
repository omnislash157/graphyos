"""The second producer: TypeScript onto the nine words, the ring over node_modules, the resolver's
`this`. A floor, never the proof — the proof is the Hono run in RECON. Skipped by name when
tree-sitter is absent (`pip install 'graphyos[typescript]'`)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_typescript", reason="the typescript_ast producer needs graphyos[typescript]")

import graphy.converge as cv
import graphy.smash as smash
from graphy.adapters import typescript_ast as ts
from graphy.ir import validate_graph


def _corpus(tmp_path: Path) -> tuple[Path, Path]:
    """A package `app` with a class hierarchy, an arrow function, a re-export, a test, an import of a
    sibling package `lib` that ships TypeScript source, and one that ships only dist."""
    root = tmp_path / "app"
    src = root / "src"
    (src / "core").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"name": "@acme/app", "version": "1.2.3", "license": "MIT"}))
    (src / "index.ts").write_text(
        "export { Base, Widget } from './core';\nexport * as helpers from './helpers';\nimport { make } from 'lib';\n"
        "import { readFileSync } from 'node:fs';\nimport dist from 'dist-only';\n"
        "export function boot() { const w = make(); readFileSync('x'); return w; }\n")
    (src / "core" / "index.ts").write_text(
        "import { helper } from '../helpers';\nexport interface Shape { area(): number }\n"
        "export abstract class Base implements Shape { abstract area(): number; describe() { return helper(this.area()); } }\n"
        "export class Widget extends Base { area() { return 1; } describe() { super.describe(); return this.area(); } }\n")
    (src / "helpers.ts").write_text("export const helper = (n: number) => String(n);\nexport function unused() {}\n")
    (src / "core.test.ts").write_text("import { Widget } from './core';\nexport function testIt() { new Widget().area(); }\n")
    nm = tmp_path / "node_modules"
    (nm / "lib" / "src").mkdir(parents=True)
    (nm / "lib" / "package.json").write_text(json.dumps({"name": "lib", "version": "0.9.0", "license": "ISC"}))
    (nm / "lib" / "src" / "index.ts").write_text("export function make() { return 1; }\n")
    (nm / "dist-only" / "dist").mkdir(parents=True)
    (nm / "dist-only" / "package.json").write_text(json.dumps({"name": "dist-only", "version": "2.0.0"}))
    (nm / "dist-only" / "dist" / "index.js").write_text(
        "'use strict';\nvar debug = require('debug')('dist');\nconst { helper: h } = require('./util');\n"
        "const fs = require('node:fs');\nexports.run = require('./util');\n"
        "function dist(n) { return h(n) + fs.readFileSync('x'); }\nmodule.exports = dist;\n")
    (nm / "dist-only" / "dist" / "util.js").write_text("exports.helper = function helper(n) { return n; };\nvar helper2 = function (n) { return n + 1; };\n")
    (nm / "no-source").mkdir(parents=True)
    (nm / "no-source" / "package.json").write_text(json.dumps({"name": "no-source", "version": "1.0.0"}))
    (nm / "no-source" / "data.json").write_text("{}")
    (src / "index.ts").write_text((src / "index.ts").read_text() + "import nothing from 'no-source';\n")
    return src, nm


def test_GREEN_producer_maps_typescript_onto_the_nine_words(tmp_path):
    src, _ = _corpus(tmp_path)
    nodes, edges = ts.build_ir(src, "app")
    validate_graph(nodes, edges, ts.TYPESCRIPT_AST_VOCABULARY)
    ids = set(nodes)
    assert {"app://module/app", "app://module/app.core", "app://module/app.helpers", "app://class/app.core.Shape",
            "app://class/app.core.Base", "app://class/app.core.Widget", "app://method/app.core.Widget.describe",
            "app://func/app.helpers.helper", "app://func/app.boot", "app://module/app.core_test"} <= ids
    assert nodes["app://class/app.core.Shape"]["interface"] and nodes["app://class/app.core.Shape"]["module"] == "app.core"
    assert nodes["app://func/app.core_test.testIt"]["role"] == "test" and "role" not in nodes["app://func/app.boot"]
    inherits = {(e["src"], e["dst_repr"]) for e in edges if e["edge_type"] == "inherits"}
    assert ("app://class/app.core.Base", "Shape") in inherits and ("app://class/app.core.Widget", "Base") in inherits
    imports = {(e["src"], e["dst"], e.get("name")) for e in edges if e["edge_type"] == "imports"}
    assert ("app://module/app", "app://module/app.core", "Base") in imports          # export … from = imports
    assert ("app://module/app", "lib://module/lib", "make") in imports                # a bare specifier is the package literal
    assert ("app://module/app", "fs://module/fs", "readFileSync") in imports          # node:fs → fs, the standard library
    assert ("app://module/app", "dist_only://module/dist_only", "default") in imports
    assert ("app://module/app.core", "app://module/app.helpers", "helper") in imports  # ../helpers resolved
    calls = {(e["src"], e["dst_repr"]) for e in edges if e["edge_type"] == "calls"}
    assert ("app://method/app.core.Widget.describe", "super.describe(...)") in calls
    assert ("app://method/app.core.Widget.describe", "this.area(...)") in calls
    assert ("app://method/app.core.Base.describe", "helper(...)") in calls
    assert ("app://func/app.core_test.testIt", "Widget(...)") in calls              # new X → a call to X


def test_GREEN_ring_follows_node_modules_and_names_dist_only(tmp_path):
    src, nm = _corpus(tmp_path)
    out = tmp_path / "out"
    receipt = smash.smash("app", site_packages=nm, out=out, corpus=src, producer="typescript_ast")
    assert receipt["producer"] == "typescript_ast" and sorted(receipt["minted"]) == ["app", "dist_only", "lib"]
    assert receipt["minted"]["app"]["version"] == "1.2.3" and receipt["minted"]["lib"]["version"] == "0.9.0"
    assert receipt["unresolved"]["no_source"].endswith("ships no TypeScript or JavaScript source")
    assert receipt["unresolved"]["debug"].startswith("not under")                 # required by dist-only, not installed
    assert "fs" in receipt["stdlib"] and "fs" in receipt["standard"]
    prov = json.loads((out / "app_graph" / "PROVENANCE.json").read_text())
    assert prov["producer"]["adapter"] == "typescript_ast" and prov["corpus"]["distribution"] == "@acme/app"
    assert "--producer typescript_ast" in prov["mint_command"]
    # the resolver: this → the containing class, super → the resolved base, an import through a re-export
    ring = cv.load_ring(out, ["app", "lib"])
    side = cv.resolve(ring, "app", write=True)
    by = {(e["src"].rsplit(".", 1)[-1], e["label"]): (e["dst"], e["via"])
          for e in json.loads((out / "app_graph" / cv.WORMHOLE_SIDECAR).read_text())["edges"]}
    assert by[("describe", "this.area(...)")] == ("app://method/app.core.Widget.area", "resolver:self")
    assert by[("describe", "super.describe(...)")] == ("app://method/app.core.Base.describe", "resolver:super")
    assert by[("describe", "helper(...)")] == ("app://func/app.helpers.helper", "resolver:import")
    assert by[("boot", "make(...)")] == ("lib://func/lib.make", "resolver:import")          # across the ring
    assert by[("Widget", "Base")][0] == "app://class/app.core.Base"


def test_GREEN_javascript_and_commonjs_bind_like_imports(tmp_path):
    _, nm = _corpus(tmp_path)
    nodes, edges = ts.build_ir(nm / "dist-only", "dist_only")
    assert {"dist_only://module/dist_only.dist", "dist_only://module/dist_only.dist.util",
            "dist_only://func/dist_only.dist.dist", "dist_only://func/dist_only.dist.util.helper2"} <= set(nodes)
    imports = {(e["dst"], e.get("name"), e.get("alias")) for e in edges if e["edge_type"] == "imports"}
    assert ("debug://module/debug", None, "debug") in imports                        # require('debug')('dist') binds debug
    assert ("dist_only://module/dist_only.dist.util", "helper", "h") in imports        # const { helper: h } = require('./util')
    assert ("fs://module/fs", None, "fs") in imports                                  # node:fs → the standard library
    assert ("dist_only://module/dist_only.dist.util", None, "run") in imports          # exports.run = require('./util')
    calls = {e["dst_repr"] for e in edges if e["edge_type"] == "calls"}
    assert "h(...)" in calls and "fs.readFileSync(...)" in calls and not any(c.startswith("require(") for c in calls)
    assert ts.excludes_for(nm / "dist-only") == ts._SHIPPED_EXCLUDES               # what it ships is read, dist/ included


def test_RED_smash_refuses_an_unknown_producer_and_names_the_extra(tmp_path):
    src, nm = _corpus(tmp_path)
    with pytest.raises(smash.SmashError, match="unknown producer"):
        smash.smash("app", site_packages=nm, out=tmp_path / "o", corpus=src, producer="rust_ast")
    assert ts.slug_of_specifier("@hono/node-server/vercel") == "hono__node_server"
    assert ts.slug_of_specifier("node:fs/promises") == "fs" and ts.slug_of_specifier("../x") is None
