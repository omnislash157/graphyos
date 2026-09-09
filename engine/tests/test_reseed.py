from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from graphy import reseed
from graphy import session_tail as st

FIX = Path(__file__).parent / "fixtures" / "transcript" / "session.jsonl"


def _payload(**kw):
    base = {"session_id": "fx-session-0001", "transcript_path": str(FIX), "cwd": "/tmp/x",
            "hook_event_name": "PreCompact", "trigger": "manual"}
    if "reason" in kw:
        base.pop("trigger")
    base.update(kw)
    return base


def test_GREEN_capture_writes_tail_and_archives_once(tmp_path):
    rec = tmp_path / "recovery"
    info = reseed.do_capture(_payload(), rec)
    tail = rec / reseed.TAIL_NAME
    assert tail.is_file() and info["exchanges"] == 2
    text = tail.read_text()
    assert "session: fx-session-0001" in text and "resolved_by: PreCompact:manual" in text
    archives = sorted((rec / "sessions").glob("*.md"))
    assert len(archives) == 1 and archives[0].name.startswith("00001__") and archives[0].name.endswith("__fx-sessi.md")
    again = reseed.do_capture(_payload(hook_event_name="SessionEnd", reason="clear"), rec)
    assert again["archived"] is None
    assert len(list((rec / "sessions").glob("*.md"))) == 1


def test_RED_capture_refuses_a_session_mismatch(tmp_path):
    with pytest.raises(st.TailError, match="session mismatch"):
        reseed.do_capture(_payload(session_id="someone-else"), tmp_path / "recovery")


def test_RED_capture_refuses_a_missing_transcript(tmp_path):
    with pytest.raises(st.TailError, match="does not exist"):
        reseed.do_capture(_payload(transcript_path=str(tmp_path / "nope.jsonl")), tmp_path / "recovery")


def test_GREEN_inject_after_compact_serves_the_same_session(tmp_path):
    rec = tmp_path / "recovery"
    reseed.do_capture(_payload(), rec)
    out = reseed.do_inject({"session_id": "fx-session-0001", "source": "compact"}, rec, tmp_path)
    assert out.startswith("# SESSION RE-SEED (compact)")
    assert f"Read  {rec / reseed.TAIL_NAME}" in out
    assert "this session, before compaction" in out
    assert "--- [2] USER" in out and "And if the id is unknown?" in out


def test_GREEN_inject_after_clear_serves_the_previous_session(tmp_path):
    rec = tmp_path / "recovery"
    reseed.do_capture(_payload(hook_event_name="SessionEnd", reason="clear"), rec)
    out = reseed.do_inject({"session_id": "a-new-session", "source": "clear"}, rec, tmp_path)
    assert "# SESSION RE-SEED (clear)" in out
    assert "this session, before compaction" not in out
    assert "resolved by SessionEnd:clear" in out


def test_GREEN_inject_with_nothing_says_so_and_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-such-config"))
    out = reseed.do_inject({"session_id": "s", "source": "startup"}, tmp_path / "recovery", tmp_path / "proj")
    assert "TAIL UNAVAILABLE" in out and "DO NOT ASSUME CONTINUITY" in out
    diag = (tmp_path / "recovery" / reseed.DIAG_NAME).read_text()
    assert "inject EMPTY source=startup session=s" in diag


def test_GREEN_inject_success_leaves_a_diag_line(tmp_path):
    """A hook that fired and rendered must be distinguishable, from the log alone, from one
    that never ran. Issue #11."""
    rec = tmp_path / "recovery"
    reseed.do_capture(_payload(hook_event_name="SessionEnd", reason="clear"), rec)
    reseed.do_inject({"session_id": "a-new-session", "source": "clear"}, rec, tmp_path)
    lines = (rec / reseed.DIAG_NAME).read_text().splitlines()
    ok = lines[-1].split(" ", 1)[1]
    assert ok.startswith("inject ok source=clear bytes=")
    assert "exchanges=2" in ok and "tail_session=fx-session-0001" in ok
    assert "resolved_by=SessionEnd:clear" in ok and "same_session" not in ok
    reseed.do_inject({"session_id": "fx-session-0001", "source": "compact"}, rec, tmp_path)
    assert (rec / reseed.DIAG_NAME).read_text().splitlines()[-1].endswith("same_session")


def test_GREEN_inject_disk_fallback_finds_the_newest_other_transcript(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    proj = tmp_path / "proj"
    slugdir = cfg / "projects" / st.project_slug(proj)
    slugdir.mkdir(parents=True)
    body = FIX.read_text()
    (slugdir / "prev-session.jsonl").write_text(body.replace("fx-session-0001", "prev-session") + ("\n" * 3000))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    out = reseed.do_inject({"session_id": "current-session", "source": "startup"}, tmp_path / "recovery", proj)
    assert "RESOLVED BY DISK FALLBACK" in out and "--- [2] USER" in out
    assert (tmp_path / "recovery" / reseed.TAIL_NAME).is_file()


def test_GREEN_main_is_fail_open_on_a_bad_capture(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(transcript_path="/nope.jsonl"))))
    rc = reseed.main(["--project-dir", str(tmp_path), "capture"])
    assert rc == 0
    assert "capture failed" in capsys.readouterr().err
    assert "capture FAILED" in (tmp_path / ".claude" / "recovery" / reseed.DIAG_NAME).read_text()


def test_GREEN_render_door(capsys):
    rc = reseed.main(["render", "--transcript", str(FIX), "--budget-chars", "700"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("# RECENT CONVERSATION CONTEXT") and "--- [2] ASSISTANT" in out


# graphyos #67 — the hooks take a Codex rollout and a Cursor payload; inject answers in JSON on request.

def test_GREEN_capture_reads_a_codex_rollout_and_checks_its_own_id(tmp_path):
    from tests.test_session_tail import _codex_rollout
    rollout = _codex_rollout(tmp_path)
    rec = tmp_path / "recovery"
    info = reseed.do_capture({"session_id": "01a0-codex", "transcript_path": str(rollout), "cwd": str(tmp_path),
                              "hook_event_name": "SessionEnd"}, rec)
    assert info["exchanges"] == 2 and (rec / reseed.TAIL_NAME).is_file()
    with pytest.raises(st.TailError, match="session mismatch"):
        reseed.do_capture({"session_id": "someone-else", "transcript_path": str(rollout)}, rec)


def test_GREEN_capture_takes_a_cursor_conversation_id(tmp_path):
    rec = tmp_path / "recovery"
    info = reseed.do_capture({"conversation_id": "fx-session-0001", "transcript_path": str(FIX),
                              "hook_event_name": "sessionEnd", "reason": "completed"}, rec)
    assert info["exchanges"] == 2
    assert "resolved_by: sessionEnd:completed" in (rec / reseed.TAIL_NAME).read_text()


def test_GREEN_inject_json_is_the_cursor_shape(tmp_path, capsys, monkeypatch):
    rec = tmp_path / "recovery"
    reseed.do_capture(_payload(), rec)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": "fx-session-0001", "source": "startup"})))
    assert reseed.main(["--project-dir", str(tmp_path), "--recovery-dir", str(rec), "inject", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {"additional_context"} and out["additional_context"].startswith("# SESSION RE-SEED (startup)")
    assert "--- [1] USER" in out["additional_context"] or "Read  " in out["additional_context"]
