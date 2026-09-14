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


def test_GREEN_the_node_modules_slug_map_is_read_once_and_answers_every_scheme(tmp_path, monkeypatch):
    """The ring asks the locator one scheme at a time; it used to scan every node_modules entry per
    ask (86 × 343 on express). The map is built in one pass and cached by path: a scoped package
    is keyed by its ``@scope/name`` specifier, the first directory in sorted order wins a slug, and
    a name with no slug is not an entry (graphyos #29)."""
    from pathlib import Path
    _, nm = _corpus(tmp_path)
    (nm / "@acme" / "tool" / "src").mkdir(parents=True)
    (nm / "@acme" / "tool" / "package.json").write_text(json.dumps({"name": "@acme/tool", "version": "1.0.0"}))
    (nm / ".bin").mkdir()
    (nm / "stray.txt").write_text("not a package")
    smash._NODE_DIRS.clear()
    globs: list[str] = []
    real_glob = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, pat: (globs.append(pat), real_glob(self, pat))[1])
    scoped = smash.slug_for_specifier("@acme/tool")
    asks = ["lib", "dist_only", "no_source", scoped, "absent", "lib"]
    got = [smash.node_dir_for(s, nm) for s in asks]
    assert got == [nm / "lib", nm / "dist-only", nm / "no-source", nm / "@acme" / "tool", None, nm / "lib"]
    assert globs == ["*", "@*/*"], f"the entries were scanned {len(globs) // 2} time(s) for {len(asks)} asks"
    assert ".bin" not in smash.node_dirs_of(nm).values() and all(d.is_dir() for d in smash.node_dirs_of(nm).values())
    files = list(ts.walk_files(nm / "dist-only"))
    assert [f.name for f in files] == ["index.js", "util.js"]


def _component_corpus(tmp_path: Path) -> Path:
    """A SvelteKit-shaped package: a store module, a Svelte component with a module script, a
    commented-out script and a TypeScript generics attribute, a route page beside its +page.ts, and
    a Vue single-file component (graphyos #85)."""
    src = tmp_path / "svapp" / "src"
    (src / "lib" / "components").mkdir(parents=True)
    (src / "routes").mkdir(parents=True)
    (src / "lib" / "stores.ts").write_text(
        "export function loadItems() { return fetch('/items'); }\nexport function saveItem(x: number) { return x; }\n")
    (src / "lib" / "components" / "Carousel.svelte").write_text(
        "<script lang=\"ts\" module>\n  export const shared = 1;\n</script>\n\n"
        "<!-- <script>import nope from './nope';</script> -->\n"
        "<script lang=\"ts\" generics=\"T extends { id: number }\">\n"
        "  import { onMount } from 'svelte';\n  import { loadItems, saveItem } from '../stores';\n"
        "  let activeIndex = $state(0);\n\n  onMount(() => { loadItems(); });\n\n"
        "  function select(i: number) {\n    activeIndex = i;\n    saveItem(i);\n  }\n</script>\n\n"
        "<div on:click={() => select(1)}>{activeIndex}</div>\n<style>.x { color: red }</style>\n")
    (src / "routes" / "+page.ts").write_text("export function load() { return {}; }\n")
    (src / "routes" / "+page.svelte").write_text(
        "<script>\n  import Carousel from '../lib/components/Carousel.svelte';\n</script>\n<Carousel />\n")
    (src / "lib" / "Widget.vue").write_text(
        "<template><div @click=\"go\">x</div></template>\n<script setup lang=\"ts\">\n"
        "import { loadItems } from './stores';\nfunction go() { loadItems(); }\n</script>\n")
    return src


