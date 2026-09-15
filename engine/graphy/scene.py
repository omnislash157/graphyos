"""scene — the codebase as a 3D scene, computed from the store: no model places a node.

The partition and its Sugiyama layers place clusters; module membership places symbols within them.
An overview aggregates the declared DEPENDS relations between modules, with a weight for every real
relation. The symbol view keeps containment separate. Size encodes incoming dependencies, paths encode
weight, and inspection names the endpoints. The page loads three.js and 3d-force-graph from jsdelivr,
pinned by version —
the one page the engine emits that fetches, because the wheel cannot carry a WebGL engine (graphyos, 0.2.7).
"""
from __future__ import annotations

import collections
import json
import re

from graphy import sugiyama as S
from graphy.draw import DrawError, pillars
from graphy.pillars import _module_of, relations_for

__all__ = ["scene", "emit_page", "FORCE_GRAPH", "BLOOM"]

FORCE_GRAPH = "https://cdn.jsdelivr.net/npm/3d-force-graph@1.80.0/dist/3d-force-graph.min.js"
BLOOM = "https://cdn.jsdelivr.net/npm/three@0.183.0/examples/jsm/postprocessing/UnrealBloomPass.js/+esm"   # the three 1.80.0 bundles
THREE = "https://cdn.jsdelivr.net/npm/three@0.183.0/+esm"
PALETTE = ("#55dfff", "#ad8bfa", "#ffc878", "#59e3b0", "#ff8ca8", "#7da4ff", "#e8a0ef", "#85dfd3", "#d8df8b", "#ecaa7d")


def scene(store, corpus: str, cut, *, max_nodes: int = 3000) -> dict:
    """A full module overview and a bounded symbol view of one corpus under a partition cut.

    Weights count distinct (source, target, relation) triples, never containment or lexical matches.
    The overview is computed before the symbol cap so it still describes the entire corpus.
    """
    if cut.groups is None:
        raise DrawError("a scene needs a partition cut — the arms are its groups")
    if max_nodes < 1:
        raise DrawError("a scene needs max_nodes >= 1")
    rec_of, arm_of, module_of = {}, {}, {}
    for nid, rec in store.owned(corpus):
        if not rec or rec.get("role") == "test":
            continue
        m = _module_of(rec, nid)
        if m:
            rec_of[nid], arm_of[nid] = rec, cut.group_of(m)
            module_of[nid] = m
    if not rec_of:
        raise DrawError(f"the store owns no module-bearing node for corpus {corpus!r}")
    depends = relations_for(store)
    fan_in: collections.Counter = collections.Counter()
    fan_out: collections.Counter = collections.Counter()
    raw = set()
    for src, dst, rel in store.edges():
        if src in rec_of and dst in rec_of and src != dst:
            if rel in depends or rel == "contains":
                raw.add((src, dst, rel))
    pairs: collections.Counter = collections.Counter()
    module_pairs: collections.Counter = collections.Counter()
    internal: collections.Counter = collections.Counter()
    for src, dst, rel in sorted(raw):
        if rel in depends:
            fan_in[dst] += 1
            fan_out[src] += 1
            pairs[src, dst, "cross" if arm_of[src] != arm_of[dst] else "depends"] += 1
            a, b = module_of[src], module_of[dst]
            if a == b:
                internal[a] += 1
            else:
                module_pairs[a, b] += 1
        else:
            pairs[src, dst, "contains"] += 1
    keep = set(sorted(rec_of, key=lambda n: (-fan_in[n], n))[:max_nodes])
    pic = pillars(store, corpus, cut)
    layer_of = S.layout(pic.nodes, pic.edges, pic.labels).layer_of
    names = sorted(set(arm_of.values()), key=lambda a: (layer_of.get(a, 0), a))
    # the crown orchestrates: depended on AND depending, so a leaf every lane raises (an error class) never wins it
    crowns = {}
    for n in sorted(keep, key=lambda n: (-(fan_in[n] * fan_out[n]), -fan_in[n], n)):
        crowns.setdefault(arm_of[n], n)
    arms = [{"name": a, "color": PALETTE[i % len(PALETTE)], "layer": layer_of.get(a, 0), "crown": crowns.get(a),
             "size": sum(1 for n in rec_of if arm_of[n] == a)} for i, a in enumerate(names)]
    nodes = [{"id": n, "label": rec_of[n].get("dotted") or n, "arm": arm_of[n], "val": 1 + fan_in[n],
              "crown": crowns.get(arm_of[n]) == n, "kind": rec_of[n].get("node_type"),
              "module": module_of[n], "fanIn": fan_in[n], "fanOut": fan_out[n],
              "where": f"{rec_of[n].get('file') or ''}:{rec_of[n].get('line') or ''}".strip(":")} for n in sorted(keep)]
    links = [{"source": s, "target": d, "kind": k, "weight": w}
             for (s, d, k), w in sorted(pairs.items()) if s in keep and d in keep]
    members: dict[str, list] = collections.defaultdict(list)
    for n in sorted(rec_of):
        members[module_of[n]].append(n)
    incoming, outgoing = collections.Counter(), collections.Counter()
    for (a, b), weight in module_pairs.items():
        outgoing[a] += weight
        incoming[b] += weight
    overview_nodes = [{"id": m, "label": m, "module": m, "arm": arm_of[ns[0]], "kind": "module",
                       "size": len(ns), "val": 1 + incoming[m], "fanIn": incoming[m], "fanOut": outgoing[m],
                       "internal": internal[m], "where": next((rec_of[n].get("file") for n in ns if rec_of[n].get("file")), "")}
                      for m, ns in sorted(members.items())]
    module_crowns = {}
    for n in sorted(overview_nodes, key=lambda n: (-(n["fanIn"] * n["fanOut"]), -n["fanIn"], n["id"])):
        module_crowns.setdefault(n["arm"], n["id"])
    for n in overview_nodes:
        n["crown"] = module_crowns[n["arm"]] == n["id"]
    overview_links = [{"source": a, "target": b, "weight": w,
                       "kind": "cross" if arm_of[members[a][0]] != arm_of[members[b][0]] else "depends"}
                      for (a, b), w in sorted(module_pairs.items())]
    return {"title": corpus, "arms": arms, "nodes": nodes, "links": links,
            "overview": {"nodes": overview_nodes, "links": overview_links},
            "counts": {"nodes": len(rec_of), "shown": len(nodes), "links": len(links),
                       "dependencies": sum(fan_in.values()), "modules": len(overview_nodes),
                       "cross": sum(1 for l in links if l["kind"] == "cross")}}


def emit_page(sc: dict, *, generation: str = "", showcase: bool = False) -> str:
    """One HTML page with script-safe inline data and pinned WebGL libraries."""
    data = json.dumps(sc, separators=(",", ":")).replace("<", "\\u003c")
    values = {"__TITLE__": S._esc(sc["title"]), "__FG__": FORCE_GRAPH, "__BLOOM__": BLOOM,
              "__THREE__": THREE, "__GEN__": S._esc(generation), "__DATA__": data,
              "__PAGE_CLASS__": "" if showcase else "standalone", "__BACK__": "index.html" if showcase else "#"}
    # Substitute once: source labels containing a template marker stay literal data.
    return re.sub(r"__(?:TITLE|FG|BLOOM|THREE|GEN|DATA|PAGE_CLASS|BACK)__", lambda m: values[m.group()], _PAGE)


