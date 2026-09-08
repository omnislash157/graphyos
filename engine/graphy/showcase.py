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
from pathlib import Path

from graphy import draw as draw_lane
from graphy import fanout, pillars as pillars_lane
from graphy import sugiyama as S

__all__ = ["ShowcaseError", "clone_dir", "compose", "fence_safe", "repo_of", "showcase", "PAGE", "TEXT"]

PAGE, TEXT = "index.html", "showcase.txt"


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
    tenant = f"--tenant {desc} --tenant-id {package}"
    from graphy.cli import mcp_args
    mcp = json.dumps({"mcpServers": {"graphy": {"command": graphy_cmd[0],
                                                 "args": graphy_cmd[1:] + mcp_args(desc, package)}}}, indent=2)
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
             "ADD YOUR MODEL — paste into .mcp.json (Claude Code) or your client's MCP settings; any model, the walk is graphy's:"]
    text += ["  " + ln for ln in mcp.splitlines()]
    text += ["", "ASK IT"] + [f"  {cmd}\n      # {why}" for cmd, why in asks]
    text += ["", "HOW IT WAS MADE", f"  pip install graphyos && cd <repo> && graphy eat . && graphy showcase .",
             "  No model drew this. Every edge is structural, a wormhole, or a label resolved through the code's own scope.", ""]

    css_extra = """
    .grid { display: grid; grid-template-columns: 1fr; gap: 1.5rem; }
    pre.ascii { font-family: var(--font-mono); font-size: 11px; line-height: 1.2; overflow-x: auto; background: var(--card);
                border: 1px solid var(--card-rule); border-radius: 6px; padding: 0.75rem; color: var(--ink); }
    table { border-collapse: collapse; font-size: 0.9rem; width: 100%; }
    th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--card-rule); vertical-align: top; }
    th { color: var(--muted); font-weight: 500; font-family: var(--font-mono); font-size: 0.7rem; letter-spacing: 0.1em; text-transform: uppercase; }
    code, .mono { font-family: var(--font-mono); font-size: 0.85em; }
    h2 { font-size: 1.05rem; font-weight: 600; margin: 1.5rem 0 0.5rem; }
    p.lede { color: var(--muted); max-width: 70ch; }
    .ask li { margin: 0.4rem 0; } .ask .why { color: var(--muted); }
"""
    h = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '  <meta charset="UTF-8">',
         '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
         f"  <title>{_esc(package)} · graphy showcase</title>", "<style>", S._TOKEN_CSS, S._HTML_CSS, css_extra, "</style>",
         "</head>", "<body>", '<div class="frame">',
         '  <p class="eyebrow">DRAWN BY GRAPHY · ONE COMMAND · NO MODEL</p>',
         f"  <h1>{_esc(package)}</h1>",
         f'  <p class="lede">{_esc(origin)} — every edge below is structural, a wormhole between packages, or a label resolved '
         'through the code\'s own scope. Click a module to light what reaches it and what it reaches; Esc clears.</p>',
         '  <h2>The modules</h2>', '  <div class="plate">', svg, "  </div>",
         '  <h2>The pillars — the arms the walk proposes</h2>',
         f'  <pre class="ascii">{_esc(ascii_p)}</pre>',
         "  <table><tr><th>arm</th><th>crown</th><th>units</th><th>the evidence</th></tr>"]
    h += [f"  <tr><td><b>{_esc(a)}</b></td><td class=\"mono\">{_esc(c)}</td><td>{n}</td><td>{_esc(e)}</td></tr>" for a, c, n, e in arms_rows]
    h += ["  </table>",
          f'  <h2>The ring</h2><p class="lede">{len(minted)} package(s) minted beside {_esc(package)}: <span class="mono">{_esc(", ".join(minted) or "none")}</span>. '
          f'Not carried: <span class="mono">{_esc(", ".join(sorted(unresolved)) or "nothing — the ring closed")}</span>.</p>',
          '  <h2>Add your model</h2><p class="lede">Paste this into <code>.mcp.json</code> (Claude Code) or your client\'s MCP settings. Any model; the walk is graphy\'s.</p>',
          f'  <pre class="ascii">{_esc(mcp)}</pre>',
          '  <h2>Ask it</h2><ul class="ask">']
    h += [f'    <li><code>{_esc(cmd)}</code><br><span class="why">{_esc(why)}</span></li>' for cmd, why in asks]
    h += ["  </ul>", '  <h2>How it was made</h2>',
          '  <pre class="ascii">pip install graphyos\ncd &lt;repo&gt; &amp;&amp; graphy eat . &amp;&amp; graphy showcase .</pre>',
          "</div>"]
    if script:
        h.append(script)
    h += ["</body>", "</html>"]
    return "\n".join(h) + "\n", fence_safe("\n".join(text))


