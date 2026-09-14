"""The march's stop hook: a rung only the operator can finish is gated and the loop moves on; a
deferral that names no real gate is interrogated; nothing but disarm and a drained board holds."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import march  # noqa: E402


@pytest.fixture
def board(tmp_path, monkeypatch):
    monkeypatch.setattr(march, "RECOVERY", tmp_path)
    monkeypatch.setattr(march, "STATE", tmp_path / "march.json")
    monkeypatch.setattr(march, "LOG", tmp_path / "march.log")
    monkeypatch.setattr(march, "pane", lambda: None)
    calls: list[tuple] = []
    issues = {103: "OPEN", 104: "OPEN"}
    labels: dict[int, list[str]] = {103: [], 104: []}
    runs: list[dict] = []
    monkeypatch.setattr(march, "_TEST_RUNS", runs, raising=False)

    def gh(*args, timeout=15):
        calls.append(args)
        if args[:2] == ("issue", "view"):
            return json.dumps({"state": issues[int(args[2])]})
        if args[:2] == ("issue", "list"):
            return json.dumps([{"number": n, "labels": [{"name": l} for l in labels[n]]}
                               for n, s in issues.items() if s == "OPEN"])
        if args[:2] == ("run", "list"):
            return json.dumps(runs)
        if args[:2] == ("issue", "edit"):
            labels[int(args[2])].append(args[4])
        return ""

    monkeypatch.setattr(march, "gh", gh)
    march.save({"issue": 103, "phase": "working", "blocks": 0, "session": "s1"})
    return calls, issues, labels


def _stop(message: str, capsys, active: bool = False, transcript: Path | None = None) -> dict:
    sys.stdin = io.StringIO(json.dumps({"session_id": "s1", "last_assistant_message": message,
                                        "stop_hook_active": active,
                                        "transcript_path": str(transcript) if transcript else None}))
    try:
        assert march.cmd_stop_hook(None) == 0
    finally:
        sys.stdin = sys.__stdin__
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else {}


def test_a_deferral_with_no_gate_is_interrogated_not_held(board, capsys):
    out = _stop("The fix is ready. Whether to split the ledger is your call.", capsys)
    assert out["decision"] == "block" and "IS IT MECHANICALLY DERIVABLE" in out["reason"]
    assert march.load()["phase"] == "working"


def test_march_hold_no_longer_holds(board, capsys):
    out = _stop("Round 2 is running.\nMARCH HOLD — waiting on the review", capsys)
    assert out["decision"] == "block" and "A hold is not a stop" in out["reason"]
    assert march.load()["phase"] == "working"


def test_a_gate_naming_no_real_gate_is_refused(board, capsys):
    out = _stop("MARCH GATE: TASTE — pick the colour", capsys)
    assert out["decision"] == "block" and "names no real gate" in out["reason"]


def test_a_real_gate_labels_the_rung_and_marches_the_next(board, capsys):
    calls, _, labels = board
    out = _stop("The vocabulary needs a word.\nMARCH GATE: LAW — rule whether `state` joins the nine words", capsys)
    assert "decision" not in out
    assert labels[103] == ["operator"]
    assert any(c[:2] == ("issue", "comment") and "MARCH GATE: LAW" in c[4] for c in calls)
    state = march.load()
    assert state["issue"] == 104 and state["previous"] == 103


def test_a_gate_or_a_hold_named_inside_code_is_prose(board, capsys):
    out = _stop("The skill now says `MARCH GATE: LAW — step` and `MARCH HOLD` is gone.", capsys)
    assert out.get("decision") == "block" and "still OPEN" in out["reason"]     # the ordinary open-issue block
    assert board[2][103] == []


def test_a_deferral_is_questioned_on_a_continuation_turn_but_never_twice_in_a_row(board, capsys):
    """stop_hook_active is true for nearly every stop of a march, so skipping on it let every later
    deferral ride the open-issue path to the cap hold — MARCH HOLD under another name (round 3, B1)."""
    _stop("Round 1 is running.", capsys)                                        # an ordinary open-issue block
    first = _stop("Whether to split the ledger is your call.", capsys, active=True)
    assert "IS IT REALLY THEIR CALL" in first["reason"]
    second = _stop("Whether to split the ledger is your call.", capsys, active=True)
    assert "IS IT REALLY THEIR CALL" not in second.get("reason", "")             # never twice in a row
    assert march.load()["blocks"] == 3                                          # and every question counts


def test_a_malformed_gate_never_holds_the_loop(board, capsys):
    for _ in range(10):
        out = _stop("The doc line reads:\nMARCH GATE: <LAW | MONEY> — <the exact step>", capsys, active=True)
        assert out["decision"] == "block"                                        # no cap: the loop never limits itself
    assert march.load()["phase"] == "working"


def test_a_gate_after_a_cap_hold_still_gates_and_marches(board, capsys):
    march.save({"issue": 103, "phase": "hold", "held_because": "4 blocks and issue 103 still open", "session": "s1"})
    out = _stop("MARCH GATE: PUBLIC — flip the repo to public", capsys, active=True)
    assert board[2][103] == ["operator"] and march.load()["issue"] == 104


def test_a_gate_after_a_disarm_does_nothing(board, capsys):
    march.save({"issue": 103, "phase": "hold", "held_because": "disarm", "session": "s1"})
    _stop("MARCH GATE: PUBLIC — flip the repo to public", capsys)
    assert board[2][103] == [] and march.load()["phase"] == "hold"


def test_a_closed_blocker_frees_the_rungs_that_named_it(board, monkeypatch):
    calls, issues, labels = board
    issues[106] = "OPEN"; labels[106] = ["blocked"]
    issues[107] = "OPEN"; labels[107] = ["blocked"]
    issues[103] = "CLOSED"
    bodies = {106: "Blocked by #103.", 107: "Blocked by #103 and blocked by #104."}
    real = march.gh

    def gh(*args, timeout=15):
        if args[:2] == ("issue", "list") and "--label" in args:
            return json.dumps([{"number": n, "body": bodies[n], "comments": []} for n in (106, 107)])
        if args[:2] == ("issue", "edit") and args[3] == "--remove-label":
            labels[int(args[2])].remove(args[4]); return ""
        return real(*args, timeout=timeout)

    monkeypatch.setattr(march, "gh", gh)
    assert march.unblock(103) == [106]                                          # 107 still waits on #104
    assert labels[106] == [] and labels[107] == ["blocked"]


def test_should_i_commit_is_a_deferral(board, capsys):
    out = _stop("The gate is green. Should I commit and push?", capsys)
    assert "IS IT MECHANICALLY DERIVABLE" in out["reason"]


def test_a_bold_or_bulleted_gate_line_is_a_gate(board, capsys):
    _stop("- **MARCH GATE: MONEY — approve the registry fee**", capsys)
    assert board[2][103] == ["operator"]


def test_a_gated_rung_is_skipped_by_next(board):
    _, _, labels = board
    labels[103].append("operator")
    assert march.next_issue() == 104


def _transcript(path: Path, *lines: dict) -> Path:
    with path.open("a") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    return path


def _launch(task: str) -> dict:
    return {"type": "user", "toolUseResult": {"isAsync": True, "status": "async_launched", "agentId": task},
            "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_1",
                                     "content": f"Async agent launched successfully.\nagentId: {task}"}]}}


def _tool_call() -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_2", "name": "Bash"}]}}


def test_a_wait_on_a_live_background_review_never_counts_toward_the_cap(board, capsys, tmp_path, monkeypatch):
    """#107: four 'still waiting' stops in 19 s while review round 1 ran capped the loop into hold."""
    t = _transcript(tmp_path / "t.jsonl", _launch("a21c424ac991b3c9b"))
    for _ in range(10):
        out = _stop("Review round 1 is still running.", capsys, active=True, transcript=t)
        assert "decision" not in out                                             # the stop is allowed
    state = march.load()
    assert state["phase"] == "working" and state["blocks"] == 0 and state["issue"] == 103


