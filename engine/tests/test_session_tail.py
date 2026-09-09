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


# graphyos #67 — a harness is a reader: the shape decides, never a name.

def _codex_row(kind: str, role: str | None, text: str, ordinal: int) -> str:
    if kind == "session_meta":
        return json.dumps({"timestamp": "t", "ordinal": ordinal, "type": "session_meta",
                           "payload": {"session_id": "01a0-codex", "id": "01a0-codex", "cwd": "/r", "cli_version": "0.153.2"}})
    if kind == "message":
        block = "input_text" if role in ("user", "developer") else "output_text"
        return json.dumps({"timestamp": "t", "ordinal": ordinal, "type": "response_item",
                           "payload": {"type": "message", "id": f"msg_{ordinal}", "role": role, "content": [{"type": block, "text": text}]}})
    return json.dumps({"timestamp": "t", "ordinal": ordinal, "type": kind, "payload": {"type": text}})


def _codex_rollout(tmp_path: Path) -> Path:
    rows = [_codex_row("session_meta", None, "", 0),
            _codex_row("message", "developer", "<skills_instructions>\n## Skills", 1),
            _codex_row("message", "user", "# AGENTS.md instructions for /r\n\n<INSTRUCTIONS>read the router</INSTRUCTIONS>", 2),
            _codex_row("message", "user", "<environment_context>\n  <cwd>/r</cwd>\n</environment_context>", 3),
            _codex_row("message", "user", "resume the batch and tell me what moved", 4),
            _codex_row("response_item", None, "reasoning", 5),
            _codex_row("response_item", None, "custom_tool_call", 6),
            _codex_row("event_msg", None, "token_count", 7),
            _codex_row("message", "assistant", "Resuming from the checkpoint.", 8),
            _codex_row("message", "assistant", "Twenty categories compiled, none moved.", 9),
            _codex_row("message", "developer", "=== GIT COMMIT AUDIT ===", 10),
            _codex_row("message", "user", "what does unchanged mean here", 11),
            _codex_row("message", "assistant", "Reported and not corrected.", 12)]
    p = tmp_path / "rollout-2026-09-08T23-24-27-01a0-codex.jsonl"
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return p


def test_GREEN_codex_rollout_reads_by_shape_dropping_the_harness_rows(tmp_path):
    p = _codex_rollout(tmp_path)
    turns, undecodable = st.extract_turns(p)
    assert undecodable == 0
    assert [t["role"] for t in turns] == ["user", "assistant", "assistant", "user", "assistant"]
    ex = st.pair_turns(turns)
    assert len(ex) == 2
    assert ex[0]["user"] == "resume the batch and tell me what moved"
    assert ex[0]["assistant"] == "Resuming from the checkpoint.\n\nTwenty categories compiled, none moved."
    assert ex[1]["user"] == "what does unchanged mean here"
    rendered, meta = st.render_full(p, session_id="01a0-codex", resolved_by="test")
    assert "AGENTS.md" not in rendered and "environment_context" not in rendered and "GIT COMMIT AUDIT" not in rendered
    assert "skills_instructions" not in rendered and meta["total"] == 2
    stats = st.scan_stats(p)
    assert stats["user_typed"] == 4 and stats["real_user"] == 2 and stats["assistant_typed"] == 3 and stats["real_assistant"] == 3


def test_GREEN_role_content_jsonl_reads_by_shape_and_skips_tool_rows(tmp_path):
    rows = [{"role": "user", "content": "where is the resolver"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "read", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "…"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "converge.py, the --resolve door."}]},
            {"role": "user", "content": [{"type": "text", "text": "and who calls it"}]},
            {"role": "assistant", "content": "cli._cmd_converge alone."}]
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    ex = st.pair_turns(st.extract_turns(p)[0])
    assert [(e["user"], e["assistant"]) for e in ex] == [("where is the resolver", "converge.py, the --resolve door."),
                                                       ("and who calls it", "cli._cmd_converge alone.")]


def test_RED_a_shape_no_harness_claims_is_refused_not_read_hollow(tmp_path):
    p = tmp_path / "other.jsonl"
    p.write_text("\n".join(json.dumps({"kind": "event", "who": "user", "body": "hello"}) for _ in range(6)) + "\n")
    assert st.extract_turns(p) == ([], 0)
    assert st.harness_of({"kind": "event"}) is None
    with pytest.raises(st.TailError, match="essentially empty"):
        st.render_full(p, session_id="x", resolved_by="test")