def test_GREEN_single_file_components_are_read_at_their_own_lines(tmp_path):
    """`.svelte` and `.vue` were never opened: the suffix list held only .ts and .js, so three
    quarters of the first client's SvelteKit frontend was invisible (graphyos #85)."""
    src = _component_corpus(tmp_path)
    nodes, edges, _ = ts.mint_records(src, "svapp")
    ids = set(nodes)
    assert "svapp://module/svapp.lib.components.Carousel" in ids
    assert "svapp://module/svapp.lib.Widget" in ids
    # +page.svelte beside +page.ts: both modules stand
    assert {"svapp://module/svapp.routes.+page", "svapp://module/svapp.routes.+page_svelte"} <= ids
    sel = nodes["svapp://func/svapp.lib.components.Carousel.select"]
    assert (sel["line"], sel["file"]) == (13, "src/lib/components/Carousel.svelte")
    assert nodes["svapp://func/svapp.lib.Widget.go"]["line"] == 4
    calls = {(e["src"], e["dst_repr"], e["line"]) for e in edges if e["edge_type"] == "calls"}
    car = "svapp://module/svapp.lib.components.Carousel"
    assert (car, "$state(...)", 9) in calls                       # the rune's declaration, at its line
    assert (car, "loadItems(...)", 11) in calls                   # inside onMount's arrow: the component's own call
    assert ("svapp://func/svapp.lib.components.Carousel.select", "saveItem(...)", 15) in calls
    specs = {e.get("dst") for e in edges if e["edge_type"] == "imports"}
    assert "svapp://module/svapp.lib.components.Carousel" in specs    # './Carousel.svelte' resolves to the component
    assert not any("nope" in str(e.get("dst")) for e in edges), "a script inside an HTML comment is markup"


def test_GREEN_component_names_never_merge_and_markup_scripts_and_plain_top_levels_mint_nothing(tmp_path):
    """Foo.svelte beside Foo.vue are two modules; a `<script>` inside a template expression is markup;
    a plain .ts file's top-level calls are not the module's (only a component's are) (graphyos #85)."""
    src = tmp_path / "app" / "src"
    src.mkdir(parents=True)
    (src / "Foo.svelte").write_text("<script>function fromSvelte() {}</script>\n{@html '<script>evil()</script>'}\n")
    (src / "Foo.vue").write_text("<script setup>\nfunction fromVue() {}\n</script>\n")
    (src / "boot.ts").write_text("init();\nexport function run() {}\n")
    nodes, edges, _ = ts.mint_records(src, "app")
    assert {"app://func/app.Foo_svelte.fromSvelte", "app://func/app.Foo_vue.fromVue"} <= set(nodes)
    calls = {(e["src"], e["dst_repr"]) for e in edges if e["edge_type"] == "calls"}
    assert not any(r == "evil(...)" for _, r in calls), "a script in a template expression is markup"
    assert not any(s == "app://module/app.boot" for s, _ in calls), "a plain module's top level mints no calls"


def test_GREEN_blast_on_a_store_function_returns_the_components_that_call_it(tmp_path):
    from graphy import cli
    src = _component_corpus(tmp_path)
    repo = src.parent
    (repo / "package.json").write_text(json.dumps({"name": "svapp", "version": "0.0.1"}))
    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["blast", "loadItems", "--tenant", str(repo / ".graphy" / "tenant.json"), "--tenant-id", "svapp"])
    out = buf.getvalue()
    assert rc == 0, out
    assert "svapp://module/svapp.lib.components.Carousel" in out
    assert "svapp://func/svapp.lib.Widget.go" in out
    assert "svapp://module/svapp.routes.+page_svelte" in out


