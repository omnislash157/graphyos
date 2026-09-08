#!/usr/bin/env python3
"""gallery — ten showcases of repos people know, one index, one receipt (graphyos #47).

    python3 gallery.py [--jobs N] <out dir> <git url>…   (bash gallery.sh does the same with the project's venv)

For every url: `graphy showcase <url> --no-provision --work <out>/.work --out <out>/<slug>/` — the clone is
shallow, nothing of the stranger's repo executes. Then `<out>/index.html`, the list of pages with each
repo's arms and ring read from its showcase.txt and the MCP block on top, and `<out>/gallery.json`, the
receipt: every url, its clone's commit, the SHOWCASE line it ended on, the page's check. A page that is
RED or REFUSED is named in the receipt and left out of the index — never a hollow entry. The directory is
the site: `python3 -m http.server --directory <out>` serves it, and the Dockerfile at the repo root builds
it inside the image so every Railway deploy is a fresh gallery on the current engine.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

try:
    from graphy.showcase import clone_dir, repo_of   # one parse: the slug and the clone dir come from it (graphyos #58)
except ImportError as exc:
    if "graphy" in sys.modules:                      # a graphy is on the path and it predates the key: say so, never guess
        sys.stderr.write(f"GALLERY REFUSED: the graphy on the path has no showcase.repo_of ({exc}) — "
                         f"the gallery runs on the engine from this checkout (bash gallery.sh)\n")
        sys.exit(2)
    sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))   # no graphy at all: this checkout's engine
    from graphy.showcase import clone_dir, repo_of

PAGE = "index.html"
TEXT = "showcase.txt"
_URL = re.compile(r"^https://(github\.com|gitlab\.com)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(\.git)?/?$")
_ARM = re.compile(r"^  (\S+)\s+(crown|the floor)\s")
_RING = re.compile(r"^THE RING: (\d+) package\(s\) minted beside (\S+)")
_OK = re.compile(r"^SHOWCASE OK: (\S+) · (\d+) arm\(s\) \(([^)]*)\) · (\d+) ring shard\(s\) · CHECK (GREEN|RED[^·]*) · ([\d.]+)s")


class GalleryError(Exception):
    pass


def slug_of(url: str) -> tuple[str, str]:
    """(slug, 'owner/name') from a github or gitlab https url; anything else refuses."""
    if not _URL.match(url.strip()):
        raise GalleryError(f"not a github.com or gitlab.com repo url: {url!r}")
    owner, name = repo_of(url)
    return re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-") or "repo", f"{owner}/{name}"


def read_text_page(text: str) -> dict:
    """What the index says about a page, read from its showcase.txt: the arms in order (name, crown), the
    ring's count and names."""
    arms: list[dict] = []
    ring = {"count": 0, "names": ""}
    for line in text.splitlines():
        m = _ARM.match(line)
        if m:
            rest = line[m.end():].strip()
            crown = rest.split("  ")[0].strip()
            arms.append({"name": m.group(1), "kind": "floor" if m.group(2) == "the floor" else "crown", "crown": crown})
            continue
        m = _RING.match(line)
        if m:
            ring["count"] = int(m.group(1))
            ring["names"] = line.split(":", 2)[-1].strip() if line.count(":") >= 2 else ""
    return {"arms": arms, "ring": ring}


def _run_showcase(graphy: list[str], url: str, out: Path, work: Path, log) -> dict:
    slug, full = slug_of(url)
    page_dir = out / slug
    argv = [*graphy, "showcase", url, "--no-provision", "--work", str(work), "--out", str(page_dir)]
    log(f"GALLERY: {full} -> {page_dir}")
    t0 = time.perf_counter()
    proc = subprocess.run(argv, capture_output=True, text=True)
    lines = [ln for ln in (proc.stdout + proc.stderr).splitlines() if ln.startswith("SHOWCASE ")]
    last = next((ln for ln in reversed(lines) if ln.startswith(("SHOWCASE OK", "SHOWCASE REFUSED", "SHOWCASE RED"))),
                lines[-1] if lines else f"SHOWCASE exited {proc.returncode} with no SHOWCASE line")
    entry = {"url": url, "repo": full, "slug": slug, "line": last, "rc": proc.returncode,
             "seconds": round(time.perf_counter() - t0, 1), "commit": None, "check": None, "arms": [], "ring": None}
    clone = clone_dir(work, url)                     # the same key the showcase clones under (graphyos #58)
    if (clone / ".git").is_dir():
        head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True)
        entry["commit"] = head.stdout.strip() or None
    m = _OK.match(last)
    if proc.returncode == 0 and m and (page_dir / PAGE).is_file() and (page_dir / TEXT).is_file():
        from graphy import sugiyama as S     # the page's own done-token check, a second time, here
        entry["check"] = S.check_artifact(page_dir / PAGE)
        entry["package"] = m.group(1)
        entry.update(read_text_page((page_dir / TEXT).read_text(encoding="utf-8")))
    log(f"GALLERY: {full}: {last}")
    return entry


