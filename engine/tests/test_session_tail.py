from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphy import session_tail as st

FIX = Path(__file__).parent / "fixtures" / "transcript" / "session.jsonl"


def test_GREEN_fixture_yields_two_clean_exchanges():
    turns, undecodable = st.extract_turns(FIX)
    assert undecodable == 0
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
    ex = st.pair_turns(turns)
    assert len(ex) == 2
    assert "system-reminder" not in ex[0]["user"] and "never render this" not in ex[0]["user"]
    assert ex[0]["assistant"].startswith("Call the store's resolver")
    assert "subagent" not in ex[1]["assistant"]
    assert ex[1]["user"] == "And if the id is unknown?"


def test_GREEN_render_carries_the_exchange_grammar():
    rendered, meta = st.render_full(FIX, session_id="fx-session-0001", resolved_by="test")
    assert "--- [1] USER" in rendered and "--- [2] ASSISTANT" in rendered
    assert rendered.rstrip().endswith("the exchange above is where you left off.")
    assert meta["total"] == 2 and len(meta["semantic_sha256"]) == 64
    assert "tool_result" not in rendered and "cat alpha.py" not in rendered


def test_GREEN_bounded_tail_keeps_the_newest_edge():
    rendered, _ = st.render_full(FIX, session_id="fx-session-0001", resolved_by="test")
    short = st.bounded_tail(rendered, 600)
    assert short.startswith("# RECENT CONVERSATION CONTEXT")
    assert short.rstrip().endswith("the exchange above is where you left off.")
    assert st.bounded_tail(rendered, 15_000) == rendered
    with pytest.raises(st.TailError):
        st.bounded_tail(rendered, 100)


def test_RED_noise_only_transcript_refuses_as_empty(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps({"type": t, "sessionId": "s"})
                           for t in ["mode", "attachment", "last-prompt", "system", "ai-title"]) + "\n")
    with pytest.raises(st.TailError, match="essentially empty"):
        st.render_full(p, session_id="s", resolved_by="test")


def test_RED_format_drift_undecodable_lines_names_the_cause(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(["not json at all"] * 12) + "\n")
    with pytest.raises(st.TailError, match="format may have MOVED"):
        st.render_full(p, session_id="s", resolved_by="test")


def test_RED_format_drift_unknown_content_shape_names_the_cause(tmp_path):
    p = tmp_path / "t.jsonl"
    rows = []
    for i in range(4):
        rows.append({"type": "user", "sessionId": "s", "message": {"role": "user", "content": {"v2": "shape"}}})
        rows.append({"type": "assistant", "sessionId": "s", "message": {"role": "assistant", "content": {"v2": "shape"}}})
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    with pytest.raises(st.TailError, match="MOVED"):
        st.render_full(p, session_id="s", resolved_by="test")


def test_GREEN_project_slug_matches_claude_code_layout():
    assert st.project_slug(Path("/home/me/graphy")) == "-home-me-graphy"
    assert st.project_slug(Path("/home/me/Enterprise_x")) == "-home-me-Enterprise-x"
