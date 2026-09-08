"""The timeline door (graphyos #60): two words as bloodhound co-occurrence over the archive, the
fan-out walked through the history shard — sessions in time order, their commits, sections, issues,
and the receipt numbers that moved. Pure over a fake store; the real one over this tenant when built."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from graphy import timeline
from graphy.federated_store import WITH, AGAINST, Neighbour

ROOT = Path(__file__).resolve().parents[2]
S1 = "history://session/aaaa1111-0000-0000-0000-000000000001"
S2 = "history://session/bbbb2222-0000-0000-0000-000000000002"


class FakeStore:
    """record · neighbours · owned — what the door reads, nothing else."""

    def __init__(self):
        self.records = {
            S1: {"node_type": "session", "captured_at": "2026-09-05T11:00:00+00:00", "file": "00001__x__aaaa1111.md"},
            S2: {"node_type": "session", "captured_at": "2026-09-05T13:30:00+00:00", "file": "00003__x__bbbb2222.md"},
            "history://commit/a" * 1: {"node_type": "commit", "name": "aaaaaaa", "authored": "2026-09-05T12:00:00+00:00", "subject": "two: the second"},
            "history://commit/b": {"node_type": "commit", "name": "bbbbbbb", "authored": "2026-09-05T12:30:00+00:00", "subject": "two-b: later"},
            "history://section/2": {"node_type": "section", "number": 2, "title": "THE SECOND"},
            "history://issue/4": {"node_type": "issue", "number": 4, "title": "four"},
            "history://receipt/recon.before3": {"node_type": "receipt", "name": "recon.before3", "measured_at": "2026-09-05T09:00:00+00:00",
                                                "numbers": {"floor.seconds": 9.8, "floor.passed": 5, "gate.rc": 0}},
            "history://receipt/recon.before4": {"node_type": "receipt", "name": "recon.before4", "measured_at": "2026-09-05T10:00:00+00:00",
                                                "numbers": {"floor.seconds": 8.1, "floor.passed": 5, "gate.rc": 1, "x.rss_kb": 3}},
        }
        self.edges = [(S2, "history://commit/a", "authored"), (S2, "history://commit/b", "authored"),
                      ("history://commit/a", "history://section/2", "records"), ("history://commit/a", "history://issue/4", "names"),
                      ("history://receipt/recon.before4", "history://issue/4", "pins"), (S1, S2, "follows")]
        self.reads = 0

    def record(self, nid):
        self.reads += 1
        return self.records.get(nid)

    def neighbours(self, nid):
        self.reads += 1
        return [Neighbour(d, r, WITH) for s, d, r in self.edges if s == nid] + [Neighbour(s, r, AGAINST) for s, d, r in self.edges if d == nid]

    def owned(self, owner):
        assert owner == "history"
        for nid, rec in self.records.items():
            yield nid, {"node_type": rec["node_type"], "dotted": None, "module": "history", "role": rec["node_type"],
                        "file": rec.get("file"), "line": None}


def _head(sid: str, cap: str) -> str:
    return f"# CONVERSATION FULL SESSION — 3 exchanges, verbatim and in order\n\nsession: {sid}\ncaptured_at: {cap}\n\n"


def _archive(tmp_path: Path) -> Path:
    d = tmp_path / "sessions"
    d.mkdir()
    a, b, c = S1.rsplit("/", 1)[-1], S2.rsplit("/", 1)[-1], "cccc3333-0000-0000-0000-000000000003"
    (d / "00001__x__aaaa1111.md").write_text(_head(a, "2026-09-05T11:00:00+00:00") + "--- [1] USER\n\nload bloodhound and follow the fan out please\n")
    (d / "00002__x__bbbb2222.md").write_text(_head(b, "2026-09-05T13:00:00+00:00") + "--- [1] USER\n\nnothing here about the hound\n\n--- [2] USER\n\nbloodhound with the fan out again\n")
    (d / "00003__x__bbbb2222.md").write_text(_head(b, "2026-09-05T13:30:00+00:00") + "--- [1] USER\n\nbloodhound fan out bloodhound fan out, the hottest capture\n")
    (d / "00004__x__cccc3333.md").write_text(_head(c, "2026-09-05T14:00:00+00:00") + "--- [1] USER\n\nbloodhound and fan out in a session the shard never saw\n")
    (d / "notes.md").write_text("# not a session\n\nbloodhound fan out\n")             # no header: never a session
    (d / "sub").mkdir()
    (d / "sub" / "deep.md").write_text(_head("dddd4444-0000-0000-0000-000000000004", "2026-09-05T15:00:00+00:00") + "bloodhound fan out\n")
    return d


def test_GREEN_hunt_is_bloodhounds_own_window_and_names_the_exchange(tmp_path):
    archive = _archive(tmp_path)
    hits, searched = timeline.hunt("bloodhound", "fan out", archive, window=10)
    assert searched == 4, "the producer's files: the top level, each with a session header — never notes.md or sub/"
    assert [h[0] for h in hits] == ["00001__x__aaaa1111.md", "00002__x__bbbb2222.md", "00003__x__bbbb2222.md", "00004__x__cccc3333.md"]
    assert hits[1][1] == (2, 2) and "fan out" in hits[1][2]
    assert hits[2][3] > hits[1][3], "the density rides along: the hottest capture speaks for a session"
    # one term: every session that says it
    assert len(timeline.hunt("bloodhound", None, archive)[0]) == 4
    with pytest.raises(timeline.TimelineError, match="no sessions archive"):
        timeline.hunt("x", None, tmp_path / "nope")


def test_GREEN_the_story_is_the_shards_fan_out_in_time_order_with_the_numbers_that_moved(tmp_path):
    store = FakeStore()
    t = timeline.timeline(store, "bloodhound", "fan out", _archive(tmp_path), window=10)
    assert [s.id for s in t.sessions] == [S1, S2], "oldest first, by the capture time; a session captured twice is one"
    assert t.hit_files == 4 and t.unmatched == ["00004__x__cccc3333.md"], "a session the shard never saw is named, never invented"
    s1, s2 = t.sessions
    assert s1.commits == [] and s1.exchanges == (1, 1)
    assert s2.file == "00003__x__bbbb2222.md", "the hottest of the two captures speaks, mapped to the node by its id prefix"
    assert [c["sha"] for c in s2.commits] == ["aaaaaaa", "bbbbbbb"]
    a = s2.commits[0]
    assert [x["number"] for x in a["sections"]] == [2] and [x["number"] for x in a["issues"]] == [4]
    r = a["issues"][0]["receipts"]
    assert [x["name"] for x in r] == ["recon.before4"]
    assert r[0]["moved"] == [("floor.seconds", 9.8, 8.1)], "against the receipt before it: a moved number, never rc, never rss"
    out = timeline.render(t)
    assert out.splitlines()[0].startswith("# TIMELINE — `bloodhound` × `fan out`")
    assert "2026-09-05T13:30  session bbbb2222  ex 1" in out
    assert "4 hold both, 2 session(s) in the shard" in out.splitlines()[0]
    assert "├─ aaaaaaa  two: the second   RECON §2 · graphyos #4" in out
    assert "recon.before4: floor.seconds 9.8 → 8.1" in out
    assert "└─ (no commit in this session's window)" in out
    assert "not in the shard: 00004__x__cccc3333.md" in out
    assert out.splitlines()[-1].startswith("TIMELINE: 2 session(s) · 2 commit(s) · 1 section(s) · 1 issue(s) · 1 receipt(s) · ")
    assert t.counts() == {"sessions": 2, "commits": 2, "sections": 1, "issues": 1, "receipts": 1}


def test_RED_a_store_with_no_history_shard_refuses_by_name(tmp_path):
    class Bare(FakeStore):
        def owned(self, owner):
            return iter(())
    with pytest.raises(timeline.TimelineError, match="no history shard — mint it"):
        timeline.timeline(Bare(), "bloodhound", None, _archive(tmp_path))


def test_GREEN_commits_order_by_the_instant_not_the_string(tmp_path):
    store = FakeStore()
    store.records["history://commit/a"]["authored"] = "2026-09-05T05:20:00-07:00"      # 12:20Z, later than b's
    store.records["history://commit/b"]["authored"] = "2026-09-05T12:10:00+00:00"
    t = timeline.timeline(store, "bloodhound", "fan out", _archive(tmp_path))
    assert [c["sha"] for c in t.sessions[1].commits] == ["bbbbbbb", "aaaaaaa"]


def test_GREEN_an_undated_receipt_is_nobodys_before(tmp_path):
    store = FakeStore()
    store.records["history://receipt/recon.x"] = {"node_type": "receipt", "name": "recon.x", "measured_at": None,
                                                  "numbers": {"floor.seconds": 1.0}}
    t = timeline.timeline(store, "bloodhound", "fan out", _archive(tmp_path))
    r = t.sessions[1].commits[0]["issues"][0]["receipts"][0]
    assert r["moved"] == [("floor.seconds", 9.8, 8.1)]


def test_RED_the_verb_refuses_without_a_tenant_or_with_two_bare_terms(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "bloodhound", "--with", "x"], capture_output=True, text=True, cwd=ROOT / "engine")
    assert proc.returncode == 2 and proc.stderr.startswith("HISTORY REFUSED: --tenant and --tenant-id are required")
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "a", "b", "--tenant", "x", "--tenant-id", "y"],
                          capture_output=True, text=True, cwd=ROOT / "engine")
    assert proc.returncode == 2 and proc.stderr.startswith("HISTORY REFUSED: one term, and the second through --with")
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "--with", "x", "--tenant", "t", "--tenant-id", "y"],
                          capture_output=True, text=True, cwd=ROOT / "engine")
    assert proc.returncode == 2 and proc.stderr.startswith("HISTORY REFUSED: the timeline needs a term")
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "gallery", "--repo", ".", "--out", str(tmp_path), "--verify"],
                          capture_output=True, text=True, cwd=ROOT / "engine")
    assert proc.returncode == 2 and proc.stderr.startswith("HISTORY REFUSED: one mode per call") and "verify" in proc.stderr


def test_GREEN_cold_over_this_tenant_under_a_second():
    """The production shape: a fresh process, the real archive, the real store — the story in under a second."""
    desc = ROOT / "engine" / "tenants" / "graphy" / "tenant.json"
    archive = ROOT / ".claude" / "recovery" / "sessions"
    if not desc.is_file() or not archive.is_dir():
        pytest.skip("the graphy tenant or the sessions archive is not on this box")
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "gallery", "--with", "showcase", "--tenant", str(desc),
                           "--tenant-id", "graphy", "--sessions", str(archive)], capture_output=True, text=True, cwd=ROOT / "engine")
    wall = time.perf_counter() - t0
    assert proc.returncode == 0, proc.stderr
    last = proc.stdout.splitlines()[-1]
    assert last.startswith("TIMELINE: ") and " 0 session(s)" not in last, last
    assert wall < 1.0, f"{wall:.2f} s"


def test_GREEN_the_mcp_tool_is_the_same_door():
    from graphy import mcp
    names = [t["name"] for t in mcp.TOOLS]
    assert "history" in names and len(names) == 7
    assert {"term", "partner", "window", "sessions"} == set(next(t for t in mcp.TOOLS if t["name"] == "history")["inputSchema"]["properties"])
