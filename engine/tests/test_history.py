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
        body = ("--- [1] USER\n\nhello, look at `showcase._clone` and showcase.py — the clone dir, and graphy/adapters/__init__.py\n\n"
                "--- [1] ASSISTANT\n\nreading graphy.showcase._clone; `helper` alone and `showcase` alone bind nothing; "
                "widgets.helper is in two shards (graphy.showcase._clone again)\n\n"
                "--- [2] USER\n\nnothing dotted here\n" if seq != "00003" else
                "--- [1] USER\n\nhello, look at `showcase._clone` and showcase.py — the clone dir, and graphy/adapters/__init__.py\n\n"
                "--- [1] ASSISTANT\n\nthe fuller capture: graphy.showcase._clone and test_showcase.py\n\n--- [2] USER\n\nadapters/__init__.py\n")
        (sessions / f"{seq}__x__{sid[:8]}.md").write_text(
            f"# CONVERSATION FULL SESSION — {ex} exchanges, verbatim and in order\n\nsource: /x.jsonl\nsession: {sid}\n"
            f"captured_at: {cap}\nresolved_by: SessionEnd\n\n{body}")
    (sessions / "notes.md").write_text("# not a session\n")
    return repo


def _code_shard(tmp_path: Path) -> Path:
    """A code shard the way python_ast records module files: relative to the corpus's parent."""
    shard = tmp_path / "graphy_graph"
    shard.mkdir()
    mods = {"graphy://module/graphy.showcase": "graphy/showcase.py", "graphy://module/graphy.adapters": "graphy/adapters/__init__.py",
            "graphy://module/graphy.café": "graphy/café.py", "tests://module/tests.test_showcase": "tests/test_showcase.py"}
    nodes = {i: {"kind": "node", "node_type": "module", "id": i, "file": f, "dotted": i.rsplit("/", 1)[-1]} for i, f in mods.items()}
    for i in ("graphy://func/graphy.showcase._clone", "graphy://func/graphy.helper", "graphy://func/graphy.widgets.helper",
              "tests://func/tests.widgets.helper"):
        nodes[i] = {"kind": "node", "node_type": "func", "id": i, "dotted": i.rsplit("/", 1)[-1], "file": "x.py", "line": 1}
    (shard / "nodes.json").write_text(json.dumps(nodes))
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
    assert kinds == {"commit", "session", "section", "issue", "receipt", "exchange"}
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


S1 = "history://session/aaaa1111-0000-0000-0000-000000000001"
S2 = "history://session/bbbb2222-0000-0000-0000-000000000002"
X1 = "history://exchange/aaaa1111-0000-0000-0000-000000000001"
X2 = "history://exchange/bbbb2222-0000-0000-0000-000000000002"


def _mentions(edges: list) -> dict[tuple[str, str], dict]:
    return {(e["src"], e["dst"]): e for e in edges if e["edge_type"] == "mentions"}


