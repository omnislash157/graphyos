"""scene — the codebase as a 3D scene, computed from the store: no model places a node.

The hierarchy the engine already derives becomes geometry. Every arm of the partition is a cluster on a ring;
its height is the arm's layer in the sugiyama layout of the pillars, so what depends on nothing rises and the
floor sits low. A node's size is its fan-in over the declared DEPENDS family, the crown of each arm (its
most-depended-on symbol) carries a label, `contains` holds a cluster together and every dependency that crosses
arms carries particles. The page loads three.js through 3d-force-graph from jsdelivr, pinned by version —
the one page the engine emits that fetches, because the wheel cannot carry a WebGL engine (graphyos, 0.2.7).
"""
from __future__ import annotations

import collections
import json

from graphy import sugiyama as S
from graphy.draw import DrawError, pillars
from graphy.pillars import _module_of, relations_for

__all__ = ["scene", "emit_page", "FORCE_GRAPH", "BLOOM"]

FORCE_GRAPH = "https://cdn.jsdelivr.net/npm/3d-force-graph@1.80.0/dist/3d-force-graph.min.js"
BLOOM = "https://cdn.jsdelivr.net/npm/three@0.183.0/examples/jsm/postprocessing/UnrealBloomPass.js/+esm"   # the three 1.80.0 bundles
PALETTE = ("#00e5ff", "#ff2bd6", "#ffd400", "#39ff88", "#ff7a1a", "#8f6bff", "#ff4d6d", "#00ffc3", "#4d9dff", "#c6ff00")


def scene(store, corpus: str, cut, *, max_nodes: int = 3000) -> dict:
    """{title, arms: [{name, color, layer, crown, size}], nodes: [{id, label, arm, val, crown, where}], links: [{source,
    target, kind}]} for one corpus under a partition cut."""
    if cut.groups is None:
        raise DrawError("a scene needs a partition cut — the arms are its groups")
    rec_of, arm_of = {}, {}
    for nid, rec in store.owned(corpus):
        if not rec or rec.get("role") == "test":
            continue
        m = _module_of(rec, nid)
        if m:
            rec_of[nid], arm_of[nid] = rec, cut.group_of(m)
    if not rec_of:
        raise DrawError(f"the store owns no module-bearing node for corpus {corpus!r}")
    depends = relations_for(store)
    fan_in: collections.Counter = collections.Counter()
    fan_out: collections.Counter = collections.Counter()
    raw = []
    for src, dst, rel in store.edges():
        if src in rec_of and dst in rec_of and src != dst:
            if rel in depends:
                fan_in[dst] += 1
                fan_out[src] += 1
                raw.append((src, dst, "cross" if arm_of[src] != arm_of[dst] else "depends"))
            elif rel == "contains":
                raw.append((src, dst, "contains"))
    keep = set(sorted(rec_of, key=lambda n: (-fan_in[n], n))[:max_nodes])
    pic = pillars(store, corpus, cut)
    layer_of = S.layout(pic.nodes, pic.edges, pic.labels).layer_of
    names = sorted({arm_of[n] for n in keep}, key=lambda a: (layer_of.get(a, 0), a))
    # the crown orchestrates: depended on AND depending, so a leaf every lane raises (an error class) never wins it
    crowns = {}
    for n in sorted(keep, key=lambda n: (-(fan_in[n] * fan_out[n]), -fan_in[n], n)):
        crowns.setdefault(arm_of[n], n)
    arms = [{"name": a, "color": PALETTE[i % len(PALETTE)], "layer": layer_of.get(a, 0), "crown": crowns.get(a),
             "size": sum(1 for n in keep if arm_of[n] == a)} for i, a in enumerate(names)]
    nodes = [{"id": n, "label": rec_of[n].get("dotted") or n, "arm": arm_of[n], "val": 1 + fan_in[n],
              "crown": crowns.get(arm_of[n]) == n, "kind": rec_of[n].get("node_type"),
              "where": f"{rec_of[n].get('file') or ''}:{rec_of[n].get('line') or ''}".strip(":")} for n in sorted(keep)]
    links = [{"source": s, "target": d, "kind": k} for s, d, k in sorted(set(raw)) if s in keep and d in keep]
    return {"title": corpus, "arms": arms, "nodes": nodes, "links": links,
            "counts": {"nodes": len(rec_of), "shown": len(nodes), "links": len(links),
                       "cross": sum(1 for l in links if l["kind"] == "cross")}}


def emit_page(sc: dict, *, generation: str = "") -> str:
    """The scene as one HTML page: the data inline, the two libraries from jsdelivr."""
    data = json.dumps(sc, separators=(",", ":")).replace("</", "<\\/")
    return (_PAGE.replace("__TITLE__", S._esc(sc["title"])).replace("__FG__", FORCE_GRAPH).replace("__BLOOM__", BLOOM)
            .replace("__GEN__", S._esc(generation)).replace("__DATA__", data))


