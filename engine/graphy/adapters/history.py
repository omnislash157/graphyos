"""history — the repo's own record minted as a shard (graphyos #59).

A codebase's history is a corpus with rules, so it becomes AST: commits (``git log``), the sessions
archive (``.claude/recovery/sessions/*.md``, each file's header), ``RECON.md``'s ``## N ·`` sections,
the issues those name, and the receipts pinned to them (``recon.before<N>.json``) are five kinds of
node, joined by edges that exist today as text in five places and as edges nowhere:

    history://commit/<sha>       history://session/<id>      history://section/<n>
    history://issue/<n>          history://receipt/<name>

    session  -authored-> commit      the commit's author time falls in the session's window —
                                     after the previous capture, up to this one (one box, one pane;
                                     a commit before the first capture or after the last has no
                                     window and no edge — counted, never guessed; the
                                     ``Claude-Session`` trailer names a claude.ai session that
                                     spans many local ones, so it is an attribute, never the join)
    commit   -records->  section     ``RECON §N`` in the message
    commit   -names->    issue       ``graphyos #N`` · ``graphyos issue N`` in the message
    section  -names->    issue       the section title's ``graphyos issue N``
    receipt  -pins->     issue       ``recon.before<N>.json``
    commit   -touches->  <code module id>   a file the commit changed, as the code shard's own
                                     module id (``graphy://module/graphy.showcase``): the same
                                     literal in two graphs — the wormhole, free by construction.
                                     The map is read from the code shards handed in (``--code``,
                                     each module node's ``file``), never from a layout this
                                     producer assumes; no code shard, no touches, said so
    x        -follows->  x           time order within a kind

Nothing private travels: a session node is an id, a time and a count — never a body; the shard is a
build product under the tenant's substrate. Stdlib only; ``git`` is the one program.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from graphy.ir import Vocabulary, validate_graph

__all__ = ["HISTORY_VOCABULARY", "HistoryError", "build_ir", "code_index", "mint", "module_id_of", "verify"]

HISTORY_VOCABULARY = Vocabulary(
    node_types=("commit", "session", "section", "issue", "receipt"),
    edge_types=("authored", "records", "names", "pins", "touches", "follows"),
    producer="history",
)

SCHEME = "history"
_SECTION = re.compile(r"^## (\d+) · (.*)$")
_ISSUE_IN_TITLE = re.compile(r"graphyos (?:issue |#)(\d+)")
_ISSUE_IN_BODY = re.compile(r"graphyos (?:issue |#)(\d+)")
_RECON_IN_BODY = re.compile(r"RECON §(\d+)")
_DATE_IN_TITLE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_CLAUDE_SESSION = re.compile(r"^Claude-Session: (\S+)$", re.M)
_RECEIPT = re.compile(r"^recon\.before(\d+)\.json$")
_SESSION_HEADER = re.compile(r"^session: ([0-9a-f-]{8,})$", re.M)
_CAPTURED = re.compile(r"^captured_at: (\S+)$", re.M)
_EXCHANGES = re.compile(r"— (\d+) exchanges")


class HistoryError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise HistoryError(f"git {' '.join(a for a in args if not a.startswith(('-c', 'core.')))[:24]} failed under "
                           f"{repo}: {(proc.stderr or '').strip()[-300:]}")
    return proc.stdout


def code_index(shards: list[Path]) -> dict[str, str]:
    """``file → module id`` from the code shards handed in: every module node's ``file`` (relative to
    the corpus's parent, the way python_ast and typescript_ast record it). Two shards naming one file
    refuse — a file is one module."""
    index: dict[str, str] = {}
    for shard in shards:
        shard = Path(shard)
        try:
            nodes = json.loads((shard / "nodes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HistoryError(f"--code {shard}: no readable nodes.json ({exc})") from exc
        for rec in (nodes.values() if isinstance(nodes, dict) else nodes):
            if rec.get("node_type") == "module" and isinstance(rec.get("file"), str) and isinstance(rec.get("id"), str):
                f = rec["file"].replace("\\", "/")
                if index.get(f, rec["id"]) != rec["id"]:
                    raise HistoryError(f"--code shards disagree on {f!r}: {index[f]} and {rec['id']}")
                index[f] = rec["id"]
    return index


def module_id_of(path: str, index: dict[str, str]) -> str | None:
    """A changed file (repo-relative) as the module id a code shard records for it, or None when no
    shard owns it — matched on a `/` boundary, so `engine/graphy/cli.py` is `graphy/cli.py`'s module."""
    parts = path.split("/")
    for i in range(len(parts)):
        hit = index.get("/".join(parts[i:]))
        if hit:
            return hit
    return None