def test_GREEN_every_exchange_is_a_node_under_its_session_welded_to_the_code_on_its_literals(tmp_path, monkeypatch):
    """graphyos #64: the archive's `--- [n] USER|ASSISTANT` markers become exchange nodes; a literal that names one
    node of the code shards — a dotted name, its unique tail, a module's file name, a slashed path — is a
    `mentions` edge that says how it bound; a bare word and an ambiguous tail bind nothing; nothing private travels."""
    repo = _repo(tmp_path)
    out = tmp_path / "history_graph"
    monkeypatch.chdir(tmp_path)
    prov = history.mint(repo, out, sessions=tmp_path / "sessions", code=[_code_shard(tmp_path)])
    nodes = json.loads((out / "nodes.json").read_text())
    edges = json.loads((out / "edges.json").read_text())
    ex = {i: n for i, n in nodes.items() if n["node_type"] == "exchange"}
    # session 1: three markers; session 2 captured twice: the fuller capture's three markers, one node each
    assert sorted(ex) == [f"{X1}/1/assistant", f"{X1}/1/user", f"{X1}/2/user", f"{X2}/1/assistant", f"{X2}/1/user", f"{X2}/2/user"]
    assert prov["history"]["exchanges"] == 6
    x = ex[f"{X1}/1/user"]
    assert x["session"] == S1 and x["n"] == 1 and x["speaker"] == "user" and x["role"] == "exchange"
    assert x["captured_at"] == "2026-09-05T11:00:00+00:00"
    assert x["dotted"] == "history.exchange.aaaa1111.1.user" and x["literals"] == 3
    for n in ex.values():
        assert set(n) <= {"kind", "node_type", "id", "dotted", "module", "role", "speaker", "session", "n", "captured_at", "file",
                          "literals", "name"}, "an exchange node is a session, a number, a speaker and a count — never a body"
        assert "hello" not in json.dumps(n) and "clone dir" not in json.dumps(n)
    assert {(e["src"], e["dst"]) for e in edges if e["edge_type"] == "contains"} == {(x["session"], i) for i, x in ex.items()}
    m = _mentions(edges)
    # the binding: `showcase._clone` is the unique tail of graphy.showcase._clone; showcase.py the module's own file;
    # graphy/adapters/__init__.py the path; the fuller capture of session 2 speaks for its exchanges
    assert m[(f"{X1}/1/user", "graphy://func/graphy.showcase._clone")] == {
        "kind": "edge", "edge_type": "mentions", "src": f"{X1}/1/user", "dst": "graphy://func/graphy.showcase._clone",
        "via": "dotted", "count": 1, "literal": "showcase._clone"}
    assert m[(f"{X1}/1/user", "graphy://module/graphy.showcase")]["via"] == "file"
    assert m[(f"{X1}/1/user", "graphy://module/graphy.adapters")]["literal"] == "graphy/adapters/__init__.py"
    a = m[(f"{X1}/1/assistant", "graphy://func/graphy.showcase._clone")]
    assert a["count"] == 2 and a["literal"] == "graphy.showcase._clone", "two literals, one node: one edge, the count summed"
    assert not [k for k in m if k[0] == f"{X1}/1/assistant" and k[1].endswith("helper")], \
        "`helper` is a bare word and widgets.helper names two nodes: neither binds — a name match is never a fact"
    assert not [k for k in m if k[0] == f"{X1}/2/user"]
    assert m[(f"{X2}/1/assistant", "tests://module/tests.test_showcase")]["literal"] == "test_showcase.py"
    assert m[(f"{X2}/2/user", "graphy://module/graphy.adapters")]["literal"] == "adapters/__init__.py", \
        "a path shorter than the shard's own is matched on a slash boundary too; `__init__.py` alone names four and binds nothing"
    h = prov["history"]
    # seven distinct literals across the archive: six bind, `widgets.helper` names two nodes and binds nothing
    assert h["mentions"] == len(m) == 10 and h["literals"] == 7 and h["bound"] == 6 and h["ambiguous"] == 1 and h["aliases"] == 0
    assert "mentions: 6 of 7 literal(s) bind a node by the roster's names, 1 name two or more and bind nothing; aliases: none" in h["note"]
    assert validate_graph(nodes, edges, history.HISTORY_VOCABULARY)
    # the record's counts are the ones §94 minted — the exchanges are added beside them, never in their place
    assert h["commits"] == 3 and h["sessions"] == 3 and h["sections"] == 2 and h["receipts"] == 2 and h["touches"] == 5


