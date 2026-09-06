#!/usr/bin/env python3
from __future__ import annotations

import math

SUPPORT_PRIOR = 5

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
