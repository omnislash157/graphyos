"""farm — mint many packages into one content-addressed index, in parallel, resumably.

One package per job: a fresh venv pinned to exactly one release (``--no-deps`` — the ring is the
index, not the venv: every dependency is its own entry, pulled by name, and a tenant's roster
names one release per scheme by the version-identity law), the package's importable names minted
by ``smash``, every shard pushed into the index under ``<distribution>==<version>``, the venv
deleted. The index is the state: a name already cataloged is skipped by address, so a farm that
stops resumes where it left. A package that cannot be minted is refused with its reason — no
importable name, a wheel over the size cap, pip's own failure, a producer flaw — and the farm
goes on; the receipt carries every verdict. Nothing is guessed: the release is PyPI's newest final
(or the one named), the import names are what the distribution's RECORD says it installed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from graphy import index as shard_index
from graphy import smash as smash_lane
from graphy.ir import IRError
from graphy.provision import venv_layout
from graphy.refresh import RefreshError, _fetch_pypi, latest_release, parse_version

__all__ = ["FarmError", "Spec", "Verdict", "top_packages", "select_release", "import_names_for",
           "farm_one", "farm", "RECEIPT_NAME"]

RECEIPT_NAME = "farm.json"
TOP_URL = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"
PYPI_URL = "https://pypi.org/pypi/{distribution}/json"
NPM_CANDIDATES_URLS = ("https://raw.githubusercontent.com/anvaka/npmrank/master/sample/dependencies.md",
                       "https://raw.githubusercontent.com/anvaka/npmrank/master/sample/alldependencies.md")
NPM_CANDIDATES_URL = NPM_CANDIDATES_URLS[0]
NPM_DOWNLOADS_URL = "https://api.npmjs.org/downloads/point/last-month/{names}"
NPM_REGISTRY_URL = "https://registry.npmjs.org/{distribution}"
_NORM = re.compile(r"[-_.]+")


class FarmError(RuntimeError):
    pass


def normalize(name: str) -> str:
    return _NORM.sub("-", name).lower()


@dataclass(frozen=True)
class Spec:
    distribution: str
    release: str | None = None

    @property
    def name(self) -> str | None:
        return f"{self.distribution}=={self.release}" if self.release else None

    @classmethod
    def parse(cls, text: str) -> "Spec":
        dist, _, rel = text.strip().partition("==")
        if not dist:
            raise FarmError(f"empty package spec {text!r}")
        return cls(dist, rel or None)


@dataclass
class Verdict:
    spec: str
    state: str                              # minted · skipped · refused
    reason: str = ""
    shards: list = field(default_factory=list)
    seconds: float = 0.0
    unresolved: dict = field(default_factory=dict)


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "graphy-farm"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def top_npm_packages(n: int, *, fetch=None, fetch_text=None) -> list[str]:
    """npm has no top-N endpoint. The candidates are npmrank's most-depended-upon list (a static
    sample, old but broad); the order is npm's own last-month download counts, fetched in bulk
    (128 names a call), so the top N is today's downloads over that candidate set."""
    cands: list[str] = []
    for url in NPM_CANDIDATES_URLS:
        try:
            text = (fetch_text or _fetch_text)(url)
        except (OSError, ValueError) as exc:
            raise FarmError(f"the npm candidate list is unreachable at {url} ({exc}) — pass --packages") from exc
        # only the "most dependent upon" section of each file: the same files go on to list the
        # packages WITH the most dependencies, which is the opposite ranking
        section = re.split(r"^# ", text, flags=re.M)
        wanted = [part for part in section if part.lower().startswith("top") and "dependent upon" in part.lower()]
        for part in wanted:
            for name in re.findall(r"^\d+\. \[([^\]]+)\]\(", part, re.M):
                if name not in cands:
                    cands.append(name)
    if not cands:
        raise FarmError(f"the npm candidate lists at {NPM_CANDIDATES_URLS} name no package under a 'most dependent upon' heading")
    counts: dict[str, int] = {}
    unscoped = [c for c in cands if not c.startswith("@")]      # the bulk endpoint takes unscoped names only
    for i in range(0, len(unscoped), 128):
        chunk = unscoped[i:i + 128]
        try:
            data = (fetch or _fetch_pypi)(NPM_DOWNLOADS_URL.format(names=",".join(chunk)))
        except (OSError, ValueError) as exc:
            raise FarmError(f"npm downloads unreachable ({exc})") from exc
        rows = data if len(chunk) > 1 else {chunk[0]: data}
        for name, row in (rows or {}).items():
            if isinstance(row, dict) and isinstance(row.get("downloads"), int):
                counts[name] = row["downloads"]
    ranked = sorted(counts, key=lambda k: -counts[k])
    return ranked[:n]