def test_GREEN_a_rune_is_state_and_every_write_to_it_is_an_edge_bound_through_scope(tmp_path):
    """`let x = $state(…)` is a `state` node; an assignment, compound assignment or `++` to it is
    `writes` from the function, method or component doing it, bound by the resolver through scope:
    local, `this.` and imports. A parameter or local that shadows the name writes nothing, and a
    plain `let` is no state at all (graphyos #85)."""
    from graphy import cli
    repo = tmp_path / "runes"
    lib = repo / "src" / "lib"
    lib.mkdir(parents=True)
    (repo / "package.json").write_text(json.dumps({"name": "runes", "version": "0.0.1"}))
    (lib / "settings.svelte.ts").write_text(
        "export const settings = $state({ dark: false });\nexport class Counter {\n  count = $state(0);\n"
        "  inc() { this.count++; }\n  reset(count: number) { count = 0; }\n}\n")
    (lib / "Carousel.svelte").write_text(
        "<script lang=\"ts\">\n  import { settings } from './settings.svelte';\n  let activeIndex = $state(0);\n"
        "  let total = 0;\n  $effect(() => { activeIndex = Math.min(activeIndex, 9); });\n"
        "  function select(i: number) {\n    activeIndex = i;\n    total += 1;\n    settings.dark = !settings.dark;\n  }\n"
        "  function shadowed(activeIndex: number) { activeIndex = 3; }\n</script>\n")
    nodes, edges, _ = ts.mint_records(repo / "src", "runes")
    state = {n["id"]: (n["line"], n["rune"]) for n in nodes.values() if n["node_type"] == "state"}
    assert state == {"runes://state/runes.lib.Carousel.activeIndex": (3, "$state"),
                     "runes://state/runes.lib.settings_svelte.settings": (1, "$state"),
                     "runes://state/runes.lib.settings_svelte.Counter.count": (3, "$state")}
    assert validate_graph(nodes, edges, ts.TYPESCRIPT_AST_VOCABULARY) >= 0
    writes = {(e["src"], e["dst_repr"], e["line"]) for e in edges if e["edge_type"] == "writes"}
    assert ("runes://func/runes.lib.Carousel.select", "activeIndex", 7) in writes
    assert ("runes://module/runes.lib.Carousel", "activeIndex", 5) in writes      # inside $effect's arrow
    assert ("runes://method/runes.lib.settings_svelte.Counter.inc", "this.count", 4) in writes
    assert not any(s.endswith((".shadowed", ".reset")) for s, _, _ in writes), "a shadowing parameter writes nothing"

    assert cli.main(["eat", str(repo), "--no-provision"]) == 0
    import io, contextlib
    t = ["--tenant", str(repo / ".graphy" / "tenant.json"), "--tenant-id", "runes"]
    def door(*argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert cli.main(list(argv) + t) == 0
        return buf.getvalue()
    out = door("blast", "Carousel.activeIndex")
    assert "dependents=2" in out and "runes.lib.Carousel.select" in out and "shadowed" not in out
    assert "runes.lib.settings_svelte.Counter.inc" in door("blast", "Counter.count")
    assert "runes://state/runes.lib.settings_svelte.settings" in door("descend", "Carousel.select")   # across the import
    assert "runes.lib.Carousel.select" in door("blast", "settings_svelte.settings")


def test_GREEN_a_write_is_bound_through_lexical_scope_and_destructuring_is_a_write(tmp_path):
    """The adversarial review's specimens (graphyos #85). A block's `let`/`const`, a `for` loop's
    variable and a `catch` parameter shadow a rune for their own subtree only, so writing them is not
    a write to state; a destructuring assignment and a bare `for (x of …)` target are writes."""
    src = tmp_path / "sc" / "src"
    src.mkdir(parents=True)
    (src / "A.svelte").write_text(
        "<script>\n"                                                          # 1
        "  let count = $state(0);\n  let a = $state(1), b = $state(2);\n"      # 2, 3
        "  if (true) { let count = 5; count = 6; }\n"                          # 4  shadowed
        "  for (let count = 0; count < 3; count++) {}\n"                       # 5  shadowed
        "  for (let count of [1]) { count = 9; }\n"                            # 6  shadowed
        "  try {} catch (count) { count = 1; }\n"                              # 7  shadowed
        "  [a, b] = [b, a];\n"                                                 # 8  writes a, b
        "  function h() { for (const count of [1]) {} { let count = 0; } count = 7; }\n"   # 9 writes
        "  function k() { if (a) { let count = 1; count = 2; } }\n"            # 10 shadowed
        "  function t() { ({ count } = { count: 1 }); }\n"                     # 11 writes
        "  function u() { for (count of [1]) {} }\n"                           # 12 writes
        "  function v() { let count; { count = 1; } }\n"                       # 13 shadowed
        "  $effect(() => { [1].forEach((count) => { count++; }); });\n"        # 14 shadowed
        "  const fe = function count() { count = 8; };\n"                     # 15 count is the function
        "</script>\n")
    (src / "t.svelte.ts").write_text(
        "export class T {\n  count = $state(0);\n"
        "  a() { [1].forEach(function () { this.count = 1; }); }\n"              # 3 `this` is not T
        "  b() { const o = { m() { this.count = 2; } }; }\n"                     # 4 `this` is o
        "  c() { [1].forEach(() => { this.count = 3; }); }\n}\n")               # 5 an arrow keeps T
    nodes, edges, _ = ts.mint_records(src, "sc")
    writes = {(e["src"].rsplit(".", 1)[-1], e["dst_repr"], e["line"]) for e in edges if e["edge_type"] == "writes"}
    assert writes == {("A", "a", 8), ("A", "b", 8), ("h", "count", 9), ("t", "count", 11), ("u", "count", 12),
                      ("c", "this.count", 5)}


def test_GREEN_a_function_referenced_as_a_value_mints_a_references_edge_in_typescript_too(tmp_path):
    """The same word from the second producer (graphyos #94): a handler passed to a router, a
    dispatch table, a shorthand property, a namespace member, a decorator's argument, a default, a
    class field and the module's own top level each mint `references`; a callee, a `new`, a
    parameter or local of the same name, a type position, a re-export clause and the function's own
    name mint nothing."""
    from collections import Counter
    src = tmp_path / "tsapp" / "src"
    src.mkdir(parents=True)
    (tmp_path / "tsapp" / "package.json").write_text(json.dumps({"name": "tsapp", "version": "0.0.1"}))
    (src / "helpers.ts").write_text(
        "export function helper(n: number) { return n; }\nexport const arrow = (n: number) => n;\n"
        "export class Svc { static handler = helper; run() { return 1; } }\n")
    (src / "app.ts").write_text(
        "import { helper, Svc } from './helpers';\nimport * as ns from './helpers';\nimport type { Shape } from './types';\n"
        "export function reg(app: any, cb = helper) {\n"                     # 4: the default
        "  app.get('/', helper);\n"                                          # 5: the callback argument
        "  const t = { helper, svc: Svc, alt: ns.arrow };\n"                 # 6: shorthand · table · namespace member
        "  helper(1);\n"                                                     # 7: a call
        "  new Svc();\n"                                                     # 8: a constructor call
        "  const x: typeof helper = helper;\n"                               # 9: the type is skipped, the value read
        "  return t as Routes;\n}\n"
        "export function shadow(helper: any) { return helper; }\n"           # 12: the parameter shadows
        "export function shadow2() { const helper = 1; return helper; }\n"   # 13: the local shadows
        "export const routes = { home: reg };\n"                             # 14: the module's own table
        "app.use(reg);\n"                                                    # 15
        "export { reg, shadow };\n"                                          # 16: a re-export binds, never reads
        "export default shadow2;\n"                                          # 17
        "class K { @dec(helper) m() { return Svc; } }\n"                     # 18: the decorator's argument, a return
        # review round 1 of #94: a lexical shadow at any depth, and a type alias, mint nothing
        "for (const helper of [1, 2]) { Svc(helper); }\n"                    # 19: the loop binds and reads its own
        "type H = typeof helper;\n"                                          # 20: a type
        "export function g() {\n"
        "  try { Svc(1); } catch (helper) { Svc(helper); }\n"                # 22
        "  { const helper = 2; Svc(helper); }\n"                             # 23
        "  for (let helper = 0; helper < 2; helper++) { Svc(helper); }\n"    # 24
        "  const h = (helper: number) => Svc(helper);\n"                     # 25: an arrow is not descended
        "  return helper;\n}\n"                                             # 26: the import, read
        # review round 2 of #94: a chain over a call result is no name — `f(1).prop` is not `f.prop`
        "export function k() { const a = helper(1)?.x; const b = helper(2).x; const c = ns.arrow[0].y; return [a, b, c]; }\n")  # 27
    nodes, edges, _ = ts.mint_records(src, "tsapp")
    refs = Counter((e["src"].rsplit("/", 1)[1], e["dst_repr"], e["line"]) for e in edges if e["edge_type"] == "references")
    assert refs == Counter({
        ("tsapp.app.reg", "helper", 4): 1, ("tsapp.app.reg", "helper", 5): 1,
        ("tsapp.app.reg", "helper", 6): 1, ("tsapp.app.reg", "Svc", 6): 1, ("tsapp.app.reg", "ns.arrow", 6): 1,
        ("tsapp.app.reg", "helper", 9): 1,
        ("tsapp.app", "reg", 14): 1, ("tsapp.app", "reg", 15): 1, ("tsapp.app", "shadow2", 17): 1,
        ("tsapp.app.K.m", "helper", 18): 1, ("tsapp.app.K.m", "Svc", 18): 1,
        ("tsapp.helpers.Svc", "helper", 3): 1,
        ("tsapp.app.g", "helper", 26): 1,
        ("tsapp.app.k", "ns.arrow", 28): 1,     # the subscript's object is read; `helper(…).x` mints nothing but its call
    }), refs
    assert ("tsapp.app.k", "helper.x", 28) not in refs and ("tsapp.app.k", "helper", 28) not in refs
    validate_graph(nodes, edges, ts.TYPESCRIPT_AST_VOCABULARY)
