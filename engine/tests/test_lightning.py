from __future__ import annotations

import json
from pathlib import Path

from graphy.lightning import Lightning, bolt_cli
from graphy.lightning import bloodhound, reseed_graph

CORPUS = Path(__file__).parent / "fixtures" / "lightning_corpus"


def test_GREEN_hunt_anchors_hits_to_blocks_across_grammars():
    result = Lightning(str(CORPUS)).hunt("resolve_widget")
    paths = {h.relative_path for h in result.hits}
    assert {"alpha.py", "beta.js", "gamma.svelte"} <= paths
    alpha = next(h for h in result.hits if h.relative_path == "alpha.py")
    assert alpha.language == "python" and alpha.total_matches >= 3
    assert any("resolve_widget" in c.text for c in alpha.chunks)
    md = result.to_markdown()
    assert "resolve_widget" in md and "alpha.py" in md


def test_GREEN_prose_overlay_makes_a_session_turn_the_block():
    result = Lightning(str(CORPUS)).hunt("unknown")
    hit = next(h for h in result.hits if h.relative_path == "transcript.md")
    assert hit.language == "prose"
    assert any("[2] USER" in c.text or "unknown" in c.text for c in hit.chunks)


def test_GREEN_cli_doors_run(capsys):
    assert bolt_cli.main(["resolve_widget", "--path", str(CORPUS), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["files_matched"] >= 3

    assert bolt_cli.main(["--containers", "resolve_widget", "--path", str(CORPUS)]) == 0
    assert "resolve_widget" in capsys.readouterr().out

    assert bolt_cli.main(["--cooccur", "resolve_widget", "--with", "marker", "--path", str(CORPUS)]) == 0
    assert "resolve_widget" in capsys.readouterr().out

    assert bolt_cli.main(["--stats", "resolve_widget", "--path", str(CORPUS)]) == 0
    assert json.loads(capsys.readouterr().out)


def test_GREEN_the_pipe_door_reaches_what_path_would_skip(tmp_path, capsys):
    listing = tmp_path / "files.txt"
    listing.write_text(str(CORPUS / "alpha.py") + "\n")
    assert bolt_cli.main(["resolve_widget", "--path", str(CORPUS), "--files-from", str(listing), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [h["relative_path"] for h in payload["hits"]] == ["alpha.py"]


def test_GREEN_memory_doors_answer_over_a_session_corpus(capsys):
    assert bloodhound.main(["resolve", "--with", "marker", "--path", str(CORPUS)]) == 0
    out = capsys.readouterr().out
    assert "resolve" in out
    assert reseed_graph.main(["--path", str(CORPUS / "transcript.md"), "search", "widget"]) == 0
    assert "widget" in capsys.readouterr().out.lower()


def test_RED_cli_refuses_a_missing_corpus_instead_of_widening(capsys):
    import pytest
    with pytest.raises(SystemExit) as exc:
        bolt_cli.main(["resolve_widget", "--path", str(CORPUS / "nope")])
    assert exc.value.code == 2
    assert "does not exist" in capsys.readouterr().err