def read_commits(repo: Path) -> list[dict]:
    """Every commit, oldest first: sha · authored (iso) · subject · body · the files it changed."""
    raw = _git(repo, "-c", "core.quotePath=false", "log", "--reverse", "--format=%x1e%H%x1f%aI%x1f%s%x1f%B",
               "--name-only")
    out = []
    for chunk in raw.split("\x1e"):
        if not chunk.strip():
            continue
        sha, when, subject, rest = chunk.split("\x1f", 3)
        # %B ends with a newline; the name list follows after one blank line
        body, _, names = rest.rpartition("\n\n")
        if not names.strip() or any("\x1f" in n for n in names.splitlines()):
            body, names = rest, ""
        files = [n.strip() for n in names.splitlines() if n.strip()]
        m = _CLAUDE_SESSION.search(body)
        out.append({"sha": sha, "authored": when, "subject": subject, "body": body.strip(), "files": files,
                    "claude_session": m.group(1) if m else None})
    return out


def read_sessions(sessions: Path | None) -> list[dict]:
    """The archive's files in sequence: id · captured_at · exchanges · the file's name."""
    if sessions is None:
        return []
    if not sessions.is_dir():
        raise HistoryError(f"no sessions directory at {sessions}")
    out = []
    for p in sorted(sessions.glob("*.md")):
        head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
        sid, cap = _SESSION_HEADER.search(head), _CAPTURED.search(head)
        if not sid or not cap:
            continue                                     # not a captured session: the header is the contract
        ex = _EXCHANGES.search(head)
        out.append({"id": sid.group(1), "captured_at": cap.group(1), "exchanges": int(ex.group(1)) if ex else None,
                    "file": p.name})
    return out


