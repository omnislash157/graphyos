"""The gallery (graphyos #47): the index and the receipt from showcase pages — a floor over the pure
halves; the proof is the ten-repo run in RECON and the image Railway builds."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("gallery", ROOT / "gallery.py")
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)

TEXT = """httpx — drawn by graphy in one command
  /tmp/x

THE ARMS
  MODELS         crown httpx._models                    4 unit(s) — …
  CLIENT         crown httpx._client                    3 unit(s) — …
  UTILS          the floor httpx._utils                 2 unit(s) — …

THE RING: 2 package(s) minted beside httpx: certifi, idna

ADD YOUR MODEL — paste into .mcp.json (Claude Code) or your client's MCP settings; any model, the walk is graphy's:
  {
    "mcpServers": {
      "graphy": {"command": "graphy", "args": ["mcp"]}
    }
  }

THREE QUESTIONS
"""


def test_slug_of_admits_github_and_gitlab_and_refuses_the_rest():
    assert gallery.slug_of("https://github.com/encode/httpx.git") == ("httpx", "encode/httpx")
    assert gallery.slug_of("https://gitlab.com/Some-Org/My.Repo/") == ("my-repo", "Some-Org/My.Repo")
    for bad in ("git@github.com:encode/httpx.git", "https://example.com/a/b", "https://github.com/onlyowner", "file:///tmp/x"):
        with pytest.raises(gallery.GalleryError):
            gallery.slug_of(bad)


def test_read_text_page_names_the_arms_in_order_and_the_ring():
    got = gallery.read_text_page(TEXT)
    assert [a["name"] for a in got["arms"]] == ["MODELS", "CLIENT", "UTILS"]
    assert got["arms"][0] == {"name": "MODELS", "kind": "crown", "crown": "httpx._models"}
    assert got["arms"][2]["kind"] == "floor" and got["arms"][2]["crown"] == "httpx._utils"
    assert got["ring"] == {"count": 2, "names": "certifi, idna"}
    assert gallery._mcp_block(TEXT).startswith("  {") and '"mcpServers"' in gallery._mcp_block(TEXT)


def test_compose_index_links_only_green_pages_and_never_a_hollow_entry():
    ok = {"repo": "encode/httpx", "slug": "httpx", "rc": 0, "check": [], "arms": gallery.read_text_page(TEXT)["arms"],
          "ring": {"count": 2, "names": "certifi, idna"}}
    red = {"repo": "x/red", "slug": "red", "rc": 0, "check": ["no done token"], "arms": [], "ring": None}
    refused = {"repo": "x/refused", "slug": "refused", "rc": 2, "check": None, "arms": [], "ring": None}
    page = gallery.compose_index([ok, red, refused], built_at="2026-09-08", engine="0.2.1", mcp="{}")
    assert 'href="httpx/index.html"' in page and "encode/httpx" in page
    assert "x/red" not in page and "x/refused" not in page and 'href="red/' not in page
    assert "<b>MODELS</b>" in page and "ring: 2 package(s) — certifi, idna" in page
    assert "1 codebase(s)" in page and "graphyos 0.2.1" in page
    assert "GRAPH" in page and "walk before you read" in page and "graphy harness" in page
    assert "<script" not in page                            # the index is static html and nothing else


def test_build_writes_the_index_and_the_receipt_and_leaves_a_refusal_out(tmp_path, monkeypatch):
    """`build` over a fake graphy: one url ends OK with a checked page, one is REFUSED — the receipt
    names both, the index links one, and the exit is 1 while anything is left out."""
    fake = tmp_path / "fake_graphy.py"
    fake.write_text(
        "import sys, pathlib\n"
        "url = sys.argv[2]; out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])\n"
        "if 'bad' in url:\n    print('SHOWCASE REFUSED: eat exited 2 for x', file=sys.stderr); sys.exit(2)\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "import os; (out / 'showcase.txt').write_text(open(os.environ['GALLERY_TEST_TEXT']).read())\n"
        "(out / 'index.html').write_text('<!doctype html><html><body>GRAPHY_ARTIFACT_OK</body></html>')\n"
        "print('SHOWCASE OK: good · 3 arm(s) (MODELS, CLIENT, UTILS) · 2 ring shard(s) · CHECK GREEN · 0.1s')\n",
        encoding="utf-8")
    text = tmp_path / "text.txt"
    text.write_text(TEXT, encoding="utf-8")
    monkeypatch.setenv("GALLERY_TEST_TEXT", str(text))
    import graphy.sugiyama as S
    monkeypatch.setattr(S, "check_artifact", lambda p: [] if "GRAPHY_ARTIFACT_OK" in Path(p).read_text() else ["no token"])
    out = tmp_path / "site"
    r = gallery.build(out, ["https://github.com/a/good.git", "https://github.com/a/bad.git"],
                      graphy=[sys.executable, str(fake)], log=lambda s: None)
    assert r["green"] == ["good"] and r["pages"][0]["check"] == [] and r["pages"][0]["arms"][0]["name"] == "MODELS"
    assert 'href="good/index.html"' in (out / "index.html").read_text() and "a/bad" not in (out / "index.html").read_text()
    assert (out / "index.html").is_file() and (out / "gallery.json").is_file()
    rec = json.loads((out / "gallery.json").read_text())
    assert [p["repo"] for p in rec["pages"]] == ["a/good", "a/bad"]
    assert rec["left_out"] and rec["left_out"][-1]["repo"] == "a/bad" and "REFUSED" in rec["left_out"][-1]["line"]


def test_build_refuses_two_urls_of_one_slug_before_any_clone(tmp_path, monkeypatch):
    """graphyos #55: a/click and b/click would share .work/click and the page directory — a silent
    overwrite in sequence, a race side by side — so the pair is refused by name before anything runs."""
    monkeypatch.setattr(gallery, "_run_showcase", lambda *a: (_ for _ in ()).throw(AssertionError("ran")))
    with pytest.raises(gallery.GalleryError, match="two urls share the slug 'click': a/click and b/click"):
        gallery.build(tmp_path / "site", ["https://github.com/a/click.git", "https://github.com/b/click"], graphy=["x"], log=lambda s: None)
    assert not (tmp_path / "site" / "index.html").exists()


def test_build_runs_the_showcases_side_by_side_and_keeps_url_order(tmp_path, monkeypatch):
    """graphyos #55: with jobs=3 the three showcases are in flight at once — every fake waits at a barrier
    that only opens when all three have arrived, so a sequential build would hang at the timeout and fail —
    and the pages still come back in url order. The width is handed in, never read from the box: the
    review's finding was a two-core runner and an inherited GALLERY_JOBS turning this red. jobs=1 is the
    old build, literally; a width that is not a count is refused by name."""
    import threading
    gate = threading.Barrier(3, timeout=2.0)
    order: list[str] = []

    def fake_run(graphy, url, out, work, log):
        slug = url.rsplit("/", 1)[-1].removesuffix(".git")
        gate.wait()                                  # BrokenBarrierError after 2 s if fewer than 3 ran together
        order.append(slug)
        (out / slug).mkdir(parents=True, exist_ok=True)
        (out / slug / "showcase.txt").write_text(TEXT, encoding="utf-8")
        return {"url": url, "repo": f"a/{slug}", "slug": slug, "line": f"SHOWCASE OK: {slug} · 0 arm(s) () · 0 ring shard(s) · CHECK GREEN · 0.1s",
                "rc": 0, "seconds": 0.0, "commit": None, "check": [], "arms": [], "ring": None, "package": slug}

    monkeypatch.setattr(gallery, "_run_showcase", fake_run)
    monkeypatch.setenv("GALLERY_JOBS", "1")          # the box's env must not decide: jobs= wins
    urls = ["https://github.com/a/slow.git", "https://github.com/a/mid.git", "https://github.com/a/fast.git"]
    r = gallery.build(tmp_path / "site", urls, graphy=["never-run"], log=lambda s: None, jobs=3)
    assert [p["slug"] for p in r["pages"]] == ["slow", "mid", "fast"] == r["green"] and sorted(order) == ["fast", "mid", "slow"]
    assert r["jobs"] == 3 and 'href="slow/index.html"' in (tmp_path / "site" / "index.html").read_text()
    # jobs=1: no pool — the barrier never fills, so the first fake times out; prove it by a fake that records
    gate2 = threading.Barrier(3, timeout=0.3)
    seen: list[str] = []

    def fake_seq(graphy, url, out, work, log):
        seen.append(url)
        with pytest.raises(threading.BrokenBarrierError):
            gate2.wait()
        return {"url": url, "repo": url, "slug": url.rsplit("/", 1)[-1].removesuffix(".git"), "line": "SHOWCASE REFUSED: x",
                "rc": 2, "seconds": 0.0, "commit": None, "check": None, "arms": [], "ring": None}
    monkeypatch.setattr(gallery, "_run_showcase", fake_seq)
    r1 = gallery.build(tmp_path / "seq", urls[:1], graphy=["never-run"], log=lambda s: None, jobs=1)
    assert r1["jobs"] == 1 and seen == urls[:1]
    # the width's rules
    monkeypatch.delenv("GALLERY_JOBS")
    assert gallery.jobs_for(3, 1) == 1 and gallery.jobs_for(3, 8) == 3 and 1 <= gallery.jobs_for(3) <= 3 and gallery.jobs_for(0) == 1
    monkeypatch.setenv("GALLERY_JOBS", "2")
    assert gallery.jobs_for(3) == 2 and gallery.jobs_for(3, 3) == 3
    for bad in ("zero", "0", "²", "-1"):
        monkeypatch.setenv("GALLERY_JOBS", bad)
        with pytest.raises(gallery.GalleryError, match="jobs must be a positive integer"):
            gallery.jobs_for(3)


def test_cli_refuses_without_two_arguments_and_a_bad_url_before_any_clone(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "gallery.py"), str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 2 and proc.stderr.startswith("GALLERY REFUSED: python3 gallery.py [--jobs N] <out dir>")
    proc = subprocess.run([sys.executable, str(ROOT / "gallery.py"), "--jobs", "²", str(tmp_path), "https://github.com/ok/ok.git"],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and proc.stderr.startswith("GALLERY REFUSED: --jobs must be a positive integer, not '²'")
    proc = subprocess.run([sys.executable, str(ROOT / "gallery.py"), str(tmp_path), "https://github.com/ok/ok.git", "ftp://nope"],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and "not a github.com or gitlab.com repo url: 'ftp://nope'" in proc.stderr
    assert not (tmp_path / ".work").exists()                # refused before the first clone
