"""provision — the repo's own dependencies, installed where the ring is read from.

`graphy eat` resolves a package's import ring from where its dependencies are installed. When
the caller names nothing, this module provisions it beside the repo and says what it did: a
Python repo gets `<repo>/.graphy/venv` with `pip install <repo>` (the repo's own metadata is the
declaration of its dependencies); a `package.json` repo gets `npm install --ignore-scripts` into
its own `node_modules`. A repo that will not install is not a failure of the eat: the package is
minted alone, the ring is whatever the site holds, and the line says so by name. Nothing is
guessed — the interpreter is this one, the repo is the one named, and every command is printed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Provisioned", "provision"]


@dataclass
class Provisioned:
    site: Path                 # where the ring is read from
    how: str                   # what happened, one line
    installed: bool            # did the dependencies land


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{type(exc).__name__}: {exc}"[:300]
    tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-3:])
    return proc.returncode, tail


def provision(repo: str | Path, producer: str, *, python: str | None = None, timeout: int = 900,
              runner=None, log=None) -> Provisioned:
    """The site the ring is read from for `repo` under `producer`, provisioned when absent."""
    repo = Path(repo).resolve()
    log = log or (lambda *_: None)
    run = runner or _run
    if producer == "typescript_ast":
        nm = repo / "node_modules"
        if not (repo / "package.json").is_file():
            return Provisioned(nm, "no package.json — the ring is the root shard alone", False)
        if shutil.which("npm") is None:
            return Provisioned(nm, "npm is not on PATH — the ring is whatever node_modules already holds", False)
        cmd = ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", "--loglevel=error"]
        log(f"PROVISION: {' '.join(cmd)}  (in {repo})")
        rc, tail = run(cmd, cwd=repo, timeout=timeout)
        if rc != 0:
            return Provisioned(nm, f"npm install failed ({tail or 'no output'}) — the ring is whatever node_modules already holds", False)
        return Provisioned(nm, f"npm install into {nm}", True)

    venv = repo / ".graphy" / "venv"
    py = venv / "bin" / "python"
    if not py.exists():
        base = python or sys.executable
        log(f"PROVISION: {base} -m venv {venv}")
        rc, tail = run([base, "-m", "venv", str(venv)], timeout=timeout)
        if rc != 0:
            raise RuntimeError(f"could not make the venv at {venv}: {tail}")
    site = next(iter(sorted(venv.glob("lib/python*/site-packages"))), None)
    if site is None:
        raise RuntimeError(f"the venv at {venv} has no site-packages")
    if not any((repo / f).is_file() for f in ("pyproject.toml", "setup.py", "setup.cfg")):
        return Provisioned(site, "no pyproject.toml or setup.py — the package is minted alone, its imports named unresolved", False)
    cmd = [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(repo)]
    log(f"PROVISION: {' '.join(cmd)}")
    rc, tail = run(cmd, timeout=timeout)
    if rc != 0:
        return Provisioned(site, f"the repo did not pip-install ({tail or 'no output'}) — the package is minted alone, its imports named unresolved", False)
    return Provisioned(site, f"pip install {repo.name} into {venv}", True)
