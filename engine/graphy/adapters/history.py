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

    history://exchange/<session id>/<n>/<speaker>   one ``--- [n] USER|ASSISTANT`` marker of the archive
                                     (reseed_graph's own ``_EX_RE``): session · n · speaker (user|assistant;
                                     ``role`` is the vocabulary's word and stays the node type) · captured_at ·
                                     the count of literals it carries — never a body (graphyos #64)
    session  -contains-> exchange
    exchange -mentions-> <code node id>   a literal the exchange carries, bound through the roster's own
                                     names — the rule ``doors.resolve`` applies to a query, minted here as
                                     an edge that says how it bound (``via`` · ``literal``), so it is never
                                     mistaken for a wormhole (a wormhole is a literal that IS a node id):
                                     ``via: dotted`` a dotted identifier that is a node's dotted name or
                                     the unique tail of one (``showcase._clone``; a bare word binds
                                     nothing, two matches bind nothing, both counted); ``via: file`` a path
                                     or file name that is a module node's own ``file`` or its unique
                                     slash-suffix (``graphy/showcase.py``, ``showcase.py``); ``via: alias``
                                     the hand weld from ``--aliases <json>`` — an exact literal on token
                                     boundaries → one node id, hand-written: a target that is not a node
                                     refuses at mint, a literal the names already bind refuses as redundant

Nothing private travels: a session node is an id, a time and a count — never a body; an exchange node
is a session, a number, a speaker and a count; the shard is a build product under the tenant's substrate.
Stdlib only; ``git`` is the one program.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from graphy.ir import Vocabulary, validate_graph

__all__ = ["HISTORY_VOCABULARY", "HistoryError", "bind", "build_ir", "code_index", "literals_of", "mint", "module_id_of",
           "read_aliases", "read_exchanges", "symbol_index", "verify"]

HISTORY_VOCABULARY = Vocabulary(
    node_types=("commit", "session", "section", "issue", "receipt", "exchange"),
    edge_types=("authored", "records", "names", "pins", "touches", "follows", "contains", "mentions"),
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
# a literal is a dotted identifier (`showcase._clone`, `graphy.cli`, `showcase.py`) or a path with a slash
# (`graphy/showcase.py`); a bare word is never a literal — `showcase` alone binds nothing
_DOTTED = re.compile(r"(?<![\w./-])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+(?![\w/])")   # a sentence's dot may follow
_PATHLIT = re.compile(r"(?<![\w./-])[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+(?![\w./-])")
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_VIA_RANK = {"dotted": 0, "file": 1, "alias": 2}


class HistoryError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise HistoryError(f"git {' '.join(a for a in args if not a.startswith(('-c', 'core.')))[:24]} failed under "
                           f"{repo}: {(proc.stderr or '').strip()[-300:]}")
    return proc.stdout


def _code_nodes(shards: list[Path]):
    for shard in shards:
        shard = Path(shard)
        try:
            nodes = json.loads((shard / "nodes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HistoryError(f"--code {shard}: no readable nodes.json ({exc})") from exc
        for rec in (nodes.values() if isinstance(nodes, dict) else nodes):
            if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                yield rec


def code_index(shards: list[Path]) -> dict[str, str]:
    """``file → module id`` from the code shards handed in: every module node's ``file`` (relative to
    the corpus's parent, the way python_ast and typescript_ast record it). Two shards naming one file
    refuse — a file is one module."""
    index: dict[str, str] = {}
    for rec in _code_nodes(shards):
        if rec.get("node_type") == "module" and isinstance(rec.get("file"), str):
            f = rec["file"].replace("\\", "/")
            if index.get(f, rec["id"]) != rec["id"]:
                raise HistoryError(f"--code shards disagree on {f!r}: {index[f]} and {rec['id']}")
            index[f] = rec["id"]
    return index


def symbol_index(shards: list[Path]) -> dict[str, set[str]]:
    """``literal → the node ids it names`` from the code shards' own names: every node's ``dotted`` and
    each of its tails with two or more segments (``graphy.showcase._clone`` · ``showcase._clone``), and
    every module's file and each of its slash-suffixes (``graphy/showcase.py`` · ``showcase.py``). A literal naming
    two nodes binds nothing — the set says so."""
    out: dict[str, set[str]] = {}
    for rec in _code_nodes(shards):
        dotted = rec.get("dotted")
        if isinstance(dotted, str) and "." in dotted:
            parts = dotted.split(".")
            for i in range(len(parts) - 1):
                out.setdefault(".".join(parts[i:]), set()).add(rec["id"])
        if rec.get("node_type") == "module" and isinstance(rec.get("file"), str):
            parts = rec["file"].replace("\\", "/").split("/")
            for i in range(len(parts)):                  # every slash-suffix, down to the file name
                out.setdefault("/".join(parts[i:]), set()).add(rec["id"])
    return out


def literals_of(text: str) -> dict[str, int]:
    """The literals a span of the archive carries, with their counts: dotted identifiers and slashed
    paths, never a bare word."""
    out: dict[str, int] = {}
    for rx in (_DOTTED, _PATHLIT):
        for m in rx.finditer(text):
            lit = m.group(0).rstrip(".-")
            if "." in lit or "/" in lit:
                out[lit] = out.get(lit, 0) + 1
    return out


def _alias_rx(lit: str) -> re.Pattern:
    """An alias is matched on token boundaries: `sugiyama` inside `graphy.sugiyama` or `sugiyama.py` is the
    name the roster already binds, never a second hit on the same characters."""
    return re.compile(r"(?<![\w./-])" + re.escape(lit) + r"(?![\w./-])")


def read_exchanges(sessions: Path, file: str, aliases: dict[str, str] | None = None) -> tuple[list[dict], str]:
    """One record per ``--- [n] USER|ASSISTANT`` marker of a captured session: n · speaker · the literals in
    its span · the alias literals the span carries on token boundaries, with their counts; and the file's
    sha256, which joins the inputs digest so an edited body is drift. The markers are reseed_graph's own
    ``_EX_RE``, imported here and not above: a `graphy.lightning` import runs its ripgrep probe, which
    speaks on stderr, and every refusal comes first (graphyos #60)."""
    from graphy.lightning.reseed_graph import _EX_RE
    raw = (sessions / file).read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    marks = [(m.start(), m.end(), int(m.group(1)), "user" if "USER" in m.group(0) else "assistant")
             for m in _EX_RE.finditer(text)]
    rxs = {lit: _alias_rx(lit) for lit in (aliases or {})}
    out = []
    for i, (start, head_end, n, speaker) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        span = text[head_end:end]
        hits = {lit: c for lit, rx in rxs.items() if (c := len(rx.findall(span)))}
        out.append({"n": n, "speaker": speaker, "literals": literals_of(span), "aliases": hits})
    return out, hashlib.sha256(raw).hexdigest()


def read_aliases(path: Path | None) -> dict[str, str]:
    """The override registry: ``{literal: node id}``, an exact literal to one node, hand-written. ``_meta``
    is the file's own note; every other key is a literal — `_clone` is exactly the kind of bare word only
    the registry can bind."""
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HistoryError(f"--aliases {path}: not a readable JSON object ({exc})") from exc
    if not isinstance(data, dict):
        raise HistoryError(f"--aliases {path}: the registry is a JSON object of literal → node id")
    out = {}
    for k, v in data.items():
        if k == "_meta":
            continue
        if not isinstance(v, str) or "://" not in v or not k.strip():
            raise HistoryError(f"--aliases {path}: {k!r} → {v!r} is not a literal → node id")
        out[k] = v
    return out


def bind(literals: dict[str, int], index: dict[str, str], symbols: dict[str, set[str]],
         aliases: dict[str, str], alias_hits: dict[str, int] | None = None) -> tuple[dict[str, dict], set[str], set[str], set[str]]:
    """Every literal of one exchange against the code: ``{node id: {via, count, literal}}`` (one edge per
    node — the literal kept is the best-bound, shortest spelling), every literal that bound, the literals
    that named two nodes (bound nothing), the literals that named none. ``alias_hits`` is the registry's
    literals the span carried, with their counts — each a weld onto its declared node."""
    bound: dict[str, dict] = {}
    matched: set[str] = set()
    ambiguous: set[str] = set()
    unbound: set[str] = set()

    def hit(nid: str, via: str, count: int, lit: str) -> None:
        matched.add(lit)
        cur = bound.get(nid)
        if cur is None:
            bound[nid] = {"via": via, "count": count, "literal": lit}
        else:
            cur["count"] += count
            if (_VIA_RANK[via], len(lit)) < (_VIA_RANK[cur["via"]], len(cur["literal"])):   # the wormhole outranks the weld
                cur["via"], cur["literal"] = via, lit

    for lit, count in literals.items():
        mid = module_id_of(lit, index) if "/" in lit else None    # a path longer than the shard's own (engine/graphy/cli.py)
        if mid:
            hit(mid, "file", count, lit)
            continue
        ids = symbols.get(lit) or set()
        if len(ids) == 1:
            hit(next(iter(ids)), "file" if "/" in lit or lit.endswith(CODE_SUFFIXES) else "dotted", count, lit)
        elif ids:
            ambiguous.add(lit)
        else:
            unbound.add(lit)
    for lit, count in (alias_hits or {}).items():
        if count and lit in aliases:
            hit(aliases[lit], "alias", count, lit)
    return bound, matched, ambiguous, unbound


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
             *, recon_file: str = "RECON.md", index: dict[str, str] | None = None,
             exchanges: dict[str, list[dict]] | None = None, symbols: dict[str, set[str]] | None = None,
             aliases: dict[str, str] | None = None) -> tuple[dict, list, dict]:
    """The records, and a tally: how many commits fell in no session's window; the exchanges and what they
    bound. ``exchanges`` is per session file (``read_exchanges``); ``symbols`` the code shards' own names
    (``symbol_index``); ``aliases`` the override registry, checked here: a target that is not a node of the
    code shards refuses, a literal the wormhole already binds refuses as redundant."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    index = index or {}
    symbols = symbols or {}
    aliases = aliases or {}
    exchanges = exchanges or {}
    tally = {"unauthored": 0, "exchanges": 0, "mentions": 0, "literals": 0, "bound": 0, "ambiguous": 0, "aliased": 0}
    code_ids = {nid for ids in symbols.values() for nid in ids} | set(index.values())
    for lit, nid in aliases.items():
        if nid not in code_ids:
            raise HistoryError(f"aliases: {lit!r} → {nid} names no node of the code shards handed in — a weld lands on a "
                               f"node or refuses")
        already, _, _, _ = bind({lit: 1}, index, symbols, {})
        if already:
            raise HistoryError(f"aliases: {lit!r} already binds {next(iter(already))} by the roster's own names — a "
                               f"redundant weld is refused, drop it from the registry")

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
    bound_by_exchange: dict[str, dict[str, dict]] = {}   # the last capture of an exchange speaks for it
    seen_literals: set[str] = set()
    bound_literals: set[str] = set()
    ambiguous_literals: set[str] = set()
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
        for ex in exchanges.get(s["file"], []):
            xid = f"{SCHEME}://exchange/{s['id']}/{ex['n']}/{ex['speaker']}"
            b, matched, ambiguous, _unbound = bind(ex["literals"], index, symbols, aliases, ex.get("aliases"))
            seen_literals |= set(ex["literals"])
            bound_literals |= matched
            ambiguous_literals |= ambiguous
            if xid not in nodes:
                node(xid, "exchange", f"{SCHEME}.exchange.{s['id'][:8]}.{ex['n']}.{ex['speaker']}", session=nid, n=ex["n"],
                     speaker=ex["speaker"], captured_at=s["captured_at"], file=s["file"], literals=len(ex["literals"]),
                     name=f"{s['id'][:8]}/{ex['n']}/{ex['speaker']}")
                edge(nid, xid, "contains")
            else:
                nodes[xid].update(captured_at=s["captured_at"], file=s["file"], literals=len(ex["literals"]))
            bound_by_exchange[xid] = b
    for xid, b in bound_by_exchange.items():
        for dst in sorted(b):
            edge(xid, dst, "mentions", via=b[dst]["via"], count=b[dst]["count"], literal=b[dst]["literal"])
            tally["mentions"] += 1
            tally["aliased"] += b[dst]["via"] == "alias"
    tally["exchanges"] = len(bound_by_exchange)
    tally["literals"] = len(seen_literals)
    tally["bound"] = len(bound_literals - set(aliases))
    tally["ambiguous"] = len(ambiguous_literals)

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


def _inputs(repo: Path, sessions: Path | None, recon: str, code: list[Path],
            aliases: Path | None = None) -> tuple[list, list, list, list, dict, dict, dict, dict, str]:
    """Everything the shard is built from, and the digest of it — the same bytes twice give the same digest,
    so `verify` can name drift in inputs git does not track (the sessions archive, the receipts, the registry)."""
    commits = read_commits(repo)
    sess = read_sessions(sessions)
    sections = read_sections(repo / recon)
    receipts = read_receipts(repo)
    index = code_index(code)
    symbols = symbol_index(code)
    alias_map = read_aliases(aliases)
    exchanges: dict[str, list[dict]] = {}
    bodies: list[str] = []
    if sessions:
        for s in sess:
            exchanges[s["file"]], sha = read_exchanges(sessions, s["file"], alias_map)
            bodies.append(f"{s['file']}#{sha}")           # the body is an input now: an edited exchange is drift
    digest = _digest([c["sha"] for c in commits] + [f"{s['id']}@{s['captured_at']}" for s in sess] + bodies
                     + [f"§{s['n']} {s['title']}" for s in sections] + [json.dumps(r, sort_keys=True) for r in receipts]
                     + [f"{k}={v}" for k, v in sorted(index.items())]
                     + sorted({nid for ids in symbols.values() for nid in ids})
                     + [f"{k}→{v}" for k, v in sorted(alias_map.items())])
    return commits, sess, sections, receipts, index, symbols, alias_map, exchanges, digest


def mint(repo: str | Path, out: str | Path, *, sessions: str | Path | None = None, recon: str = "RECON.md",
         code: list[str | Path] | None = None, aliases: str | Path | None = None, mint_command: str | None = None) -> dict:
    """Mint the shard at ``out`` (nodes.json · edges.json · PROVENANCE.json, the smash shape) and return
    the PROVENANCE. ``sessions`` absent: no session and no exchange, said in the receipt; ``code`` absent: no
    touches and no mentions, said; ``aliases`` absent: no weld, said."""
    from graphy import smash as smash_lane
    repo = Path(repo).resolve()
    if not (repo / ".git").exists():
        raise HistoryError(f"not a git repository: {repo}")
    out = Path(out).resolve()
    sess_dir = Path(sessions).resolve() if sessions else None
    shards = [Path(c).resolve() for c in (code or [])]
    alias_path = Path(aliases).resolve() if aliases else None
    commits, sess, sections, receipts, index, symbols, alias_map, exchanges, digest = _inputs(repo, sess_dir, recon, shards, alias_path)
    nodes, edges, tally = build_ir(commits, sess, sections, receipts, recon_file=recon, index=index,
                                   exchanges=exchanges, symbols=symbols, aliases=alias_map)
    out.mkdir(parents=True, exist_ok=True)
    smash_lane._write_records(out / "nodes.json", nodes)
    smash_lane._write_records(out / "edges.json", edges)
    head = smash_lane.git_head(repo)
    if mint_command is None:
        mint_command = (f"python3 -m graphy history --repo {smash_lane.portable(repo)} --out {smash_lane.portable(out)}"
                        + (f" --sessions {smash_lane.portable(sess_dir)}" if sess_dir else "")
                        + (f" --recon {recon}" if recon != "RECON.md" else "")
                        + "".join(f" --code {smash_lane.portable(c)}" for c in shards)
                        + (f" --aliases {smash_lane.portable(alias_path)}" if alias_path else ""))
    notes = []
    notes.append("a commit is authored by the session whose capture window holds its author time" if sess_dir
                 else "sessions: none given — commits · sections · issues · receipts alone")
    notes.append(f"touches: the module ids of {len(shards)} code shard(s)" if shards
                 else "touches: none — no --code shard given, so no file maps to a module id")
    if sess_dir and shards:
        notes.append(f"mentions: {tally['bound']} of {tally['literals']} literal(s) bind a node by the roster's names, "
                     f"{tally['ambiguous']} name two or more and bind nothing"
                     + (f", {len(alias_map)} alias(es) welded {tally['aliased']} edge(s)" if alias_map
                        else "; aliases: none — no --aliases registry given"))
    elif sess_dir:
        notes.append("mentions: none — no --code shard given, so no literal has a node to bind")
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
                   "recon": recon, "code": [smash_lane.portable(c) for c in shards],
                   "aliases": smash_lane.portable(alias_path) if alias_path else None},
        "counts": smash_lane._counts(nodes, edges),
        "files": {name: smash_lane._file_receipt(out / name) for name in ("nodes.json", "edges.json")},
        "history": {"commits": len(commits), "sessions": len(sess), "sections": len(sections),
                    "issues": sum(1 for n in nodes.values() if n["node_type"] == "issue"),
                    "receipts": len(receipts),
                    "authored": sum(1 for e in edges if e["edge_type"] == "authored"),
                    "unauthored": tally["unauthored"],
                    "touches": sum(1 for e in edges if e["edge_type"] == "touches"),
                    "exchanges": tally["exchanges"], "mentions": tally["mentions"], "literals": tally["literals"],
                    "bound": tally["bound"], "ambiguous": tally["ambiguous"], "aliases": len(alias_map),
                    "aliased": tally["aliased"],
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
    alias_path = _place(corpus["aliases"], "aliases registry") if corpus.get("aliases") else None
    *_, digest = _inputs(repo, sess_dir, corpus.get("recon") or "RECON.md", code, alias_path)
    if digest == corpus.get("sha256"):
        return True, f"fresh: the inputs digest {digest[:16]} is the shard's"
    return False, (f"stale: the inputs digest {digest[:16]} is not the shard's {str(corpus.get('sha256'))[:16]} — "
                   f"a commit, a session capture or body, a RECON section, a receipt, a code shard or the registry moved; re-mint")
