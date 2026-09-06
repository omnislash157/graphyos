#!/usr/bin/env python3
"""measure — every number RECON carries, re-derived by one command into one receipt.

    python3 measure.py run [--out recon.json] [--quick]     the receipt: the floor, the gate, the wheel, and
                                                            (unless --quick) every tenant's rebuild, the pinned
                                                            quickstarts, the index — each with its seconds
    python3 measure.py diff OLD NEW [--time-tolerance 0.15] every number that moved, its direction; exit 1 on a
                                                            regression past tolerance (times) or any (counts)

A number without the command that re-derives it is a lie waiting to happen; this file is the
commands. The receipt is the before-and-after the improvement gate compares: a change is positive
when a number moved the right way, and it regresses nothing past tolerance. Nothing here decides;
it measures and says.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine"
VENV_PY = HERE / ".venv" / "bin" / "python"
QUICKSTARTS = ("https://github.com/encode/httpx.git", "https://github.com/expressjs/express.git")
TENANTS = ("fastapi", "sqlalchemy", "hono", "express")

# direction: which way is better for a number; a number not listed is informational
BETTER = {"floor.seconds": "down", "floor.failed": "down", "gate.seconds": "down", "wheel.bytes": "down", "sdist.bytes": "down",
          "index.broken": "down", "floor.passed": "up", "index.names": "up"}


def _run(cmd, *, cwd=None, env=None, timeout=3600) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    e = dict(os.environ)
    e.update(env or {})
    try:
        p = subprocess.run(cmd, cwd=str(cwd or HERE), env=e, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
    except subprocess.TimeoutExpired as exc:
        out, rc = f"timeout after {timeout}s", 124
    return rc, out, round(time.perf_counter() - t0, 1)


def _num(pattern: str, text: str, cast=int, default=None):
    m = re.search(pattern, text)
    return cast(m.group(1)) if m else default


def measure_floor(py: str) -> dict:
    rc, out, secs = _run([py, "-m", "pytest"], cwd=ENGINE)      # pyproject already says -q; a second -q silences the summary
    return {"passed": _num(r"(\d+) passed", out, default=0), "failed": _num(r"(\d+) failed", out, default=0),
            "skipped": _num(r"(\d+) skipped", out, default=0), "seconds": secs, "rc": rc}


def measure_gate() -> dict:
    rc, out, secs = _run(["bash", str(HERE / "standalone_check.sh")])
    return {"ok": "GRAPHY_STANDALONE_OK" in out, "seconds": secs, "rc": rc}


def measure_wheel(py: str) -> dict:
    rc, out, secs = _run(["bash", str(HERE / "release.sh")], env={"PYTHON": py})
    wheels = sorted((HERE / "dist").glob("*.whl"))
    sdists = sorted((HERE / "dist").glob("*.tar.gz"))
    return {"ok": rc == 0, "seconds": secs, "wheel_bytes": wheels[0].stat().st_size if wheels else None,
            "sdist_bytes": sdists[0].stat().st_size if sdists else None,
            "version": _num(r"graphyos-([\d.]+)-py3", wheels[0].name, cast=str) if wheels else None}


def measure_tenant(name: str, py: str) -> dict:
    env = {"PYTHON": py}
    if name == "fastapi":
        sp = sorted((HERE / "staging" / "corpora" / "venv" / "lib").glob("python*/site-packages"))
        if sp:
            env["GRAPHY_CORPUS_SITE_PACKAGES"] = str(sp[0])
    rc, out, secs = _run(["bash", str(ENGINE / "tenants" / name / "rebuild.sh")], env=env)
    return {"ok": f"{name.upper()}_TENANT_OK" in out, "seconds": secs,
            "shards": len(re.findall(r"^MINT OK: |^PULL OK: ", out, re.M)),
            "nodes": _num(r"BUILD OK: compiled (\d+) nodes", out), "edges": _num(r"BUILD OK: compiled \d+ nodes / (\d+) edges", out),
            "arms": _num(r"ARMS OK: (\d+) arm", out), "atlas": _num(r"ATLAS OK: (\d+) picture", out), "rc": rc}


def measure_quickstart(url: str) -> dict:
    name = url.rsplit("/", 1)[-1][:-4]
    shutil.rmtree(HERE / "staging" / "quickstart" / name, ignore_errors=True)
    rc, out, secs = _run(["bash", str(HERE / "quickstart.sh"), url])
    return {"repo": name, "ok": "GRAPHY_QUICKSTART_OK" in out, "seconds": secs,
            "ring": _num(r"RING: (\d+) shard", out), "rc": rc}


def measure_index(py: str) -> dict:
    idx = HERE / "staging" / "index" / "farm"
    if not (idx / "catalog.json").is_file():
        return {"present": False}
    rc, out, secs = _run([py, "-m", "graphy", "index", "--index", str(idx), "--verify"], cwd=ENGINE)
    return {"present": True, "names": _num(r"INDEX OK: (\d+) named", out) or _num(r"(\d+) named shard", out),
            "broken": _num(r"(\d+) broken", out, default=None), "verify_seconds": secs, "rc": rc}


def run(out: Path, quick: bool) -> dict:
    py = str(VENV_PY if VENV_PY.exists() else sys.executable)
    t0 = time.perf_counter()
    r = {"measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "host": os.uname().nodename, "python": py, "quick": quick,
         "floor": measure_floor(py), "gate": measure_gate(), "wheel": measure_wheel(py)}
    if not quick:
        r["tenants"] = {t: measure_tenant(t, py) for t in TENANTS}
        r["quickstart"] = {q["repo"]: q for q in (measure_quickstart(u) for u in QUICKSTARTS)}
        r["index"] = measure_index(py)
    r["seconds"] = round(time.perf_counter() - t0, 1)
    out.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return r


def flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = v
        elif isinstance(v, bool):
            out[key] = v
    return out


def diff(old: dict, new: dict, time_tolerance: float = 0.15) -> tuple[list[str], list[str]]:
    """(lines, regressions). A time is a regression past tolerance; a count is a regression on any
    move the wrong way; a verdict flipping to false is a regression."""
    a, b = flatten(old), flatten(new)
    lines, bad = [], []
    for k in sorted(set(a) | set(b)):
        if k in ("measured_at",) or k.endswith(".rc"):
            continue
        va, vb = a.get(k), b.get(k)
        if va == vb or va is None or vb is None:
            continue
        better = BETTER.get(k) or ("down" if k.endswith(("seconds", "bytes", "broken", "failed")) else
                                   "up" if k.endswith(("passed", "names", "shards", "nodes", "edges", "arms", "ring", "atlas")) else None)
        if isinstance(va, bool) or isinstance(vb, bool):
            lines.append(f"  {k}: {va} -> {vb}")
            if va is True and vb is False:
                bad.append(f"{k} flipped to false")
            continue
        delta = vb - va
        rel = (delta / va) if va else float("inf")
        arrow = "↑" if delta > 0 else "↓"
        verdict = ""
        if better:
            good = (delta < 0) == (better == "down")
            is_time = k.endswith(("seconds", "bytes"))
            if not good and (not is_time or abs(rel) > time_tolerance):
                verdict = "  REGRESSION"
                bad.append(f"{k} {va} -> {vb} ({rel:+.0%})")
            elif good:
                verdict = "  better"
        lines.append(f"  {k}: {va} -> {vb} {arrow}{rel:+.0%}{verdict}" if va else f"  {k}: {va} -> {vb}{verdict}")
    return lines, bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", default=str(HERE / "recon.json"))
    r.add_argument("--quick", action="store_true", help="the floor, the gate and the wheel only (CI)")
    d = sub.add_parser("diff")
    d.add_argument("old"), d.add_argument("new")
    d.add_argument("--time-tolerance", type=float, default=0.15)
    args = ap.parse_args(argv)
    if args.verb == "run":
        rec = run(Path(args.out), args.quick)
        f = rec["floor"]
        print(f"MEASURE OK: floor {f['passed']} passed / {f['failed']} failed in {f['seconds']}s · gate {'OK' if rec['gate']['ok'] else 'RED'} {rec['gate']['seconds']}s · "
              f"wheel {rec['wheel']['wheel_bytes']} B" + ("" if args.quick else
              " · tenants " + " ".join(f"{t}={'OK' if v['ok'] else 'RED'}/{v['seconds']}s" for t, v in rec['tenants'].items())
              + " · quickstart " + " ".join(f"{q}={'OK' if v['ok'] else 'RED'}/{v['seconds']}s" for q, v in rec['quickstart'].items()))
              + f" · {rec['seconds']}s -> {args.out}")
        red = [k for k, v in flatten(rec).items() if k.endswith(".ok") and v is False]
        return 1 if red else 0
    old, new = json.loads(Path(args.old).read_text()), json.loads(Path(args.new).read_text())
    lines, bad = diff(old, new, args.time_tolerance)
    print("\n".join(lines) if lines else "  (no number moved)")
    if bad:
        print(f"MEASURE REGRESSION: {len(bad)} number(s) moved the wrong way — " + "; ".join(bad))
        return 1
    print(f"MEASURE DIFF OK: {len(lines)} number(s) moved, none the wrong way past tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
