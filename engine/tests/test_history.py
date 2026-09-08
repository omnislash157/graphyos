"""The history shard (graphyos #59): the repo's own record — commits · sessions · RECON sections ·
issues · receipts — minted as a shard beside the code, a commit's `touches` the code shard's module
ids (the wormhole), a session's window the join that authors a commit."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import os

import pytest

from graphy.adapters import history
from graphy.ir import validate_graph

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str, env_date: str | None = None) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin"}
    if env_date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = env_date
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "engine" / "graphy" / "adapters").mkdir(parents=True)
    (repo / "engine" / "tests").mkdir()
    _git(repo, "init", "-q")
    (repo / "engine" / "graphy" / "showcase.py").write_text("x = 1\n")
    (repo / "engine" / "graphy" / "adapters" / "__init__.py").write_text("")
    (repo / "engine" / "graphy" / "café.py").write_text("")             # git quotes this path by default
    (repo / "RECON.md").write_text("# r\n\n## 1 · THE FIRST (2026-09-05 · graphyos issue 3)\n\ntext\n\n## 2 · THE SECOND (2026-09-06)\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "one: the first (graphyos #3)\n\nRECON §1\n\nClaude-Session: https://claude.ai/code/session_A",
         env_date="2026-09-05T10:00:00+00:00")
    (repo / "engine" / "tests" / "test_showcase.py").write_text("y = 2\n")
    (repo / "engine" / "graphy" / "showcase.py").write_text("x = 2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "two: the second, graphyos issue 4 — RECON §2 and RECON §9 (a section the file lost)",
         env_date="2026-09-05T12:00:00+00:00")
    (repo / "README.md").write_text("r\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "three: prose only", env_date="2026-09-05T14:00:00+00:00")
    (repo / "recon.before3.json").write_text(json.dumps({"floor": {"seconds": 9.8, "passed": 5, "hot": ["a 1s"]},
                                                        "measured_at": "2026-09-05T09:00:00+00:00", "seconds": 1.5}))
    (repo / "recon.json").write_text(json.dumps({"floor": {"seconds": 8.1}, "measured_at": "2026-09-05T15:00:00+00:00"}))
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    for seq, sid, cap, ex in (("00001", "aaaa1111-0000-0000-0000-000000000001", "2026-09-05T11:00:00+00:00", 4),
                              ("00002", "bbbb2222-0000-0000-0000-000000000002", "2026-09-05T13:00:00+00:00", 7),
                              ("00003", "bbbb2222-0000-0000-0000-000000000002", "2026-09-05T13:30:00+00:00", 9)):
        (sessions / f"{seq}__x__{sid[:8]}.md").write_text(
            f"# CONVERSATION FULL SESSION — {ex} exchanges, verbatim and in order\n\nsource: /x.jsonl\nsession: {sid}\n"
            f"captured_at: {cap}\nresolved_by: SessionEnd\n\n--- [1] USER\n\nhello\n")
    (sessions / "notes.md").write_text("# not a session\n")
    return repo


def _code_shard(tmp_path: Path) -> Path:
    """A code shard the way python_ast records module files: relative to the corpus's parent."""
    shard = tmp_path / "graphy_graph"
    shard.mkdir()
    mods = {"graphy://module/graphy.showcase": "graphy/showcase.py", "graphy://module/graphy.adapters": "graphy/adapters/__init__.py",
            "graphy://module/graphy.café": "graphy/café.py", "tests://module/tests.test_showcase": "tests/test_showcase.py"}
    (shard / "nodes.json").write_text(json.dumps({i: {"kind": "node", "node_type": "module", "id": i, "file": f} for i, f in mods.items()}))
    (shard / "edges.json").write_text("[]")
    return shard


