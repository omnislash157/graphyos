"""The continuity hooks. `capture` turns the session Claude Code is ending or compacting
into its semantic tail on disk and archives it; `inject` hands the newest tail back as
context when a session starts. Fail-open: a hook that cannot help never wedges the session."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from graphy import session_tail as st

TAIL_NAME = "reseed_tail.md"
ARCHIVE_SUBDIR = "sessions"
DIAG_NAME = "reseed_diag.log"
DEFAULT_INLINE_CHARS = 8_000
DISK_FALLBACK_WINDOW_SECONDS = 24 * 3600
MIN_TRANSCRIPT_BYTES = 2_000
_HEADER_RE = re.compile(r"^(session|captured_at|semantic_sha256|resolved_by):\s*(.+?)\s*$", re.MULTILINE)
_USER_TURN_RE = re.compile(r"^--- \[\d+\] USER$", re.MULTILINE)


def recovery_dir(project_dir: Path) -> Path:
    return Path(project_dir) / ".claude" / "recovery"


def _read_hook_stdin() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise st.TailError(f"hook stdin was not JSON: {exc}") from exc
    return value if isinstance(value, dict) else {}


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _diag(recovery: Path, line: str) -> None:
    try:
        recovery.mkdir(parents=True, exist_ok=True)
        with (recovery / DIAG_NAME).open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {line}\n")
    except OSError:
        pass


def _assert_exact_session(transcript: Path, session_id: str) -> None:
    observed: set[str] = set()
    try:
        with transcript.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    cand = row.get("sessionId") or row.get("session_id")
                    if isinstance(cand, str) and cand:
                        observed.add(cand)
    except OSError as exc:
        raise st.TailError(f"cannot read transcript identity: {exc}") from exc
    if observed and observed != {session_id}:
        raise st.TailError(f"transcript session mismatch: hook={session_id} rows={sorted(observed)}")


def _header(text: str) -> dict:
    return {m.group(1): m.group(2) for m in _HEADER_RE.finditer(text[:2000])}


def _exchange_count(rendered: str) -> int:
    return len(_USER_TURN_RE.findall(rendered))


def _newest_archive_sha(archive: Path) -> str | None:
    files = sorted(archive.glob("[0-9]*__*.md"))
    if not files:
        return None
    try:
        return _header(files[-1].read_text(encoding="utf-8", errors="replace")).get("semantic_sha256")
    except OSError:
        return None


def _archive(archive: Path, rendered: str, meta: dict) -> Path | None:
    if _newest_archive_sha(archive) == meta["semantic_sha256"]:
        return None
    archive.mkdir(parents=True, exist_ok=True)
    seqs = [int(p.name.split("__", 1)[0]) for p in archive.glob("[0-9]*__*.md")
            if p.name.split("__", 1)[0].isdigit()]
    seq = (max(seqs) if seqs else 0) + 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = re.sub(r"[^A-Za-z0-9_-]", "", str(meta.get("session_id") or "unknown"))[:8] or "unknown"
    target = archive / f"{seq:05d}__{stamp}__{short}.md"
    _atomic_write(target, rendered)
    return target


def do_capture(payload: dict, recovery: Path) -> dict:
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        raise st.TailError("hook payload has no session_id")
    raw = payload.get("transcript_path")
    if not isinstance(raw, str) or not raw:
        raise st.TailError("hook payload has no transcript_path")
    transcript = Path(raw).expanduser().resolve()
    if not transcript.is_file():
        raise st.TailError(f"transcript does not exist: {transcript}")
    _assert_exact_session(transcript, session_id)
    event = str(payload.get("hook_event_name") or "hook")
    why = str(payload.get("trigger") or payload.get("reason") or "")
    rendered, meta = st.render_full(transcript, session_id=session_id,
                                    resolved_by=f"{event}:{why}" if why else event)
    tail = recovery / TAIL_NAME
    _atomic_write(tail, rendered)
    archived = _archive(recovery / ARCHIVE_SUBDIR, rendered, meta)
    return {"tail": str(tail), "archived": str(archived) if archived else None,
            "exchanges": meta["total"], "semantic_sha256": meta["semantic_sha256"]}


def _disk_fallback(project_dir: Path, current_session: str, now: float | None = None) -> Path | None:
    now = time.time() if now is None else now
    slug = st.project_slug(project_dir)
    best: tuple[float, Path] | None = None
    for root in st.projects_roots():
        for cand in (root / slug).glob("*.jsonl"):
            if cand.stem == current_session:
                continue
            try:
                stat = cand.stat()
            except OSError:
                continue
            if stat.st_size < MIN_TRANSCRIPT_BYTES or now - stat.st_mtime > DISK_FALLBACK_WINDOW_SECONDS:
                continue
            if best is None or stat.st_mtime > best[0]:
                best = (stat.st_mtime, cand)
    return best[1] if best else None


def _age(captured_at: str | None) -> str:
    if not captured_at:
        return "unknown age"
    try:
        then = datetime.fromisoformat(captured_at)
    except ValueError:
        return "unknown age"
    secs = max(0, int((datetime.now(timezone.utc) - then).total_seconds()))
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} h ago"
    return f"{secs // 86400} d ago"


def do_inject(payload: dict, recovery: Path, project_dir: Path,
              inline_chars: int = DEFAULT_INLINE_CHARS) -> str:
    source = str(payload.get("source") or "startup")
    session_id = str(payload.get("session_id") or "")
    tail = recovery / TAIL_NAME
    rendered: str | None = None
    if tail.is_file():
        rendered = tail.read_text(encoding="utf-8", errors="replace")
    else:
        fallback = _disk_fallback(project_dir, session_id)
        if fallback is not None:
            try:
                rendered, _meta = st.render_full(fallback, session_id=fallback.stem,
                                                 resolved_by="disk-fallback")
                _atomic_write(tail, rendered)
            except st.TailError as exc:
                _diag(recovery, f"inject source={source} disk-fallback refused: {exc}")
                rendered = None

    out = [f"# SESSION RE-SEED ({source})", ""]
    if rendered is None:
        _diag(recovery, f"inject EMPTY source={source} session={session_id or '?'}: no tail and no recent transcript")
        out += [
            "## ⚠ CONVERSATION TAIL UNAVAILABLE — DO NOT ASSUME CONTINUITY",
            "",
            "No captured tail exists and no recent transcript was found for this project, so",
            "NOTHING of the prior conversation is in this context. Treat your memory of it as absent.",
            "",
            "Recover by hand if it exists (newest first):",
            "```",
            "ls -t ~/.claude*/projects/*/*.jsonl | head -5",
            "python3 -m graphy.reseed render --transcript <the-one-you-want>",
            "```",
            "Then re-orient mechanically: `gh issue list --repo omnislash157/graphy`, `git log --oneline -10`, `git status -s`.",
        ]
        return "\n".join(out) + "\n"

    hdr = _header(rendered)
    same = hdr.get("session") == session_id and session_id
    _diag(recovery, f"inject ok source={source} bytes={len(rendered)} exchanges={_exchange_count(rendered)} "
                    f"tail_session={hdr.get('session', '?')} resolved_by={hdr.get('resolved_by', '?')}"
                    f"{' same_session' if same else ''}")
    out += [
        "## ⚠ FIRST ACTION — read the complete conversation session",
        "",
        "```",
        f"Read  {tail}",
        "```",
        "",
        f"{len(rendered):,} bytes · captured {_age(hdr.get('captured_at'))} · "
        f"session {hdr.get('session', '?')}{' (this session, before compaction)' if same else ''} · "
        f"resolved by {hdr.get('resolved_by', '?')}",
        "",
        "That file is the COMPLETE VERBATIM 1:1 semantic record. Below is only its newest bounded",
        "edge; the earlier session is on disk and intentionally absent from injection. A truncated",
        "preview here is EXPECTED — read the file, do not continue on the preview alone.",
        "",
        "Walk the live state before trusting recalled state:",
        "  `gh issue list --repo omnislash157/graphy`   the board",
        "  `git log --oneline -10` + `git status -s`      where the tree stands",
        "",
        "## Newest bounded conversation context",
        "",
        st.bounded_tail(rendered, inline_chars),
    ]
    return "\n".join(out) + "\n"


def _project_dir(args: argparse.Namespace, payload: dict) -> Path:
    for cand in (args.project_dir, os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd")):
        if cand:
            return Path(str(cand)).expanduser().resolve()
    return Path.cwd().resolve()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="graphy.reseed", description=__doc__)
    ap.add_argument("--project-dir", default=None, help="overrides CLAUDE_PROJECT_DIR and the hook cwd")
    ap.add_argument("--recovery-dir", default=None, help="overrides <project>/.claude/recovery")
    sub = ap.add_subparsers(dest="verb", required=True)
    c = sub.add_parser("capture", help="PreCompact / SessionEnd: write the tail and archive it (stdin = hook JSON)")
    c.set_defaults(verb="capture")
    i = sub.add_parser("inject", help="SessionStart: print the newest tail as context (stdin = hook JSON)")
    i.add_argument("--inline-chars", type=int, default=DEFAULT_INLINE_CHARS)
    r = sub.add_parser("render", help="render one transcript to stdout")
    r.add_argument("--transcript", required=True)
    r.add_argument("--budget-chars", type=int, default=None, help="bounded edge instead of the full record")
    args = ap.parse_args(argv)

    if args.verb == "render":
        transcript = Path(args.transcript).expanduser().resolve()
        try:
            rendered, _meta = st.render_full(transcript, session_id=transcript.stem, resolved_by="render")
        except st.TailError as exc:
            print(f"RENDER REFUSED: {exc}", file=sys.stderr)
            return 3
        print(st.bounded_tail(rendered, args.budget_chars) if args.budget_chars else rendered, end="")
        return 0

    try:
        payload = _read_hook_stdin()
    except st.TailError as exc:
        payload = {}
        print(f"[graphy.reseed] {exc}", file=sys.stderr)
    project_dir = _project_dir(args, payload)
    recovery = Path(args.recovery_dir).expanduser().resolve() if args.recovery_dir else recovery_dir(project_dir)

    if args.verb == "capture":
        try:
            info = do_capture(payload, recovery)
        except Exception as exc:  # fail-open: a capture that cannot help never wedges the session
            _diag(recovery, f"capture FAILED: {exc}")
            print(f"[graphy.reseed] capture failed: {exc}", file=sys.stderr)
            return 0
        _diag(recovery, f"capture ok exchanges={info['exchanges']} archived={info['archived']}")
        print(f"[graphy.reseed] tail {info['exchanges']} exchange(s) -> {info['tail']}"
              + (f" · archived {info['archived']}" if info["archived"] else " · archive unchanged"))
        return 0

    try:
        sys.stdout.write(do_inject(payload, recovery, project_dir, inline_chars=args.inline_chars))
    except Exception as exc:  # fail-open
        _diag(recovery, f"inject FAILED: {exc}")
        print(f"# SESSION RE-SEED FAILED — {exc}\nRe-orient from the board and git before trusting any memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