_SEG = r"[A-Za-z0-9_~][A-Za-z0-9_.-]*"      # a path segment: never `.`, `..` or `.git`; `~user` is sr.ht's owner
_REPO = re.compile(r"^(?:[a-z][a-z0-9+.-]*://(?:[^/@]*@)?(?P<host>[^/]+)/|(?:[^@]*@)?(?P<sshhost>[^:/]+):|/)"
                   r"(?P<owner>" + _SEG + r"(?:/" + _SEG + r")*)/(?P<name>" + _SEG + r"?)(?:\.git)?/?$")


def _parse(url: str) -> tuple[str, str, str]:
    m = _REPO.match(url.strip())
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
    if (repo / ".git").is_dir():
        # A directory that stands is reused only when it is a clone of the url asked for: the origin is read
        # from the clone itself, and a mismatch refuses by name — never a page drawn from another repo's tree.
        proc = subprocess.run(["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
                              capture_output=True, text=True)
        if proc.returncode not in (0, 1):                       # 1 is git's "no such key"; anything else, git refused
            raise ShowcaseError(f"{repo} stands but git cannot read it: {(proc.stderr or '').strip()[-300:]}")
        origin = (proc.stdout or "").strip()
        if not _same_repo(origin, url):
            raise ShowcaseError(f"{repo} is a clone of {_shown(origin) or '<no origin>'}, not {_shown(url)}")
        log(f"SHOWCASE: reusing the clone at {repo}")
    else:
        work.mkdir(parents=True, exist_ok=True)
        log(f"SHOWCASE: git clone --depth 1 {url} {repo}")
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
    from graphy.cli import _load_tenant, _roster, _graphy_command, main as cli_main
    log = log or (lambda *_: None)
    t0 = time.perf_counter()
    if target.startswith(("http://", "https://", "git@")):
        if work is None:                                         # graphyos #43: the clone lands where you stand, said so
            work = Path.cwd() / "showcase"
            log(f"SHOWCASE: no --work — the clone lands under {work.resolve()} (the current directory); "
                f"--work <dir> puts it elsewhere")
        repo = _clone(target, Path(work).resolve(), log)
        origin = target
    else:
        repo = Path(target).resolve()
        origin = str(repo)
    if not repo.is_dir():
        raise ShowcaseError(f"not a directory: {repo}")
    home = repo / ".graphy"
    desc = home / "tenant.json"
    stale = None
    if desc.is_file():                                   # graphyos #39: a store behind the working tree is re-eaten
        from graphy.cartograph import cursor_drift
        try:
            stale = cursor_drift(json.loads(desc.read_text(encoding="utf-8")).get("cursor", ""), repo, exclude=(home,))
        except (OSError, ValueError, AttributeError) as exc:
            stale = f"the descriptor at {desc} is unreadable ({exc})"
        if stale:
            log(f"SHOWCASE: {stale} — eating again")
    if not desc.is_file() or stale:
        argv = ["eat", str(repo)] + (["--no-provision"] if no_provision else [])
        rc = (eat or (lambda r: cli_main(argv)))(repo)
        if rc != 0:
            raise ShowcaseError(f"eat exited {rc} for {repo}")
    ring = json.loads((home / "substrate" / "ring.json").read_text(encoding="utf-8"))
    package = ring["root"]
    tenant = _load_tenant(str(desc))
    roster = _roster(tenant)
    store = (open_store or (lambda: fstore.open_for(roster, tenant=tenant, tenant_id=package)))()
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
    red = S.check_artifact(out_dir / PAGE)
    return {"repo": str(repo), "package": package, "page": str(out_dir / PAGE), "text": str(out_dir / TEXT),
            "arms": list(proposal.arms), "ring": len(ring.get("minted", {})) - 1, "check": red,
            "seconds": round(time.perf_counter() - t0, 1)}