_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ · graphy</title>
<style>
html,body{margin:0;height:100%;background:#000;color:#dfe7ff;font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;overflow:hidden}
#g{position:fixed;inset:0}#hud{position:fixed;left:24px;top:20px;pointer-events:none;max-width:70ch}
#hud h1{font:600 30px/1.1 ui-sans-serif,system-ui,sans-serif;margin:4px 0 6px;letter-spacing:-.02em;text-shadow:0 0 18px #00e5ff88}
.eb{letter-spacing:.2em;font-size:10px;color:#7f8bb3}#legend{position:fixed;left:24px;bottom:20px;display:flex;flex-wrap:wrap;gap:6px;max-width:70vw}
#legend button{all:unset;cursor:pointer;padding:4px 9px;border:1px solid #ffffff22;border-radius:99px;background:#ffffff0a}
#legend button i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;box-shadow:0 0 8px currentColor}
#legend button.on{border-color:currentColor}.lab{position:fixed;pointer-events:none;transform:translate(-50%,-160%);font-size:11px;
white-space:nowrap;text-shadow:0 0 6px #000,0 0 12px currentColor}
</style></head><body><div id="g"></div>
<div id="hud"><div class="eb">GRAPHY · NO MODEL DREW THIS</div><h1>__TITLE__</h1><div id="stats"></div></div>
<div id="legend"></div><div id="labs"></div>
<script src="__FG__"></script>
<script type="module">
const S=__DATA__;const color=Object.fromEntries(S.arms.map(a=>[a.name,a.color]));
const layer=Object.fromEntries(S.arms.map(a=>[a.name,a.layer]));const maxL=Math.max(1,...S.arms.map(a=>a.layer));
const R=160+26*Math.sqrt(S.nodes.length),H=60+7*Math.sqrt(S.nodes.length);const home={};
S.arms.forEach((a,i)=>{const t=2*Math.PI*i/S.arms.length;home[a.name]={x:R*Math.cos(t),y:H*(maxL/2-a.layer),z:R*Math.sin(t)}});
document.getElementById('stats').textContent=`${S.counts.shown} of ${S.counts.nodes} symbols · ${S.arms.length} arms · ${S.counts.links} edges · ${S.counts.cross} cross the arms`+(`__GEN__`?` · store __GEN__`:``);
let focus=null;const lit=n=>!focus||n.arm===focus;
function cluster(alpha){for(const n of S.nodes){const h=home[n.arm];n.vx+=(h.x-n.x)*.04*alpha;n.vy+=(h.y-n.y)*.06*alpha;n.vz+=(h.z-n.z)*.04*alpha}}
cluster.initialize=()=>{};
const G=new ForceGraph3D(document.getElementById('g'),{controlType:'orbit'}).backgroundColor('#000000').graphData(S)
 .nodeVal(n=>n.crown?Math.max(n.val,40):n.val).nodeRelSize(3.4).nodeOpacity(1).nodeResolution(10)
 .nodeColor(n=>lit(n)?color[n.arm]:'#1a1f33').nodeLabel(n=>`<b>${n.label}</b><br>${n.kind||''} · ${n.where}<br>${n.val-1} depend on it`)
 .width(innerWidth).height(innerHeight).showNavInfo(false)
 .linkColor(l=>color[l.source.arm||l.source]||'#445').linkOpacity(.32).linkWidth(l=>l.kind==='cross'?.35:0)
 .linkVisibility(l=>!focus||l.source.arm===focus||l.target.arm===focus)
 .linkDirectionalParticles(l=>l.kind==='cross'?2:0).linkDirectionalParticleWidth(1.3).linkDirectionalParticleSpeed(.006)
 .linkDirectionalParticleColor(l=>color[l.source.arm]).d3Force('cluster',cluster).warmupTicks(220).cooldownTime(9000)
 .onNodeClick(n=>{const d=90,r=1+d/Math.hypot(n.x,n.y,n.z);G.cameraPosition({x:n.x*r,y:n.y*r,z:n.z*r},n,1600)});
G.d3Force('charge').strength(-40);G.d3Force('link').distance(l=>l.kind==='contains'?8:30).strength(l=>l.kind==='cross'?.01:.3);
import {UnrealBloomPass} from '__BLOOM__';const b=new UnrealBloomPass();b.strength=2.2;b.radius=.55;b.threshold=.12;G.postProcessingComposer().addPass(b);
const lg=document.getElementById('legend');for(const a of S.arms){const e=document.createElement('button');e.style.color=a.color;
 e.innerHTML=`<i></i>${a.name} <span style="opacity:.6">${a.size}</span>`;e.onclick=()=>{focus=focus===a.name?null:a.name;
 [...lg.children].forEach(c=>c.classList.toggle('on',c===e&&!!focus));G.nodeColor(G.nodeColor()).linkVisibility(G.linkVisibility())};lg.appendChild(e)}
const labs=document.getElementById('labs');const crowns=S.nodes.filter(n=>n.crown).map(n=>{const e=document.createElement('div');
 e.className='lab';e.style.color=color[n.arm];e.textContent=n.label.split('.').slice(-2).join('.');labs.appendChild(e);return [n,e]});
let spin=true,t0=performance.now();['pointerdown','wheel'].forEach(ev=>addEventListener(ev,()=>spin=false,{once:true}));
G.cameraPosition({x:0,y:H*1.2,z:R*2.6},{x:0,y:0,z:0});G.onEngineStop(()=>{});setTimeout(()=>G.zoomToFit(2500,20),400);
addEventListener('resize',()=>G.width(innerWidth).height(innerHeight));
(function tick(){requestAnimationFrame(tick);if(spin&&performance.now()-t0>4500){const c=G.camera(),a=.0012,x=c.position.x,z=c.position.z;
 c.position.x=x*Math.cos(a)-z*Math.sin(a);c.position.z=x*Math.sin(a)+z*Math.cos(a);c.lookAt(G.controls().target)}
 for(const [n,e] of crowns){const p=G.graph2ScreenCoords(n.x||0,n.y||0,n.z||0);e.style.left=p.x+'px';e.style.top=p.y+'px';e.style.opacity=lit(n)?1:.15}})();
</script></body></html>
"""