def _mcp_block(text: str) -> str:
    """The MCP block from a showcase.txt, verbatim, for the top of the index."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("ADD YOUR MODEL"):
            block = []
            for ln2 in lines[i + 1:]:
                if ln2.strip() == "" and block and block[-1].strip() == "}":
                    break
                block.append(ln2)
            return "\n".join(block).rstrip()
    return ""


def compose_index(pages: list[dict], *, built_at: str, engine: str, mcp: str = "") -> str:
    """The index: every green page linked with its arms and ring; nothing else listed."""
    green = [p for p in pages if p.get("rc") == 0 and p.get("check") == []]
    rows = []
    for p in green:
        arms = " · ".join(f"<b>{html.escape(a['name'])}</b> <small>({html.escape(a['crown'])})</small>" for a in p["arms"]) or "one pillar"
        ring = p.get("ring") or {"count": 0, "names": ""}
        rows.append(
            f'<li><a href="{html.escape(p["slug"])}/{PAGE}">{html.escape(p["repo"])}</a>'
            f'<div class="arms">{arms}</div>'
            f'<div class="ring">ring: {ring["count"]} package(s){(" — " + html.escape(ring["names"])) if ring["names"] and ring["count"] else ""}</div></li>')
    mcp_html = f'<pre class="mcp">{html.escape(mcp)}</pre>' if mcp else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>graphy — the gallery</title>
<style>
:root{{color-scheme:light dark;--fg:#1a1a1a;--bg:#fafaf8;--mute:#666;--line:#ddd;--acc:#2a5db0}}
@media(prefers-color-scheme:dark){{:root{{--fg:#e8e8e6;--bg:#151515;--mute:#9a9a9a;--line:#333;--acc:#8ab4f8}}}}
body{{margin:0;padding:2rem 1rem 4rem;font:16px/1.5 system-ui,sans-serif;color:var(--fg);background:var(--bg);max-width:56rem;margin-inline:auto}}
h1{{font-size:1.6rem;margin:0 0 .25rem}} p.lede{{color:var(--mute);margin:0 0 1.5rem}}
pre{{overflow-x:auto;padding:1rem;border:1px solid var(--line);border-radius:6px;font-size:13px;background:transparent}}
ul{{list-style:none;padding:0}} li{{padding:1rem 0;border-top:1px solid var(--line)}} li:last-child{{border-bottom:1px solid var(--line)}}
a{{color:var(--acc);font-weight:600;font-size:1.1rem}} .arms{{margin-top:.25rem}} .ring,small{{color:var(--mute);font-size:.9rem}}
code{{font-size:.95em}} footer{{margin-top:2rem;color:var(--mute);font-size:.85rem}}
</style></head><body>
<h1>graphy — the gallery</h1>
<p class="lede">{len(green)} codebase(s), each drawn by one command: the modules, the pillars the walk proposes, the dependency ring, and the MCP block. No model decided an edge. Every page is a query over the code's own structure.</p>
<pre>uvx --from 'graphyos[typescript]' graphy showcase .        # your own repo, one page, no venv
pip install 'graphyos[typescript]' &amp;&amp; graphy showcase https://github.com/you/your-repo.git</pre>
<p>Or open an issue on <a href="https://github.com/omnislash157/graphyos/issues/new">omnislash157/graphyos</a> naming a GitHub url — the CI posts your repo's page back, running nothing of your code.</p>
<ul>
{chr(10).join(rows)}
</ul>
<h2>Add your model</h2>
<p>Paste into <code>.mcp.json</code> (Claude Code) or your client's MCP settings after <code>graphy eat .</code> — six tools: hunt · descend · blast · walk · draw · explain.</p>
{mcp_html}
<footer>built {html.escape(built_at)} · graphyos {html.escape(engine)} · <a href="https://github.com/omnislash157/graphyos">source, Apache 2.0</a> · <a href="https://pypi.org/project/graphyos/">PyPI</a></footer>
</body></html>
"""


