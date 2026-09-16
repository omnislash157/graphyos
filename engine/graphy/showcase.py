"""showcase — one page that shows a stranger their own codebase, made by one command.

`graphy showcase <git url | path>`: clone shallow when a URL, eat (the one-liner's path, skipped
when a fresh `.graphy/` already stands), propose the pillars from the walk (no curated partition
exists for a stranger's repo, so the proposal is the cut, written beside the substrate), draw
the pillars and the unit map, and write one self-contained page: the interactive drawing, the
ASCII beside it, the arms the walk proposed with their crowns and evidence, the ring the repo
carries and what it could not, the MCP block to paste into Claude Code or Cursor, three questions
to ask, and how to add a model in three lines. `showcase.txt` is the same as plain text for a
README or a post, written for a Markdown fence: a module or arm name is printed verbatim, so any
line that could close a backtick fence (up to three spaces, then three or more backticks) has its
backticks backslash-escaped — visible, never a hidden character (graphyos #40). The page passes the
draw check and carries nothing fetched.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path, PureWindowsPath

from graphy import draw as draw_lane
from graphy import fanout, pillars as pillars_lane
from graphy import sugiyama as S

__all__ = ["ShowcaseError", "clone_dir", "compose", "fence_safe", "repo_of", "showcase", "PAGE", "TEXT"]

PAGE, TEXT, GALAXY = "index.html", "showcase.txt", "galaxy.html"


class ShowcaseError(RuntimeError):
    pass


def _esc(s) -> str:
    return S._esc(s)


_FENCE_LINE = re.compile(r"^( {0,3})(`{3,})")


def fence_safe(text: str) -> str:
    """The text page written for a Markdown fence: every line that could close one — at most three
    spaces of indent, then three or more backticks — has that run backslash-escaped (`\\``), so a
    file named ```` ``` ```` cannot break out of the comment the workflow posts it in. Every other
    line is untouched; the escape is visible in the fence, never a zero-width character."""
    return "\n".join(_FENCE_LINE.sub(lambda m: m.group(1) + "".join("\\`" for _ in m.group(2)), ln)
                     for ln in text.split("\n"))


def compose(store, *, package: str, desc: Path, home: Path, proposal, cut, ring: dict, graphy_cmd: list[str],
            origin: str = "") -> tuple[str, str]:
    """(html, text) for one eaten repo, from the store and the proposal."""
    pic_p = draw_lane.pillars(store, package, cut)
    pic_u = draw_lane.units(store, package, min_weight=2)
    lo_p = S.layout(pic_p.nodes, pic_p.edges, pic_p.labels)
    lo_u = S.layout(pic_u.nodes, pic_u.edges, pic_u.labels)
    ascii_p = S.render(lo_p, color=False, title=pic_p.title, orient="LR")
    ascii_u = S.render(lo_u, color=False, title=pic_u.title, orient="LR")
    svg, script = S.emit_svg(lo_u, title=f"{package} · the modules", orient="LR", interactive=True, node_meta=pic_u.meta)
    g = " ".join(graphy_cmd)
    tenant = f"--tenant {desc.as_posix()} --tenant-id {package}"
    from graphy.cli import mcp_config
    mcp = json.dumps(mcp_config(graphy_cmd, desc, package), indent=2)
    crowns = list(proposal.crowns.items())
    asks = []
    if crowns:
        asks.append((f"{g} blast {crowns[0][1]} {tenant}", f"if {crowns[0][1]} changes, what breaks"))
        asks.append((f"{g} descend {crowns[-1][1]} {tenant} --depth 3", f"what {crowns[-1][1]} reaches, across packages"))
    minted = [m for m in ring.get("minted", {}) if m != package]
    if minted:
        asks.append((f"{g} walk {tenant} --seed {package}://module/{package} --target {minted[0]}://module/{minted[0]}",
                     f"does {package} reach {minted[0]}, and through what"))
    else:
        asks.append((f"{g} draw {tenant} --symbol {crowns[0][1] if crowns else package} --radius 2 --lr", "the neighbourhood, drawn"))
    arms_rows = []
    for arm, units in proposal.arms.items():
        crown = proposal.crowns.get(arm, units[0] if units else "")
        evidence = next((r.how for r in proposal.rulings if r.unit == crown), "")
        arms_rows.append((arm, crown, len(units), evidence))
    unresolved = ring.get("unresolved", {})

    text = [f"{package} — drawn by graphy in one command", f"  {origin}".rstrip(), "",
            "THE PILLARS (the arms the walk proposes; the crown is the unit that orchestrates each)", ""]
    text += ["  " + ln for ln in ascii_p.splitlines()]
    text += ["", "THE ARMS"]
    text += [f"  {arm:14} crown {crown:32} {n} unit(s) — {ev}" for arm, crown, n, ev in arms_rows]
    text += ["", "THE MODULES (edges ≥ 2)", ""]
    text += ["  " + ln for ln in ascii_u.splitlines()]
    text += ["", f"THE RING: {len(minted)} package(s) minted beside {package}: {', '.join(minted) or 'none'}",
             f"  not carried: {', '.join(sorted(unresolved)) or 'nothing — the ring closed'}", "",
             "ADD YOUR MODEL — paste into the repo's .mcp.json (Claude Code) or your client's MCP settings — the client can start anywhere in the repo; any model, the walk is graphy's:"]
    text += ["  " + ln for ln in mcp.splitlines()]
    text += ["", "ASK IT"] + [f"  {cmd}\n      # {why}" for cmd, why in asks]
    text += ["", "HOW IT WAS MADE", f"  pip install graphyos && cd <repo> && graphy eat . && graphy showcase .",
             "  No model drew this. Every edge is structural, a wormhole, or a label resolved through the code's own scope.", ""]

    # Keep arm colors in the same layer/name order as the 3D atlas.
    arm_names = sorted(set(proposal.arms) | {cut.group_of(n) for n in pic_u.nodes},
                       key=lambda a: (lo_p.layer_of.get(a, 0), a))
    arm_colors = {name: i % 10 for i, name in enumerate(arm_names)}
    atlas = {
        "nodes": [{"id": n, "label": pic_u.labels[n], "arm": cut.group_of(n),
                   "color": arm_colors[cut.group_of(n)]} for n in pic_u.nodes],
        "edges": [{"source": a, "target": b, "weight": pic_u.weights[a, b]} for a, b in pic_u.edges],
    }
    arm_counts = {name: sum(n["arm"] == name for n in atlas["nodes"]) for name in arm_names}
    largest_arm = max(arm_counts.values(), default=1) or 1
    dependency_count = sum(e["weight"] for e in atlas["edges"])
    hub = home / "GRAPH.md"
    if hub.is_file():
        text += ["", f"THE HUB: {hub.as_posix()} — open one arm, blast its crown, do not dump every arm into context"]
    h = ["<!DOCTYPE html>", '<html lang="en" data-theme="dark">', '<head>',
         '<meta charset="UTF-8">', '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
         f'<title>{_esc(package)} · graphy codebase atlas</title>', '<style>', S._TOKEN_CSS, S._HTML_CSS, _ATLAS_CSS, '</style>',
         '</head><body>', '<a class="skip-link" href="#graph-canvas">Skip to graph</a>',
         '<header class="topbar"><div class="brand"><span class="brand-mark" aria-hidden="true"></span>graphy<small>CODEBASE ATLAS</small></div>',
         '<nav class="header-actions" aria-label="Views"><span class="view-tag">2D EXPLORER</span><a href="galaxy.html">3D explorer ↗</a>',
         '<button type="button" class="theme-button" id="theme-toggle" aria-label="Switch to light theme">Light</button></nav></header>',
         '<div class="workspace"><aside class="explorer" id="explorer" aria-label="Architecture explorer">',
         '<div class="sidebar-head"><div><p class="eyebrow">Repository</p>',
         f'<p class="repo">{_esc(package)}</p><p class="repo-note">Your architecture. Every connection.</p></div>',
         '<label class="search"><span aria-hidden="true">⌕</span><input id="module-search" type="search" placeholder="Find a module…" aria-label="Find a module" autocomplete="off" spellcheck="false"><kbd>/</kbd></label></div>',
         '<section class="sidebar-section"><h2 class="section-label">Architecture <span>IN VIEW</span></h2><div class="arm-list">',
         f'<button class="arm-button" type="button" data-arm="" aria-pressed="true"><i class="dot"></i>All arms<span class="count">{len(pic_u.nodes)}</span></button>']
    for name in arm_names:
        count = arm_counts[name]
        h.append(f'<button class="arm-button" type="button" data-arm="{_esc(name)}" aria-pressed="false" style="--arm:var(--arm-{arm_colors[name]})">'
                 f'<i class="dot"></i>{_esc(name)}<span class="count">{count}</span><span class="arm-meter" aria-hidden="true"><i style="width:{round(count/largest_arm*100)}%"></i></span></button>')
    h += ['</div></section>',
          '<section class="sidebar-section modules-section"><h2 class="section-label">Module groups <span id="module-count"></span></h2><div class="module-list" id="module-list"></div><p class="empty-list" id="no-results" hidden></p></section>',
          '<div class="sidebar-foot"><p class="eyebrow">Read the architecture</p><p>Color identifies an arm.<br>Line weight counts dependencies.<br>Arrows point to the dependency.</p><p>Module paths are grouped at depth 2.<br>Connections with 2+ dependencies.</p><a href="#architecture-notes">Architecture &amp; terminal setup ↓</a></div></aside>',
          '<main><section class="scene-head"><div><p class="eyebrow">Explore the structure</p><h1>Follow the connections.</h1><p>Find what depends on your code. See what your code depends on.</p></div>',
          f'<div class="stats" aria-label="Visible graph counts"><div><b>{len(pic_u.nodes)}</b><span>groups</span></div><div><b>{len(pic_u.edges)}</b><span>connections</span></div><div><b>{dependency_count:,}</b><span>dependencies</span></div></div></section>',
          '<section class="graph-shell" aria-label="Interactive module map"><div class="graph-topline"><div class="graph-label">MODULE MAP<small id="graph-context">All arms</small></div><a href="#selection-panel">Inspect a module ↓</a></div>',
          '<div class="graph-area"><div class="plate" id="graph-canvas">', svg, '</div></div>',
          '<div class="graph-bottom"><div class="legend" aria-label="Connection colors"><span><i class="incoming"></i>Upstream</span><span><i class="outgoing"></i>Downstream</span><span><i class="cycle"></i>Cycle return</span></div>',
          '<div class="toolbar" role="group" aria-label="Graph controls"><button id="zoom-out" type="button" aria-label="Zoom out" title="Zoom out (−)">−</button><span class="zoom-readout" id="zoom-level">100%</span><button id="zoom-in" type="button" aria-label="Zoom in" title="Zoom in (+)">+</button><button class="fit" id="fit-graph" type="button" title="Fit graph (0)">Fit view</button></div></div></section>',
          f'<div class="canvas-help"><span id="graph-status" role="status">{len(pic_u.nodes)} groups · {len(pic_u.edges)} connections · drag to pan</span><span>SCROLL to zoom · CLICK to trace · ESC to clear</span></div>',
          '<section class="selection-panel" id="selection-panel" aria-label="Module inspector"><div class="selection-empty" id="selection-empty"><span class="selection-icon" aria-hidden="true">⌖</span><div><strong>Every module has a story.</strong><p>Select a node to trace its connections, or find a module in the explorer.</p></div></div>',
          '<div id="selection-detail" hidden><div class="selection-head"><div><p class="eyebrow" id="selection-arm"></p><h2 class="selection-id" id="selection-name"></h2></div><div><button type="button" id="focus-selection">Fit neighbors</button> <button type="button" id="clear-selection" aria-label="Clear selected module">Clear ×</button></div></div>',
          '<p class="selection-note" id="selection-note"></p><div class="connections"><div><h3 id="incoming-title"></h3><div class="connection-list" id="incoming-list"></div></div><div class="out"><h3 id="outgoing-title"></h3><div class="connection-list" id="outgoing-list"></div></div></div></div></section>',
          '<section class="details-area" id="architecture-notes"><div class="details-heading"><div><p class="eyebrow">Keep exploring</p><h2>From the map to your terminal.</h2></div><span>COMPUTED FROM CODE</span></div>',
          f'<details><summary>The pillars<small>{len(proposal.arms)} arms · crowns &amp; evidence</small></summary><div class="detail-body"><p>The arms the walk proposes. Each crown is the unit that orchestrates its arm.</p><pre class="ascii">{_esc(ascii_p)}</pre>',
          '<div class="table-scroll"><table><thead><tr><th scope="col">Arm</th><th scope="col">Crown</th><th scope="col">Units</th><th scope="col">Evidence</th></tr></thead><tbody>']
    h += [f'<tr><td>{_esc(a)}</td><td class="mono">{_esc(c)}</td><td>{n}</td><td>{_esc(e)}</td></tr>' for a, c, n, e in arms_rows]
    h += ['</tbody></table></div>']
    if hub.is_file():
        h += [f'<p>Compiled arms live at <code>{_esc(hub.as_posix())}</code>. Open one arm; blast its crown.</p>']
    h += ['</div></details>',
          f'<details><summary>The package ring<small>{len(minted)} connected packages</small></summary><div class="detail-body"><p>Minted beside {_esc(package)}: <span class="mono">{_esc(", ".join(minted) or "none")}</span>.</p>',
          f'<p>Not carried: <span class="mono">{_esc(", ".join(sorted(unresolved)) or "nothing — the ring closed")}</span>.</p></div></details>',
          '<details><summary>Add your model<small>MCP configuration</small></summary><div class="detail-body"><p>Paste this into the repo\'s <code>.mcp.json</code> (Claude Code) or your client\'s MCP settings. The client can start anywhere in the repo. Any model; the walk is graphy\'s.</p>',
          f'<pre class="ascii">{_esc(mcp)}</pre></div></details>',
          '<details><summary>Ask the codebase<small>Three starting points</small></summary><div class="detail-body"><ul class="ask">']
    h += [f'<li><code>{_esc(cmd)}</code><span class="why">{_esc(why)}</span></li>' for cmd, why in asks]
    h += ['</ul></div></details><details><summary>Make your own atlas<small>One command · no model</small></summary><div class="detail-body">',
          '<pre class="ascii">pip install graphyos\ncd &lt;repo&gt; &amp;&amp; graphy eat . &amp;&amp; graphy showcase .</pre></div></details>',
          f'<p class="source-note">{_esc(origin)}<br>Every edge comes from code structure, a wormhole between packages, or a label resolved through the code\'s own scope. The module map shows cross-group connections with at least 2 dependencies; {pic_u.dropped} below that floor.</p>',
          '</section></main></div>', script,
          _ATLAS_SCRIPT.replace('__ATLAS_DATA__', json.dumps(atlas, separators=(",", ":")).replace('<', '\\u003c')),
          '</body></html>']
    return "\n".join(h) + "\n", fence_safe("\n".join(text))


_SEG = r"[A-Za-z0-9_~][A-Za-z0-9_.-]*"      # a path segment: never `.`, `..` or `.git`; `~user` is sr.ht's owner
_REPO = re.compile(r"^(?:[a-z][a-z0-9+.-]*://(?:[^/@]*@)?(?P<host>[^/]+)/|(?:[^@]*@)?(?P<sshhost>[^:/]+):|/)"
                   r"(?P<owner>" + _SEG + r"(?:/" + _SEG + r")*)/(?P<name>" + _SEG + r"?)(?:\.git)?/?$")


_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def _parse(url: str) -> tuple[str, str, str]:
    url = url.strip()
    if _DRIVE.match(url):
        # a drive-lettered path (`C:\work\src/`, or git's own `C:/work/src` in a clone's origin) is a path,
        # never an ssh `host:` — spelled POSIX with the drive folded, so both spellings parse alike (graphyos #125)
        win = PureWindowsPath(url)
        url = f"/{win.drive[0].lower()}/" + win.as_posix()[len(win.drive):].lstrip("/")   # the drive is a segment: C:\a\src and D:\a\src are two repos
    m = _REPO.match(url)
    if not m or not m.group("name") or m.group("name") == ".git":
        raise ShowcaseError(f"not an <owner>/<name> git url: {url!r} (an https, ssh or absolute path ending in "
                            f"<owner>/<name>[.git]; a segment is never `.`, `..` or `.git`)")
    return (m.group("host") or m.group("sshhost") or "").lower(), m.group("owner"), m.group("name")


def repo_of(url: str) -> tuple[str, str]:
    """(owner, name) from a git url or an absolute path: the name is the last segment, the owner every
    segment before it under the host (a GitLab group path stays whole: `groupA/tools` and `groupB/tools` are
    two owners), `.git` and a trailing slash folded, userinfo ignored. The one parse the clone key and the
    gallery's slug share (graphyos #58); a url with no owner/name tail, or a `.`/`..`/`.git` segment that
    would walk out of --work, refuses by name."""
    _, owner, name = _parse(url)
    return owner, name


def clone_dir(work: Path, url: str) -> Path:
    """Where a url's clone lands under --work: `<work>/<owner>/<name>`. Two repos of one name never share
    a directory, and the directory is still named for the repo — an eat that falls back to the directory's
    name (a package.json with no name) says the same thing it said (graphyos #58)."""
    owner, name = repo_of(url)
    return work.joinpath(*owner.split("/")) / name


def _same_repo(a: str, b: str) -> bool:
    """One repo under two spellings: https or ssh, `.git` or not, a trailing slash, userinfo, the host's case."""
    try:
        return _parse(a) == _parse(b)
    except ShowcaseError:
        return False


def _shown(url: str) -> str:
    """A url for a message: userinfo (a token) never travels."""
    return re.sub(r"^([a-z][a-z0-9+.-]*://)[^/@]*@", r"\1", url)


def _clone(url: str, work: Path, log) -> Path:
    repo = clone_dir(work, url)
    if shutil.which("git") is None:                              # the missing program is named, never a raw FileNotFoundError (graphyos #95)
        raise ShowcaseError("git is not on PATH — a url is cloned with git; install it, or showcase a local path")
    if (repo / ".git").is_dir():
        # A directory that stands is reused only when it is a clone of the url asked for: the origin is read
        # from the clone itself, and a mismatch refuses by name — never a page drawn from another repo's tree.
        proc = subprocess.run(["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
                              capture_output=True, text=True)
        if proc.returncode not in (0, 1):                       # 1 is git's "no such key"; anything else, git refused
            raise ShowcaseError(f"{repo.as_posix()} stands but git cannot read it: {(proc.stderr or '').strip()[-300:]}")
        origin = (proc.stdout or "").strip()
        if not _same_repo(origin, url):
            raise ShowcaseError(f"{repo.as_posix()} is a clone of {_shown(origin) or '<no origin>'}, not {_shown(url)}")
        log(f"SHOWCASE: reusing the clone at {repo.as_posix()}")
    else:
        work.mkdir(parents=True, exist_ok=True)
        log(f"SHOWCASE: git clone --depth 1 {url} {repo.as_posix()}")
        proc = subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(repo)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise ShowcaseError(f"clone failed: {(proc.stderr or '').strip()[-300:]}")
    return repo


def showcase(target: str, *, out: str | Path | None = None, work: str | Path | None = None, log=None,
             eat=None, open_store=None, graphy_cmd: list[str] | None = None, no_provision: bool = False) -> dict:
    """Clone when a URL, eat when no .graphy stands or the one standing is behind the working tree
    (its cursor drifted, graphyos #39), propose, draw, compose, check.
    ``no_provision`` is handed to the eat: nothing of the repo's runs, the ring is empty (graphyos #35)."""
    from graphy import federated_store as fstore
    from graphy.cli import _load_tenant, _roster, _graphy_command, served_data_home, main as cli_main
    log = log or (lambda *_: None)
    t0 = time.perf_counter()
    if target.startswith(("http://", "https://", "git@")):
        if work is None:                                         # graphyos #43: the clone lands where you stand, said so
            work = Path.cwd() / "showcase"
            log(f"SHOWCASE: no --work — the clone lands under {work.resolve().as_posix()} (the current directory); "
                f"--work <dir> puts it elsewhere")
        repo = _clone(target, Path(work).resolve(), log)
        origin = target
    else:
        repo = Path(target).resolve()
        origin = repo.as_posix()                                 # the page and showcase.txt carry it: POSIX (graphyos #125)
    if not repo.is_dir():
        raise ShowcaseError(f"not a directory: {repo.as_posix()}")
    home = repo / ".graphy"
    desc = home / "tenant.json"
    stale = None
    if desc.is_file():                                   # graphyos #39: a store behind the working tree is re-eaten
        from graphy.cartograph import cursor_drift, cursor_exclude
        try:
            served = served_data_home(desc)
            stale = (f"the descriptor at {desc} names no data_home" if served is None else
                     cursor_drift(json.loads(desc.read_text(encoding="utf-8")).get("cursor", ""), repo,
                                  exclude=cursor_exclude(desc, served, root=repo)))
        except (OSError, ValueError, AttributeError) as exc:
            stale = f"the descriptor at {desc} is unreadable ({exc})"
        if stale:
            log(f"SHOWCASE: {stale} — eating again")
    if not desc.is_file() or stale:
        argv = ["eat", str(repo)] + (["--no-provision"] if no_provision else [])
        rc = (eat or (lambda r: cli_main(argv)))(repo)
        if rc != 0:
            raise ShowcaseError(f"eat exited {rc} for {repo.as_posix()}")
    served = served_data_home(desc)
    if served is None:
        raise ShowcaseError(f"the descriptor at {desc.as_posix()} names no data_home — eat did not land")
    ring = json.loads((served / "ring.json").read_text(encoding="utf-8"))
    package = ring["root"]
    tenant = _load_tenant(str(desc))
    roster = _roster(tenant)
    store = (open_store or (lambda: fstore.open_for(roster, tenant=tenant, tenant_id=package)))()
    with store:
        graph = pillars_lane.module_graph(store, package)
        try:
            proposal = pillars_lane.propose(graph)
        except pillars_lane.PillarsError as exc:
            # one pillar: the whole package is one arm, and the page says so
            units = sorted(graph.size)
            proposal = pillars_lane.Proposal(corpus=package, depth=graph.depth, floor=5, owned=2 / 3, client=1 / 3, rest="EDGE",
                                             crowns={package.upper(): units[0] if units else package}, floor_arm=None,
                                             arms={package.upper(): units}, rulings=[], total=0)
            log(f"SHOWCASE: one pillar — {exc}")
        partition = home / "partition.json"
        pillars_lane.write_partition(partition, pillars_lane.to_partition(proposal))
        cut = fanout.load_partition(partition)
        html, text = compose(store, package=package, desc=desc, home=home, proposal=proposal, cut=cut, ring=ring,
                             graphy_cmd=graphy_cmd or _graphy_command(), origin=origin)
        out_dir = Path(out).resolve() if out else home / "showcase"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / PAGE).write_text(html, encoding="utf-8")
        (out_dir / TEXT).write_text(text, encoding="utf-8")
        from graphy import scene as scene_lane           # the 3D galaxy beside the page: the one drawing that fetches (three.js)
        (out_dir / GALAXY).write_text(scene_lane.emit_page(scene_lane.scene(store, package, cut), generation=store.generation(), showcase=True),
                                      encoding="utf-8", newline="\n")
        red = S.check_artifact(out_dir / PAGE)
        # showcase.txt is a receipt too: the same output property the page holds (graphyos #125)
        red += [f"{TEXT}: path spelled the OS way: {p!r}" for p in S.os_spelled_paths(text)]
        return {"repo": repo.as_posix(), "package": package, "page": (out_dir / PAGE).as_posix(), "text": (out_dir / TEXT).as_posix(), "galaxy": (out_dir / GALAXY).as_posix(),
                "arms": list(proposal.arms), "ring": len(ring.get("minted", {})) - 1, "check": red,
                "seconds": round(time.perf_counter() - t0, 1)}


# The 2D atlas presentation: shared graph geometry and interactions, explorer chrome.
_ATLAS_CSS = """
    :root {
      color-scheme: light;
      --paper: #f2f5f9; --card: #ffffff; --panel: #f9fbfd; --ink: #182b40; --muted: #52677e; --soft: #70849a;
      --accent: #087d8b; --link: #7353bd; --card-rule: #d5dfe9; --head-wash: #e8eff6; --grid: #dce5ef;
      --edge: #93a6ba; --up: #087d8b; --down: #a56816; --selection: #7353bd; --shadow: #21364e12;
      --arm-0: #087d8b; --arm-1: #7952c2; --arm-2: #a56816; --arm-3: #168164; --arm-4: #bf4277; --arm-5: #426ec4; --arm-6: #a354ac; --arm-7: #227f78; --arm-8: #717828; --arm-9: #a85b32;
    }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        color-scheme: dark;
        --paper: #080c13; --card: #101925; --panel: #0d131e; --ink: #e3ebf6; --muted: #99acc2; --soft: #7b90aa;
        --accent: #72e1ec; --link: #b599ff; --card-rule: #243246; --head-wash: #182434; --grid: #172232;
        --edge: #4b617b; --up: #72e1ec; --down: #ffc572; --selection: #b599ff; --shadow: #00000030;
        --arm-0: #55dfff; --arm-1: #ad8bfa; --arm-2: #ffc878; --arm-3: #59e3b0; --arm-4: #ff8ca8; --arm-5: #7da4ff; --arm-6: #e8a0ef; --arm-7: #85dfd3; --arm-8: #d8df8b; --arm-9: #ecaa7d;
      }
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --paper: #080c13; --card: #101925; --panel: #0d131e; --ink: #e3ebf6; --muted: #99acc2; --soft: #7b90aa;
      --accent: #72e1ec; --link: #b599ff; --card-rule: #243246; --head-wash: #182434; --grid: #172232;
      --edge: #4b617b; --up: #72e1ec; --down: #ffc572; --selection: #b599ff; --shadow: #00000030;
      --arm-0: #55dfff; --arm-1: #ad8bfa; --arm-2: #ffc878; --arm-3: #59e3b0; --arm-4: #ff8ca8; --arm-5: #7da4ff; --arm-6: #e8a0ef; --arm-7: #85dfd3; --arm-8: #d8df8b; --arm-9: #ecaa7d;
    }
    html { scroll-behavior: smooth; }
    body { display: block; padding: 0; font-size: 13px; line-height: 1.55; -webkit-font-smoothing: antialiased; }
    button, input { font: inherit; }
    button, a { -webkit-tap-highlight-color: transparent; }
    button { cursor: pointer; color: var(--muted); background: transparent; border: 1px solid transparent; }
    button:hover, a:hover { color: var(--ink); }
    a { color: var(--accent); text-decoration: none; }
    button:focus-visible, a:focus-visible, input:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
    [hidden] { display: none !important; }
    .topbar { height: 65px; padding: 0 26px; display: flex; align-items: center; justify-content: space-between; gap: 16px; background: var(--panel); border-bottom: 1px solid var(--card-rule); }
    .brand { display: flex; align-items: center; gap: 12px; font-size: 21px; font-weight: 650; letter-spacing: -.8px; color: var(--ink); }
    .brand-mark { color: var(--accent); position: relative; display: inline-block; width: 24px; height: 24px; flex: none; background: linear-gradient(45deg, transparent 47%, currentColor 49%, currentColor 51%, transparent 53%), linear-gradient(-45deg, transparent 47%, currentColor 49%, currentColor 51%, transparent 53%); }
    .brand-mark::before { content: ''; position: absolute; width: 5px; height: 5px; border-radius: 50%; background: currentColor; top: 1px; left: 1px; box-shadow: 17px 0 currentColor, 0 17px currentColor, 17px 17px currentColor; }
    .brand-mark::after { content: ''; position: absolute; inset: 3px; border-left: 1px solid currentColor; border-right: 1px solid currentColor; }
    .brand small { border-left: 1px solid var(--card-rule); padding-left: 23px; margin-left: 12px; font: 10px var(--font-mono); letter-spacing: 2px; color: var(--muted); }
    .header-actions { display: flex; align-items: center; gap: 18px; font-size: 11px; }
    .view-tag { color: var(--accent); border: 1px solid var(--card-rule); background: var(--head-wash); border-radius: 5px; padding: 4px 9px; font: 9px var(--font-mono); letter-spacing: 1px; }
    .theme-button { min-height: 36px; border-radius: 6px; padding: 0 9px; }
    .workspace { display: grid; grid-template-columns: 244px minmax(0,1fr); align-items: start; }
    .explorer { min-width: 0; position: sticky; top: 0; height: 100dvh; overflow-y: auto; background: var(--panel); border-right: 1px solid var(--card-rule); scrollbar-width: thin; scrollbar-color: var(--card-rule) transparent; }
    .sidebar-head { padding: 25px 20px 20px; }
    .eyebrow { font: 10px/1.5 var(--font-mono); letter-spacing: 1.5px; margin: 0; }
    .repo { font-size: 20px; font-weight: 600; letter-spacing: -.5px; margin: 8px 0 3px; overflow-wrap: anywhere; }
    .repo-note { font-size: 11px; color: var(--muted); }
    .search { display: flex; align-items: center; gap: 8px; margin-top: 22px; padding: 9px 10px; border: 1px solid var(--card-rule); border-radius: 7px; background: var(--paper); color: var(--muted); }
    .search:focus-within { border-color: var(--accent); }
    .search input { width: 100%; min-width: 0; border: 0; outline: none; background: transparent; color: var(--ink); font-size: 11px; }
    .search input::placeholder { color: var(--soft); }
    kbd { font: 10px var(--font-mono); border: 1px solid var(--card-rule); border-radius: 3px; padding: 1px 4px; color: var(--muted); }
    .sidebar-section { padding: 0 12px 18px; }
    .section-label { display: flex; justify-content: space-between; align-items: center; padding: 7px 8px 12px; font: 9px var(--font-mono); letter-spacing: 1.2px; color: var(--muted); text-transform: uppercase; }
    .arm-button, .module-button { width: 100%; display: flex; align-items: center; gap: 9px; text-align: left; padding: 10px 9px; border-radius: 6px; min-height: 37px; }
    .arm-button { font-size: 11px; margin: 2px 0; }
    .arm-button[aria-pressed="true"] { background: var(--head-wash); color: var(--ink); border-color: var(--card-rule); }
    .dot { width: 6px; height: 6px; flex: 0 0 6px; border-radius: 50%; background: var(--arm, var(--accent)); box-shadow: 0 0 9px color-mix(in srgb, var(--arm, var(--accent)) 25%, transparent); }
    .arm-button .count { margin-left: auto; color: var(--soft); font: 10px var(--font-mono); }
    .arm-meter { width: 25px; height: 3px; background: var(--head-wash); }
    .arm-meter i { display: block; height: 100%; background: var(--arm); opacity: .8; }
    .modules-section { border-top: 1px solid var(--card-rule); padding-top: 15px; }
    .module-list { max-height: 300px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--card-rule) transparent; }
    .module-button { font: 10px/1.5 var(--font-mono); padding: 8px; }
    .module-button:hover, .module-button[aria-pressed="true"] { background: var(--head-wash); color: var(--ink); }
    .module-button .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .module-button .degree { margin-left: auto; color: var(--soft); font-size: 9px; }
    .empty-list { padding: 12px 8px; color: var(--muted); font-size: 11px; }
    .sidebar-foot { padding: 20px; border-top: 1px solid var(--card-rule); color: var(--muted); font-size: 10px; }
    .sidebar-foot p { margin: 10px 0; }
    .sidebar-foot a { display: block; margin-top: 14px; }
    main { min-width: 0; }
    .scene-head { display: flex; justify-content: space-between; align-items: start; gap: 25px; padding: 30px 32px 20px; }
    .scene-head .eyebrow { color: var(--accent); }
    .scene-head .eyebrow::before { content: ''; display: inline-block; width: 15px; height: 1px; background: currentColor; vertical-align: middle; margin-right: 9px; }
    h1 { font-size: clamp(27px, 3vw, 39px); font-weight: 450; letter-spacing: -1.4px; line-height: 1.2; margin: 9px 0 10px; }
    .scene-head p { color: var(--muted); font-size: 12px; }
    .stats { display: flex; gap: 25px; padding-top: 9px; flex-shrink: 0; }
    .stats b { display: block; font: 18px/1.5 var(--font-mono); color: var(--ink); }
    .stats span { font: 9px var(--font-mono); text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
    .graph-shell { margin: 0 24px; border: 1px solid var(--card-rule); border-radius: 12px; overflow: hidden; background: var(--paper); box-shadow: 0 12px 35px var(--shadow); }
    .graph-topline { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 17px; background: var(--panel); border-bottom: 1px solid var(--card-rule); }
    .graph-label { font: 10px var(--font-mono); color: var(--ink); letter-spacing: .7px; }
    .graph-label small { color: var(--muted); font-size: 9px; margin-left: 10px; letter-spacing: 0; }
    .graph-topline a { font: 10px var(--font-mono); white-space: nowrap; }
    .graph-area { position: relative; background-image: radial-gradient(var(--grid) .7px, transparent .7px); background-size: 20px 20px; }
    .plate { padding: 0; overflow: hidden; }
    .plate svg { width: 100%; min-width: 0; height: clamp(410px, 61vh, 760px); cursor: grab; }
    .plate svg:active { cursor: grabbing; }
    .bg { fill: transparent; }
    .node rect { fill: var(--card); stroke: color-mix(in srgb, var(--node-color, var(--accent)) 45%, var(--card-rule)); stroke-width: 1.25; }
    .node text { font-family: var(--font-mono); font-size: 11px; fill: var(--ink); }
    .node .srcb text { font-size: 8px; }
    .node .srcb rect { fill: var(--head-wash); stroke: var(--card-rule); }
    .node:hover > rect, .node:focus-visible > rect { stroke: var(--node-color, var(--accent)); stroke-width: 2.5; }
    .node.selected > rect { fill: color-mix(in srgb, var(--selection) 14%, var(--card)); stroke: var(--selection); stroke-width: 2.5; }
    .node.up > rect { stroke: var(--up); stroke-width: 2; }
    .node.down > rect { stroke: var(--down); stroke-width: 2; }
    .node.both > rect { stroke: var(--selection); stroke-width: 2; stroke-dasharray: 4 2; }
    .rel, .rev { stroke: var(--edge); stroke-linejoin: round; stroke-linecap: round; opacity: .75; }
    .rev { stroke-dasharray: 5 4; }
    .rel.up, .rev.up { stroke: var(--up); opacity: 1; }
    .rel.down, .rev.down { stroke: var(--down); opacity: 1; }
    .mk-muted { fill: var(--edge); }
    .mk-link { fill: var(--edge); }
    .dim, .arm-dim { opacity: .12; }
    path.dim { opacity: .06; }
    .node { transition: opacity .16s; }
    .graph-bottom { display: flex; justify-content: space-between; align-items: center; gap: 15px; padding: 10px 14px; border-top: 1px solid var(--card-rule); background: var(--panel); }
    .legend { display: flex; flex-wrap: wrap; gap: 14px; color: var(--muted); font: 9px var(--font-mono); }
    .legend span { display: inline-flex; align-items: center; gap: 6px; }
    .legend i { width: 15px; height: 2px; background: var(--edge); }
    .legend .incoming { background: var(--up); }
    .legend .outgoing { background: var(--down); }
    .legend .cycle { height: 0; background: transparent; border-top: 2px dashed var(--edge); }
    .toolbar { display: flex; align-items: center; gap: 3px; }
    .toolbar button { min-width: 33px; height: 32px; border-radius: 5px; font-size: 14px; }
    .toolbar button:hover { background: var(--head-wash); }
    .toolbar .fit { font: 10px var(--font-mono); padding: 0 9px; }
    .zoom-readout { font: 9px var(--font-mono); color: var(--muted); min-width: 37px; text-align: center; }
    .canvas-help { display: flex; justify-content: space-between; gap: 16px; margin: 12px 27px 23px; color: var(--soft); font: 9px/1.6 var(--font-mono); }
    .selection-panel { margin: 0 24px 24px; padding: 20px; border: 1px solid var(--card-rule); border-radius: 10px; background: var(--panel); }
    .selection-id { font: 16px/1.5 var(--font-mono); margin-top: 8px; overflow-wrap: anywhere; color: var(--ink); }
    .selection-head { display: flex; align-items: start; justify-content: space-between; gap: 16px; }
    .selection-head button { padding: 6px 10px; border: 1px solid var(--card-rule); border-radius: 5px; font-size: 11px; }
    .selection-empty { display: flex; align-items: center; gap: 16px; }
    .selection-icon { flex: none; width: 40px; height: 40px; display: grid; place-items: center; border: 1px solid var(--card-rule); border-radius: 9px; color: var(--accent); font-size: 22px; }
    .selection-empty strong { color: var(--ink); font-weight: 500; }
    .selection-empty p, .selection-note { font-size: 11px; color: var(--muted); margin-top: 4px; }
    .connections { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-top: 18px; }
    .connections h3 { font: 10px var(--font-mono); margin-bottom: 10px; color: var(--up); }
    .connections .out h3 { color: var(--down); }
    .connection-list { display: flex; flex-wrap: wrap; gap: 6px; max-height: 160px; overflow-y: auto; }
    .connection-list button { padding: 5px 8px; border: 1px solid var(--card-rule); border-radius: 5px; font: 10px var(--font-mono); color: var(--ink); overflow-wrap: anywhere; text-align: left; }
    .connection-list button:hover { border-color: var(--accent); background: var(--head-wash); }
    .connection-list small { margin-left: 8px; color: var(--soft); font-size: 9px; }
    .connection-list p { color: var(--muted); font-size: 11px; }
    .details-area { padding: 7px 24px 40px; }
    .details-heading { display: flex; justify-content: space-between; align-items: end; margin-bottom: 17px; }
    h2 { font-size: 19px; font-weight: 500; letter-spacing: -.4px; color: var(--ink); }
    .details-heading .eyebrow { margin-bottom: 6px; }
    .details-heading > span { color: var(--soft); font: 10px var(--font-mono); }
    details { border: 1px solid var(--card-rule); background: var(--panel); border-radius: 9px; margin-bottom: 10px; overflow: hidden; }
    summary { padding: 16px 18px; cursor: pointer; color: var(--ink); font-size: 12px; }
    summary small { margin-left: 12px; font-size: 10px; color: var(--muted); }
    .detail-body { padding: 0 18px 19px; color: var(--muted); font-size: 12px; }
    .detail-body p { margin: 8px 0 13px; overflow-wrap: anywhere; }
    pre.ascii { font: 11px/1.5 var(--font-mono); background: var(--paper); border: 1px solid var(--card-rule); border-radius: 7px; padding: 16px; overflow-x: auto; color: var(--ink); }
    .table-scroll { overflow-x: auto; margin-top: 15px; }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 11px; }
    th { color: var(--soft); font: 9px var(--font-mono); letter-spacing: 1px; text-transform: uppercase; }
    th, td { padding: 10px; border-bottom: 1px solid var(--card-rule); vertical-align: top; }
    td:first-child { color: var(--ink); }
    .mono, code { font-family: var(--font-mono); }
    .ask { padding-left: 17px; }
    .ask li { margin: 13px 0; }
    .ask code { display: block; color: var(--ink); overflow-wrap: anywhere; font-size: 11px; }
    .why { font-size: 11px; }
    .source-note { color: var(--soft); font: 9px/1.7 var(--font-mono); margin-top: 21px; overflow-wrap: anywhere; }
    .skip-link { position: absolute; top: -50px; left: 20px; z-index: 10; padding: 10px; background: var(--card); }
    .skip-link:focus { top: 10px; }
    @media (min-width: 1600px) { .scene-head { padding: 35px 40px 25px; } .graph-shell, .selection-panel { margin-left: 32px; margin-right: 32px; } .details-area { padding-left: 32px; padding-right: 32px; } }
    @media (max-width: 1100px) { .stats { gap: 14px; } .stats b { font-size: 16px; } .scene-head { padding: 25px 24px 20px; } h1 { font-size: 30px; } .graph-bottom { flex-wrap: wrap; } .toolbar { margin-left: auto; } }
    @media (max-width: 800px) {
      .topbar { padding: 0 16px; height: 58px; } .brand small { display: none; } .header-actions { gap: 10px; } .view-tag { font-size: 8px; }
      .workspace { grid-template-columns: minmax(0,1fr); } .explorer { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--card-rule); overflow: visible; }
      .sidebar-head { padding: 16px; display: flex; align-items: center; gap: 14px; } .repo { font-size: 17px; margin: 2px 0; } .repo-note, .sidebar-head .eyebrow { display: none; }
      .search { margin-top: 0; flex: 1; min-width: 0; } .sidebar-section { padding: 0 12px 12px; } .sidebar-section > .section-label { display: none; }
      .arm-list { display: flex; gap: 6px; overflow-x: auto; } .arm-button { width: auto; flex-shrink: 0; padding: 8px 10px; border: 1px solid var(--card-rule); font-size: 10px; } .arm-button .count { margin-left: 3px; } .arm-meter { display: none; }
      .modules-section { display: none; } .explorer.searching .modules-section { display: block; } .module-list { max-height: 180px; } .sidebar-foot { display: none; }
      .scene-head { padding: 23px 17px 18px; gap: 18px; } h1 { font-size: 27px; letter-spacing: -1px; } .scene-head p { font-size: 11px; } .stats { gap: 11px; } .stats span { font-size: 8px; letter-spacing: .5px; } .stats b { font-size: 15px; }
      .graph-shell { margin: 0 12px; border-radius: 9px; } .graph-topline { padding: 11px 12px; } .graph-label small { display: none; } .plate svg { height: 440px; }
      .graph-bottom { gap: 9px; padding: 9px 10px; } .legend { gap: 10px; font-size: 8px; } .toolbar button { min-width: 38px; min-height: 38px; }
      .canvas-help { margin: 10px 15px 17px; font-size: 8px; } .canvas-help > span:last-child { display: none; }
      .selection-panel { margin: 0 12px 22px; padding: 16px; } .details-area { padding: 0 12px 30px; } .selection-id { font-size: 13px; } .connections { gap: 18px; } summary small { display: none; }
    }
    @media (max-width: 480px) { .view-tag { display: none; } .selection-head { flex-wrap: wrap; } .scene-head { flex-wrap: wrap; } .stats { padding-top: 0; gap: 26px; } .stats b { display: inline; margin-right: 5px; } .stats span { font-size: 8px; } .header-actions > a { font-size: 10px; } .connections { grid-template-columns: 1fr; } .sidebar-head { gap: 10px; } .repo { max-width: 120px; } .details-heading > span { display: none; } .plate svg { height: 290px; } }
    @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } .node { transition: none; } }
"""

_ATLAS_SCRIPT = """<script>
(function(){
  const DATA = __ATLAS_DATA__;
  const svg = document.querySelector('svg[data-interactive="1"]');
  const $ = id => document.getElementById(id);
  const nodes = new Map(DATA.nodes.map(n => [n.id,n]));
  const groups = new Map(Array.from(svg.querySelectorAll('g.node')).map(n => [n.dataset.id,n]));
  const paths = Array.from(svg.querySelectorAll('path[data-from]'));
  const incoming = new Map(DATA.nodes.map(n => [n.id,[]])), outgoing = new Map(DATA.nodes.map(n => [n.id,[]]));
  const weights = new Map();
  DATA.edges.forEach(e => { incoming.get(e.target)?.push(e); outgoing.get(e.source)?.push(e); weights.set(JSON.stringify([e.source,e.target]), e.weight); });
  const maxWeight = Math.max(1,...DATA.edges.map(e => e.weight));
  const notify = (name, detail) => svg.dispatchEvent(new CustomEvent('graphy-'+name, {detail}));
  let activeArm = '', selection = null, searchFrame = 0, fittedWidth = 0;
  for (const n of DATA.nodes) {
    const g = groups.get(n.id);
    if (!g) continue;
    g.style.setProperty('--node-color', `var(--arm-${n.color})`);
    g.querySelector('rect').setAttribute('rx','6');
    const title = document.createElementNS('http://www.w3.org/2000/svg','title');
    title.textContent = `${n.id}\n${n.arm} · ${incoming.get(n.id).length} incoming · ${outgoing.get(n.id).length} outgoing connections`;
    g.prepend(title);
  }
  paths.forEach(p => {
    const weight = weights.get(JSON.stringify([p.dataset.from,p.dataset.to])) || 1;
    p.style.strokeWidth = String(.7 + 1.8 * Math.log1p(weight)/Math.log1p(maxWeight));
    const title = document.createElementNS('http://www.w3.org/2000/svg','title');
    title.textContent = `${p.dataset.from} → ${p.dataset.to}\n${weight} dependencies`;
    p.append(title);
  });
  // Marker color follows the focus direction, including reversed layout routes.
  for (const [name,token] of [['incoming','up'],['outgoing','down']]) {
    const marker = svg.querySelector('#arrow').cloneNode(true);
    marker.id = `arrow-${name}`;
    marker.querySelector('polygon').style.fill = `var(--${token})`;
    svg.querySelector('defs').append(marker);
  }
  function edgeMarkers(){
    paths.forEach(p => {
      const direction = p.classList.contains('up') ? 'incoming' : p.classList.contains('down') ? 'outgoing' : '';
      p.setAttribute('marker-end', `url(#arrow${direction ? '-'+direction : ''})`);
    });
  }
  const moduleButtons = new Map();
  const ranked = [...DATA.nodes].sort((a,b) => incoming.get(b.id).length-incoming.get(a.id).length || a.id.localeCompare(b.id));
  ranked.forEach(n => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'module-button';
    button.title = n.id; button.setAttribute('aria-label', 'Inspect '+n.id); button.setAttribute('aria-pressed','false');
    const dot = document.createElement('i'); dot.className = 'dot'; dot.style.setProperty('--arm',`var(--arm-${n.color})`);
    const name = document.createElement('span'); name.className = 'name'; name.textContent = n.label;
    const degree = document.createElement('span'); degree.className = 'degree'; degree.textContent = incoming.get(n.id).length+' in';
    button.append(dot,name,degree); button.addEventListener('click', () => select(n.id));
    $('module-list').append(button); moduleButtons.set(n.id,button);
  });
  function select(id){
    notify('focus',id);
    notify('fit',[id, ...incoming.get(id).map(e=>e.source), ...outgoing.get(id).map(e=>e.target)]);
    if (window.matchMedia('(max-width: 800px)').matches) $('selection-panel').scrollIntoView({block:'nearest'});
  }
  function applyArm(){
    groups.forEach((g,id) => g.classList.toggle('arm-dim', !selection && !!activeArm && nodes.get(id)?.arm !== activeArm));
    paths.forEach(p => p.classList.toggle('arm-dim', !selection && !!activeArm && nodes.get(p.dataset.from)?.arm !== activeArm && nodes.get(p.dataset.to)?.arm !== activeArm));
  }
  function filterList(){
    if (searchFrame) cancelAnimationFrame(searchFrame);
    searchFrame = 0;
    const query = $('module-search').value.trim().toLowerCase(); let count = 0;
    $('explorer').classList.toggle('searching', !!query);
    moduleButtons.forEach((button,id) => {
      const n = nodes.get(id), visible = (!activeArm || n.arm === activeArm) && (!query || n.id.toLowerCase().includes(query));
      button.hidden = !visible; if (visible) count++;
    });
    $('module-count').textContent = String(count);
    $('no-results').hidden = count > 0;
    $('no-results').textContent = DATA.nodes.length ? 'No matching modules. Try another name or choose All arms.' : 'No module connections meet the weight floor. Explore the pillars below.';
  }
  $('module-search').addEventListener('input', () => { if (!searchFrame) searchFrame = requestAnimationFrame(filterList); });
  $('module-search').addEventListener('keydown', e => {
    if (e.key === 'Enter') { filterList(); const first = [...moduleButtons.entries()].find(([,button]) => !button.hidden); if (first) select(first[0]); }
    if (e.key === 'Escape') { $('module-search').value = ''; filterList(); }
  });
  const armButtons = Array.from(document.querySelectorAll('[data-arm]'));
  armButtons.forEach(button => button.addEventListener('click', () => {
    activeArm = button.dataset.arm;
    armButtons.forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    notify('clear'); filterList(); applyArm();
    $('graph-context').textContent = activeArm ? activeArm+' highlighted' : 'All arms';
    notify('fit', activeArm ? DATA.nodes.filter(n => n.arm === activeArm).map(n => n.id) : undefined);
  }));
  function renderConnections(host, edges, direction){
    host.replaceChildren();
    for (const edge of [...edges].sort((a,b) => b.weight-a.weight)) {
      const id = direction === 'in' ? edge.source : edge.target, n = nodes.get(id);
      const button = document.createElement('button'); button.type = 'button'; button.title = `${edge.source} → ${edge.target} · ${edge.weight} dependencies`;
      button.append(document.createTextNode(n?.label || id));
      const weight = document.createElement('small'); weight.textContent = String(edge.weight); button.append(weight);
      button.addEventListener('click', () => select(id)); host.append(button);
    }
    if (!edges.length) { const p = document.createElement('p'); p.textContent = 'None in this view'; host.append(p); }
  }
  svg.addEventListener('graphy-selection', e => {
    selection = e.detail;
    $('selection-empty').hidden = !!selection; $('selection-detail').hidden = !selection;
    moduleButtons.forEach((b,id) => b.setAttribute('aria-pressed', String(selection?.id === id)));
    applyArm(); edgeMarkers();
    $('graph-context').textContent = selection ? 'Tracing '+nodes.get(selection.id).label : activeArm ? activeArm+' highlighted' : 'All arms';
    if (!selection) { $('graph-status').textContent = `${DATA.nodes.length} groups · ${DATA.edges.length} connections · drag to pan`; return; }
    const id = selection.id, n = nodes.get(id), ins = incoming.get(id), outs = outgoing.get(id);
    $('selection-name').textContent = id;
    $('selection-arm').textContent = n.arm+' / module group';
    $('incoming-title').textContent = `← Depended on by · ${ins.length}`;
    $('outgoing-title').textContent = `Depends on → · ${outs.length}`;
    $('selection-note').textContent = `Direct connections below. Highlighted paths include transitive reach: ${selection.incoming.length} upstream · ${selection.outgoing.length} downstream. Numbers on connections count dependencies.`;
    renderConnections($('incoming-list'), ins, 'in'); renderConnections($('outgoing-list'), outs, 'out');
    $('graph-status').textContent = `${n.label} · ${selection.incoming.length} upstream · ${selection.outgoing.length} downstream`;
  });
  $('clear-selection').addEventListener('click', () => notify('clear'));
  $('focus-selection').addEventListener('click', () => {
    if (selection) notify('fit',[selection.id, ...incoming.get(selection.id).map(e=>e.source), ...outgoing.get(selection.id).map(e=>e.target)]);
  });
  $('zoom-in').addEventListener('click', () => notify('zoom',.8));
  $('zoom-out').addEventListener('click', () => notify('zoom',1.25));
  $('fit-graph').addEventListener('click', () => { notify('fit'); });
  svg.addEventListener('graphy-viewport', e => { if (!fittedWidth) fittedWidth = e.detail.w; $('zoom-level').textContent = Math.round(fittedWidth/e.detail.w*100)+'%'; });
  $('theme-toggle').addEventListener('click', () => {
    const light = document.documentElement.dataset.theme !== 'light';
    document.documentElement.dataset.theme = light ? 'light' : 'dark';
    $('theme-toggle').textContent = light ? 'Dark' : 'Light';
    $('theme-toggle').setAttribute('aria-label', 'Switch to '+(light ? 'dark' : 'light')+' theme');
  });
  document.addEventListener('keydown', e => {
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !e.target.matches('input,textarea,[contenteditable="true"]')) { e.preventDefault(); $('module-search').focus(); }
  });
  let size = '';
  new ResizeObserver(entries => {
    const r = entries[0].contentRect, next = `${Math.round(r.width)}:${Math.round(r.height)}`;
    if (!r.width || !r.height || next === size) return;
    size = next; fittedWidth = 0; notify('fit');
  }).observe(svg);
  filterList();
  if (!DATA.nodes.length) {
    $('graph-status').textContent = 'No connections with at least 2 dependencies. See the pillars below.';
    $('selection-empty').querySelector('strong').textContent = 'A quiet module map.';
    $('selection-empty').querySelector('p').textContent = 'No connections meet this view’s weight floor. Open the pillars below to explore the architecture.';
  }
})();
</script>
"""
