"""The refresh lane. When a tenant's package moves upstream, ``refresh`` re-mints the tenant at
the newer release into a *sibling* substrate and proves it there, then reports what was born and
what died per shard between the two versions — never in place, never silent.

The lane, in order, every step a verb the tenant's own rebuild runs:

1. read the current shard's ``PROVENANCE.json`` for the distribution and the version it was
   minted from; an absent provenance or version refuses;
2. ask PyPI for the newest release (``--release`` names one instead; ``--site-packages`` names
   an already-provisioned ring and reads the version off its ``dist-info``); a release no newer
   than the current one is ``CURRENT`` and the lane stops;
3. provision a fresh venv beside the sibling substrate, pinned to exactly that release, with
   the interpreter the lane runs on;
4. ``smash`` the package and its import ring into the sibling substrate; declare a sibling
   descriptor (``<tenant>.<version>.json``) over exactly the shards the ring minted; write the
   scheme index the way ``rebuild.sh`` does;
5. ``converge --resolve`` · ``build`` · ``check`` on the sibling — a red check is exit 1 and the
   sibling stays on disk for the operator to read; the current substrate is never touched;
6. stamp one journal page per shard into the *sibling's* journal — ``old`` the current shard's
   ids, ``new`` the sibling's, ``prev_cursor`` the old version, ``cursor`` the new — and report
   what the journal says was born and died. A shard the new ring dropped or gained is named.

``--fixture <shard dir>`` re-mints the tenant's golden fixture from the sibling's site-packages
with the engine's own ``--no-ring`` mint command once the check is green, closing the pin: the
next ``rebuild.sh`` against the new ring passes parity. Promotion — making the sibling the
tenant's substrate — is the operator's move and is printed, never taken.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from graphy import journal
from graphy import smash as smash_lane
from graphy.tenant import Tenant

__all__ = ["RefreshError", "CheckFailed", "Plan", "current_provenance", "latest_release",
           "parse_version", "is_newer", "plan_for", "provision", "diff_shards", "render_pages",
           "refresh", "RECEIPT_NAME", "PYPI_URL"]

RECEIPT_NAME = "refresh.json"
PYPI_URL = "https://pypi.org/pypi/{distribution}/json"
_PRE = {"a": -3, "b": -2, "rc": -1}
_GARBAGE = ((-1,), (0, 0), 0, 0)
_VERSION_RE = re.compile(r"^v?(?P<release>\d+(?:\.\d+)*)(?:(?P<pre>a|b|rc)(?P<pren>\d*))?(?:\.post(?P<post>\d+))?(?:\.dev(?P<dev>\d+))?$")


class RefreshError(RuntimeError):
    """The lane refused: a precondition is missing. Exit 2."""


class CheckFailed(RuntimeError):
    """The sibling was minted and built but its audit is red. Exit 1; the sibling stays."""


@dataclass(frozen=True)
class Plan:
    package: str
    slug: str
    distribution: str
    current: str
    release: str
    data_home: Path
    descriptor: Path
    venv: Path
    site_packages: Path | None


# --------------------------------------------------------------------------- the pin

def current_provenance(tenant: Tenant, package: str) -> dict:
    """The current shard's PROVENANCE.json; refuses when it, or its version, is absent."""
    slug = smash_lane.slug_for(package)
    if slug is None:
        raise RefreshError(f"package {package!r} cannot name a shard: the slug grammar is [a-z0-9_]+")
    path = Path(tenant.data_home) / f"{slug}_graph" / smash_lane.PROVENANCE_NAME
    if not path.is_file():
        raise RefreshError(f"no {smash_lane.PROVENANCE_NAME} at {path} — the tenant holds no minted "
                           f"shard for {package!r} to refresh against")
    try:
        prov = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RefreshError(f"{path} is unreadable: {exc}") from exc
    corpus = prov.get("corpus") if isinstance(prov, dict) else None
    if not isinstance(corpus, dict) or not corpus.get("version"):
        raise RefreshError(f"{path} carries no corpus.version — a shard minted from a checkout, not a "
                           f"wheel, has no release to refresh from")
    return prov


def parse_version(text: str) -> tuple:
    """A PEP 440 release, as far as the lane needs: numeric segments, then a pre-release rank
    (a < b < rc < final), post and dev. Unparseable text sorts below everything, so a garbled
    upstream version never reads as newer."""
    m = _VERSION_RE.match(str(text).strip())
    if not m:
        return _GARBAGE
    release = tuple(int(x) for x in m.group("release").split("."))
    while len(release) > 1 and release[-1] == 0:
        release = release[:-1]
    pre = (_PRE[m.group("pre")], int(m.group("pren") or 0)) if m.group("pre") else (0, 0)
    post = int(m.group("post") or 0)
    dev = 0 if m.group("dev") is None else -1 - int(m.group("dev"))
    return (release, pre, post, dev)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def is_final(text: str) -> bool:
    """PEP 440's final release: no a/b/rc segment and no .devN. A post-release of a final is
    final. Garbage is not."""
    v = parse_version(text)
    return v != _GARBAGE and v[1] == (0, 0) and v[3] == 0