def test_a_notified_task_is_no_longer_pending_and_a_quoted_id_launches_nothing(board, capsys, tmp_path):
    t = _transcript(tmp_path / "t.jsonl", _launch("abc"),
                    {"type": "queue-operation", "content": "<task-notification>\n<task-id>abc</task-id>\n<status>completed</status>"},
                    {"type": "user", "message": {"content": "an old tail said agentId: zzz"}},
                    {"type": "user", "toolUseResult": {"stdout": "x.jsonl:running in background with ID: yyy"},
                     "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "agentId: yyy"}]}})
    out = _stop("Round 1 is back.", capsys, transcript=t)
    assert out["decision"] == "block" and march.load()["blocks"] == 1


def test_a_turn_that_called_a_tool_resets_the_stall_count(board, capsys, tmp_path):
    t = tmp_path / "t.jsonl"
    for _ in range(6):
        _transcript(t, _tool_call())
        out = _stop("Fixed a blocker; the gate is running.", capsys, active=True, transcript=t)
        assert out["decision"] == "block"
    assert march.load()["phase"] == "working"
    for _ in range(12):
        out = _stop("Nothing to do.", capsys, active=True, transcript=t)              # a true stall is blocked, never held
        assert out["decision"] == "block"
    state = march.load()
    assert state["phase"] == "working" and state["blocks"] == 13                    # 1 from the last tool turn + 12 stalls


def test_an_issue_closed_during_a_cap_hold_marches_the_next_rung(board, capsys):
    """#107 closed at the end of a cap hold and the hold branch never looked: nothing armed the next rung."""
    _, issues, _ = board
    march.save({"issue": 103, "phase": "hold", "held_because": "4 stalled blocks and issue 103 still open", "session": "s1"})
    issues[103] = "CLOSED"
    _stop("Closed #103 with the evidence.", capsys, active=True)
    state = march.load()
    assert state["issue"] == 104 and state["previous"] == 103


def test_a_closed_issue_after_a_disarm_arms_nothing(board, capsys):
    _, issues, _ = board
    march.save({"issue": 103, "phase": "hold", "held_because": "disarm", "session": "s1"})
    issues[103] = "CLOSED"
    _stop("Closed #103.", capsys)
    assert march.load()["phase"] == "hold" and march.load()["issue"] == 103


def test_a_background_shell_is_pending_until_notified(board, capsys, tmp_path):
    t = _transcript(tmp_path / "t.jsonl", {"type": "user", "toolUseResult": {"stdout": "", "backgroundTaskId": "b7hm0k2wk"}})
    assert "decision" not in _stop("The floor is running.", capsys, transcript=t)
    _transcript(t, {"type": "queue-operation", "content": "<task-notification><task-id>b7hm0k2wk</task-id><status>completed</status>"})
    assert _stop("The floor is back.", capsys, transcript=t)["decision"] == "block"


def test_a_rung_closed_on_a_red_main_blocks_until_main_is_green(board, capsys):
    """Eight rungs closed while `ci` on main was red (the gate ran pytest on the host interpreter): the close
    now reads main's newest ci run, and a definite failure blocks with the sha; green or pending marches."""
    calls, issues, labels = board
    runs = march._TEST_RUNS
    issues[103] = "CLOSED"
    runs.append({"status": "completed", "conclusion": "failure", "headSha": "f0b6e55deadbeef"})
    out = _stop("Closed 103.", capsys)
    assert out["decision"] == "block" and "RED at f0b6e55deadb" in out["reason"]
    assert march.load()["issue"] == 103
    assert _stop("Still red.", capsys)["decision"] == "block" and march.load()["issue"] == 103   # never once-and-through
    runs[0].update(conclusion="timed_out")
    assert _stop("Timed out.", capsys)["decision"] == "block"
    runs[0].update(conclusion="success")
    out = _stop("Main is green again.", capsys)
    assert march.load()["issue"] == 104


def test_a_red_main_never_holds_a_session_waiting_on_its_own_background_work(board, capsys, tmp_path):
    """Review round 1 of the red-main fix: the hold ran before the §125 pending check, so a session waiting on its
    own review round was blocked every stop instead of woken by the notification."""
    calls, issues, labels = board
    issues[103] = "CLOSED"
    march._TEST_RUNS.append({"status": "completed", "conclusion": "failure", "headSha": "abc"})
    t = _transcript(tmp_path / "t.jsonl", _launch("a1b2c3"))
    out = _stop("Review round running.", capsys, transcript=t)
    assert out.get("decision") != "block" and march.load()["issue"] == 103


def test_a_declared_order_is_marched_first_and_a_closed_or_gated_rung_falls_through(board, monkeypatch):
    calls, issues, labels = board
    monkeypatch.setattr(march, "ORDER", march.RECOVERY / "march_order.json")
    issues.update({122: "OPEN", 124: "OPEN", 97: "OPEN"})
    labels.update({122: [], 124: [], 97: []})
    assert march.next_issue() == 97                      # no order: the number sequence
    assert march.main(["order", "122", "124", "97"]) == 0
    assert march.load_order() == [122, 124, 97]
    assert march.next_issue() == 122                     # the first tenant's priority
    issues[122] = "CLOSED"
    assert march.next_issue() == 124                     # a closed rung falls through
    labels[124].append("operator")
    assert march.next_issue() == 97                      # a gated one too
    issues[97] = "CLOSED"
    assert march.next_issue() == 103                     # then the sequence, for what the order never named
    assert march.main(["order", "--clear"]) == 0
    assert march.load_order() == []
    march.ORDER.write_text("[122,", encoding="utf-8")   # a torn or hand-edited file
    assert march.next_issue() == 103                     # the sequence, never a crash in a hook
    assert "order ignored" in march.LOG.read_text(encoding="utf-8")   # and NAMED, never a silent fall-back
    assert march.main(["order"]) == 1                    # bare `order` says so too, and exits 1
    march.ORDER.write_text("[true, 122]", encoding="utf-8")
    assert march.main(["order"]) == 1                    # a bool is not an issue number
    with pytest.raises(SystemExit):
        march.main(["order", "--clear", "122"])          # numbers or --clear, never both
    assert march.main(["order", "104"]) == 0             # redeclared: readable again
    assert march.next_issue() == 104
