"""Where the session archive lives. Explicit over ambient: GRAPHY_SESSIONS, then the project
dir Claude Code hands to hooks, then the nearest enclosing directory that already carries
`.claude/recovery`, then the current directory."""
from __future__ import annotations

import os
from pathlib import Path

_RELATIVE = Path(".claude") / "recovery" / "sessions"


def sessions_dir() -> Path:
    env = os.environ.get("GRAPHY_SESSIONS")
    if env:
        return Path(env).expanduser()
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        return Path(proj).expanduser() / _RELATIVE
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        if (base / ".claude" / "recovery").is_dir():
            return base / _RELATIVE
    return cwd / _RELATIVE