def test_GREEN_the_alias_registry_is_an_admitted_weld_and_refuses_by_name(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    out = tmp_path / "history_graph"
    monkeypatch.chdir(tmp_path)
    shard = _code_shard(tmp_path)
    reg = tmp_path / "aliases.json"
    reg.write_text(json.dumps({"_meta": "notes", "the clone dir": "graphy://func/graphy.showcase._clone"}))
    prov = history.mint(repo, out, sessions=tmp_path / "sessions", code=[shard], aliases=reg)
    edges = json.loads((out / "edges.json").read_text())
    m = _mentions(edges)
    e = m[(f"{X1}/1/user", "graphy://func/graphy.showcase._clone")]
    assert e["via"] == "dotted" and e["count"] == 2 and e["literal"] == "showcase._clone", \
        "the alias and the name land on one node: one edge, the roster's name outranks the weld, the count summed"
    assert m[(f"{X2}/1/user", "graphy://func/graphy.showcase._clone")]["count"] == 2
    assert prov["history"]["aliases"] == 1 and prov["history"]["aliased"] == 0 and "1 alias(es) welded 0 edge(s)" in prov["history"]["note"]
    assert prov["corpus"]["aliases"] == "aliases.json" and prov["mint_command"].endswith(" --aliases aliases.json")
    # the weld alone: a literal only the registry binds
    reg.write_text(json.dumps({"clone dir": "graphy://func/graphy.helper"}))
    prov = history.mint(repo, out, sessions=tmp_path / "sessions", code=[shard], aliases=reg)
    m = _mentions(json.loads((out / "edges.json").read_text()))
    assert m[(f"{X1}/1/user", "graphy://func/graphy.helper")] == {
        "kind": "edge", "edge_type": "mentions", "src": f"{X1}/1/user", "dst": "graphy://func/graphy.helper",
        "via": "alias", "count": 1, "literal": "clone dir"}
    assert prov["history"]["aliased"] == 2
    # the registry moved: the shard is stale by the digest
    fresh, why = history.verify(out, repo=repo)
    assert fresh, why
    reg.write_text(json.dumps({"clone dir": "graphy://func/graphy.showcase._clone"}))
    fresh, why = history.verify(out, repo=repo)
    assert not fresh and "the registry moved" in why
    # a target that is not a node refuses; a literal the roster's names already bind refuses as redundant
    reg.write_text(json.dumps({"clone dir": "graphy://func/graphy.nope"}))
    with pytest.raises(history.HistoryError, match="'clone dir' → graphy://func/graphy.nope names no node"):
        history.mint(repo, out, sessions=tmp_path / "sessions", code=[shard], aliases=reg)
    reg.write_text(json.dumps({"showcase._clone": "graphy://func/graphy.helper"}))
    with pytest.raises(history.HistoryError, match="'showcase._clone' already binds graphy://func/graphy.showcase._clone by the roster's own names"):
        history.mint(repo, out, sessions=tmp_path / "sessions", code=[shard], aliases=reg)
    reg.write_text(json.dumps({"x": 3}))
    with pytest.raises(history.HistoryError, match="not a literal → node id"):
        history.mint(repo, out, sessions=tmp_path / "sessions", code=[shard], aliases=reg)
    with pytest.raises(history.HistoryError, match="not a readable JSON object"):
        history.mint(repo, out, sessions=tmp_path / "sessions", code=[shard], aliases=tmp_path / "nope.json")


def test_GREEN_literals_are_dotted_names_and_paths_never_bare_words():
    lits = history.literals_of("see `showcase._clone`, graphy.showcase._clone(url), showcase.py; e.g. x — bare showcase, "
                               "a-b.c no, tree-sitter.py no, engine/graphy/cli.py yes, .claude/recovery yes, v1.2 no")
    assert lits == {"showcase._clone": 1, "graphy.showcase._clone": 1, "showcase.py": 1, "engine/graphy/cli.py": 1,
                    ".claude/recovery": 1, "e.g": 1}, "a dotfile path keeps its dot; `e.g` is a dotted token that binds nothing"
    assert history.literals_of("nothing dotted") == {}
    # the review's specimen: a name at a sentence's end, or before a hyphen, is still the name
    assert history.literals_of("see graphy.cli.") == {"graphy.cli": 1} and history.literals_of("graphy.cli-based") == {"graphy.cli": 1}
    assert history.literals_of("in graphy/cli.py.") == {"graphy/cli.py": 1} and history.literals_of("(graphy.cli)") == {"graphy.cli": 1}
    assert history.symbol_index([]) == {}
    # two spellings of one node in one exchange: one edge, both literals counted as bound
    bound, matched, ambiguous, unbound = history.bind({"graphy.cli": 1, "cli.py": 1, "x.y": 1, "a.b": 1}, {},
                                                      {"graphy.cli": {"M"}, "cli.py": {"M"}, "a.b": {"P", "Q"}}, {})
    assert bound == {"M": {"via": "dotted", "count": 2, "literal": "graphy.cli"}}
    assert matched == {"graphy.cli", "cli.py"} and ambiguous == {"a.b"} and unbound == {"x.y"}


def test_GREEN_an_alias_is_matched_on_token_boundaries_and_the_registry_keeps_every_key_but_meta(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "a.md").write_text("--- [1] USER\n\nlook at graphy.sugiyama and sugiyama.py, then sugiyama alone; the showcase.txt, the showcase page\n")
    aliases = {"sugiyama": "g://module/g.sugiyama", "the showcase": "g://func/g.showcase.showcase"}
    (ex,), sha = history.read_exchanges(d, "a.md", aliases)
    assert ex["aliases"] == {"sugiyama": 1, "the showcase": 1}, \
        "`sugiyama` inside `graphy.sugiyama` and `sugiyama.py` is the name the roster binds, never a second hit"
    assert len(sha) == 64
    reg = tmp_path / "aliases.json"
    reg.write_text(json.dumps({"_meta": "a note", "_clone": "g://func/g.showcase._clone"}))
    assert history.read_aliases(reg) == {"_clone": "g://func/g.showcase._clone"}, "`_clone` is exactly the bare word only the registry binds"
    reg.write_text(json.dumps({"_note": "prose"}))
    with pytest.raises(history.HistoryError, match="'_note' → 'prose' is not a literal → node id"):
        history.read_aliases(reg)


def test_RED_an_edited_exchange_body_is_drift(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    out = tmp_path / "history_graph"
    monkeypatch.chdir(tmp_path)
    history.mint(repo, out, sessions=tmp_path / "sessions", code=[_code_shard(tmp_path)])
    assert history.verify(out, repo=repo)[0]
    f = tmp_path / "sessions" / "00001__x__aaaa1111.md"
    f.write_text(f.read_text() + "\n--- [3] USER\n\ngraphy.showcase._clone again\n")      # below the header: the same capture line
    fresh, why = history.verify(out, repo=repo)
    assert not fresh and "session capture or body" in why


def test_RED_every_refusal_comes_before_the_lightning_import(tmp_path):
    """graphyos #60's law: a box with no ripgrep hears the refusal first and nothing else — the producer imports
    reseed_graph's marker inside the read, never at the top of the module."""
    proc = subprocess.run([sys.executable, "-m", "graphy", "history", "--repo", str(tmp_path / "nope"), "--out", str(tmp_path / "h")],
                          capture_output=True, text=True, cwd=ROOT / "engine",
                          env={"PATH": "/nonexistent", "PYTHONPATH": str(ROOT / "engine"), "GRAPHY_RG": "/nonexistent/rg"})
    assert proc.returncode == 2 and proc.stderr.startswith("HISTORY REFUSED: not a git repository"), proc.stderr


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
    assert prov["history"]["touches"] == 0 and prov["history"]["exchanges"] == 0 and prov["history"]["mentions"] == 0
    assert prov["history"]["note"] == ("sessions: none given — commits · sections · issues · receipts alone; "
                                       "touches: none — no --code shard given, so no file maps to a module id")
    assert prov["corpus"]["sessions"] is None and prov["corpus"]["code"] == [] and prov["corpus"]["aliases"] is None
    prov = history.mint(repo, tmp_path / "h2", sessions=tmp_path / "sessions")
    assert prov["history"]["exchanges"] == 6 and prov["history"]["mentions"] == 0
    assert prov["history"]["note"].endswith("mentions: none — no --code shard given, so no literal has a node to bind")


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
    mentioned = {e["dst"] for e in edges if e["edge_type"] == "mentions"}
    assert mentioned <= own, sorted(mentioned - own)[:5]
