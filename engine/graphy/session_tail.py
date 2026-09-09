"""A Claude Code transcript → its semantic tail: 1:1 user/assistant exchanges, tool use
stripped, verbatim and in order. Pure: reads one file, writes nothing."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "TailError", "CHARS_PER_TOKEN", "MAX_RECENT_CONTEXT_CHARS", "NOISE_TYPES",
    "projects_root", "projects_roots", "project_slug", "extract_turns", "pair_turns",
    "semantic_sha256", "render_markdown", "bounded_tail", "render_recent_markdown",
    "render_json", "scan_stats", "assert_plausible", "render_full",
]

CHARS_PER_TOKEN = 4
MAX_RECENT_CONTEXT_CHARS = 15_000

NOISE_TYPES = frozenset({
    "attachment", "mode", "last-prompt", "ai-title", "system",
    "file-history-snapshot", "file-history-delta", "queue-operation",
    "summary", "progress", "permission-mode", "atis-latch", "bridge-session", "cost-state",
})

_COMMAND_ECHO = re.compile(
    r"<(command-name|command-message|command-args|local-command-stdout|local-command-stderr)>",
)
_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_END_MARKER = "--- END OF TAIL — the exchange above is where you left off."


class TailError(RuntimeError):
    pass


def projects_root() -> Path:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return (Path(cfg) if cfg else Path.home() / ".claude") / "projects"


def projects_roots() -> list[Path]:
    primary = projects_root()
    roots = [primary] if primary.is_dir() else []
    for cand in sorted(primary.parent.parent.glob(".claude*/projects")):
        if cand.is_dir() and cand not in roots:
            roots.append(cand)
    return roots or [primary]


def project_slug(project_dir: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(project_dir)))


def _blocks(entry: dict) -> list[dict]:
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text_of(entry: dict) -> str:
    parts = [b.get("text", "") for b in _blocks(entry) if b.get("type") == "text"]
    text = "\n".join(p for p in parts if p and p.strip())
    return _SYSTEM_REMINDER.sub("", text).strip()


def _is_real_user(entry: dict, text: str) -> bool:
    if entry.get("toolUseResult") is not None:
        return False
    if any(b.get("type") == "tool_result" for b in _blocks(entry)):
        return False
    if not text:
        return False
    return not _COMMAND_ECHO.search(text)


# The harness's own rows in a Codex rollout: the AGENTS.md injection and the environment block arrive as
# `role: user` and are never the person (graphyos #67).
_CODEX_HARNESS_USER = ("# AGENTS.md instructions", "<environment_context>", "<user_instructions>")

HARNESSES = ("claude", "codex", "generic")


def harness_of(entry: dict) -> str | None:
    """Which harness wrote this row, from its shape alone — never from a name in the payload. Claude
    Code: `type: user|assistant` with `message`; Codex: `type: response_item|session_meta|…` with `payload`;
    a role/content jsonl (Cursor's transcript_path, as documented outside Cursor): `role` at the top. None
    for a row no harness shape claims."""
    t = entry.get("type")
    if "payload" in entry and isinstance(entry.get("payload"), dict) and isinstance(t, str):
        return "codex"
    if t in ("user", "assistant") or "message" in entry or t in NOISE_TYPES or t == "queue-operation":
        return "claude"
    if entry.get("role") in ("user", "assistant") and "content" in entry:
        return "generic"
    return None


def _codex_text(payload: dict) -> str:
    parts = [b.get("text", "") for b in payload.get("content") or []
             if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text")]
    return "\n".join(x for x in parts if x and x.strip()).strip()


def turn_of(entry: dict) -> tuple[str, str, bool] | None:
    """(role, text, real) for a row that is a turn in any harness's shape; None for noise. `real` is
    whether the row is a person's prompt or the model's prose — a tool result, a harness injection or an
    empty body is typed but not real, which is what `assert_plausible` counts."""
    h = harness_of(entry)
    if h == "claude":
        etype = entry.get("type")
        if etype in NOISE_TYPES or entry.get("isMeta") or entry.get("isSidechain"):
            return None
        text = _text_of(entry)
        if etype == "user":
            return "user", text, _is_real_user(entry, text)
        if etype == "assistant":
            return "assistant", text, bool(text)
        return None
    if h == "codex":
        p = entry["payload"]
        if entry.get("type") != "response_item" or p.get("type") != "message":
            return None
        role = p.get("role")
        text = _SYSTEM_REMINDER.sub("", _codex_text(p)).strip()
        if role == "user":
            return "user", text, bool(text) and not text.startswith(_CODEX_HARNESS_USER)
        if role == "assistant":
            return "assistant", text, bool(text)
        return None                                   # developer rows are the harness, never the person
    if h == "generic":
        blocks = _blocks({"message": {"content": entry.get("content")}})
        if any(b.get("type") in ("tool_result", "tool_use") for b in blocks):
            return entry["role"], "", False
        text = _SYSTEM_REMINDER.sub("", "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")).strip()
        return entry["role"], text, bool(text) and not _COMMAND_ECHO.search(text)
    return None


def extract_turns(transcript: Path) -> tuple[list[dict], int]:
    try:
        raw = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        raise TailError(f"cannot read {transcript}: {err}") from err

    lines = [s for s in (ln.strip() for ln in raw.splitlines()) if s]
    turns: list[dict] = []
    undecodable = 0
    queued: list[str] = []
    for idx, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            if idx < len(lines) - 1:
                undecodable += 1
            continue
        if not isinstance(entry, dict):
            undecodable += 1
            continue
        etype = entry.get("type")
        if etype == "queue-operation":
            op = entry.get("operation")
            qtext = _SYSTEM_REMINDER.sub("", str(entry.get("content") or "")).strip()
            if op == "enqueue":
                if qtext and not qtext.startswith("/") and not _COMMAND_ECHO.search(qtext):
                    turns.append({"role": "user", "text": qtext})
                    queued.append(qtext)
            elif op == "remove" and qtext in queued:
                queued.remove(qtext)
            continue
        turn = turn_of(entry)
        if turn is None or not turn[2]:
            continue
        role, text, _real = turn
        if role == "user":
            if text in queued:
                queued.remove(text)
            else:
                turns.append({"role": "user", "text": text})
        else:
            turns.append({"role": "assistant", "text": text})
    return turns, undecodable


def pair_turns(turns: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for t in turns:
        if merged and merged[-1]["role"] == t["role"]:
            merged[-1]["text"] += "\n\n" + t["text"]
        else:
            merged.append(dict(t))
    exchanges: list[dict] = []
    pending: str | None = None
    for t in merged:
        if t["role"] == "user":
            if pending is not None:
                exchanges.append({"user": pending, "assistant": ""})
            pending = t["text"]
        else:
            exchanges.append({"user": pending or "", "assistant": t["text"]})
            pending = None
    if pending is not None:
        exchanges.append({"user": pending, "assistant": ""})
    for i, ex in enumerate(exchanges, 1):
        ex["n"] = i
    return exchanges


def semantic_sha256(exchanges: list[dict]) -> str:
    payload = json.dumps(exchanges, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _budget(exchanges: list[dict], budget_chars: int) -> list[dict]:
    kept: list[dict] = []
    total = 0
    for ex in reversed(exchanges):
        size = len(ex["user"]) + len(ex["assistant"]) + 80
        if total + size > budget_chars and kept:
            break
        kept.insert(0, ex)
        total += size
    return kept


def render_markdown(exchanges: list[dict], meta: dict) -> str:
    warn = ""
    if meta.get("undecodable"):
        warn += (f"\n⚠ {meta['undecodable']} transcript line(s) did not decode — the tail may be "
                 f"missing turns. Treat gaps as real and re-derive from git and the board.\n")
    if meta.get("resolved_by") == "disk-fallback":
        warn += ("\n⚠ RESOLVED BY DISK FALLBACK: the most recent transcript in this project other than "
                 "the current session. Almost certainly yours after a cold start, but VERIFY the "
                 "first exchange below is where you actually left off before continuing it.\n")
    scope = "FULL SESSION" if meta.get("full_session") else "TAIL"
    out = [
        f"# CONVERSATION {scope} — {len(exchanges)} exchanges, verbatim and in order",
        "",
        f"source: {meta.get('transcript')}",
        f"session: {meta.get('session_id') or '(unknown)'}",
        f"exchanges {meta.get('first_n')}–{meta.get('last_n')} of {meta.get('total')}"
        f" · ~{meta.get('tokens', 0):,} tokens",
        f"semantic_sha256: {meta.get('semantic_sha256') or '(not calculated)'}",
        f"captured_at: {meta.get('captured_at') or '(unknown)'}",
        f"resolved_by: {meta.get('resolved_by') or '(unknown)'}",
        warn,
        ("This is the COMPLETE RAW semantic record, not a summary." if meta.get("full_session")
         else "This is the NEWEST bounded edge of the raw record, not a summary."),
        "Read it as the conversation you were just having, and continue from its end.",
        "",
    ]
    for ex in exchanges:
        out += [f"--- [{ex['n']}] USER", "", ex["user"] or "(none)", ""]
        out += [f"--- [{ex['n']}] ASSISTANT", "", ex["assistant"] or "(none)", ""]
    out += [_END_MARKER, ""]
    return "\n".join(out)


def bounded_tail(rendered: str, limit: int) -> str:
    if limit < 512:
        raise TailError("recent-context budget must be at least 512 characters")
    if limit > MAX_RECENT_CONTEXT_CHARS:
        raise TailError(f"recent-context budget {limit} exceeds the {MAX_RECENT_CONTEXT_CHARS}-character "
                        "injection ceiling; the full record stays on disk")
    if len(rendered) <= limit:
        return rendered
    marker = (f"# RECENT CONVERSATION CONTEXT — newest {limit:,} characters maximum\n\n"
              "[... older semantic session content omitted; read the full on-disk reseed ...]\n\n")
    if len(marker) >= limit:
        raise TailError("recent-context marker exhausted the injection budget")
    return marker + rendered[-(limit - len(marker)):]


def render_recent_markdown(exchanges: list[dict], meta: dict,
                           limit: int = MAX_RECENT_CONTEXT_CHARS) -> str:
    return bounded_tail(render_markdown(exchanges, meta), limit)


def render_json(exchanges: list[dict], meta: dict) -> str:
    return json.dumps({"meta": meta, "exchanges": exchanges}, indent=2, ensure_ascii=False, default=str)


def scan_stats(transcript: Path) -> dict:
    try:
        raw = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return {"unreadable": str(err), "lines": 0, "decodable": 0, "undecodable": 0,
                "user_typed": 0, "assistant_typed": 0, "real_user": 0, "real_assistant": 0}
    lines = [s for s in (ln.strip() for ln in raw.splitlines()) if s]
    st = {"unreadable": "", "lines": len(lines), "decodable": 0, "undecodable": 0,
          "user_typed": 0, "assistant_typed": 0, "real_user": 0, "real_assistant": 0}
    for idx, line in enumerate(lines):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            if idx < len(lines) - 1:
                st["undecodable"] += 1
            continue
        if not isinstance(e, dict):
            st["undecodable"] += 1
            continue
        st["decodable"] += 1
        turn = turn_of(e)
        if turn is None:
            continue
        role, _text, real = turn
        st[f"{role}_typed"] += 1
        if real:
            st[f"real_{role}"] += 1
    return st


def assert_plausible(exchanges: list[dict], transcript: Path, min_exchanges: int) -> None:
    if len(exchanges) >= min_exchanges:
        return
    s = scan_stats(transcript)
    typed = s["user_typed"] + s["assistant_typed"]
    real = s["real_user"] + s["real_assistant"]
    if s["unreadable"]:
        cause = f"the transcript could not be read ({s['unreadable']}) — an I/O fault, not an empty session."
    elif s["undecodable"] >= max(3, s["lines"] // 20):
        cause = (f"{s['undecodable']} of {s['lines']} lines did not decode as JSON — the transcript "
                 f"format may have MOVED and session_tail's parser needs updating.")
    elif s["real_assistant"] >= min_exchanges and s["real_user"] == 0:
        cause = (f"{s['real_assistant']} assistant entries carry real prose but ZERO standalone user "
                 f"prompts — an autonomous, wake-driven shape, not an empty session.")
    elif typed >= 2 * min_exchanges and real < min_exchanges:
        cause = (f"the file holds {s['user_typed']} user / {s['assistant_typed']} assistant entries but "
                 f"only {s['real_user']}/{s['real_assistant']} carried real prose — a tool-only session, "
                 f"OR the transcript format MOVED and the discriminator over-filtered. Inspect the "
                 f"transcript before assuming either.")
    else:
        cause = (f"the transcript is essentially empty ({s['decodable']} decodable entries, "
                 f"{s['user_typed']} user / {s['assistant_typed']} assistant) — a fresh or barely-used "
                 f"session with nothing to re-seed. This is NOT a schema problem.")
    raise TailError(f"extracted only {len(exchanges)} exchange(s) from {transcript} (minimum "
                    f"{min_exchanges}). {cause} Refusing to inject a hollow tail.")


def render_full(transcript: Path, *, session_id: str, resolved_by: str,
                min_exchanges: int = 1) -> tuple[str, dict]:
    turns, undecodable = extract_turns(transcript)
    exchanges = pair_turns(turns)
    assert_plausible(exchanges, transcript, min_exchanges=min_exchanges)
    meta = {
        "transcript": str(transcript),
        "session_id": session_id,
        "resolved_by": resolved_by,
        "total": len(exchanges),
        "first_n": exchanges[0]["n"],
        "last_n": exchanges[-1]["n"],
        "tokens": sum(len(ex["user"]) + len(ex["assistant"]) for ex in exchanges) // CHARS_PER_TOKEN,
        "undecodable": undecodable,
        "full_session": True,
        "semantic_sha256": semantic_sha256(exchanges),
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return render_markdown(exchanges, meta), meta