_PAGE = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link
      rel="icon"
      href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E%3Cpath d=%22M8 8L24 24M8 24L24 8%22 stroke=%22%2372e1ec%22 stroke-width=%222%22/%3E%3Cg fill=%22%2372e1ec%22%3E%3Ccircle cx=%228%22 cy=%228%22 r=%224%22/%3E%3Ccircle cx=%228%22 cy=%2224%22 r=%224%22/%3E%3Ccircle cx=%2224%22 cy=%228%22 r=%224%22/%3E%3Ccircle cx=%2224%22 cy=%2224%22 r=%224%22/%3E%3C/g%3E%3C/svg%3E"
    />
    <meta name="color-scheme" content="dark" />
    <meta name="graphy-generation" content="__GEN__" />
    <title>__TITLE__ · Codebase atlas · graphy</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #080c13;
        --panel: #0d121c;
        --line: #ffffff12;
        --muted: #8996aa;
        --text: #e8edf5;
        --accent: #72e1ec;
        --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        --side: 264px;
      }
      .standalone .showcase-link {
        display: none !important;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font:
          13px/1.5 -apple-system,
          BlinkMacSystemFont,
          "Segoe UI",
          sans-serif;
        overflow: hidden;
      }
      button,
      input {
        font: inherit;
      }
      button,
      a,
      input {
        -webkit-tap-highlight-color: transparent;
      }
      button {
        color: inherit;
        cursor: pointer;
      }
      button:disabled {
        cursor: wait;
        opacity: 0.45;
      }
      a {
        color: inherit;
        text-decoration: none;
      }
      button:focus-visible,
      a:focus-visible,
      input:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 4px;
      }
      button {
        border: 0;
      }
      button:hover {
        color: #fff;
      }
      svg {
        display: block;
        flex: none;
      }
      button svg {
        width: 16px;
        height: 16px;
      }
      button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        background: transparent;
      }
      button[aria-pressed="true"] {
        color: var(--accent);
      }
      [hidden] {
        display: none !important;
      }
      header {
        height: 65px;
        position: fixed;
        inset: 0 0 auto;
        z-index: 5;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 26px;
        border-bottom: 1px solid var(--line);
        background: #0a0e17;
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 11px;
        font-size: 21px;
        font-weight: 650;
        letter-spacing: -1px;
      }
      .brand svg {
        color: var(--accent);
        width: 28px;
        height: 28px;
      }
      .brand small {
        margin-left: 17px;
        padding-left: 22px;
        border-left: 1px solid #ffffff20;
        font: 10px var(--mono);
        letter-spacing: 2px;
        color: var(--muted);
      }
      .header-right {
        display: flex;
        align-items: center;
        gap: 22px;
        font-size: 12px;
        color: #b5bfce;
      }
      .header-right a {
        display: flex;
        align-items: center;
        gap: 7px;
      }
      .tag {
        border: 1px solid #72e1ec24;
        background: #72e1ec09;
        color: #a4dfe3;
        border-radius: 5px;
        padding: 4px 8px;
        font: 10px var(--mono);
        letter-spacing: 1px;
      }
      .live {
        display: inline-block;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 8px #72e1ec88;
        margin-right: 6px;
      }
      aside#explorer {
        position: fixed;
        z-index: 4;
        left: 0;
        top: 65px;
        bottom: 0;
        width: var(--side);
        display: flex;
        flex-direction: column;
        border-right: 1px solid var(--line);
        background: linear-gradient(150deg, #101622, #0b1019 65%);
      }
      .sidebar-head {
        padding: 25px 22px 19px;
      }
      .eyebrow {
        font: 10px/1.4 var(--mono);
        letter-spacing: 1.6px;
        color: var(--muted);
        text-transform: uppercase;
      }
      .repo {
        font-size: 20px;
        font-weight: 600;
        letter-spacing: -0.5px;
        margin: 9px 0 3px;
        overflow-wrap: anywhere;
      }
      .repo-note {
        font-size: 11px;
        color: var(--muted);
      }
      .switch {
        display: flex;
        padding: 4px;
        margin: 19px 0 18px;
        background: #060a11;
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .switch button {
        flex: 1;
        padding: 7px 0;
        border-radius: 5px;
        color: var(--muted);
        font-size: 12px;
      }
      .switch button[aria-pressed="true"] {
        background: #202b3b;
        color: #f1f7ff;
        box-shadow: 0 2px 5px #0005;
      }
      .search {
        display: flex;
        align-items: center;
        gap: 8px;
        border: 1px solid #ffffff1b;
        background: #080d16;
        border-radius: 7px;
        padding: 9px 10px;
      }
      .search svg {
        width: 14px;
        height: 14px;
        color: var(--muted);
      }
      .search input {
        min-width: 0;
        width: 100%;
        background: transparent;
        border: 0;
        color: var(--text);
        font-size: 12px;
        outline: 0;
      }
      .search:focus-within {
        border-color: #72e1ec88;
      }
      .search kbd {
        font: 10px var(--mono);
        color: #8592a5;
        border: 1px solid #ffffff25;
        border-radius: 3px;
        padding: 0 4px;
      }
      .sidebar-content {
        padding: 0 14px;
        overflow: auto;
        min-height: 0;
        flex: 1;
        scrollbar-width: thin;
        scrollbar-color: #35435b transparent;
      }
      .section-title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 7px 9px 12px;
      }
      .section-title span {
        font: 10px var(--mono);
        color: #708098;
      }
      .arm {
        width: 100%;
        justify-content: flex-start;
        padding: 9px 10px;
        margin: 2px 0;
        border-radius: 6px;
        color: #a3afc1;
        font-size: 11px;
        text-align: left;
        transition: background 0.15s;
      }
      .arm:hover,
      .result:hover {
        background: #ffffff08;
      }
      .arm[aria-pressed="true"] {
        background: #72e1ec0b;
        color: #eefaff;
      }
      .dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex: none;
        background: var(--arm, var(--accent));
        box-shadow: 0 0 10px color-mix(in srgb, var(--arm, var(--accent)) 50%, transparent);
      }
      .arm .arm-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
      }
      .arm .count {
        font: 10px var(--mono);
        color: #8290a5;
      }
      .arm .bar {
        width: 28px;
        height: 3px;
        background: #ffffff08;
        border-radius: 2px;
        overflow: hidden;
        margin-left: 8px;
      }
      .arm .bar i {
        display: block;
        background: var(--arm);
        height: 100%;
        opacity: 0.65;
      }
      .rank-section {
        border-top: 1px solid var(--line);
        margin-top: 22px;
        padding-top: 18px;
      }
      .result {
        width: 100%;
        display: flex;
        justify-content: flex-start;
        text-align: left;
        border-radius: 6px;
        padding: 9px;
        color: #adb9cc;
        font: 11px var(--mono);
        gap: 10px;
      }
      .result .name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .result .rank {
        color: #526079;
        font-size: 10px;
      }
      .result .count {
        font-size: 10px;
        color: #7d8fa7;
      }
      .empty {
        padding: 10px;
        color: var(--muted);
        font-size: 12px;
      }
      .sidebar-foot {
        padding: 20px 22px 22px;
        margin-top: 12px;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 11px;
      }
      .scale {
        display: flex;
        align-items: center;
        gap: 7px;
        height: 21px;
        margin: 11px 0 4px;
      }
      .scale i {
        display: block;
        background: #8ca9bc;
        border-radius: 50%;
        box-shadow: 0 0 7px #72e1ec33;
      }
      .scale i:nth-child(1) {
        width: 3px;
        height: 3px;
      }
      .scale i:nth-child(2) {
        width: 5px;
        height: 5px;
      }
      .scale i:nth-child(3) {
        width: 8px;
        height: 8px;
      }
      .scale i:nth-child(4) {
        width: 12px;
        height: 12px;
      }
      .scale span {
        height: 1px;
        flex: 1;
        background: linear-gradient(90deg, #44596c, #96bbc4);
        margin-left: 10px;
        transform: skewY(-1deg);
      }
      .foot-note {
        margin-top: 10px;
        font-size: 10px;
        line-height: 1.7;
        color: #687991;
      }
      #stage {
        position: fixed;
        inset: 65px 0 0 var(--side);
        background: radial-gradient(ellipse at 48% 45%, #13203388, transparent 62%), #080c13;
        overflow: hidden;
      }
      #g {
        position: absolute;
        inset: 0;
      }
      #g canvas {
        display: block;
      }
      .scene-head {
        position: absolute;
        z-index: 2;
        top: 31px;
        left: 36px;
        pointer-events: none;
      }
      .scene-head .eyebrow {
        color: #81b4c3;
        display: flex;
        align-items: center;
        gap: 9px;
      }
      .scene-head .eyebrow:before {
        content: "";
        width: 15px;
        height: 1px;
        background: #81b4c3;
      }
      h1 {
        font-weight: 450;
        font-size: clamp(25px, 3vw, 40px);
        line-height: 1.2;
        letter-spacing: -1.4px;
        margin: 9px 0 9px;
      }
      .scene-head p {
        color: var(--muted);
        margin: 0;
        font-size: 12px;
      }
      .stats {
        position: absolute;
        top: 36px;
        right: 32px;
        display: flex;
        gap: 26px;
        z-index: 2;
        pointer-events: none;
      }
      .stat b {
        display: block;
        font: 18px/1.4 var(--mono);
        font-weight: 400;
        letter-spacing: -0.5px;
        color: #d6e1f1;
      }
      .stat span {
        font: 9px var(--mono);
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #7f91a9;
      }
      .view-caption {
        position: absolute;
        left: 36px;
        bottom: 94px;
        z-index: 2;
        pointer-events: none;
        color: #a2b2c9;
        font: 10px var(--mono);
        letter-spacing: 0.4px;
      }
      .view-caption strong {
        font-weight: 400;
        color: #e6edf6;
      }
      .view-caption small {
        display: block;
        color: #697e99;
        margin-top: 6px;
        font-size: 10px;
      }
      .status {
        position: absolute;
        bottom: 24px;
        left: 28px;
        color: #6e829b;
        font: 10px var(--mono);
        z-index: 2;
        pointer-events: none;
        max-width: 30%;
      }
      .toolbar {
        position: absolute;
        bottom: 26px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        gap: 3px;
        padding: 6px;
        background: #101824eb;
        border: 1px solid #ffffff1c;
        box-shadow: 0 10px 40px #0006;
        border-radius: 11px;
        z-index: 3;
        backdrop-filter: blur(16px);
      }
      .toolbar button {
        min-height: 35px;
        padding: 0 11px;
        border-radius: 6px;
        white-space: nowrap;
        font-size: 11px;
        color: #a4b3c9;
      }
      .toolbar button:hover {
        background: #ffffff09;
      }
      .toolbar button[aria-pressed="true"] {
        color: #9ee9ed;
        background: #72e1ec0a;
      }
      .divider {
        width: 1px;
        background: var(--line);
        margin: 5px 4px;
      }
      .orientation {
        position: absolute;
        right: 28px;
        bottom: 22px;
        z-index: 2;
        color: #526780;
        font: 9px var(--mono);
        text-align: center;
      }
      .orientation svg {
        width: 54px;
        height: 54px;
        margin: auto;
      }
      .orientation span {
        letter-spacing: 1.5px;
      }
      .labels {
        position: absolute;
        inset: 0;
        pointer-events: none;
        overflow: hidden;
      }
      .node-label {
        position: absolute;
        font: 10px/1.4 var(--mono);
        white-space: nowrap;
        text-shadow:
          0 1px 6px #000,
          0 0 12px #080c13;
        transform: translate(-50%, 0);
        color: #b2c7de;
        transition: opacity 0.18s;
      }
      .node-label.crown {
        font-size: 11px;
        color: var(--arm);
        font-weight: 600;
      }
      .node-label .label-arm {
        display: block;
        font: 8px/1.5 var(--mono);
        text-transform: uppercase;
        letter-spacing: 1.6px;
        color: #8499ae;
        text-align: center;
        margin-bottom: 3px;
      }
      .tooltip {
        position: absolute;
        z-index: 8;
        pointer-events: none;
        max-width: 290px;
        width: max-content;
        padding: 13px 15px;
        border: 1px solid #6ba4bf40;
        background: #111b29f5;
        border-radius: 8px;
        box-shadow: 0 12px 45px #0008;
        backdrop-filter: blur(12px);
      }
      .tooltip b {
        display: block;
        color: #ecf3ff;
        overflow-wrap: anywhere;
        white-space: normal;
        font: 12px/1.6 var(--mono);
        margin: 4px 0 7px;
      }
      .tooltip .sub {
        font-size: 11px;
        color: #95a9c3;
      }
      .tooltip .tip-foot {
        font-size: 10px;
        color: #617b97;
        margin-top: 9px;
        border-top: 1px solid var(--line);
        padding-top: 7px;
      }
      .tooltip .tip-path {
        overflow-wrap: anywhere;
        font: 10px/1.6 var(--mono);
        color: #8199b5;
        margin-top: 5px;
      }
      #inspector {
        position: absolute;
        top: 144px;
        right: 23px;
        width: 284px;
        max-height: calc(100% - 248px);
        overflow: auto;
        padding: 21px;
        background: #0e1724f5;
        border: 1px solid #ffffff21;
        border-radius: 11px;
        z-index: 4;
        box-shadow: 0 16px 65px #0006;
        backdrop-filter: blur(18px);
        scrollbar-width: thin;
      }
      .close {
        position: absolute;
        right: 12px;
        top: 11px;
        width: 28px;
        height: 28px;
        border-radius: 5px;
        color: #8ca0ba;
      }
      .close:hover {
        background: #ffffff10;
      }
      #inspector h2 {
        font: 14px/1.6 var(--mono);
        overflow-wrap: anywhere;
        margin: 13px 16px 7px 0;
        color: #e5f0ff;
      }
      #inspector .path {
        font: 10px/1.7 var(--mono);
        overflow-wrap: anywhere;
        color: #7e96b3;
      }
      .metrics {
        display: flex;
        gap: 8px;
        margin: 20px 0;
      }
      .metric {
        flex: 1;
        padding: 10px 8px;
        border: 1px solid var(--line);
        border-radius: 5px;
      }
      .metric b {
        display: block;
        font: 18px var(--mono);
        color: #d9edf7;
      }
      .metric span {
        font-size: 9px;
        color: #869bb5;
      }
      .relations-title {
        margin: 18px 0 7px;
        font: 9px var(--mono);
        color: #8da5c0;
        letter-spacing: 1px;
        text-transform: uppercase;
      }
      .relation {
        width: 100%;
        padding: 7px 0;
        justify-content: space-between;
        border-top: 1px solid #ffffff07;
        font: 10px var(--mono);
        text-align: left;
        color: #afc1d7;
      }
      .relation span:first-child {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .relation span:last-child {
        color: #728aa7;
        flex: none;
      }
      .primary {
        width: 100%;
        padding: 9px;
        margin-top: 17px;
        border: 1px solid #72e1ec30;
        background: #72e1ec0b;
        color: #aaeaf0;
        border-radius: 6px;
        font-size: 11px;
      }
      .inspector-note {
        font-size: 10px;
        color: #758ca8;
        margin-top: 13px;
      }
      .loading {
        position: absolute;
        z-index: 6;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 290px;
        padding: 23px;
        background: #101b2df5;
        border: 1px solid #72e1ec25;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 0 100px #4fbbda10;
      }
      .loading strong {
        font-size: 14px;
        font-weight: 500;
      }
      .loading p {
        color: #92a4bd;
        font-size: 12px;
      }
      .loader-mark {
        width: 24px;
        height: 24px;
        border: 1px solid #72e1ec33;
        border-top-color: var(--accent);
        border-radius: 50%;
        margin: 0 auto 15px;
        animation: rotate 1.3s linear infinite;
      }
      @keyframes rotate {
        to {
          transform: rotate(360deg);
        }
      }
      #menu {
        display: none;
      }
      .mobile-hint {
        display: none;
      }
      @media (min-width: 1500px) {
        :root {
          --side: 285px;
        }
        .sidebar-head {
          padding: 30px 26px;
        }
        .sidebar-content {
          padding: 0 18px;
        }
        .scene-head {
          left: 44px;
          top: 38px;
        }
        .stats {
          top: 43px;
        }
      }
      @media (max-width: 1100px) {
        :root {
          --side: 230px;
        }
        .stats {
          top: 139px;
          left: 36px;
          right: auto;
          gap: 20px;
        }
        .stat b {
          font-size: 15px;
        }
        .scene-head {
          top: 25px;
        }
        .sidebar-head {
          padding: 23px 18px 18px;
        }
        .status {
          bottom: 8px;
          left: 20px;
          max-width: 90%;
          font-size: 9px;
        }
        .orientation {
          display: none;
        }
        #inspector {
          top: 200px;
          max-height: calc(100% - 290px);
        }
        .toolbar {
          bottom: 25px;
        }
        .view-caption {
          bottom: 90px;
        }
      }
      @media (max-width: 700px) {
        :root {
          --side: 0px;
        }
        header {
          height: 56px;
          padding: 0 16px;
        }
        .brand {
          font-size: 19px;
        }
        .brand small {
          display: none;
        }
        .brand svg {
          width: 23px;
          height: 23px;
        }
        .header-right {
          gap: 13px;
          font-size: 11px;
        }
        .header-right .tag {
          display: none;
        }
        #stage {
          top: 56px;
        }
        #menu {
          display: flex;
          padding: 4px;
          color: #9caec5;
        }
        aside#explorer {
          top: 56px;
          width: 264px;
          transform: translateX(-100%);
          transition: transform 0.2s;
          box-shadow: 20px 0 50px #0005;
        }
        body.menu-open #explorer {
          transform: translateX(0);
        }
        .scene-head {
          left: 22px;
          top: 23px;
        }
        .scene-head p {
          max-width: 260px;
          font-size: 11px;
        }
        h1 {
          font-size: 29px;
          letter-spacing: -1px;
        }
        .stats {
          left: 22px;
          top: 143px;
          gap: 24px;
        }
        .stat b {
          font-size: 15px;
        }
        .view-caption {
          left: 22px;
          bottom: 94px;
          font-size: 9px;
        }
        .view-caption small {
          font-size: 9px;
          max-width: 280px;
        }
        .toolbar {
          bottom: 28px;
          max-width: calc(100% - 26px);
          padding: 5px;
          gap: 1px;
        }
        .toolbar button {
          padding: 0 8px;
          min-height: 36px;
          font-size: 10px;
          gap: 5px;
        }
        .toolbar button svg {
          width: 14px;
        }
        .toolbar .divider {
          margin: 5px 2px;
        }
        .status {
          left: 22px;
          bottom: 9px;
          font-size: 8px;
        }
        .tooltip {
          max-width: 240px;
        }
        #inspector {
          top: auto;
          bottom: 80px;
          left: 12px;
          right: 12px;
          width: auto;
          max-height: 49%;
          padding: 18px 20px;
        }
        .metrics {
          margin: 12px 0;
        }
        #inspector h2 {
          margin: 8px 0;
        }
        .mobile-hint {
          display: inline;
        }
        .desktop-hint {
          display: none;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        *,
        *:before,
        *:after {
          animation: none !important;
          transition: none !important;
        }
      }
    </style>
  </head>
  <body class="__PAGE_CLASS__">
    <svg style="display: none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <symbol id="icon-search" viewBox="0 0 24 24">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m16 16 5 5" />
        </symbol>
        <symbol id="icon-fit" viewBox="0 0 24 24">
          <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />
          <circle cx="12" cy="12" r="3" />
        </symbol>
        <symbol id="icon-orbit" viewBox="0 0 24 24">
          <ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-35 12 12)" />
          <circle cx="12" cy="12" r="2" />
          <path d="m18 3 2 2-3 1" />
        </symbol>
        <symbol id="icon-glow" viewBox="0 0 24 24">
          <path d="m12 2 2.6 7.4L22 12l-7.4 2.6L12 22l-2.6-7.4L2 12l7.4-2.6Z" />
        </symbol>
        <symbol id="icon-detail" viewBox="0 0 24 24">
          <path d="M4 6h16M4 12h16M4 18h16" />
          <circle cx="9" cy="6" r="2" fill="currentColor" />
          <circle cx="15" cy="12" r="2" fill="currentColor" />
          <circle cx="7" cy="18" r="2" fill="currentColor" />
        </symbol>
        <symbol id="icon-close" viewBox="0 0 24 24"><path d="m6 6 12 12M6 18 18 6" /></symbol>
      </defs>
    </svg>
    <header>
      <a class="brand" href="__BACK__" aria-label="Graphy">
        <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path d="m7 9 9 5 9-7M7 9l1 16 8-11 9 10V7" stroke="currentColor" stroke-width="1.3" />
          <g fill="currentColor">
            <circle cx="7" cy="9" r="3" />
            <circle cx="8" cy="25" r="2.5" />
            <circle cx="16" cy="14" r="3" />
            <circle cx="25" cy="7" r="2.5" />
            <circle cx="25" cy="24" r="3" />
          </g>
        </svg>
        graphy
        <small>CODEBASE ATLAS</small>
      </a>
      <div class="header-right">
        <span class="tag">
          <i class="live"></i>
          3D EXPLORER
        </span>
        <a class="showcase-link" href="index.html">
          2D showcase
          <span aria-hidden="true">↗</span>
        </a>
        <button id="menu" aria-label="Toggle explorer" aria-expanded="false" aria-controls="explorer">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>
    </header>
    <aside id="explorer" aria-label="Graph explorer">
      <div class="sidebar-head">
        <div class="eyebrow">Repository</div>
        <div class="repo">__TITLE__</div>
        <div class="repo-note">Your architecture. Every connection.</div>
        <div class="switch" role="group" aria-label="Graph level">
          <button id="modules" aria-pressed="true" disabled>Modules</button>
          <button id="symbols" aria-pressed="false" disabled>Symbols</button>
        </div>
        <label class="search">
          <svg fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <use href="#icon-search" />
          </svg>
          <input
            id="search"
            type="search"
            placeholder="Find a module…"
            aria-label="Search graph"
            autocomplete="off"
            disabled
          />
          <kbd>/</kbd>
        </label>
      </div>
      <div class="sidebar-content">
        <section id="search-section" hidden>
          <div class="section-title">
            <div class="eyebrow">Search results</div>
            <span id="result-count"></span>
          </div>
          <div id="results"></div>
        </section>
        <section id="arms-section">
          <div class="section-title">
            <div class="eyebrow">Architecture</div>
            <span id="arm-count"></span>
          </div>
          <div id="legend"></div>
        </section>
        <section class="rank-section" id="rank-section">
          <div class="section-title">
            <div class="eyebrow">Most depended on</div>
            <span>IN ↓</span>
          </div>
          <div id="ranking"></div>
        </section>
      </div>
      <div class="sidebar-foot">
        <div class="eyebrow">Read the constellation</div>
        <div class="scale" aria-hidden="true">
          <i></i>
          <i></i>
          <i></i>
          <i></i>
          <span></span>
        </div>
        <div>Size = incoming dependencies</div>
        <div id="weight-key">Thickness = dependency count</div>
        <div class="foot-note">
          Color = partition · ring = cluster anchor.
          <br />
          Every connection comes from the code.
        </div>
      </div>
    </aside>
    <main id="stage" aria-label="Interactive 3D codebase graph">
      <div id="g"></div>
      <div class="scene-head">
        <div class="eyebrow">Explore the structure</div>
        <h1>Architecture, illuminated.</h1>
        <p>Follow the dependencies. Find what holds it together.</p>
      </div>
      <div class="stats" id="stats"></div>
      <div class="labels" id="labels"></div>
      <div id="tooltip" class="tooltip" role="tooltip" hidden></div>
      <section id="inspector" aria-label="Selected node details" hidden></section>
      <div class="view-caption">
        <strong id="view-title">MODULE CONSTELLATION</strong>
        <small id="view-description">Weighted paths reveal the strongest relationships.</small>
      </div>
      <div class="status" id="status" role="status">Preparing the atlas…</div>
      <div class="toolbar" role="group" aria-label="View controls">
        <button id="orbit" aria-pressed="false" title="Toggle automatic orbit and flowing particles" disabled>
          <svg fill="none" stroke="currentColor" stroke-width="1.4"><use href="#icon-orbit" /></svg>
          <span>Motion</span>
        </button>
        <button id="fit" title="Reset focus and fit the graph (R)" disabled>
          <svg fill="none" stroke="currentColor" stroke-width="1.4"><use href="#icon-fit" /></svg>
          <span>Recenter</span>
        </button>
        <span class="divider"></span>
        <button id="glow" aria-pressed="false" title="Toggle bloom" disabled>
          <svg fill="none" stroke="currentColor" stroke-width="1.4"><use href="#icon-glow" /></svg>
          <span>Glow</span>
        </button>
        <button
          id="detail"
          aria-pressed="false"
          title="Show all dependency paths, including containment in Symbols"
          disabled
        >
          <svg fill="none" stroke="currentColor" stroke-width="1.4"><use href="#icon-detail" /></svg>
          <span>All paths</span>
        </button>
      </div>
      <div class="orientation" aria-hidden="true">
        <svg viewBox="0 0 60 60" fill="none">
          <circle cx="30" cy="30" r="22" stroke="#172638" />
          <path d="m30 30 18 9M30 30 12 41M30 30V10" stroke="#51657f" />
          <circle cx="30" cy="30" r="2" fill="#9acbdf" />
          <text x="47" y="47" fill="#648d9d" font-size="8">x</text>
          <text x="28" y="8" fill="#648d9d" font-size="8">y</text>
          <text x="6" y="48" fill="#648d9d" font-size="8">z</text>
        </svg>
        <span>ORBIT VIEW</span>
      </div>
      <div class="loading" id="loading" role="status">
        <div class="loader-mark"></div>
        <strong>Tracing the architecture</strong>
        <p>Preparing your codebase in three dimensions.</p>
      </div>
      <noscript>
        <div class="loading">
          This explorer needs JavaScript and WebGL.
          <p><a class="showcase-link" href="index.html">Open the 2D showcase →</a></p>
        </div>
      </noscript>
    </main>
    <script src="__FG__"></script>
    <script type="module">
      const S = __DATA__;
      const $ = (id) => document.getElementById(id),
        fmt = (n) => Number(n || 0).toLocaleString();
      const esc = (s) =>
        String(s ?? "").replace(
          /[&<>"']/g,
          (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
        );
      const short = (n) => n.label.split(".").slice(-2).join("."),
        idOf = (n) => (typeof n === "object" ? n.id : n);
      const color = new Map(S.arms.map((a) => [a.name, a.color]));
      const tint = (n) => color.get(n.arm) || "#87cfe0";
      const reduced = matchMedia("(prefers-reduced-motion: reduce)");
      let G,
        THREE,
        bloom,
        view = "modules",
        data,
        selected = null,
        hovered = null,
        arm = null,
        search = "",
        detail = false,
        motion = !reduced.matches;
      let adjacent = new Set(),
        edgesByNode = new Map(),
        nodeById = new Map(),
        labelItems = [],
        objects = [],
        frame = 0;
      let sceneRadius = 350,
        pointer = { x: 0, y: 0 },
        flyUntil = 0;
      // Geometry and the glow atlas are shared; each node only owns its material and transform.
      let sphereGeometry, crownGeometry, haloTexture;
      const stage = $("stage"),
        tooltip = $("tooltip");
      function message(text) {
        $("status").textContent = text;
      }
      function fail() {
        const panel = $("loading");
        panel.hidden = false;
        panel.innerHTML =
          '<strong>The 3D view could not load</strong><p>Check your connection and WebGL support, then try again.</p><button class="primary" id="retry">Try again</button><a class="primary showcase-link" href="index.html">Open the 2D showcase →</a>';
        $("retry").onclick = () => location.reload();
        message("3D unavailable · check your connection and WebGL support");
      }
      function activeNode() {
        return hovered || selected;
      }
      function inScope(n) {
        return (!arm || n.arm === arm) && (!search || n.label.toLowerCase().includes(search));
      }
      function intensity(n) {
        const active = activeNode();
        if (active) return n === active ? 1 : adjacent.has(n.id) ? 0.8 : 0.07;
        return inScope(n) ? 1 : 0.08;
      }
      function connected(l, n) {
        return n && (idOf(l.source) === n.id || idOf(l.target) === n.id);
      }
      function visibleLink(l) {
        const a = nodeById.get(idOf(l.source)),
          b = nodeById.get(idOf(l.target));
        if (!a || !b) return false;
        const active = activeNode();
        if (active) return connected(l, active);
        if (arm && a.arm !== arm && b.arm !== arm) return false;
        if (search && !inScope(a) && !inScope(b)) return false;
        return detail || l.major;
      }
      function linkColor(l) {
        const a = nodeById.get(idOf(l.source));
        const opacity = l.kind === "contains" ? 0.12 : activeNode() ? 0.72 : l.major ? 0.38 : 0.09;
        return (
          tint(a) +
          Math.round(opacity * 255)
            .toString(16)
            .padStart(2, "0")
        );
      }
      function linkWidth(l) {
        if (l.kind === "contains") return 0;
        if (activeNode()) return 0.55 + 1.7 * l.strength;
        return l.major ? 0.45 + 2.4 * l.strength : 0;
      }
      function particles(l) {
        return motion && visibleLink(l) && l.kind !== "contains" && (l.major || activeNode())
          ? l.strength > 0.6
            ? 3
            : 1
          : 0;
      }
      function refresh() {
        if (!G) return;
        const active = activeNode();
        adjacent = new Set(
          active ? (edgesByNode.get(active.id) || []).flatMap((l) => [idOf(l.source), idOf(l.target)]) : [],
        );
        for (const item of objects) {
          const v = intensity(item.n);
          item.core.material.opacity = v;
          item.halo.material.opacity = (item.n.crown ? 0.25 : 0.13) * v;
          item.ring && (item.ring.material.opacity = 0.48 * v);
        }
        G.linkVisibility(visibleLink)
          .linkColor(linkColor)
          .linkWidth(linkWidth)
          .linkDirectionalParticles(particles)
          .linkDirectionalArrowLength((l) =>
            !motion && visibleLink(l) && l.kind !== "contains" ? 3 + 3 * l.strength : 0,
          );
        $("orbit").setAttribute("aria-pressed", String(motion));
        $("detail").setAttribute("aria-pressed", String(detail));
        document
          .querySelectorAll(".arm")
          .forEach((e) => e.setAttribute("aria-pressed", String((e.dataset.arm || null) === arm)));
      }
      function hash(s) {
        let h = 2166136261;
        for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
        return (h >>> 0) / 4294967296;
      }
      function position(nodes, level = view) {
        const maxIn = Math.max(1, ...nodes.map((n) => n.fanIn));
        if (level === "symbols") {
          // Keep module centers identical across levels, then open each module into its symbols.
          const parents = S.overview.nodes.map((n) => ({ ...n }));
          position(parents, "modules");
          const centers = new Map(parents.map((n) => [n.id, n]));
          const members = new Map();
          for (const n of nodes) {
            if (!members.has(n.module)) members.set(n.module, []);
            members.get(n.module).push(n);
          }
          for (const [module, items] of members) {
            const home = centers.get(module);
            items.sort((a, b) => b.fanIn - a.fanIn || a.id.localeCompare(b.id));
            for (const [i, n] of items.entries()) {
              const angle = i * 2.399963 + hash(module) * 6.28,
                r = i === 0 ? 0 : 8 + 4.8 * Math.sqrt(i);
              n.x = home.x + Math.cos(angle) * r;
              n.z = home.z + Math.sin(angle) * r;
              n.y = home.y + (hash(n.id) - 0.5) * r * 0.8;
            }
          }
        } else {
          const groups = S.arms
            .map((a) => ({ ...a, members: nodes.filter((n) => n.arm === a.name) }))
            .filter((a) => a.members.length);
          const maxLayer = Math.max(1, ...groups.map((a) => a.layer));
          const ring = groups.length === 1 ? 0 : Math.max(210, 75 * groups.length);
          for (const [i, a] of groups.entries()) {
            const theta = (2 * Math.PI * i) / groups.length - 0.4,
              home = {
                x: ring * Math.cos(theta),
                y: (maxLayer / 2 - a.layer) * 38,
                z: ring * Math.sin(theta) * 0.9,
              };
            a.members.sort(
              (a, b) => Number(b.crown) - Number(a.crown) || b.fanIn - a.fanIn || a.id.localeCompare(b.id),
            );
            for (const [j, n] of a.members.entries()) {
              const angle = j * 2.399963 + hash(a.name) * 6.28,
                r = j === 0 ? 0 : 36 + Math.sqrt(j) * 24;
              n.x = home.x + Math.cos(angle) * r;
              n.z = home.z + Math.sin(angle) * r * 0.7;
              n.y = home.y + (hash(n.module) - 0.5) * 55;
            }
          }
        }
        for (const n of nodes) {
          n.fx = n.x;
          n.fy = n.y;
          n.fz = n.z;
          n.score = Math.log1p(n.fanIn) / Math.log1p(maxIn);
          n.radius = (level === "modules" ? 3 : 1.05) + (level === "modules" ? 10 : 5.5) * n.score;
          if (n.crown) n.radius = Math.max(n.radius, level === "modules" ? 7 : 4);
        }
        sceneRadius = Math.max(130, ...nodes.map((n) => Math.hypot(n.x, n.y, n.z))) + 50;
      }
      function buildData() {
        const source = view === "modules" ? S.overview : S;
        const nodes = source.nodes.map((n) => ({ ...n })),
          links = source.links.map((l) => ({ ...l }));
        nodeById = new Map(nodes.map((n) => [n.id, n]));
        edgesByNode = new Map(nodes.map((n) => [n.id, []]));
        const maxWeight = Math.max(1, ...links.map((l) => l.weight)),
          maxVal = Math.max(1, ...nodes.map((n) => n.val));
        for (const l of links) {
          l.strength =
            view === "modules"
              ? Math.log1p(l.weight) / Math.log1p(maxWeight)
              : Math.sqrt(Math.max(nodeById.get(l.source).val, nodeById.get(l.target).val) / maxVal);
          edgesByNode.get(l.source).push(l);
          edgesByNode.get(l.target).push(l);
        }
        const dependencies = links
          .filter((l) => l.kind !== "contains")
          .sort((a, b) => b.strength - a.strength || idOf(a.source).localeCompare(idOf(b.source)));
        const budget =
          view === "modules"
            ? Math.min(180, Math.max(24, nodes.length * 1.3))
            : Math.min(240, Math.max(35, nodes.length * 0.35));
        const important = new Set(dependencies.slice(0, budget));
        for (const l of links) l.major = important.has(l);
        position(nodes);
        return { nodes, links };
      }
      function makeNode(n) {
        sphereGeometry ||= new THREE.SphereGeometry(1, 10, 8);
        crownGeometry ||= new THREE.IcosahedronGeometry(1, 0);
        const group = new THREE.Group(),
          geometry = n.crown ? crownGeometry : sphereGeometry;
        const core = new THREE.Mesh(
          geometry,
          new THREE.MeshBasicMaterial({ color: tint(n), transparent: true, opacity: 1 }),
        );
        core.scale.setScalar(n.radius);
        group.add(core);
        if (!haloTexture) {
          const canvas = document.createElement("canvas");
          canvas.width = 64;
          canvas.height = 64;
          const ctx = canvas.getContext("2d"),
            gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
          gradient.addColorStop(0, "#ffffff");
          gradient.addColorStop(0.2, "#ffffff80");
          gradient.addColorStop(1, "#ffffff00");
          ctx.fillStyle = gradient;
          ctx.fillRect(0, 0, 64, 64);
          haloTexture = new THREE.CanvasTexture(canvas);
        }
        const halo = new THREE.Sprite(
          new THREE.SpriteMaterial({
            map: haloTexture,
            color: tint(n),
            transparent: true,
            opacity: 0.2,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
          }),
        );
        halo.scale.setScalar(n.radius * (n.crown ? 9 : 6));
        group.add(halo);
        let ring;
        if (n.crown) {
          ring = new THREE.Mesh(
            new THREE.TorusGeometry(n.radius * 1.9, 0.22, 4, 48),
            new THREE.MeshBasicMaterial({
              color: tint(n),
              transparent: true,
              opacity: 0.48,
              depthWrite: false,
            }),
          );
          ring.rotation.x = Math.PI / 2.6;
          group.add(ring);
        }
        objects.push({ n, core, halo, ring });
        return group;
      }
      function labels() {
        const host = $("labels");
        host.replaceChildren();
        const ranked = [...data.nodes].sort((a, b) => Number(b.crown) - Number(a.crown) || b.fanIn - a.fanIn);
        labelItems = ranked.slice(0, view === "modules" ? 40 : 24).map((n) => {
          const el = document.createElement("div");
          el.className = "node-label" + (n.crown ? " crown" : "");
          el.style.setProperty("--arm", tint(n));
          if (n.crown) {
            const armLabel = document.createElement("span");
            armLabel.className = "label-arm";
            armLabel.textContent = n.arm;
            el.appendChild(armLabel);
          }
          el.appendChild(document.createTextNode(short(n)));
          host.appendChild(el);
          return { n, el };
        });
      }
      function fit(animated = true) {
        flyUntil = performance.now() + 900;
        const aspect = stage.clientWidth / stage.clientHeight;
        const distance = sceneRadius * (aspect < 0.8 ? 4.1 : aspect < 1.2 ? 2.8 : 1.95);
        G.cameraPosition(
          { x: distance * 0.12, y: distance * 0.95, z: distance * 0.65 },
          { x: 0, y: -sceneRadius * 0.08, z: 0 },
          animated && !reduced.matches ? 800 : 0,
        );
      }
      function inspect(n) {
        selected = n;
        hovered = null;
        tooltip.hidden = true;
        refresh();
        renderInspector();
        document.body.classList.remove("menu-open");
        $("menu").setAttribute("aria-expanded", "false");
        message("Selected " + n.label + " · Esc to clear");
      }
      function clearSelection() {
        selected = null;
        hovered = null;
        $("inspector").hidden = true;
        tooltip.hidden = true;
        refresh();
        updateCaption();
      }
      function renderInspector() {
        const host = $("inspector");
        host.hidden = !selected;
        if (!selected) return;
        const n = selected;
        host.innerHTML =
          '<button class="close" id="close-inspector" aria-label="Close node details"><svg fill="none" stroke="currentColor" stroke-width="1.5"><use href="#icon-close"/></svg></button><div class="eyebrow" style="color:' +
          tint(n) +
          '">' +
          esc(n.arm) +
          " / " +
          esc(n.kind || "symbol") +
          "</div><h2>" +
          esc(n.label) +
          '</h2><div class="path">' +
          esc(n.where || "Source location unavailable") +
          '</div><div class="metrics"><div class="metric"><b>' +
          fmt(n.fanIn) +
          '</b><span>incoming dependencies</span></div><div class="metric"><b>' +
          fmt(n.fanOut) +
          "</b><span>outgoing dependencies</span></div></div>";
        $("close-inspector").onclick = () => {
          clearSelection();
          $("fit").focus();
        };
        const links = (edgesByNode.get(n.id) || []).filter((l) => l.kind !== "contains");
        for (const [heading, incoming] of [
          ["Depended on by", true],
          ["Depends on", false],
        ]) {
          const list = links
            .filter((l) => idOf(incoming ? l.target : l.source) === n.id)
            .sort((a, b) => b.weight - a.weight);
          const title = document.createElement("div");
          title.className = "relations-title";
          title.textContent = heading + " · " + list.length;
          host.appendChild(title);
          if (!list.length) {
            const none = document.createElement("div");
            none.className = "inspector-note";
            none.textContent = "No connections in this view";
            host.appendChild(none);
          }
          for (const l of list.slice(0, 8)) {
            const other = nodeById.get(idOf(incoming ? l.source : l.target));
            const b = document.createElement("button");
            b.className = "relation";
            b.title = other.label;
            b.innerHTML =
              "<span>" +
              esc(short(other)) +
              "</span><span>" +
              fmt(l.weight) +
              " " +
              (incoming ? "←" : "→") +
              "</span>";
            b.onclick = () => inspect(other);
            host.appendChild(b);
          }
          if (list.length > 8) {
            const more = document.createElement("div");
            more.className = "inspector-note";
            more.textContent = "+" + (list.length - 8) + " more connections highlighted in the graph";
            host.appendChild(more);
          }
        }
        const note = document.createElement("div");
        note.className = "inspector-note";
        note.textContent =
          view === "modules"
            ? fmt(n.size) + " symbols · " + fmt(n.internal) + " internal dependencies"
            : "Counts include the full corpus; paths show loaded symbols.";
        host.appendChild(note);
        if (view === "modules") {
          const drill = document.createElement("button");
          drill.className = "primary";
          drill.textContent = "Explore symbols in this module →";
          drill.onclick = () => {
            const module = n.module;
            switchView("symbols");
            $("search").value = module;
            runSearch(module);
          };
          host.appendChild(drill);
        }
      }
      function showTooltip(n, l) {
        if (!n && !l) {
          tooltip.hidden = true;
          return;
        }
        tooltip.hidden = false;
        if (n)
          tooltip.innerHTML =
            '<div class="eyebrow" style="color:' +
            tint(n) +
            '">' +
            esc(n.arm) +
            " · " +
            esc(n.kind || "symbol") +
            "</div><b>" +
            esc(n.label) +
            '</b><div class="sub">' +
            fmt(n.fanIn) +
            " incoming · " +
            fmt(n.fanOut) +
            ' outgoing</div><div class="tip-path">' +
            esc(n.where) +
            '</div><div class="tip-foot">Click to inspect connections</div>';
        else {
          const a = nodeById.get(idOf(l.source)),
            b = nodeById.get(idOf(l.target));
          tooltip.innerHTML =
            '<div class="eyebrow">' +
            (l.kind === "contains" ? "Containment" : "Dependency path") +
            "</div><b>" +
            esc(short(a)) +
            " → " +
            esc(short(b)) +
            '</b><div class="sub">' +
            fmt(l.weight) +
            " " +
            (l.kind === "contains" ? "containment relationships" : "dependency relationships") +
            '</div><div class="tip-foot">' +
            (l.kind === "contains" ? "Parent → contained symbol" : "Source depends on target") +
            "</div>";
        }
        placeTooltip();
      }
      function placeTooltip() {
        const w = tooltip.offsetWidth,
          h = tooltip.offsetHeight;
        tooltip.style.left = Math.max(8, Math.min(pointer.x + 16, stage.clientWidth - w - 12)) + "px";
        tooltip.style.top = Math.max(8, Math.min(pointer.y + 16, stage.clientHeight - h - 12)) + "px";
      }
      function updateCaption() {
        const count = data.links.filter(visibleLink).length;
        $("weight-key").textContent =
          view === "modules" ? "Thickness = dependency count" : "Thickness = connected hub influence";
        $("view-title").textContent = view === "modules" ? "MODULE CONSTELLATION" : "SYMBOL CONSTELLATION";
        $("view-description").textContent = arm
          ? "Exploring " + arm + " · click a node to trace its dependencies."
          : view === "modules"
            ? "Weighted paths reveal the strongest relationships."
            : "Symbols gather by module. Larger nodes carry more dependents.";
        message(
          fmt(data.nodes.length) +
            " " +
            view +
            " · " +
            fmt(count) +
            " / " +
            fmt(data.links.length) +
            " paths" +
            (view === "symbols" && S.counts.shown < S.counts.nodes
              ? " · " + fmt(S.counts.shown) + " of " + fmt(S.counts.nodes) + " symbols loaded"
              : ""),
        );
      }
      function renderRanking() {
        const nodes = data.nodes
          .filter((n) => !arm || n.arm === arm)
          .sort((a, b) => b.fanIn - a.fanIn || a.id.localeCompare(b.id));
        const host = $("ranking");
        host.replaceChildren();
        nodes.slice(0, 5).forEach((n, i) => host.appendChild(nodeButton(n, i + 1)));
        renderLegend();
      }
      function nodeButton(n, rank) {
        const b = document.createElement("button");
        b.className = "result";
        b.title = n.label;
        b.innerHTML =
          '<span class="rank">' +
          (rank ? String(rank).padStart(2, "0") : "↳") +
          '</span><span class="name">' +
          esc(short(n)) +
          '</span><span class="count">' +
          fmt(n.fanIn) +
          "</span>";
        b.onclick = () => inspect(n);
        return b;
      }
      function renderLegend() {
        const host = $("legend");
        host.replaceChildren();
        const maxSize = Math.max(1, ...S.arms.map((a) => a.size));
        for (const a of [{ name: "All clusters", color: "#91abba", size: S.counts.nodes }, ...S.arms]) {
          const key = host.children.length === 0 ? "" : a.name;
          const b = document.createElement("button");
          b.className = "arm";
          b.dataset.arm = key;
          b.title = fmt(a.size) + " symbols" + (key ? " in " + a.name : " in the codebase");
          b.style.setProperty("--arm", a.color);
          b.setAttribute("aria-pressed", String((key || null) === arm));
          b.innerHTML =
            '<i class="dot"></i><span class="arm-name">' +
            esc(a.name) +
            '</span><span class="count">' +
            fmt(a.size) +
            "</span>" +
            (key
              ? '<span class="bar"><i style="width:' + Math.round((100 * a.size) / maxSize) + '%"></i></span>'
              : "");
          b.onclick = () => {
            arm = arm === key || !key ? null : key;
            clearSelection();
            renderRanking();
            updateCaption();
          };
          host.appendChild(b);
        }
      }
      function runSearch(value) {
        search = value.trim().toLowerCase();
        clearSelection();
        $("search-section").hidden = !search;
        $("arms-section").hidden = !!search;
        $("rank-section").hidden = !!search;
        const results = data.nodes
          .filter((n) => n.label.toLowerCase().includes(search))
          .sort((a, b) => b.fanIn - a.fanIn);
        $("result-count").textContent = fmt(results.length);
        $("results").replaceChildren();
        results.slice(0, 40).forEach((n) => $("results").appendChild(nodeButton(n)));
        if (!results.length)
          $("results").innerHTML = '<div class="empty">No matches. Try a shorter name.</div>';
        refresh();
        if (search)
          message(
            fmt(results.length) + " matching " + view + (results.length > 40 ? " · first 40 listed" : ""),
          );
      }
      function switchView(next) {
        view = next;
        selected = null;
        hovered = null;
        search = "";
        $("search").value = "";
        $("search").placeholder = view === "modules" ? "Find a module…" : "Find a symbol…";
        $("modules").setAttribute("aria-pressed", String(view === "modules"));
        $("symbols").setAttribute("aria-pressed", String(view === "symbols"));
        $("search-section").hidden = true;
        $("arms-section").hidden = false;
        $("rank-section").hidden = false;
        $("inspector").hidden = true;
        tooltip.hidden = true;
        objects = [];
        data = buildData();
        G.graphData(data);
        labels();
        renderRanking();
        refresh();
        fit(false);
        updateCaption();
      }
      try {
        THREE = await import("__THREE__");
        if (typeof ForceGraph3D === "undefined") throw new Error("Graph library unavailable");
        G = new ForceGraph3D($("g"), {
          controlType: "orbit",
          rendererConfig: { antialias: true, alpha: true, powerPreference: "high-performance" },
        })
          .backgroundColor("#000000")
          .width(stage.clientWidth)
          .height(stage.clientHeight)
          .showNavInfo(false)
          .enableNodeDrag(false)
          .nodeLabel(() => false)
          .linkLabel(() => false)
          .nodeThreeObject(makeNode)
          .linkOpacity(1)
          .linkResolution(6)
          .linkCurvature((l) => (l.kind === "contains" ? 0 : l.kind === "cross" ? 0.22 : 0.14))
          .linkCurveRotation((l) => hash(idOf(l.source) + idOf(l.target)) * 0.8)
          .linkDirectionalParticleWidth((l) => 0.8 + 1.4 * l.strength)
          .linkDirectionalParticleSpeed(0.0022)
          .linkDirectionalParticleColor((l) => tint(nodeById.get(idOf(l.source))))
          .linkDirectionalArrowColor((l) => tint(nodeById.get(idOf(l.source))))
          .linkDirectionalArrowRelPos(0.78)
          .cooldownTicks(0)
          .onNodeHover((n) => {
            hovered = n;
            refresh();
            showTooltip(n, null);
            $("g").style.cursor = n ? "pointer" : "grab";
          })
          .onLinkHover((l) => {
            if (!hovered) showTooltip(null, l);
          })
          .onNodeClick(inspect)
          .onBackgroundClick(clearSelection);
        G.renderer().setPixelRatio(Math.min(devicePixelRatio, 1.75));
        G.controls().enableDamping = true;
        G.controls().dampingFactor = 0.08;
        G.controls().rotateSpeed = 0.5;
        G.controls().minDistance = 30;
        G.controls().maxDistance = 14000;
        G.controls().autoRotateSpeed = 0.24;
        G.controls().addEventListener("start", () => {
          motion = false;
          refresh();
        });
        switchView("modules");
        $("arm-count").textContent = String(S.arms.length).padStart(2, "0");
        $("stats").innerHTML = [
          ["modules", S.counts.modules],
          ["symbols", S.counts.nodes],
          ["dependencies", S.counts.dependencies],
        ]
          .map(
            ([label, count]) => '<div class="stat"><b>' + fmt(count) + "</b><span>" + label + "</span></div>",
          )
          .join("");
        $("loading").hidden = true;
        for (const id of ["modules", "symbols", "search", "orbit", "fit", "detail"]) $(id).disabled = false;
        $("modules").onclick = () => switchView("modules");
        $("symbols").onclick = () => switchView("symbols");
        $("search").oninput = (e) => runSearch(e.target.value);
        $("search").onkeydown = (e) => {
          if (e.key === "Enter") $("results").querySelector("button")?.click();
        };
        $("fit").onclick = () => {
          arm = null;
          search = "";
          $("search").value = "";
          clearSelection();
          runSearch("");
          renderRanking();
          fit();
        };
        $("orbit").onclick = () => {
          motion = !motion;
          refresh();
        };
        $("detail").onclick = () => {
          detail = !detail;
          refresh();
          updateCaption();
        };
        $("menu").onclick = () => {
          const open = document.body.classList.toggle("menu-open");
          $("menu").setAttribute("aria-expanded", String(open));
        };
        stage.addEventListener("pointermove", (e) => {
          const rect = stage.getBoundingClientRect();
          pointer = { x: e.clientX - rect.left, y: e.clientY - rect.top };
          if (!tooltip.hidden) placeTooltip();
        });
        stage.addEventListener("pointerleave", () => {
          hovered = null;
          tooltip.hidden = true;
          refresh();
        });
        addEventListener("keydown", (e) => {
          const editing = e.target instanceof HTMLInputElement;
          if (e.key === "Escape") {
            document.body.classList.remove("menu-open");
            $("menu").setAttribute("aria-expanded", "false");
            if (search) {
              $("search").value = "";
              runSearch("");
            } else clearSelection();
            $("search").blur();
          }
          if (editing) return;
          if (e.key === "/") {
            e.preventDefault();
            document.body.classList.add("menu-open");
            $("menu").setAttribute("aria-expanded", "true");
            $("search").focus();
          }
          if (e.key.toLowerCase() === "r") $("fit").click();
        });
        new ResizeObserver(() => {
          G.width(stage.clientWidth).height(stage.clientHeight);
          fit(false);
        }).observe(stage);
        reduced.addEventListener("change", (e) => {
          if (e.matches) {
            motion = false;
            refresh();
          }
        });
        document.addEventListener("visibilitychange", () => {
          if (document.hidden) G.pauseAnimation();
          else G.resumeAnimation();
        });
        const projected = new THREE.Vector3();
        function tick() {
          requestAnimationFrame(tick);
          if (document.hidden) return;
          G.controls().autoRotate = motion && !hovered && !selected && performance.now() > flyUntil;
          if (++frame % 2) return;
          const occupied = [];
          for (const { n, el } of labelItems) {
            projected.set(n.x, n.y, n.z).project(G.camera());
            const p = G.graph2ScreenCoords(n.x, n.y, n.z);
            const x = p.x,
              y = p.y + n.radius + 13;
            const selectedLabel = activeNode() === n;
            const w = Math.min(240, short(n).length * 6.6),
              h = n.crown ? 32 : 17;
            const rect = { left: x - w / 2, right: x + w / 2, top: y, bottom: y + h };
            const obscured =
              y < 210 ||
              y > stage.clientHeight - 125 ||
              x < 30 ||
              x > stage.clientWidth - 30 ||
              (!selectedLabel &&
                occupied.some(
                  (r) =>
                    rect.left < r.right + 9 &&
                    rect.right > r.left - 9 &&
                    rect.top < r.bottom + 6 &&
                    rect.bottom > r.top - 6,
                ));
            const visible = projected.z > -1 && projected.z < 1 && intensity(n) > 0.2 && !obscured;
            el.style.opacity = visible ? "1" : "0";
            if (visible) {
              el.style.left = x + "px";
              el.style.top = y + "px";
              occupied.push(rect);
            }
          }
        }
        tick();
        import("__BLOOM__")
          .then(({ UnrealBloomPass }) => {
            bloom = new UnrealBloomPass(
              new THREE.Vector2(stage.clientWidth, stage.clientHeight),
              0.72,
              0.55,
              0.4,
            );
            G.postProcessingComposer().addPass(bloom);
            $("glow").disabled = false;
            $("glow").setAttribute("aria-pressed", "true");
            $("glow").onclick = () => {
              bloom.enabled = !bloom.enabled;
              $("glow").setAttribute("aria-pressed", String(bloom.enabled));
            };
          })
          .catch(() => {
            $("glow").title = "Bloom could not load; the graph is available";
            message("Graph ready · bloom unavailable");
          });
      } catch (error) {
        console.error("Graphy 3D:", error);
        fail();
      }
    </script>
  </body>
</html>
"""