def top_packages(n: int, *, fetch=None, producer: str = "python_ast", fetch_text=None) -> list[str]:
    """The top-n distributions by downloads: PyPI from hugovk's monthly list, npm from the
    candidate set ranked by last-month downloads."""
    if producer == "typescript_ast":
        return top_npm_packages(n, fetch=fetch, fetch_text=fetch_text)
    try:
        data = (fetch or _fetch_pypi)(TOP_URL)
    except (OSError, ValueError) as exc:
        raise FarmError(f"the top-packages list is unreachable at {TOP_URL} ({exc}) — pass --packages") from exc
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise FarmError(f"the top-packages list at {TOP_URL} has no rows")
    return [str(r["project"]) for r in rows[:n] if isinstance(r, dict) and r.get("project")]


def select_npm_release(distribution: str, release: str | None, *, max_wheel_mb: float | None, fetch=None) -> tuple[str, float]:
    """npm's ``latest`` dist-tag (or the release named) and its unpacked size in MB; over the cap refuses."""
    data = (fetch or _fetch_pypi)(NPM_REGISTRY_URL.format(distribution=distribution))
    tags = data.get("dist-tags") if isinstance(data, dict) else None
    versions = data.get("versions") if isinstance(data, dict) else None
    if not isinstance(versions, dict) or not versions:
        raise RefreshError(f"the npm registry lists no version for {distribution!r}")
    rel = release or (tags or {}).get("latest")
    if not rel or rel not in versions:
        raise RefreshError(f"the npm registry names no latest release for {distribution!r}" if not release
                           else f"{distribution}@{release} is not on the npm registry")
    size = ((versions[rel].get("dist") or {}).get("unpackedSize"))
    mb = (size / 1e6) if isinstance(size, int) else 0.0
    if max_wheel_mb is not None and isinstance(size, int) and mb > max_wheel_mb:
        raise FarmError(f"{distribution}=={rel}: unpacked size {mb:.0f} MB, over the {max_wheel_mb:.0f} MB cap")
    return rel, mb


def select_release(distribution: str, release: str | None, *, max_wheel_mb: float | None, fetch=None,
                   producer: str = "python_ast") -> tuple[str, float]:
    """The release to mint and the smallest file PyPI lists for it, in MB. Refuses a release whose
    every file is over the cap — a cap is a budget, and a budget refuses, never truncates."""
    if producer == "typescript_ast":
        return select_npm_release(distribution, release, max_wheel_mb=max_wheel_mb, fetch=fetch)
    data = (fetch or _fetch_pypi)(PYPI_URL.format(distribution=distribution))
    rel = release or latest_release(distribution, fetch=lambda _u: data)
    files = (data.get("releases") or {}).get(rel) or []
    sizes = [f.get("size") for f in files if isinstance(f, dict) and isinstance(f.get("size"), int)]
    mb = (min(sizes) / 1e6) if sizes else 0.0
    if max_wheel_mb is not None and sizes and mb > max_wheel_mb:
        raise FarmError(f"{distribution}=={rel}: the smallest file is {mb:.0f} MB, over the {max_wheel_mb:.0f} MB cap")
    return rel, mb


def import_names_for(distribution: str, site_packages: Path, producer: smash_lane.Producer) -> list[str]:
    """The import names the distribution installed that the producer can mint, the one matching the
    distribution's own name first. An npm package is one scheme: its name as a slug."""
    if producer.name == "typescript_ast":
        slug = smash_lane.slug_for_specifier(distribution)
        return [slug] if slug and producer.locate(slug, site_packages) is not None else []
    want = normalize(distribution)
    names = sorted(name for name, meta in producer.distributions(site_packages).items()
                   if meta.get("distribution") and normalize(meta["distribution"]) == want
                   and not name.startswith("_") and smash_lane.slug_for(name)
                   and producer.locate(name, site_packages) is not None)
    names.sort(key=lambda n: (normalize(n) != want, n))
    return names


def _pip(venv: Path, args: list[str], *, timeout: int) -> None:
    pip = venv_layout(venv).scripts / "pip"
    proc = subprocess.run([str(pip), *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-4:])
        raise RefreshError(f"pip {' '.join(args[:2])} exited {proc.returncode}: {tail}")