def test_GREEN_the_record_becomes_a_shard_and_the_joins_are_edges(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    out = tmp_path / "history_graph"
    monkeypatch.chdir(tmp_path)
    prov = history.mint(repo, out, sessions=tmp_path / "sessions", code=[_code_shard(tmp_path)])
    nodes = json.loads((out / "nodes.json").read_text())
    edges = json.loads((out / "edges.json").read_text())
    assert validate_graph(nodes, edges, history.HISTORY_VOCABULARY) == len(nodes) + len(edges)
    kinds = {n["node_type"] for n in nodes.values()}
    assert kinds == {"commit", "session", "section", "issue", "receipt"}
    assert prov["history"]["commits"] == 3 and prov["history"]["sections"] == 2 and prov["history"]["receipts"] == 2
    assert prov["history"]["sessions"] == 3 and sum(1 for n in nodes.values() if n["node_type"] == "session") == 2, \
        "a session captured twice is one node"
    assert prov["producer"]["adapter"] == "history" and len(prov["producer"]["source"]) == 16
    assert prov["files"]["nodes.json"]["sha256"]
    shas = _git(repo, "log", "--reverse", "--format=%H").split()
    one, two, three = (f"history://commit/{s}" for s in shas)
    by = lambda t: {(e["src"], e["dst"]) for e in edges if e["edge_type"] == t}
    # the session window authors the commit: 12:00 falls in the second capture's (11:00, 13:00]; 10:00 is
    # before the first capture and 14:00 after the last — no window, no edge, counted, never guessed
    assert by("authored") == {("history://session/bbbb2222-0000-0000-0000-000000000002", two)}
    assert prov["history"]["authored"] == 1 and prov["history"]["unauthored"] == 2
    assert nodes[one]["claude_session"] == "https://claude.ai/code/session_A" and nodes[two]["claude_session"] is None
    # the message names the section and the issue; a section the file lost is no node and no edge
    assert by("records") == {(one, "history://section/1"), (two, "history://section/2")}
    assert by("names") == {(one, "history://issue/3"), (two, "history://issue/4"), ("history://section/1", "history://issue/3")}
    for n in nodes.values():                           # the id law: <scheme>://<node_type>/<dotted>
        assert n["id"].split("://", 1)[1].split("/", 1)[0] == n["node_type"], n["id"]
    assert nodes["history://issue/3"]["title"] == "THE FIRST (2026-09-05 · graphyos issue 3)"
    assert nodes["history://issue/4"]["title"].startswith("two: the second")
    # the files a commit changed, as the code shards' own module ids — the wormhole; prose touches nothing;
    # a path git would quote (café) still maps
    assert by("touches") == {(one, "graphy://module/graphy.showcase"), (one, "graphy://module/graphy.adapters"),
                             (one, "graphy://module/graphy.café"),
                             (two, "graphy://module/graphy.showcase"), (two, "tests://module/tests.test_showcase")}
    assert nodes[three]["files"] == 1 and not [e for e in edges if e["src"] == three and e["edge_type"] == "touches"]
    # the receipt pins its issue and carries the numbers, never the frames
    assert by("pins") == {("history://receipt/recon.before3", "history://issue/3")}
    assert nodes["history://receipt/recon.before3"]["numbers"] == {"floor.seconds": 9.8, "floor.passed": 5, "seconds": 1.5}
    # time order within a kind
    assert by("follows") >= {(one, two), (two, three), ("history://section/1", "history://section/2"),
                             ("history://session/aaaa1111-0000-0000-0000-000000000001",
                              "history://session/bbbb2222-0000-0000-0000-000000000002")}
    for n in nodes.values():
        assert n["module"] == "history" and n["role"] == n["node_type"]
        assert "body" not in n and "text" not in n, "nothing private travels: a session is an id, a time, a count"
    # the receipt names no box: every path portable, the mint command rebuilt from them
    blob = json.dumps(prov)
    assert str(tmp_path) not in blob, blob
    assert prov["corpus"]["sessions"] == "sessions" and prov["corpus"]["code"] == ["graphy_graph"]
    assert prov["mint_command"] == "python3 -m graphy history --repo repo --out history_graph --sessions sessions --code graphy_graph"
    assert prov["producer"]["source"] != "unknown"


def test_GREEN_verify_names_drift_in_inputs_git_does_not_track(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    out = tmp_path / "history_graph"
    monkeypatch.chdir(tmp_path)
    history.mint(repo, out, sessions=tmp_path / "sessions", code=[_code_shard(tmp_path)])
    fresh, why = history.verify(out, repo=repo)
    assert fresh and why.startswith("fresh:"), why
    (tmp_path / "sessions" / "00004__x__cccc3333.md").write_text(
        "# CONVERSATION FULL SESSION — 2 exchanges, verbatim and in order\n\nsession: cccc3333-0000-0000-0000-000000000003\n"
        "captured_at: 2026-09-05T16:00:00+00:00\n")
    fresh, why = history.verify(out, repo=repo)
    assert not fresh and "stale" in why and "re-mint" in why
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "--repo", str(repo), "--out", str(out), "--verify"],
                          capture_output=True, text=True, cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(ROOT / "engine")})
    assert proc.returncode == 1 and proc.stdout.startswith("HISTORY STALE:"), proc.stdout + proc.stderr
    history.mint(repo, out, sessions=tmp_path / "sessions", code=[tmp_path / "graphy_graph"])
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "--repo", str(repo), "--out", str(out), "--verify"],
                          capture_output=True, text=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "engine")})
    assert proc.returncode == 0 and proc.stdout.startswith("HISTORY OK:"), proc.stdout + proc.stderr


