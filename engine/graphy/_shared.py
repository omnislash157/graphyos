#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import math
from pathlib import Path

SUPPORT_PRIOR = 5


def source_sha(file: str) -> str | None:
    """A module's own bytes as sha16, taken when the module is imported — the code this process runs,
    never what the disk holds later (graphyos #111). None when the source is unreadable (a zipimport)."""
    try:
        return hashlib.sha256(Path(file).read_bytes()).hexdigest()[:16]
    except OSError:
        return None


SOURCE_SHA = source_sha(__file__)   # the door rules this process runs (graphyos #111)

DEFAULT_EXCLUDE = ("tests/", "test/", "docs_src/", "docs/", "scripts/", "examples/")


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