def provision_alone(venv: Path, distribution: str, release: str, *, python: str, timeout: int = 900) -> Path:
    """A fresh venv holding exactly ``distribution==release`` and nothing else (``--no-deps``,
    ``--no-cache-dir``): the ring is the index."""
    if venv.exists():
        shutil.rmtree(venv)
    subprocess.run([python, "-m", "venv", "--without-pip", str(venv)], check=True, capture_output=True)
    # pip from the farm's own interpreter, run against the fresh venv's site-packages
    layout = venv_layout(venv)
    sp = layout.site
    if not sp.is_dir():
        raise RefreshError(f"the venv at {venv} has no site-packages at {sp} ({layout.scheme} layout)")
    proc = subprocess.run([python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-deps",
                           "--no-cache-dir", "--prefer-binary", "--target", str(sp), f"{distribution}=={release}"],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-4:])
        raise RefreshError(f"pip install {distribution}=={release} exited {proc.returncode}: {tail}")
    return sp


def provision_npm(job: Path, distribution: str, release: str, *, python: str = "", timeout: int = 900) -> Path:
    """``npm install --prefix <job>`` of exactly ``distribution@release`` with its runtime
    dependencies (``--omit=dev --ignore-scripts``); returns the node_modules the ring is read from."""
    if job.exists():
        shutil.rmtree(job)
    job.mkdir(parents=True)
    proc = subprocess.run(["npm", "install", "--prefix", str(job), "--ignore-scripts", "--no-save", "--no-audit",
                           "--no-fund", "--omit=dev", "--silent", f"{distribution}@{release}"],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-4:])
        raise RefreshError(f"npm install {distribution}@{release} exited {proc.returncode}: {tail}")
    nm = job / "node_modules"
    if not nm.is_dir():
        raise RefreshError(f"npm install {distribution}@{release} left no node_modules under {job}")
    return nm


