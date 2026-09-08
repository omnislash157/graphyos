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

import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Provisioned", "VenvLayout", "venv_layout", "provision", "RECEIPT_NAME"]


@dataclass(frozen=True)
class VenvLayout:
    python: Path               # the venv's interpreter
    scripts: Path              # bin/ on POSIX, Scripts\ on Windows — where pip lands
    site: Path                 # its site-packages — where the ring is read from
    scheme: str                # the sysconfig scheme that placed them


def _venv_version(venv: Path) -> str:
    """The venv's own `major.minor`, from the `pyvenv.cfg` its creation wrote (`version = 3.12.3`;
    `version_info` on some builders); the running interpreter's when the file names none."""
    try:
        for line in (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            key, _, val = line.partition("=")
            if key.strip() in ("version", "version_info"):
                parts = val.strip().split(".")
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    return f"{parts[0]}.{parts[1]}"
    except OSError:
        pass
    return "%d.%d" % sys.version_info[:2]


def venv_layout(venv: str | Path, *, os_name: str | None = None) -> VenvLayout:
    """Where a venv keeps its interpreter and its site-packages, resolved by `sysconfig` for the
    platform's scheme — `posix_prefix` (`bin/python` · `lib/python3.X/site-packages`) or `nt`
    (`Scripts\\python.exe` · `Lib\\site-packages`) — never by a glob. The version in the path is the
    venv's own (`pyvenv.cfg`); when it is the running interpreter's, the live `py_version_short`
    is used so an ABI-suffixed layout (`python3.13t`) resolves too."""
    venv = Path(venv)
    os_name = os_name or os.name
    scheme = "nt" if os_name == "nt" else "posix_prefix"
    version = _venv_version(venv)
    if version == "%d.%d" % sys.version_info[:2]:
        version = sysconfig.get_config_var("py_version_short") or version
    base = str(venv)
    paths = sysconfig.get_paths(scheme, vars={"base": base, "platbase": base, "installed_base": base,
                                              "installed_platbase": base, "py_version_short": version,
                                              "py_version_nodot": version.replace(".", "")})
    scripts = Path(paths["scripts"])
    python = scripts / ("python.exe" if os_name == "nt" else "python")
    return VenvLayout(python=python, scripts=scripts, site=Path(paths["purelib"]), scheme=scheme)


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
              runner=None, log=None, os_name: str | None = None) -> Provisioned:
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
    if not (venv / "pyvenv.cfg").is_file():
        base = python or sys.executable
        log(f"PROVISION: {base} -m venv {venv}")
        rc, tail = run([base, "-m", "venv", str(venv)], timeout=timeout)
        if rc != 0:
            raise RuntimeError(f"could not make the venv at {venv}: {tail}")
    layout = venv_layout(venv, os_name=os_name)
    py, site = layout.python, layout.site
    if not site.is_dir():
        raise RuntimeError(f"the venv at {venv} has no site-packages at {site} ({layout.scheme} layout)")
    if not any((repo / f).is_file() for f in ("pyproject.toml", "setup.py", "setup.cfg")):
        return Provisioned(site, "no pyproject.toml or setup.py — the package is minted alone, its imports named unresolved", False)
    declared = _declaration(repo)
    receipt = venv / RECEIPT_NAME
    try:
        if json.loads(receipt.read_text(encoding="utf-8")).get("declaration") == declared:
            return Provisioned(site, f"pip install skipped — {venv} was provisioned from this declaration "
                                     f"(pyproject.toml · setup.py · setup.cfg unchanged; delete {receipt} to force)", True)
    except (OSError, ValueError, AttributeError):
        pass
    cmd = [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(repo)]
    log(f"PROVISION: {' '.join(cmd)}")
    rc, tail = run(cmd, timeout=timeout)
    if rc != 0:
        return Provisioned(site, f"the repo did not pip-install ({tail or 'no output'}) — the package is minted alone, its imports named unresolved", False)
    receipt.write_text(json.dumps({"declaration": declared, "command": cmd}, indent=2) + "\n", encoding="utf-8")
    return Provisioned(site, f"pip install {repo.name} into {venv}", True)


RECEIPT_NAME = "provision.json"
_DECLARATION_FILES = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")


def _declaration(repo: Path) -> dict[str, str]:
    """What the pip install read: the sha256 of each declaration file the repo carries. The
    receipt beside the venv pins it; a re-eat under the same declaration skips the install."""
    out: dict[str, str] = {}
    for name in _DECLARATION_FILES:
        f = repo / name
        if f.is_file():
            out[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out
