"""timeline — two words as bloodhound co-occurrence, the fan-out walked into the story (graphyos #60).

`graphy history <A> --with <B> --tenant … --tenant-id …`: bloodhound names the sessions where the two
terms sit within one window (the archive on disk, rg-fast); the compiled store's history shard
(graphyos #59) walks each `history://session/<id>` to the commits it authored, each commit to the RECON
section it recorded and the issue it named, each issue to the receipt pinned to it, and each receipt
to the numbers that moved against the receipt before it. Printed oldest first. No model decides an
edge and none writes the story: every line is a node's attrs. The walk is a query over the store —
never a shard opened, never a file parsed past the archive bloodhound already reads.

`graphy history --symbol <id>` (graphyos #64): the same story from the other end — the exchanges that
mention the symbol (the history shard's `mentions` edges, the wormhole on the code's own names), their
sessions in time order, each session's commits; no archive is read at all. Either way a session's block
names the symbols its exchanges discussed, from the store.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from graphy.adapters.history import read_sessions, _iso
from graphy.federated_store import WITH, AGAINST, BOTH
from graphy.lightning import bloodhound

__all__ = ["TimelineError", "Session", "Timeline", "hunt", "hunt_symbol", "story", "render", "timeline", "timeline_symbol"]

HISTORY_OWNER = "history"
_SESSION_ID = re.compile(r"^history://session/(.+)$")
_KEEP = ("floor.seconds", "floor.passed", "wheel.wheel_bytes", "gate.seconds", "floor.rss_kb")


class TimelineError(RuntimeError):
    pass


@dataclass
class Session:
    id: str
    file: str
    captured_at: str
    exchanges: tuple[int, int] | None
    snippet: str
    commits: list[dict] = field(default_factory=list)
    symbols: list[tuple[str, int]] = field(default_factory=list)   # (code node id, mentions) the session's exchanges bound


@dataclass
class Timeline:
    a: str
    b: str | None
    window: int
    corpus: Path | None
    searched: int
    hit_files: int                             # session files bloodhound hit, before the shard is asked
    sessions: list[Session]
    unmatched: list[str]                       # session files bloodhound hit that the shard does not carry
    seconds: float = 0.0
    symbol: str | None = None                  # the --symbol mode: `a` is the node id, no archive was read
    exchanges: int = 0                         # the --symbol mode: how many exchanges mention it

    def counts(self) -> dict:
        commits = [c for s in self.sessions for c in s.commits]
        return {"sessions": len(self.sessions), "commits": len(commits),
                "sections": len({sec["id"] for c in commits for sec in c["sections"]}),
                "issues": len({i["id"] for c in commits for i in c["issues"]}),
                "receipts": len({r["id"] for c in commits for i in c["issues"] for r in i["receipts"]})}


def hunt(a: str, b: str | None, corpus: Path, window: int = 10) -> tuple[list[tuple[str, tuple | None, str, float]], int]:
    """The captured sessions where `a` (and `b`, within ±window tokens) occur: (file name, the hottest
    cluster's exchanges, its snippet, its density), and how many files were searched. The files are the
    ones the producer mints — the archive's top level, each with a session header — so a hit is always a
    session the shard can carry; the trail is bloodhound's own, imported."""
    if not corpus.is_dir():
        raise TimelineError(f"no sessions archive at {corpus} — nothing was searched, and that is not a miss")
    files = [corpus / s["file"] for s in read_sessions(corpus)]
    rx_a, rx_b = bloodhound._matcher(a), (bloodhound._matcher(b) if b else None)
    hits = []
    for p in files:
        t = bloodhound.trail_file(p, rx_a, window, rx_b)
        if not t:
            continue
        clusters = [c for c in t.clusters if c.both] if rx_b else list(t.clusters)
        if not clusters:
            continue
        best = max(clusters, key=lambda c: (c.density, c.hits))
        text = p.read_text(encoding="utf-8", errors="ignore")
        snippet = re.sub(r"\s+", " ", text[best.start_char:best.end_char]).strip()[:160]
        hits.append((p.name, best.exchanges, snippet, best.density))
    return hits, len(files)


def hunt_symbol(store, symbol: str) -> tuple[list[tuple[str, tuple | None, str, float]], int]:
    """The captured sessions whose exchanges mention `symbol` — from the store, no archive read: the
    `mentions` edges against the node, each exchange's session through its record, one hit per session
    (its file name, the span of exchange numbers, the mentions as the snippet, their count as the
    density), and how many exchanges name it. A symbol nothing mentions is an empty list, not a miss."""
    per_session: dict[str, list[tuple[int, str]]] = {}
    exchanges = 0
    for nb in store.neighbours(symbol):
        if nb.relation != "mentions" or nb.direction not in (AGAINST, BOTH):
            continue
        ex = store.record(nb.node) or {}
        sid = ex.get("session")
        if not sid:
            continue
        exchanges += 1
        per_session.setdefault(sid, []).append((int(ex.get("n") or 0), ex.get("speaker") or ""))
    hits = []
    for sid, rows in per_session.items():
        sess = store.record(sid) or {}
        rows.sort()
        snippet = f"{len(rows)} exchange(s) name it — ex " + ", ".join(f"{n} {r}" for n, r in rows[:6]) \
            + (f", … {len(rows) - 6} more" if len(rows) > 6 else "")
        hits.append((sess.get("file") or sid, (rows[0][0], rows[-1][0]), snippet, float(len(rows))))
    hits.sort()
    return hits, exchanges


def _discussed(store, sid: str) -> list[tuple[str, int]]:
    """The code nodes a session's exchanges mention, most mentioned first: contains → mentions, summed."""
    counts: dict[str, int] = {}
    for nb in store.neighbours(sid):
        if nb.relation != "contains" or nb.direction not in (WITH, BOTH):
            continue
        for m in store.neighbours(nb.node):
            if m.relation == "mentions" and m.direction in (WITH, BOTH):
                counts[m.node] = counts.get(m.node, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _sessions_by_file(store) -> dict[str, str]:
    """A session file name → the session node: the node's own `file`, or the session id's first eight
    characters the archive stamps on every capture of it (a session captured twice is one node)."""
    out = {}
    for nid, cols in store.owned(HISTORY_OWNER):
        if cols and cols.get("node_type") == "session":
            if cols.get("file"):
                out[cols["file"]] = nid
            m = _SESSION_ID.match(nid)
            if m:
                out[f"__{m.group(1)[:8]}"] = nid
    return out


def _session_for(by_file: dict[str, str], fname: str) -> str | None:
    if fname in by_file:
        return by_file[fname]
    stem = fname[:-3] if fname.endswith(".md") else fname
    tail = stem.rsplit("__", 1)[-1] if "__" in stem else ""
    return by_file.get(f"__{tail}") if tail else None


def _moved(numbers: dict, before: dict | None) -> list[tuple[str, object, object]]:
    """The receipt's numbers against the receipt before it: the kept keys first, then the largest
    relative moves — at most four, never a number that did not move."""
    if not before:
        return []
    rows = []
    for k, v in numbers.items():
        if k not in before or before[k] == v or k.endswith(".rc") or "rss" in k and k not in _KEEP:
            continue
        old = before[k]
        rel = abs((v - old) / old) if old else 1.0
        rows.append((0 if k in _KEEP else 1, -rel, k, old, v))
    rows.sort()
    return [(k, old, v) for _, _, k, old, v in rows[:4]]


def story(store, hits: list[tuple[str, tuple | None, str, float]]) -> tuple[list[Session], list[str]]:
    """The fan-out per hit session, from the store: commits (authored), each one's sections (records),
    issues (names) and the receipts pinned to those issues, with the numbers that moved. A session
    captured twice is two files and one node: the hottest capture speaks for it. A store with no history
    shard refuses by name — the door has nothing to walk."""
    by_file = _sessions_by_file(store)
    if not by_file:
        if any(True for _ in store.owned(HISTORY_OWNER)):
            raise TimelineError("the history shard carries no session — the archive at .claude/recovery/sessions is empty "
                                "or its files lack the capture header (`session:` · `captured_at:`); `graphy shell install` "
                                "bolts on the hooks that fill it, and `graphy eat .` re-mints the shard over what they captured")
        raise TimelineError("this store carries no history shard — `graphy eat .` mints it beside the code when the repo "
                            "is a git checkout (by hand: `graphy history --repo <abs> --out <data_home>/history_graph "
                            "--sessions <archive> --code <code shard>…`, then `graphy build`)")
    receipts_by_time: list[tuple[str, str, dict]] = []
    for nid, cols in store.owned(HISTORY_OWNER):
        if cols and cols.get("node_type") == "receipt":
            rec = store.record(nid) or {}
            if rec.get("measured_at"):                 # an undated receipt is nobody's "before"
                receipts_by_time.append((rec["measured_at"], nid, rec))
    receipts_by_time.sort()
    previous = {nid: ((receipts_by_time[i - 1][2].get("numbers") or {}) if i else None)
                for i, (_, nid, _) in enumerate(receipts_by_time)}
    best_by_sid: dict[str, tuple] = {}
    unmatched: list[str] = []
    for hit in hits:
        sid = _session_for(by_file, hit[0])
        if sid is None:
            unmatched.append(hit[0])
        elif sid not in best_by_sid or hit[3] > best_by_sid[sid][3]:
            best_by_sid[sid] = hit
    sessions: list[Session] = []
    for sid, (fname, exchanges, snippet, _density) in best_by_sid.items():
        rec = store.record(sid) or {}
        s = Session(id=sid, file=fname, captured_at=rec.get("captured_at") or "", exchanges=exchanges, snippet=snippet)
        for nb in store.neighbours(sid):
            if nb.relation != "authored" or nb.direction not in (WITH, BOTH):
                continue
            c = store.record(nb.node) or {}
            entry = {"id": nb.node, "sha": c.get("name") or nb.node.rsplit("/", 1)[-1][:7], "authored": c.get("authored") or "",
                     "subject": c.get("subject") or "", "sections": [], "issues": []}
            for cn in store.neighbours(nb.node):
                if cn.direction not in (WITH, BOTH):
                    continue
                if cn.relation == "records":
                    sec = store.record(cn.node) or {}
                    entry["sections"].append({"id": cn.node, "number": sec.get("number"), "title": sec.get("title") or ""})
                elif cn.relation == "names":
                    iss = store.record(cn.node) or {}
                    issue = {"id": cn.node, "number": iss.get("number"), "title": iss.get("title") or "", "receipts": []}
                    for rn in store.neighbours(cn.node):
                        if rn.relation == "pins" and rn.direction in (AGAINST, BOTH):
                            r = store.record(rn.node) or {}
                            issue["receipts"].append({"id": rn.node, "name": r.get("name") or rn.node.rsplit("/", 1)[-1],
                                                      "moved": _moved(r.get("numbers") or {}, previous.get(rn.node))})
                    entry["issues"].append(issue)
            entry["sections"].sort(key=lambda x: x["number"] or 0)
            entry["issues"].sort(key=lambda x: x["number"] or 0)
            s.commits.append(entry)
        s.commits.sort(key=lambda c: _iso(c["authored"]) if c["authored"] else datetime.min.replace(tzinfo=timezone.utc))
        s.symbols = _discussed(store, sid)
        sessions.append(s)
    sessions.sort(key=lambda s: s.captured_at)
    return sessions, unmatched


def _fmt_num(v) -> str:
    return f"{v:,}" if isinstance(v, int) else str(v)


def _tail(nid: str) -> str:
    return nid.split("/", 3)[-1] if "://" in nid else nid


def render(t: Timeline, limit: int = 8) -> str:
    if t.symbol:
        lines = [f"# TIMELINE — `{t.symbol}`  ·  {t.exchanges} exchange(s) mention it in {t.hit_files} session file(s), "
                 f"{len(t.sessions)} session(s) in the shard  ·  from the store, no archive read  ·  oldest first"]
    else:
        label = f"`{t.a}`" + (f" × `{t.b}`" if t.b else "")
        lines = [f"# TIMELINE — {label}  ·  window ±{t.window} tokens  ·  {t.searched} session file(s) searched, "
                 f"{t.hit_files} hold {'both' if t.b else 'it'}, {len(t.sessions)} session(s) in the shard  ·  oldest first"]
    for s in t.sessions:
        when = s.captured_at[:16].replace("+00:00", "")
        ex = f"ex {s.exchanges[0]}" + (f"-{s.exchanges[1]}" if s.exchanges[1] != s.exchanges[0] else "") if s.exchanges else ""
        quote = s.snippet if t.symbol else f"\"…{s.snippet}…\""
        lines.append(f"{when}  session {s.id.rsplit('/', 1)[-1][:8]}  {ex:<8} {quote}")
        if s.symbols:
            shown = " · ".join(f"{_tail(n)} ×{c}" if c > 1 else _tail(n) for n, c in s.symbols[:limit])
            more = f" (+{len(s.symbols) - limit} more)" if len(s.symbols) > limit else ""
            lines.append(f"    discussed: {shown}{more}")
        for i, c in enumerate(s.commits):
            last = i == len(s.commits) - 1
            tee, bar = ("└─", "  ") if last else ("├─", "│ ")
            tags = [f"RECON §{sec['number']}" for sec in c["sections"]] + [f"graphyos #{iss['number']}" for iss in c["issues"]]
            lines.append(f"    {tee} {c['sha']}  {c['subject'][:96]}" + (f"   {' · '.join(tags)}" if tags else ""))
            for iss in c["issues"]:
                for r in iss["receipts"]:
                    moved = " · ".join(f"{k} {_fmt_num(o)} → {_fmt_num(v)}" for k, o, v in r["moved"])
                    lines.append(f"    {bar}      {r['name']}: {moved or 'no number moved against the receipt before it'}")
        if not s.commits:
            lines.append("    └─ (no commit in this session's window)")
    if t.unmatched:
        lines.append(f"  not in the shard: {', '.join(t.unmatched)} — captured after the shard was minted"
                     + (", so their exchanges cannot answer" if t.symbol else "") + "; re-mint it "
                     f"(`graphy history --out <shard> --repo <repo> --verify` names the drift)")
    c = t.counts()
    lines.append(f"TIMELINE: {c['sessions']} session(s) · {c['commits']} commit(s) · {c['sections']} section(s) · "
                 f"{c['issues']} issue(s) · {c['receipts']} receipt(s) · {t.seconds:.2f} s")
    return "\n".join(lines)


def timeline(store, a: str, b: str | None, corpus: Path, window: int = 10) -> Timeline:
    t0 = time.perf_counter()
    hits, searched = hunt(a, b, corpus, window)
    sessions, unmatched = story(store, hits)
    return Timeline(a=a, b=b, window=window, corpus=corpus, searched=searched, hit_files=len(hits), sessions=sessions,
                    unmatched=unmatched, seconds=round(time.perf_counter() - t0, 3))


def timeline_symbol(store, symbol: str, corpus: Path | None = None) -> Timeline:
    """The --symbol mode: `symbol` is an exact node id or a dotted tail the doors resolve (two matches
    refuse); the hits come from the store's `mentions` edges, the story is the same walk. With `corpus`,
    the archive's captured sessions the shard does not carry are named — captured after the mint, so
    their exchanges cannot answer — never searched."""
    from graphy.doors import DoorError, resolve
    t0 = time.perf_counter()
    try:
        nid = resolve(store, symbol)
    except DoorError as exc:
        raise TimelineError(str(exc)) from exc
    hits, exchanges = hunt_symbol(store, nid)
    sessions, unmatched = story(store, hits)
    searched = 0
    if corpus is not None:
        if not corpus.is_dir():
            raise TimelineError(f"no sessions archive at {corpus} — nothing was compared, and that is not a miss")
        by_file = _sessions_by_file(store)
        files = [s["file"] for s in read_sessions(corpus)]
        searched = len(files)
        unmatched = sorted(set(unmatched) | {f for f in files if _session_for(by_file, f) is None})
    return Timeline(a=nid, b=None, window=0, corpus=corpus, searched=searched, hit_files=len(hits), sessions=sessions,
                    unmatched=unmatched, seconds=round(time.perf_counter() - t0, 3), symbol=nid, exchanges=exchanges)