def farm_one(spec_text: str, work: str, *, python: str, producer: str = "python_ast",
             max_wheel_mb: float | None = 200.0, keep_venv: bool = False, fetch=None,
             provision=None, timeout: int = 900, have: frozenset = frozenset()) -> dict:
    """One package, start to shards. Runs in a worker; returns a plain dict (a Verdict's fields)."""
    t0 = time.perf_counter()
    spec = Spec.parse(spec_text)
    prod = smash_lane.PRODUCERS[producer]
    try:
        release, _mb = select_release(spec.distribution, spec.release, max_wheel_mb=None, fetch=fetch, producer=producer)
    except (FarmError, RefreshError, OSError, ValueError) as exc:
        return Verdict(spec_text, "refused", str(exc), seconds=time.perf_counter() - t0).__dict__
    # the index name: PyPI's own distribution name; an npm name as its slug (a scoped name has a `/`)
    name = (f"{spec.distribution}=={release}" if producer == "python_ast"
            else f"{smash_lane.slug_for_specifier(spec.distribution) or spec.distribution}=={release}")
    if name in have:
        return Verdict(name, "skipped", "already in the index (the release PyPI names is the one it holds)",
                       seconds=time.perf_counter() - t0).__dict__
    try:
        select_release(spec.distribution, release, max_wheel_mb=max_wheel_mb, fetch=fetch, producer=producer)
    except FarmError as exc:
        return Verdict(name, "refused", str(exc), seconds=time.perf_counter() - t0).__dict__
    slug = smash_lane.slug_for(normalize(spec.distribution).replace("-", "_")) or re.sub(r"[^a-z0-9_]", "_", name.lower())
    job = Path(work) / slug
    venv, out = job / "venv", job / "out"
    if out.is_dir():
        shutil.rmtree(out)
    try:
        if provision is not None:
            sp = provision(venv, spec.distribution, release)
        elif producer == "typescript_ast":
            sp = provision_npm(venv, spec.distribution, release, python=python, timeout=timeout)
        else:
            sp = provision_alone(venv, spec.distribution, release, python=python, timeout=timeout)
        names = import_names_for(spec.distribution, sp, prod)
        if not names:
            return Verdict(name, "refused", "installs no importable package the producer reads (an extension-only, "
                           "namespace or data distribution)", seconds=time.perf_counter() - t0).__dict__
        shards: list = []
        unresolved: dict = {}
        for i, imp in enumerate(names):
            receipt = smash_lane.smash(imp, site_packages=sp, out=out / imp, ring=False, producer=producer,
                                       corpus=prod.locate(imp, sp) if producer == "typescript_ast" else None)
            # the first import name carries the distribution's own name; every other one the index
            # names `<dist>==<version>@<import>` so two shards of one release never share a name
            shards.append({"shard": receipt["minted"][imp]["shard"], "name": name if i == 0 else f"{name}@{imp}"})
            unresolved.update(receipt.get("unresolved") or {})
            # the imports the venv did not carry are the ring the index will: every scheme the shard names
            for scheme in receipt.get("imports", {}).get(imp, []):
                unresolved.setdefault(scheme, "the ring is the index")
        return Verdict(name, "minted", shards=shards, seconds=time.perf_counter() - t0,
                       unresolved={k: v for k, v in sorted(unresolved.items())}).__dict__
    except (RefreshError, smash_lane.SmashError, IRError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return Verdict(name, "refused", f"{type(exc).__name__}: {exc}"[:400], seconds=time.perf_counter() - t0).__dict__
    finally:
        if not keep_venv and venv.exists():
            shutil.rmtree(venv, ignore_errors=True)


def farm(specs: list[str], *, index: str | Path, work: str | Path, jobs: int = 1, python: str | None = None,
         producer: str = "python_ast", max_wheel_mb: float | None = 200.0, keep_venv: bool = False,
         log=None, fetch=None, provision=None, force: bool = False, timeout: int = 900) -> dict:
    log = log or (lambda *_: None)
    python = python or sys.executable
    if not Path(index).is_absolute() or not Path(work).is_absolute():
        raise FarmError(f"--index and --work must be absolute, got {index} and {work} — a relative path is an ambient fallback")
    index = str(index)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    have = shard_index.catalog(index) if Path(index).is_dir() else {}
    verdicts: dict[str, dict] = {}
    todo: list[str] = []
    for s in specs:
        spec = Spec.parse(s)
        if not force and spec.name and spec.name in have:
            verdicts[s] = Verdict(spec.name, "skipped", f"already in the index at {have[spec.name][:12]}…").__dict__
            log(f"FARM SKIPPED: {spec.name} — already in the index")
        else:
            todo.append(s)
    t0 = time.perf_counter()
    pushes: dict[str, list] = {}

    def _land(v: dict) -> None:
        if v["state"] == "minted":
            v["shards_pushed"] = []
            try:
                for shard in v["shards"]:
                    m = shard_index.push(shard["shard"], index, name=shard["name"])
                    v["shards_pushed"].append({"name": m["name"], "address": m["address"], "state": m["state"]})
            except (shard_index.IndexError_, OSError) as exc:
                v["state"], v["reason"] = "refused", f"push: {exc}"[:400]
        if v["state"] == "minted":
            names = ", ".join(f"{p['name']} ({p['state']})" for p in v["shards_pushed"])
            log(f"FARM: {v['spec']} minted {len(v['shards'])} shard(s) in {v['seconds']:.1f}s -> {names}")
        elif v["state"] == "refused":
            log(f"FARM REFUSED: {v['spec']}: {v['reason']}")
        elif v["state"] == "skipped":
            log(f"FARM SKIPPED: {v['spec']} — {v['reason']}")
        verdicts[v["spec"]] = v

    kw = dict(python=python, producer=producer, max_wheel_mb=max_wheel_mb, keep_venv=keep_venv,
              fetch=fetch, provision=provision, timeout=timeout, have=frozenset() if force else frozenset(have))
    if jobs <= 1 or fetch is not None or provision is not None:
        for s in todo:
            _land(farm_one(s, str(work), **kw))
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(farm_one, s, str(work), **kw): s for s in todo}
            for fut in as_completed(futs):
                try:
                    _land(fut.result())
                except Exception as exc:  # a worker died: the verdict is the refusal, never a crash
                    _land(Verdict(futs[fut], "refused", f"worker: {type(exc).__name__}: {exc}"[:400]).__dict__)
    totals = {"minted": sum(1 for v in verdicts.values() if v["state"] == "minted"),
              "skipped": sum(1 for v in verdicts.values() if v["state"] == "skipped"),
              "refused": sum(1 for v in verdicts.values() if v["state"] == "refused"),
              "shards_new": sum(1 for v in verdicts.values() for p in v.get("shards_pushed", []) if p["state"] == "pushed"),
              "shards_exist": sum(1 for v in verdicts.values() for p in v.get("shards_pushed", []) if p["state"] != "pushed"),
              "seconds": round(time.perf_counter() - t0, 1)}
    receipt = {"index": index, "work": str(work), "jobs": jobs, "producer": producer, "python": python,
               "max_wheel_mb": max_wheel_mb, "totals": totals,
               "packages": {k: verdicts[k] for k in sorted(verdicts)}}
    (work / RECEIPT_NAME).write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
