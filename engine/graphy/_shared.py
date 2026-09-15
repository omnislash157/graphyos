#!/usr/bin/env python3
from __future__ import annotations

import math

SUPPORT_PRIOR = 5


DEFAULT_EXCLUDE = ("tests/", "test/", "docs_src/", "docs/", "scripts/", "examples/")

GLYPHS = "│─┌┐└┘├┤┬┴┼╪▶◀▾═→←·—⚠✗…"
"""The glyphs the engine prints: the drawings' box and arrows, the doors' hops, the receipts' separators."""


# The first line of every pointer `harness` writes: the pointer is the engine's while it carries it (graphyos #143).
POINTER_MARK = "This repo's agent hub is generated."


def utf8_streams(*streams) -> list[str]:
    """Every stream that cannot encode the engine's glyphs is reconfigured to utf-8 — what
    ``PYTHONUTF8=1`` would have made it — before the first line prints, so a cp1252 console or pipe
    on Windows never crashes a door that draws (graphyos #123: `EAT OK` printed, then exit 1, on
    windows-latest and the first client's box). No streams named means stdout and stderr; every
    entry point (`cli.main`, the memory doors, the gate, the hooks) calls it first. The encoding is
    judged, never the error handler: stderr's default is ``backslashreplace``, which never crashes,
    but a stderr left cp1252 beside a utf-8 stdout puts two encodings into the one pipe the two
    streams share. The stream's handler is kept. A stream that refuses the encoding is reconfigured
    to replace what it cannot encode instead; one whose encoding carries the glyphs already (utf-8)
    is left as it is; one with no ``reconfigure`` (a capture, a wrapper) is left alone. Returns what
    changed, ``<encoding>->utf-8`` or ``<encoding>->replace`` per stream, for the tests.

    stdin is judged the same way (graphyos #136): the hook JSON, the MCP client's lines and a
    `--files-from -` list arrive as utf-8, and a cp1252 stdin read them as mojibake — the gate missed
    the walk under ``C:\\Users\\José`` and allowed the edit. It is reconfigured here, before any entry
    point's first read, which is the only moment a text stream accepts a new encoding."""
    import sys
    if not streams:
        streams = (sys.stdout, sys.stderr, sys.stdin)
    changed: list[str] = []
    for stream in streams:
        encoding = getattr(stream, "encoding", None)
        reconfigure = getattr(stream, "reconfigure", None)
        if not encoding or reconfigure is None:
            continue
        try:
            GLYPHS.encode(encoding)
            continue
        except (UnicodeEncodeError, LookupError):
            pass
        try:
            reconfigure(encoding="utf-8", errors=getattr(stream, "errors", None) or "strict")
            changed.append(f"{encoding}->utf-8")
        except Exception:
            try:
                reconfigure(errors="replace")
                changed.append(f"{encoding}->replace")
            except Exception:
                pass
    return changed


def nonneg_int(v) -> int:
    import argparse
    i = int(v)
    if i < 0:
        raise argparse.ArgumentTypeError("--support-prior must be >= 0")
    return i


def credibility(support: int, prior: int = SUPPORT_PRIOR) -> float:
    if support <= 0:
        return 0.0
    prior = max(0, prior)
    return support / (support + prior)


def salience(lift: float, support: int, recency: float, prior: int = SUPPORT_PRIOR) -> float:
    return lift * credibility(support, prior) * recency


def lift(support: int, n_a: int, n_b: int, n_commits: int) -> float:
    return (support * n_commits) / (n_a * n_b) if (n_a and n_b and n_commits) else 0.0


def resolve_excludes(user_exclude: str, use_defaults: bool = True) -> tuple[str, ...]:
    user = tuple(x.strip() for x in user_exclude.split(",") if x.strip())
    return (DEFAULT_EXCLUDE + user) if use_defaults else user


AST_STRUCT_SALIENCE = 1.0
AST_WIRE_SALIENCE = 5.0
AST_WIRE_RELATIONS = {"serves", "fetches", "fetches_static", "navigates"}


def _ast_edge_salience(relation: str) -> float:
    return AST_WIRE_SALIENCE if relation in AST_WIRE_RELATIONS else AST_STRUCT_SALIENCE


def _shim_adj_for_activate(unified_adj: dict) -> dict:
    return {k: [(n, s, w) for (n, s, w, _r) in vs] for k, vs in unified_adj.items()}


GENERATION_INFIX = ".gen-"   # <substrate>.gen-<token>: one generation of a data home (graphyos #98)
# The one spelling of generation identity: every module asks these, never the infix (review.py `generation-identity`,
# review round 4 of #98 — three predicates had disagreed, and a refresh sibling was named after a token).
GENERATION_IDENTITY = ("generation_name", "generation_of")


def generation_name(base: str, token: str) -> str:
    """The directory name of one generation of the substrate named ``base``."""
    return f"{base}{GENERATION_INFIX}{token}"


def generation_of(name: str) -> str | None:
    """The substrate a directory name is a generation of, or None: exactly ``<base>.gen-<token>`` with a token of
    ``[0-9A-Za-z-]``. A refresh sibling's dotted release (``substrate.gen-x.2.0``) is not a generation."""
    import re
    m = re.fullmatch(r"(.+?)" + re.escape(GENERATION_INFIX) + r"([0-9A-Za-z-]+)", name)
    return m.group(1) if m else None
