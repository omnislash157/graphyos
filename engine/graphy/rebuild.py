"""rebuild — the supported multi-lane rebuild, and the only public orchestration lane.

``eat`` is first-class for "one repo, one import ring" and there was nothing for "many lanes, mixed
producers" — so a tenant that mints its own shards assembled the sequence itself out of private
internals. The first client's rebuild imported ``cli._clear_substrate``, ``cartograph.repo_cursor``
and ``graphy._portable_flock``: two underscore-private, none exported, all three free to move under
them at any release. Roughly half of their 210-line script was a reimplementation of ``eat`` minus
the prune, which is also why ``eat`` kept being reached for by tenants it was never written for —
it was the only thing that looked like a rebuild, and it prunes (graphyos #70, #71).

The sequence is the same one ``eat`` runs, with the lane set opened up:

    stage (a sibling generation seeded from the served one, placed lanes whole) → smash each minted
      lane → history → init → scheme index → converge --resolve → build → land → check

The served data home is never written: the next generation is built in ``<substrate>.gen-<token>/``
and lands in one rename of the descriptor, so a door opened at any step opens the last good store,
fresh, and a rebuild that fails or is interrupted discards its stage (graphyos #98).

A house driver that runs the CLI verbs itself instead of calling ``rebuild`` gets the same two
steps as verbs — ``graphy generation stage`` and ``graphy generation land`` (graphyos #133): stage →
its own mint lanes into the stage → init · converge · build against the staged descriptor → land → check.

**A placed lane is the point.** The engine does not run a tenant's producer: `cartograph` carries no
build-lane runner and the engine never runs a shell, so a foreign emitter stays the tenant's to
invoke. It writes its shard into the substrate and declares the lane ``placed``; this lane keeps it
across the clear, indexes its schemes from its own edges, declares it to the descriptor, and walks it
like any other. What the engine owns is the orchestration around it, which is exactly the half that
was being copied.

    from graphy import rebuild
    rebuild.rebuild(
        root=repo, substrate=repo / ".graphy" / "substrate",
        descriptor=repo / ".graphy" / "tenant.json", tenant_id="core",
        lanes=[rebuild.Lane.mint("core", package="core", site_packages=sp, corpus=repo / "core"),
               rebuild.Lane.placed("pg_schema"), rebuild.Lane.placed("sql_census")],
    )
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Lane", "RebuildError", "clear_substrate", "rebuild", "repo_cursor"]

from graphy.cartograph import cursor_exclude, repo_cursor            # re-exported: a tenant needs it and it was not public
from graphy.cross_substrate import DocDeclarationError


class RebuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class Lane:
    """One lane of a tenant's roster.

    A MINTED lane names a package this engine's own producer walks. A PLACED lane is a shard the
    tenant wrote itself — the engine never invokes a foreign producer, it only refuses to destroy
    what one left and carries the lane through the rest of the sequence.
    """

    slug: str
    kind: str = "static-dep"
    producer: str | None = None          # None ⇒ placed by the tenant
    package: str | None = None
    site_packages: str | None = None
    corpus: str | None = None

    @classmethod
    def mint(cls, slug: str, *, package: str, site_packages, corpus, producer: str = "python_ast",
             kind: str = "static-dep") -> "Lane":
        return cls(slug=slug, kind=kind, producer=producer, package=package,
                   site_packages=str(site_packages), corpus=str(corpus))

    @classmethod
    def placed(cls, slug: str, *, kind: str = "static-dep") -> "Lane":
        return cls(slug=slug, kind=kind)

    @property
    def is_placed(self) -> bool:
        return self.producer is None

    @property
    def dirname(self) -> str:
        return f"{self.slug}_graph"

    def __post_init__(self) -> None:
        if not self.slug or not self.slug.strip():
            raise RebuildError("Lane.slug is required — a lane is named or it is not a lane")
        if self.is_placed:
            if self.package or self.site_packages or self.corpus:
                raise RebuildError(
                    f"lane {self.slug!r} is placed (no producer) but names a package, site-packages "
                    f"or corpus. A placed lane is a shard the tenant wrote; the engine does not mint it"
                )
        elif not (self.package and self.site_packages and self.corpus):
            raise RebuildError(
                f"lane {self.slug!r} declares producer {self.producer!r} and must name package, "
                f"site_packages and corpus — the engine refuses to guess a corpus"
            )


def clear_substrate(substrate, *, keep=()) -> list[str]:
    """Wipe the substrate's build products, keeping every shard named in ``keep``.

    The public form of what ``eat`` does between runs: each ``<slug>_graph/`` keeps exactly
    nodes.json · edges.json · PROVENANCE.json — the splice the re-mint reads — the stored walks keep
    their directory so they diff against the new generation, and everything else (the registry, the
    journal, the resolver's sidecars, the store, the parquet) is rebuilt.

    ``keep`` is what makes it safe for a placed lane: those shards are not this engine's to re-mint,
    so their whole directory is left alone rather than stripped to the three files a splice needs.
    Returns the kept directory names.
    """
    from graphy import cli as cli_lane

    sub = Path(substrate)
    kept = sorted({str(k) for k in keep})
    stash: dict[str, bytes] = {}
    holds = [sub / k for k in kept if (sub / k).is_dir()]
    # A placed lane's extra files (a sidecar, a receipt the emitter wrote) would be stripped by the
    # clear, which keeps only the three a splice reads. Hold them aside by name and put them back.
    held: list[tuple[Path, bytes]] = []
    for d in holds:
        for f in d.rglob("*"):
            if f.is_file() and f.name not in ("nodes.json", "edges.json", "PROVENANCE.json"):
                held.append((f.relative_to(sub), f.read_bytes()))
    cli_lane._clear_substrate(sub)
    for rel, blob in held:
        target = sub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    del stash
    return kept


def rebuild(*, root, substrate, descriptor, tenant_id: str, lanes, join_keys=None, journal=None,
            cursor: str | None = None, policy: str = "refuse", container: str = "all",
            history: bool = False, history_package: str | None = None, resolve: bool = True,
            check: bool = True, log=print) -> dict:
    """Run the multi-lane rebuild and return its receipt.

    Every step is a public CLI verb; this is the glue that was not public. ``eat`` is the single-ring
    special case of this sequence — one minted lane, its import ring, and the prune.

    A placed lane must already hold its shard when this is called: the tenant's producer runs first,
    because the engine never runs a shell.
    """
    from graphy import cli as cli_lane

    t0 = time.perf_counter()
    root, sub, desc = Path(root), Path(substrate), Path(descriptor)
    lanes = list(lanes)
    if not lanes:
        raise RebuildError("rebuild: no lanes declared — an empty roster builds nothing and is "
                           "never what a caller meant")
    seen = sorted({l.slug for l in lanes})
    if len(seen) != len(lanes):
        dupes = sorted({l.slug for l in lanes if [x.slug for x in lanes].count(l.slug) > 1})
        raise RebuildError(f"rebuild: lane(s) declared twice: {dupes}")
    placed = [l for l in lanes if l.is_placed]
    minted = [l for l in lanes if not l.is_placed]
    if not minted:
        raise RebuildError(
            "rebuild: every lane is placed, so there is no ring to derive the scheme index from. "
            "Declare at least one minted lane, or build the descriptor with `graphy init` and call "
            "converge · build · check yourself"
        )
    missing = [l.slug for l in placed if not (sub / l.dirname / "nodes.json").is_file()]
    if missing:
        raise RebuildError(
            f"rebuild: placed lane(s) {missing} hold no shard at {sub}. The engine never runs a "
            f"foreign producer — run it first, then declare the lane placed"
        )

    # The served data home is never touched: the next generation is staged beside it and lands in one
    # descriptor rename after build (graphyos #98). A rebuild that fails before then discards its stage.
    kept = sorted(l.dirname for l in placed)
    stage, staged, prev = cli_lane.stage_generation(sub, desc, whole=kept)
    try:
        receipt = _rebuild_stage(root=root, served=sub, sub=stage, desc=desc, staged=staged, prev=prev,
                                 tenant_id=tenant_id, lanes=lanes, placed=placed, minted=minted,
                                 join_keys=join_keys, journal=journal, cursor=cursor, policy=policy,
                                 container=container, history=history, history_package=history_package,
                                 resolve=resolve, check=check, log=log, cli_lane=cli_lane)
    except BaseException:
        if cli_lane.served_data_home(desc) != stage:  # not landed: the served generation stands untouched
            shutil.rmtree(stage, ignore_errors=True)
            staged.unlink(missing_ok=True)
        raise
    receipt["seconds"] = round(time.perf_counter() - t0, 2)
    log(f"REBUILD OK: {len(receipt['lanes'])} lane(s) — {len(minted)} minted · {len(placed)} placed"
        f"{' · history' if receipt['history'] else ''} · cursor {receipt['cursor'][:24]}… ({receipt['seconds']}s)")
    return receipt


def _rebuild_stage(*, root, served, sub, desc, staged, prev, tenant_id, lanes, placed, minted, join_keys,
                   journal, cursor, policy, container, history, history_package, resolve, check, log,
                   cli_lane) -> dict:
    if placed:
        log(f"REBUILD: {len(placed)} placed lane(s) carried into the next generation: "
            + " · ".join(sorted(l.dirname for l in placed)))

    for lane in minted:
        rc = cli_lane.main(["smash", "--package", lane.package, "--site-packages", lane.site_packages,
                            "--out", str(sub), "--corpus", lane.corpus, "--producer", lane.producer])
        if rc != 0:
            raise RebuildError(f"rebuild: smash failed for lane {lane.slug!r} (exit {rc})")

    with_history = False
    if history:
        pkg = history_package or minted[0].package
        with_history = cli_lane.eat_history(root, sub, desc.parent, pkg, log=log)

    ring = json.loads((sub / "ring.json").read_text(encoding="utf-8"))
    ring_lanes = {f"{m['slug']}_graph" for m in ring["minted"].values()}
    declared = [f"--lane={lane.dirname}:{lane.kind}" for lane in lanes]
    # A ring shard the roster did not name (a dependency of a minted lane) is still a lane: it is on
    # disk and the store would refuse an id it cannot own. Declared, never pruned — this lane does
    # not delete (graphyos #70 is the reason eat had to learn the same thing).
    for name in sorted(ring_lanes - {l.dirname for l in lanes}):
        declared.append(f"--lane={name}:static-dep")
    if with_history:
        declared.append(f"--lane={cli_lane.HISTORY_SLUG}_graph:static-dep")

    if cursor is None:
        cursor, dirty = repo_cursor(root, exclude=cursor_exclude(desc, sub, root=root, journal=journal, join_keys=join_keys))
        if cursor is None:
            raise RebuildError(
                f"rebuild: {root} is not a git checkout, so there is no cursor to pin the store to. "
                f"Pass cursor=… explicitly — a tenant without one cannot be told it is stale"
            )
        if dirty:
            log(f"REBUILD: the working tree is dirty ({dirty} file(s) past HEAD) — the cursor "
                f"carries it; `graphy check` reads STALE the moment they move")

    rc = cli_lane.main(["init", "--tenant", str(staged), "--root", str(root), "--data-home", str(sub),
                        "--join-keys", str(join_keys or sub / "registry.json"),
                        "--journal", str(journal or sub / "journal"),
                        "--cursor", cursor, "--policy", policy, *declared])
    if rc != 0:
        raise RebuildError(f"rebuild: init failed (exit {rc})")

    extra = tuple(l.slug for l in placed) + ((cli_lane.HISTORY_SLUG,) if with_history else ())
    try:
        cli_lane._scheme_index_from_ring(
            sub, f"{tenant_id} scheme index — derived from ring.json by graphy rebuild", extra=extra)
    except DocDeclarationError as exc:            # a malformed or overlapping doc declaration (graphyos #86)
        raise RebuildError(f"rebuild: {exc}") from exc

    steps = []
    if resolve:
        steps.append(["converge", "--tenant", str(staged), "--tenant-id", tenant_id, "--resolve"])
    steps.append(["build", "--tenant", str(staged), "--tenant-id", tenant_id, "--container", container])
    for step in steps:
        rc = cli_lane.main(step)
        if rc != 0:
            raise RebuildError(f"rebuild: {step[0]} failed (exit {rc})")
    try:
        cli_lane.land_generation(sub, staged, desc, prev, served, keep=[l.dirname for l in placed])
    except OSError as exc:
        raise RebuildError(f"rebuild: the next generation could not land ({type(exc).__name__}: {exc}) "
                           f"— the served store stands") from exc
    if check:
        rc = cli_lane.main(["check", "--tenant", str(desc), "--tenant-id", tenant_id])
        if rc != 0:
            raise RebuildError(f"rebuild: check failed (exit {rc}) — the next generation landed at {sub}")

    receipt = {
        "tenant_id": tenant_id,
        "descriptor": str(desc),
        "substrate": str(sub),
        "cursor": cursor,
        "lanes": sorted(l.dirname for l in lanes) + sorted(ring_lanes - {l.dirname for l in lanes}),
        "minted": sorted(l.slug for l in minted),
        "placed": sorted(l.slug for l in placed),
        "history": with_history,
    }
    return receipt