def test_RED_two_code_shards_naming_one_file_refuse(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d, mid in ((a, "x://module/x"), (b, "y://module/y")):
        d.mkdir()
        (d / "nodes.json").write_text(json.dumps({mid: {"kind": "node", "node_type": "module", "id": mid, "file": "p/m.py"}}))
    with pytest.raises(history.HistoryError, match="disagree on 'p/m.py'"):
        history.code_index([a, b])


def test_GREEN_without_sessions_or_code_the_shard_says_so(tmp_path):
    repo = _repo(tmp_path)
    prov = history.mint(repo, tmp_path / "h")
    assert prov["history"]["sessions"] == 0 and prov["history"]["authored"] == 0 and prov["history"]["unauthored"] == 3
    assert prov["history"]["touches"] == 0
    assert prov["history"]["note"] == ("sessions: none given — commits · sections · issues · receipts alone; "
                                       "touches: none — no --code shard given, so no file maps to a module id")
    assert prov["corpus"]["sessions"] is None and prov["corpus"]["code"] == []


def test_RED_history_refusals(tmp_path):
    with pytest.raises(history.HistoryError, match="not a git repository"):
        history.mint(tmp_path, tmp_path / "h")
    repo = _repo(tmp_path)
    with pytest.raises(history.HistoryError, match="no sessions directory"):
        history.mint(repo, tmp_path / "h", sessions=tmp_path / "nope")
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "--out", str(tmp_path / "h")],
                          capture_output=True, text=True, cwd=ROOT / "engine")
    assert proc.returncode == 2 and proc.stderr.startswith("HISTORY REFUSED: --repo is required")


def test_GREEN_module_id_of_matches_on_a_slash_boundary_from_the_shards_own_files():
    index = {"graphy/showcase.py": "graphy://module/graphy.showcase", "tests/test_smash.py": "tests://module/tests.test_smash"}
    assert history.module_id_of("engine/graphy/showcase.py", index) == "graphy://module/graphy.showcase"
    assert history.module_id_of("graphy/showcase.py", index) == "graphy://module/graphy.showcase"
    assert history.module_id_of("engine/tests/test_smash.py", index) == "tests://module/tests.test_smash"
    for other in ("RECON.md", "gallery.py", "xgraphy/showcase.py", "engine/graphy/showcase.pyc", "engine/tenants/graphy/rebuild.sh"):
        assert history.module_id_of(other, index) is None, other


def test_GREEN_the_verb_mints_this_repo_onto_the_tenants_own_code_shards(tmp_path):
    """The real record over this checkout's code shards: every `touches` dst is a module id one of them owns."""
    shards = [ROOT / "engine" / "tenants" / "graphy" / "substrate" / f"{s}_graph" for s in ("graphy", "tests")]
    if not all((s / "nodes.json").is_file() for s in shards):
        pytest.skip("the graphy tenant is not built on this box (bash tenants/graphy/rebuild.sh)")
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "--repo", str(ROOT), "--out", str(tmp_path / "h"),
                           *[a for s in shards for a in ("--code", str(s))]], capture_output=True, text=True, cwd=ROOT / "engine")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines()[-1].startswith("HISTORY OK: ")
    own = set()
    for s in shards:
        own |= set(json.loads((s / "nodes.json").read_text()))
    edges = json.loads((tmp_path / "h" / "edges.json").read_text())
    dsts = {e["dst"] for e in edges if e["edge_type"] == "touches"}
    assert dsts and dsts <= own, sorted(dsts - own)[:5]