def jobs_for(n: int, jobs: int | None = None) -> int:
    """How many showcases run at once: `jobs` when given (`--jobs N`), else `GALLERY_JOBS`, else every core —
    never more than the urls, never fewer than 1. A value that is not a count is refused by name."""
    raw = os.environ.get("GALLERY_JOBS") if jobs is None else str(jobs)
    if raw is None:
        return max(1, min(n, os.cpu_count() or 2))
    if not re.fullmatch(r"[0-9]+", raw) or int(raw) < 1:
        raise GalleryError(f"jobs must be a positive integer, not {raw!r} (--jobs N or GALLERY_JOBS)")
    return max(1, min(n, int(raw)))


def build(out: str | Path, urls: list[str], *, graphy: list[str] | None = None, log=print, jobs: int | None = None) -> dict:
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / ".work"
    graphy = graphy or [sys.executable, "-m", "graphy"]
    seen: dict[str, str] = {}
    for u in urls:
        slug, full = slug_of(u)                      # every url refused before any clone
        if slug in seen:                             # two urls of one slug would share a page dir (the clone is
            raise GalleryError(f"two urls share the slug {slug!r}: {seen[slug]} and {full}")   # keyed on owner too, #58)
        seen[slug] = full
    t0 = time.perf_counter()
    # The showcases run side by side (graphyos #55): each is its own subprocess with its own clone under
    # .work/<owner>/<name> and its own --out, and more than half of a sequential build was the parent waiting on
    # one `git clone` at a time. `map` hands the pages back in url order, so the index, the receipt and
    # `green` are the sequential build's byte for byte; only the log lines interleave.
    width = jobs_for(len(urls), jobs)
    if width == 1:                                   # one job is the old build, literally: no pool, no threads
        pages = [_run_showcase(graphy, u, out, work, log) for u in urls]
    else:
        with ThreadPoolExecutor(max_workers=width) as pool:
            pages = list(pool.map(lambda u: _run_showcase(graphy, u, out, work, log), urls))
    from graphy import __version__ as engine
    green = [p for p in pages if p["rc"] == 0 and p["check"] == []]
    mcp = ""
    for p in green:
        mcp = _mcp_block((out / p["slug"] / TEXT).read_text(encoding="utf-8"))
        if mcp:
            break
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (out / PAGE).write_text(compose_index(pages, built_at=built_at, engine=engine, mcp=mcp), encoding="utf-8")
    # `seconds` is the build's wall; `jobs` says how many pages ran at once, so two receipts can be told
    # apart — each page's own `seconds` is its wall while the others ran beside it.
    receipt = {"built_at": built_at, "engine": engine, "seconds": round(time.perf_counter() - t0, 1), "jobs": width,
               "pages": pages, "green": [p["slug"] for p in green],
               "left_out": [{"repo": p["repo"], "line": p["line"], "check": p["check"]} for p in pages if p not in green]}
    (out / "gallery.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    jobs: int | None = None
    if argv[:1] == ["--jobs"]:                       # --jobs N, before the out dir; GALLERY_JOBS is the other door
        if len(argv) < 2 or not re.fullmatch(r"[0-9]+", argv[1]) or int(argv[1]) < 1:
            print(f"GALLERY REFUSED: --jobs must be a positive integer, not {argv[1] if len(argv) > 1 else ''!r}", file=sys.stderr)
            return 2
        jobs, argv = int(argv[1]), argv[2:]
    if len(argv) < 2:
        print("GALLERY REFUSED: python3 gallery.py [--jobs N] <out dir> <git url>…", file=sys.stderr)
        return 2
    try:
        r = build(argv[0], argv[1:], jobs=jobs)
    except GalleryError as exc:
        print(f"GALLERY REFUSED: {exc}", file=sys.stderr)
        return 2
    out = Path(argv[0]).resolve()
    for p in r["left_out"]:
        print(f"GALLERY LEFT OUT: {p['repo']} — {p['line']}" + (f" — check: {'; '.join(p['check'])}" if p["check"] else ""))
    print(f"GALLERY OK: {len(r['green'])} page(s) of {len(r['pages'])} checked green -> {out / PAGE} · "
          f"{len(r['left_out'])} left out · receipt {out / 'gallery.json'} · {r['seconds']}s · {r['jobs']} job(s)")
    return 0 if r["green"] and not r["left_out"] else 1


if __name__ == "__main__":
    sys.exit(main())