def _fetch_pypi(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "graphy-refresh"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_release(distribution: str, *, fetch: Callable[[str], dict] | None = None) -> str:
    """The newest final release PyPI lists for ``distribution`` (pre-releases are skipped, the
    same way pip's default resolver skips them). Unreachable is refused, never guessed."""
    url = PYPI_URL.format(distribution=distribution)
    try:
        data = (fetch or _fetch_pypi)(url)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RefreshError(f"PyPI unreachable for {distribution!r} ({exc}) — name the release with "
                           f"--release, or an already-provisioned ring with --site-packages") from exc
    releases = data.get("releases") if isinstance(data, dict) else None
    if not isinstance(releases, dict) or not releases:
        raise RefreshError(f"PyPI lists no releases for {distribution!r} at {url}")
    finals = [v for v, files in releases.items()
              if files and is_final(v) and not any(f.get("yanked") for f in files)]
    if not finals:
        raise RefreshError(f"PyPI lists no final, un-yanked release for {distribution!r}")
    return max(finals, key=parse_version)


def plan_for(tenant: Tenant, descriptor: Path, package: str, prov: dict, release: str,
             site_packages: Path | None = None) -> Plan:
    """The sibling's paths, all derived from the current descriptor: ``<data_home>.<release>``
    beside the current substrate, ``<descriptor stem>.<release>.json`` beside the descriptor,
    the venv inside the sibling."""
    slug = smash_lane.slug_for(package)
    home = Path(tenant.data_home)
    sibling = home.with_name(f"{home.name}.{release}")
    desc = Path(descriptor)
    return Plan(package=package, slug=slug, distribution=prov["corpus"].get("distribution") or package,
                current=str(prov["corpus"]["version"]), release=release,
                data_home=sibling, descriptor=desc.with_name(f"{desc.stem}.{release}{desc.suffix}"),
                venv=sibling / "venv", site_packages=site_packages)


# --------------------------------------------------------------------------- the ring

def _run(cmd: list[str], *, log, what: str, audit: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    pkg_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = pkg_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    for line in (proc.stdout or "").splitlines():
        if line.strip():
            log(f"  {line}")
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        tail = "\n".join(f"    {ln}" for ln in err[-12:]) or "    (no stderr)"
        kind = CheckFailed if audit else RefreshError
        raise kind(f"{what} exited {proc.returncode}:\n{tail}")
    return proc


def provision(venv: Path, distribution: str, release: str, *, python: str, log) -> Path:
    """A fresh venv at ``venv`` pinned to ``distribution==release``; returns its site-packages."""
    if venv.exists():
        shutil.rmtree(venv)
    log(f"VENV: {python} -m venv {venv}")
    _run([python, "-m", "venv", str(venv)], log=log, what="venv")
    pip = venv / "bin" / "pip"
    if not pip.exists():
        raise RefreshError(f"the venv at {venv} has no pip — ensurepip is missing from {python}")
    log(f"PIP: {distribution}=={release}")
    _run([str(pip), "install", "--quiet", "--disable-pip-version-check", f"{distribution}=={release}"],
         log=log, what=f"pip install {distribution}=={release}")
    sp = next(iter(sorted(venv.glob("lib/python*/site-packages"))), None)
    if sp is None:
        raise RefreshError(f"the venv at {venv} has no site-packages")
    return sp


def _version_in(site_packages: Path, package: str) -> str:
    dist = smash_lane.distributions(site_packages).get(package)
    if not dist or not dist.get("version"):
        raise RefreshError(f"{site_packages} carries no dist-info for {package!r} — the release cannot be read")
    return dist["version"]


def _descriptor(tenant: Tenant, plan: Plan, ring: dict, cursor: str) -> dict:
    lanes = {f"{m['slug']}_graph": [None, "static-dep"] for m in ring["minted"].values()}
    return {
        "root": str(tenant.root),
        "data_home": str(plan.data_home),
        "adapters": ["python_ast"],
        "build_lanes": lanes,
        "join_keys": str(plan.data_home / "registry.json"),
        "cursor": cursor,
        "policy": "refuse",
        "journal": str(plan.data_home / "journal"),
    }


def _sibling_tenant(desc: dict) -> Tenant:
    return Tenant(root=Path(desc["root"]), data_home=Path(desc["data_home"]),
                  adapters=tuple(desc["adapters"]),
                  build_lanes={k: tuple(v) for k, v in desc["build_lanes"].items()},
                  join_keys=Path(desc["join_keys"]), cursor=desc["cursor"], policy=desc["policy"],
                  journal=Path(desc["journal"]))


def _declare(tenant: Tenant, plan: Plan, ring: dict) -> Tenant:
    root_edges = plan.data_home / f"{plan.slug}_graph" / "edges.json"
    cursor = "sha256:" + hashlib.sha256(root_edges.read_bytes()).hexdigest()
    desc = _descriptor(tenant, plan, ring, cursor)
    (plan.data_home / "journal").mkdir(parents=True, exist_ok=True)
    registry = plan.data_home / "registry.json"
    if not registry.exists():
        registry.write_text(json.dumps({"_meta": {"description": "graphy refresh registry"},
                                        "registered_joins": {"literal_joins": {}}}, indent=2, sort_keys=True),
                            encoding="utf-8")
    index = {"_meta": {"description": f"{plan.slug} tenant scheme index — derived from ring.json by graphy refresh",
                       "standard": ring.get("standard", [])},
             **ring["scheme_index"]}
    (plan.data_home / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n",
                                                                  encoding="utf-8")
    plan.descriptor.write_text(json.dumps(desc, indent=2, sort_keys=True), encoding="utf-8")
    return _sibling_tenant(desc)


def _prove(plan: Plan, tenant_id: str, *, python: str, log) -> None:
    base = [python, "-m", "graphy"]
    tenant_args = ["--tenant", str(plan.descriptor), "--tenant-id", tenant_id]
    _run(base + ["converge", *tenant_args, "--resolve"], log=log, what="converge --resolve")
    _run(base + ["build", *tenant_args], log=log, what="build")
    _run(base + ["check", *tenant_args], log=log, what="check", audit=True)


# --------------------------------------------------------------------------- the diff

def _shards(home: Path) -> dict[str, Path]:
    return {p.name[: -len("_graph")]: p for p in sorted(home.glob("*_graph"))
            if (p / "nodes.json").is_file()}


def diff_shards(old_home: Path, new_home: Path, *, sibling: Tenant, old_version: str,
                new_version: str) -> list[dict]:
    """One journal page per shard in either substrate, stamped into the sibling's journal:
    old the current shard's node ids and edge keys, new the sibling's, ``prev_cursor`` the old
    version and ``cursor`` the new. A shard on one side only is born or died whole. Returns the
    pages as the journal reads them back, each with ``shard`` and ``presence`` added."""
    old, new = _shards(old_home), _shards(new_home)
    pages: list[dict] = []
    for slug in sorted(set(old) | set(new)):
        o_nodes, o_edges = journal._read_ids(old[slug]) if slug in old else (set(), set())
        n_nodes, n_edges = journal._read_ids(new[slug]) if slug in new else (set(), set())
        journal.append_page(f"{slug}_graph", o_nodes, n_nodes, o_edges, n_edges,
                            cursor=new_version, prev_cursor=old_version, tenant=sibling)
        _, read_back, torn = journal.read_journal(f"{slug}_graph", sibling)
        if torn or not read_back:
            raise RefreshError(f"the sibling journal for {slug}_graph did not read back the page it stamped")
        page = dict(read_back[-1])
        page["shard"] = f"{slug}_graph"
        page["presence"] = "both" if slug in old and slug in new else ("new" if slug in new else "gone")
        pages.append(page)
    return pages


def _ids(page: dict, key: str, cap: int = 8) -> str:
    ids = page.get(key) or []
    shown = ", ".join(str(i).split("://", 1)[-1] for i in ids[:cap])
    more = f" … +{len(ids) - cap}" if len(ids) > cap else ""
    return shown + more


def render_pages(pages: list[dict], *, old_version: str, new_version: str) -> str:
    lines = [f"DIFF {old_version} -> {new_version}: {len(pages)} shard(s), what the journal says"]
    for p in pages:
        tag = {"both": "", "new": "  [shard born: not in the old ring]", "gone": "  [shard died: not in the new ring]"}[p["presence"]]
        lines.append(f"  {p['shard']}: nodes +{p['n_born']} -{p['n_died']} · edges +{p['n_eborn']} -{p['n_edied']}{tag}")
        if p.get("n_born") and p["presence"] == "both":
            lines.append(f"    born  {_ids(p, 'born')}")
        if p.get("n_died") and p["presence"] == "both":
            lines.append(f"    died  {_ids(p, 'died')}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- the lane

def _remint_fixture(plan: Plan, fixture: Path, *, log) -> dict:
    fixture = Path(fixture).resolve()
    if fixture.name != f"{plan.slug}_graph":
        raise RefreshError(f"--fixture must be the golden shard directory {plan.slug}_graph, got {fixture}")
    ring_receipt = fixture.parent / smash_lane.RING_NAME
    had_ring = ring_receipt.exists()
    receipt = smash_lane.smash(plan.package, site_packages=plan.site_packages, out=fixture.parent,
                               ring=False, log=log)
    if not had_ring and ring_receipt.exists():
        ring_receipt.unlink()
    minted = receipt["minted"][plan.package]
    log(f"FIXTURE OK: {fixture} re-minted at {plan.release} — {minted['nodes']} nodes / {minted['edges']} edges")
    return minted


def refresh(descriptor: str | Path, tenant_id: str, *, package: str, release: str | None = None,
            site_packages: str | Path | None = None, python: str | None = None,
            fixture: str | Path | None = None, force: bool = False, check_only: bool = False,
            fetch: Callable[[str], dict] | None = None, log=None) -> dict:
    """Run the lane. Returns the receipt (also written to ``<sibling>/refresh.json``). Raises
    RefreshError when a precondition is missing, CheckFailed when the sibling's audit is red."""
    from graphy.cli import _load_tenant  # the descriptor reader; cli imports this module lazily
    log = log or (lambda s: None)
    python = python or sys.executable
    desc_path = Path(descriptor).resolve()
    tenant = _load_tenant(str(desc_path))
    prov = current_provenance(tenant, package)
    distribution = prov["corpus"].get("distribution") or package
    current = str(prov["corpus"]["version"])

    sp = Path(site_packages).resolve() if site_packages else None
    if sp is not None:
        if not sp.is_dir():
            raise RefreshError(f"--site-packages is not a directory: {sp}")
        found = _version_in(sp, package)
        if release and release != found:
            raise RefreshError(f"--release {release} but {sp} holds {package} {found}")
        release, source = found, f"read off {sp}"
    elif release:
        source = "named by --release"
    else:
        release, source = latest_release(distribution, fetch=fetch), PYPI_URL.format(distribution=distribution)

    receipt: dict = {"package": package, "distribution": distribution, "tenant_id": tenant_id,
                     "descriptor": str(desc_path), "current": current, "release": release,
                     "release_source": source,
                     "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if not is_newer(release, current):
        receipt["verdict"] = "CURRENT"
        log(f"REFRESH CURRENT: {package} {current} is the newest release ({source}); nothing to mint")
        return receipt
    log(f"UPSTREAM: {distribution} {current} -> {release} ({source})")
    if check_only:
        receipt["verdict"] = "NEWER"
        return receipt

    plan = plan_for(tenant, desc_path, package, prov, release, sp)
    if plan.data_home.resolve() == Path(tenant.data_home).resolve():
        raise RefreshError("the sibling would be the current substrate — refuse")
    for p in (plan.data_home, plan.descriptor):
        if p.exists():
            if not force:
                raise RefreshError(f"{p} exists — a previous refresh at {release}; pass --force to re-mint over it")
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    plan.data_home.mkdir(parents=True)
    receipt.update({"sibling": str(plan.data_home), "sibling_descriptor": str(plan.descriptor)})

    if sp is None:
        sp = provision(plan.venv, distribution, release, python=python, log=log)
        plan = Plan(**{**plan.__dict__, "site_packages": sp})
        if (got := _version_in(sp, package)) != release:
            raise RefreshError(f"the venv installed {package} {got}, not {release}")
    receipt["site_packages"] = str(sp)

    ring = smash_lane.smash(package, site_packages=sp, out=plan.data_home, log=log)
    receipt["ring"] = {"minted": sorted(ring["minted"]), "unresolved": ring["unresolved"]}
    sibling = _declare(tenant, plan, ring)
    log(f"DECLARED: {plan.descriptor} over {len(ring['minted'])} shard(s)")
    try:
        _prove(plan, tenant_id, python=python, log=log)
    except CheckFailed as exc:
        receipt["verdict"] = "CHECK FAILED"
        receipt["error"] = str(exc)
        smash_lane._write_json(plan.data_home / RECEIPT_NAME, receipt)
        raise
    receipt["verdict"] = "OK"

    pages = diff_shards(Path(tenant.data_home), plan.data_home, sibling=sibling,
                        old_version=current, new_version=release)
    receipt["diff"] = [{k: p.get(k) for k in ("shard", "presence", "n_born", "n_died", "n_eborn", "n_edied", "seq")}
                       for p in pages]
    log(render_pages(pages, old_version=current, new_version=release))
    if fixture is not None:
        receipt["fixture"] = _remint_fixture(plan, Path(fixture), log=log)
    smash_lane._write_json(plan.data_home / RECEIPT_NAME, receipt)
    log(f"REFRESH OK: {package} {current} -> {release} proven at {plan.data_home}; the current substrate "
        f"is untouched. Promote: GRAPHY_CORPUS_SITE_PACKAGES={sp} bash <tenant>/rebuild.sh"
        + ("" if fixture is not None else " (after --fixture re-mints the golden shard, or parity refuses)"))
    return receipt
