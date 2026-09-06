"""release — the version-identity law, enforced at the seam.

A node id is a name, never a version: ``<scheme>://<node_type>/<dotted>``. That is what makes a
wormhole free (the same literal in two shards) and what makes two releases of one package spell the
same ids. The roster is the resolution: a tenant names exactly one release per scheme, its shard's
``PROVENANCE.json`` is the only place the version lives, and two releases of one scheme in a roster,
or across a bridge's declared join, are a refusal at the seam — never a guess, never a merge.
``build`` and ``check`` refuse a roster whose shards own one scheme under two releases; the bridge's
join receipt prints each side's release and refuses when they differ unless the operator says the
skew is theirs to carry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from graphy.smash import PROVENANCE_NAME

__all__ = ["ReleaseError", "Release", "release_of", "roster_releases", "collisions", "require_one_release"]

UNPINNED = "unpinned"


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    slug: str
    scheme: str
    distribution: str | None
    version: str | None

    @property
    def pin(self) -> str:
        return f"{self.distribution or self.scheme}=={self.version}" if self.version else UNPINNED


def release_of(shard_dir: str | Path) -> Release | None:
    """What the shard's own PROVENANCE says it was minted from; None when the shard carries none
    (a placed or synthetic shard — unpinned, never guessed)."""
    d = Path(shard_dir)
    p = d / PROVENANCE_NAME
    if not p.is_file():
        return None
    try:
        prov = json.loads(p.read_text(encoding="utf-8"))
        corpus = prov.get("corpus") or {}
    except (OSError, ValueError, AttributeError):
        return None
    slug = d.name[:-len("_graph")] if d.name.endswith("_graph") else d.name
    scheme = str(corpus.get("scheme") or slug)
    return Release(slug=slug, scheme=scheme, distribution=corpus.get("distribution"),
                   version=str(corpus["version"]) if corpus.get("version") else None)


def _owned_schemes(data_home: Path, slug: str) -> list[str]:
    """The schemes the tenant's scheme index says a slug owns; the slug itself when the index is silent."""
    idx = data_home / ".federation_scheme_index.json"
    try:
        rows = json.loads(idx.read_text(encoding="utf-8"))
        own = (rows.get(slug) or {}).get("own") or ()
        return [str(s) for s in own] or [slug]
    except (OSError, ValueError, AttributeError):
        return [slug]


def roster_releases(data_home: str | Path, roster: list[str]) -> dict[str, dict[str, Release]]:
    """scheme -> slug -> Release, over every shard the roster names under one data_home."""
    home = Path(data_home)
    out: dict[str, dict[str, Release]] = {}
    for slug in roster:
        rel = release_of(home / f"{slug}_graph")
        for scheme in _owned_schemes(home, slug):
            out.setdefault(scheme, {})[slug] = rel or Release(slug=slug, scheme=scheme, distribution=None, version=None)
    return out


def collisions(releases: dict[str, dict[str, Release]]) -> list[tuple[str, dict[str, str]]]:
    """Every scheme two or more shards own under different pins. An unpinned shard beside a pinned
    one is a collision too: the roster cannot say which release the literal means."""
    out = []
    for scheme, by_slug in sorted(releases.items()):
        pins = {slug: r.pin for slug, r in by_slug.items()}
        if len(set(pins.values())) > 1:
            out.append((scheme, pins))
    return out


def require_one_release(data_home: str | Path, roster: list[str]) -> dict[str, dict[str, Release]]:
    rel = roster_releases(data_home, roster)
    bad = collisions(rel)
    if bad:
        detail = "; ".join(f"{scheme}: " + ", ".join(f"{slug}_graph={pin}" for slug, pin in sorted(pins.items()))
                           for scheme, pins in bad)
        raise ReleaseError(f"two releases of one scheme in the roster — a node id is a name, the roster is "
                           f"the resolution, and it must name one release per scheme: {detail}")
    return rel
