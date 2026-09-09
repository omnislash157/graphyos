"""The harness compile step: GRAPH.md, arms, drawings, walk receipts, pointers. A floor; the
proof is an eaten store plus `graphy arms --verify` after the run."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.arms as arms
import graphy.cli as cli
import graphy.harness as harness
import graphy.sugiyama as sugi
from test_doors import _fixture


def _cut(tenant_dir: Path) -> Path:
    p = tenant_dir / "partition.json"
    p.write_text(json.dumps({
        "groups": {"ROUTING": ["fastapi.routing"], "DEPS": ["fastapi.dependencies"]},
        "rest": "EDGE",
    }), encoding="utf-8")
    return p


def _scaffold_of(text: str, name: str) -> str:
    start = text.find(f"<!-- graphy:scaffold {name}")
    end = text.find(f"<!-- /graphy:scaffold {name} -->")
    assert start >= 0 and end > start
    return text[start:end]


def test_GREEN_harness_writes_graph_arms_drawings_walks_and_pointers(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    _cut(tmp_path)
    repo = tmp_path / "checkout"
    repo.mkdir()
    rc = cli.main(["harness", "--repo", str(repo), "--tenant", str(desc), "--tenant-id", "doors",
                   "--corpus", "fastapi"])
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "HARNESS OK:" in out.out
    graph = (tmp_path / "GRAPH.md").read_text(encoding="utf-8")
    assert graph.startswith("# GRAPH — arms for fastapi")
    assert "drawings/pillars.svg" in graph
    assert "ROUTING" in graph and "DEPS" in graph
    assert "fastapi://" in graph or "`" in graph
    pillars_svg = tmp_path / "drawings" / "pillars.svg"
    assert pillars_svg.is_file() and sugi.check_artifact(pillars_svg) == []
    assert (tmp_path / "drawings" / "pillars.html").is_file()
    for name in ("ROUTING", "DEPS"):
        md = (tmp_path / "arms" / f"{name}.md").read_text(encoding="utf-8")
        assert f"<!-- graphy:arm {name} generated" in md
        assert f"<!-- graphy:arm-draw {name}" in md
        assert f"<!-- graphy:scaffold {name}" in md
        assert f"](../drawings/{name}.svg)" in md
        assert (tmp_path / "drawings" / f"{name}.svg").is_file()
        assert sugi.check_artifact(tmp_path / "drawings" / f"{name}.svg") == []
        walk = (tmp_path / "arms" / f"{name}.walk.txt").read_text(encoding="utf-8")
        assert walk.startswith(f"WALK {name}") and "store:" in walk and "crown:" in walk
        assert "Last walk:" in md
    assert "agent hub is generated" in (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "agent hub is generated" in (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "GRAPH.md" in (repo / "CLAUDE.md").read_text(encoding="utf-8")


def test_GREEN_second_run_is_stable_scaffold_unchanged_and_arms_verify_green(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    _cut(tmp_path)
    repo = tmp_path / "checkout"
    repo.mkdir()
    argv = ["harness", "--repo", str(repo), "--tenant", str(desc), "--tenant-id", "doors",
            "--corpus", "fastapi"]
    assert cli.main(argv) == 0
    capsys.readouterr()
    routing = tmp_path / "arms" / "ROUTING.md"
    text = routing.read_text(encoding="utf-8")
    # operator prose in the scaffold must survive a second compile
    mutated = text.replace(
        "- What this arm is for (one sentence):",
        "- What this arm is for (one sentence): the request path")
    routing.write_text(mutated, encoding="utf-8")
    scaffold = _scaffold_of(mutated, "ROUTING")
    graph_1 = (tmp_path / "GRAPH.md").read_text(encoding="utf-8")
    assert cli.main(argv) == 0
    capsys.readouterr()
    again = routing.read_text(encoding="utf-8")
    assert _scaffold_of(again, "ROUTING") == scaffold
    assert "the request path" in again
    graph_2 = (tmp_path / "GRAPH.md").read_text(encoding="utf-8")
    assert graph_2 == graph_1
    rc = cli.main(["arms", "--tenant", str(desc), "--tenant-id", "doors", "--corpus", "fastapi",
                   "--partition", str(tmp_path / "partition.json"), "--dir", str(tmp_path / "arms"),
                   "--verify"])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith("ARMS OK:")


def test_GREEN_existing_claude_that_is_not_a_pointer_is_left_alone(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    _cut(tmp_path)
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# the constitution\n\nHand-written. Do not smash.\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("# also human\n", encoding="utf-8")
    rc = cli.main(["harness", "--repo", str(repo), "--tenant", str(desc), "--tenant-id", "doors",
                   "--corpus", "fastapi"])
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == "# the constitution\n\nHand-written. Do not smash.\n"
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "# also human\n"
    assert "pointer not installed: existing CLAUDE.md left alone" in out.out
    assert "pointer not installed: existing AGENTS.md left alone" in out.out
    assert (tmp_path / "GRAPH.md").is_file()


def test_GREEN_curated_partition_is_left_byte_identical(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    part = _cut(tmp_path)
    before = part.read_bytes()
    repo = tmp_path / "checkout"
    repo.mkdir()
    rc = cli.main(["harness", "--repo", str(repo), "--tenant", str(desc), "--tenant-id", "doors",
                     "--corpus", "fastapi"])
    out = capsys.readouterr().out
    assert rc == 0
    assert part.read_bytes() == before
    assert "partition left alone (curated)" in out


def test_GREEN_pointer_rewritten_when_already_a_graphy_stub(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    _cut(tmp_path)
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text(harness.pointer_text("old/path/GRAPH.md"), encoding="utf-8")
    assert cli.main(["harness", "--repo", str(repo), "--tenant", str(desc), "--tenant-id", "doors",
                     "--corpus", "fastapi"]) == 0
    capsys.readouterr()
    text = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert harness.POINTER_MARK in text
    assert "old/path/GRAPH.md" not in text
    assert "GRAPH.md" in text


def test_GREEN_harness_writes_partition_when_absent(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    repo = tmp_path / "checkout"
    repo.mkdir()
    assert not (tmp_path / "partition.json").exists()
    rc = cli.main(["harness", "--repo", str(repo), "--tenant", str(desc), "--tenant-id", "doors",
                   "--corpus", "fastapi"])
    out = capsys.readouterr()
    assert rc == 0, out.err
    part = tmp_path / "partition.json"
    assert part.is_file() and "partition wrote" in out.out
    doc = json.loads(part.read_text(encoding="utf-8"))
    assert "groups" in doc and "ROUTING" in doc["groups"]
    assert (tmp_path / "GRAPH.md").is_file()
    assert "GRAPH — arms for fastapi" in (tmp_path / "GRAPH.md").read_text(encoding="utf-8")


def test_RED_cli_refuses_without_repo(tmp_path, capsys):
    rc = cli.main(["harness"])
    err = capsys.readouterr().err
    assert rc == 2 and "HARNESS REFUSED" in err and "--repo is required" in err
    rc = cli.main(["harness", "--repo", str(tmp_path / "nowhere")])
    err = capsys.readouterr().err
    assert rc == 2 and "HARNESS REFUSED" in err


def test_GREEN_generate_seeds_scaffold_once_and_leaves_it(tmp_path):
    """The arms door's first create writes the empty scaffold; a second generate does not touch it."""
    from test_arms import _regions
    d = tmp_path / "arms"
    regs = _regions(tmp_path)
    assert dict(arms.generate(regs, d))["BASE"] == "created"
    base = (d / "BASE.md").read_text(encoding="utf-8")
    assert "<!-- graphy:scaffold BASE" in base
    scaffold = _scaffold_of(base, "BASE")
    filled = base.replace("- What this arm is for (one sentence):",
                          "- What this arm is for (one sentence): the floor")
    (d / "BASE.md").write_text(filled, encoding="utf-8")
    assert dict(arms.generate(regs, d))["BASE"] == "unchanged"
    assert "the floor" in _scaffold_of((d / "BASE.md").read_text(encoding="utf-8"), "BASE")