def read_sections(recon: Path) -> list[dict]:
    if not recon.is_file():
        return []
    out = []
    for i, line in enumerate(recon.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        m = _SECTION.match(line)
        if not m:
            continue
        n, title = int(m.group(1)), m.group(2).strip()
        issue, date = _ISSUE_IN_TITLE.search(title), _DATE_IN_TITLE.search(title)
        out.append({"n": n, "title": title, "line": i, "issue": int(issue.group(1)) if issue else None,
                    "date": date.group(1) if date else None})
    return out


def _numbers(obj, prefix: str = "", out: dict | None = None) -> dict:
    """The receipt's numeric leaves as dotted keys; the profile's frame lists are not numbers."""
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("profile", "hot", "engine_hot", "argv"):
                continue
            _numbers(v, f"{prefix}{k}.", out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix.rstrip(".")] = obj
    return out


def read_receipts(repo: Path) -> list[dict]:
    out = []
    for p in sorted(repo.glob("recon*.json")):
        m = _RECEIPT.match(p.name)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        out.append({"name": p.stem, "issue": int(m.group(1)) if m else None, "measured_at": data.get("measured_at"),
                    "numbers": _numbers(data)})
    return out


def _iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_ir(commits: list[dict], sessions: list[dict], sections: list[dict], receipts: list[dict],
             *, recon_file: str = "RECON.md", index: dict[str, str] | None = None) -> tuple[dict, list, dict]:
    """The records, and a tally: how many commits fell in no session's window."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    index = index or {}
    tally = {"unauthored": 0}

    def node(nid: str, node_type: str, dotted: str, **attrs) -> dict:
        rec = {"kind": "node", "node_type": node_type, "id": nid, "dotted": dotted, "module": SCHEME,
               "role": node_type, **attrs}
        nodes[nid] = rec
        return rec

    def edge(src: str, dst: str, edge_type: str, **attrs) -> None:
        edges.append({"kind": "edge", "edge_type": edge_type, "src": src, "dst": dst, **attrs})

    def issue_node(n: int, title: str | None = None) -> str:
        nid = f"{SCHEME}://issue/{n}"
        if nid not in nodes:
            node(nid, "issue", f"{SCHEME}.issue.{n}", number=n, title=title, name=f"graphyos #{n}")
        elif title and not nodes[nid].get("title"):
            nodes[nid]["title"] = title
        return nid

    prev = None
    for s in sections:
        nid = f"{SCHEME}://section/{s['n']}"
        node(nid, "section", f"{SCHEME}.section.{s['n']}", number=s["n"], title=s["title"], date=s["date"],
             file=recon_file, line=s["line"], name=f"§{s['n']}")
        if s["issue"] is not None:
            edge(nid, issue_node(s["issue"], s["title"]), "names", via="title")
        if prev:
            edge(prev, nid, "follows")
        prev = nid

    prev = None
    windows: list[tuple[datetime | None, datetime, str]] = []
    lo = None
    for s in sessions:
        nid = f"{SCHEME}://session/{s['id']}"
        if nid in nodes:                                 # captured twice (a compact, then the end): one node,
            nodes[nid].update(captured_at=s["captured_at"], exchanges=s["exchanges"], file=s["file"])   # two windows
        else:
            node(nid, "session", f"{SCHEME}.session.{s['id'][:8]}", captured_at=s["captured_at"],
                 exchanges=s["exchanges"], file=s["file"], name=s["id"][:8])
            if prev:
                edge(prev, nid, "follows")
            prev = nid
        hi = _iso(s["captured_at"])
        windows.append((lo, hi, nid))
        lo = hi

    prev = None
    for c in commits:
        nid = f"{SCHEME}://commit/{c['sha']}"
        touched = [m for m in (module_id_of(f, index) for f in c["files"]) if m]
        node(nid, "commit", f"{SCHEME}.commit.{c['sha'][:7]}", sha=c["sha"], authored=c["authored"],
             subject=c["subject"][:200], files=len(c["files"]), claude_session=c["claude_session"],
             name=c["sha"][:7])
        when = _iso(c["authored"])
        for w_lo, w_hi, sid in windows:                    # the first window has no floor: a commit before
            if w_lo is not None and w_lo < when <= w_hi:   # the first capture is nobody's, like one after the last
                edge(sid, nid, "authored", via="window")
                break
        else:
            tally["unauthored"] += 1
        for n in sorted({int(x) for x in _RECON_IN_BODY.findall(c["body"])}):
            edge(nid, f"{SCHEME}://section/{n}", "records", via="message")
        for n in sorted({int(x) for x in _ISSUE_IN_BODY.findall(c["body"])}):
            edge(nid, issue_node(n, c["subject"][:200]), "names", via="message")
        for mid in sorted(set(touched)):
            edge(nid, mid, "touches")
        if prev:
            edge(prev, nid, "follows")
        prev = nid

    for r in receipts:
        nid = f"{SCHEME}://receipt/{r['name']}"
        node(nid, "receipt", f"{SCHEME}.receipt.{r['name'].removeprefix('recon.')}", measured_at=r["measured_at"],
             numbers=r["numbers"], name=r["name"])
        if r["issue"] is not None:
            edge(nid, issue_node(r["issue"]), "pins")
    # a records/names edge onto a section the file no longer carries: the dst stays a label the
    # store leaves unowned — never a node invented for it
    edges = [e for e in edges if not (e["dst"].startswith(f"{SCHEME}://section/") and e["dst"] not in nodes)]
    validate_graph(nodes, edges, HISTORY_VOCABULARY)
    return nodes, edges, tally


def _digest(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", "surrogateescape"))
        h.update(b"\0")
    return h.hexdigest()


def _inputs(repo: Path, sessions: Path | None, recon: str, code: list[Path]) -> tuple[list, list, list, list, dict, str]:
    """Everything the shard is built from, and the digest of it — the same bytes twice give the same digest,
    so `verify` can name drift in inputs git does not track (the sessions archive, the receipts)."""
    commits = read_commits(repo)
    sess = read_sessions(sessions)
    sections = read_sections(repo / recon)
    receipts = read_receipts(repo)
    index = code_index(code)
    digest = _digest([c["sha"] for c in commits] + [f"{s['id']}@{s['captured_at']}" for s in sess]
                     + [f"§{s['n']} {s['title']}" for s in sections] + [json.dumps(r, sort_keys=True) for r in receipts]
                     + [f"{k}={v}" for k, v in sorted(index.items())])
    return commits, sess, sections, receipts, index, digest


def mint(repo: str | Path, out: str | Path, *, sessions: str | Path | None = None, recon: str = "RECON.md",
         code: list[str | Path] | None = None, mint_command: str | None = None) -> dict:
    """Mint the shard at ``out`` (nodes.json · edges.json · PROVENANCE.json, the smash shape) and return
    the PROVENANCE. ``sessions`` absent: no session, said in the receipt; ``code`` absent: no touches, said."""
    from graphy import smash as smash_lane
    repo = Path(repo).resolve()
    if not (repo / ".git").exists():
        raise HistoryError(f"not a git repository: {repo}")
    out = Path(out).resolve()
    sess_dir = Path(sessions).resolve() if sessions else None
    shards = [Path(c).resolve() for c in (code or [])]
    commits, sess, sections, receipts, index, digest = _inputs(repo, sess_dir, recon, shards)
    nodes, edges, tally = build_ir(commits, sess, sections, receipts, recon_file=recon, index=index)
    out.mkdir(parents=True, exist_ok=True)
    smash_lane._write_records(out / "nodes.json", nodes)
    smash_lane._write_records(out / "edges.json", edges)
    head = smash_lane.git_head(repo)
    if mint_command is None:
        mint_command = (f"python3 -m graphy history --repo {smash_lane.portable(repo)} --out {smash_lane.portable(out)}"
                        + (f" --sessions {smash_lane.portable(sess_dir)}" if sess_dir else "")
                        + (f" --recon {recon}" if recon != "RECON.md" else "")
                        + "".join(f" --code {smash_lane.portable(c)}" for c in shards))
    notes = []
    notes.append("a commit is authored by the session whose capture window holds its author time" if sess_dir
                 else "sessions: none given — commits · sections · issues · receipts alone")
    notes.append(f"touches: the module ids of {len(shards)} code shard(s)" if shards
                 else "touches: none — no --code shard given, so no file maps to a module id")
    prov = {
        "surface": f"{out.name}.records",
        "oracle_commit": head or f"sha256:{digest}",
        "mint_command": mint_command,
        "producer": {"adapter": "history", "graphy": smash_lane._graphy_version(),
                     "python": smash_lane.platform.python_version(), "source": smash_lane.producer_source("history")},
        "minted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {"scheme": SCHEME, "kind": "record", "path": smash_lane.portable(repo),
                   "files": len(commits) + len(sess) + len(sections) + len(receipts), "sha256": digest,
                   "git_head": head, "sessions": smash_lane.portable(sess_dir) if sess_dir else None,
                   "recon": recon, "code": [smash_lane.portable(c) for c in shards]},
        "counts": smash_lane._counts(nodes, edges),
        "files": {name: smash_lane._file_receipt(out / name) for name in ("nodes.json", "edges.json")},
        "history": {"commits": len(commits), "sessions": len(sess), "sections": len(sections),
                    "issues": sum(1 for n in nodes.values() if n["node_type"] == "issue"),
                    "receipts": len(receipts),
                    "authored": sum(1 for e in edges if e["edge_type"] == "authored"),
                    "unauthored": tally["unauthored"],
                    "touches": sum(1 for e in edges if e["edge_type"] == "touches"),
                    "note": "; ".join(notes)},
    }
    smash_lane._write_json(out / smash_lane.PROVENANCE_NAME, prov)
    return prov


def verify(shard: str | Path, *, repo: str | Path, sessions: str | Path | None = None) -> tuple[bool, str]:
    """Is the shard at ``shard`` minted from these inputs as they stand now? The PROVENANCE's digest against
    the live one — the door for inputs git never tracks (the archive, the receipts), which the tenant's
    cursor cannot see (graphyos #59). (fresh, reason)."""
    from graphy import smash as smash_lane
    shard = Path(shard).resolve()
    try:
        prov = json.loads((shard / smash_lane.PROVENANCE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HistoryError(f"{shard}: no readable {smash_lane.PROVENANCE_NAME} ({exc})") from exc
    corpus = prov.get("corpus") or {}
    if corpus.get("scheme") != SCHEME:
        raise HistoryError(f"{shard} is not a history shard (scheme {corpus.get('scheme')!r})")
    repo = Path(repo).resolve()

    def _place(rel: str, what: str) -> Path:
        """A portable path from the receipt, found again: under the repo, the shard's home, or the cwd."""
        for base in (repo, shard.parent, Path.cwd()):
            cand = (base / rel).resolve()
            if cand.exists():
                return cand
        raise HistoryError(f"{shard}: the receipt's {what} {rel!r} is not under {repo}, {shard.parent} or the cwd")
    sess_dir = Path(sessions).resolve() if sessions else None
    if sess_dir is None and corpus.get("sessions"):
        sess_dir = _place(corpus["sessions"], "sessions")
    code = [_place(c, "code shard") for c in corpus.get("code") or []]
    *_, digest = _inputs(repo, sess_dir, corpus.get("recon") or "RECON.md", code)
    if digest == corpus.get("sha256"):
        return True, f"fresh: the inputs digest {digest[:16]} is the shard's"
    return False, (f"stale: the inputs digest {digest[:16]} is not the shard's {str(corpus.get('sha256'))[:16]} — "
                   f"a commit, a session capture, a RECON section or a receipt moved; re-mint")
