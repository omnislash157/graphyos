#!/usr/bin/env python3
"""burden — the invariants that keep the engine light, refused by name when they grow.

    python3 burden.py            check the engine against burden.json; exit 3 on any growth

Runtime dependencies stay at zero and the extras carry only the declared names; the wheel stays
under its cap; every network host the engine names is on the list; every subprocess the engine
runs is one of the declared programs; every tracked document under engine/ is either an arm file
carrying its generated region or on the list; the keyed scrub over everything tracked. A change
that adds a responsibility — a package, a host, a program, a document — must add it to
burden.json in the same commit, where a human reads it. Nothing here is a guess: each check
names the file and line it refuses.
"""
from __future__ import annotations

import ast
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine"
RULES = HERE / "burden.json"
_HOST = re.compile(r"https?://([A-Za-z0-9._-]+)")
_SUBPROC = ("run", "Popen", "check_output", "check_call", "call")


def load_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def check_dependencies(pyproject: Path, rules: dict) -> list[str]:
    try:
        import tomllib  # 3.11+; the gate runs there — a 3.10 floor skips this one check by name
    except ModuleNotFoundError as exc:
        raise RuntimeError("burden: check_dependencies needs tomllib (Python 3.11+); "
                           "the gate runs on 3.12 and a 3.10 floor skips it") from exc
    red = []
    proj = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
    deps = proj.get("dependencies", [])
    allowed = set(rules.get("runtime_dependencies", []))
    for d in deps:
        name = re.split(r"[<>=!~\[; ]", d, 1)[0].strip().lower()
        if name not in allowed:
            red.append(f"{pyproject}: runtime dependency {d!r} — the engine leans on nothing; burden.json says which")
    extras = proj.get("optional-dependencies", {})
    for extra, pkgs in extras.items():
        if extra not in rules.get("extras", {}):
            red.append(f"{pyproject}: extra {extra!r} is not declared in burden.json")
            continue
        ok = {p.lower() for p in rules["extras"][extra]}
        for p in pkgs:
            name = re.split(r"[<>=!~\[; ]", p, 1)[0].strip().lower()
            if name not in ok:
                red.append(f"{pyproject}: extra {extra!r} carries {p!r}, not declared in burden.json")
    return red


def check_wheel(dist: Path, rules: dict) -> tuple[list[str], str]:
    wheels = sorted(dist.glob("*.whl")) if dist.is_dir() else []
    if not wheels:
        return [], "wheel: not built (bash release.sh) — SKIPPED"
    w = wheels[-1]
    size = w.stat().st_size
    cap = int(rules.get("wheel_max_bytes", 0))
    if cap and size > cap:
        return [f"{w}: {size} bytes over the {cap} byte cap"], f"wheel: {size} B"
    return [], f"wheel: {size} B (cap {cap})"


def scan_hosts(root: Path, rules: dict) -> tuple[list[str], int]:
    allowed = set(rules.get("hosts", []))
    red, n = [], 0
    for f in sorted(root.rglob("*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for host in _HOST.findall(line):
                n += 1
                if host not in allowed:
                    red.append(f"{f.relative_to(root.parent)}:{i}: host {host} is not in burden.json")
    return red, n


def _literal_head(node, consts: dict) -> str:
    """The program a value names: a literal's basename; a module constant's literal
    (`GIT_PATH = shutil.which("git")` → git, `RG_PATH = resolve_rg()` → rg); `str(x)` → x."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.rsplit("/", 1)[-1]
    if isinstance(node, ast.Name):
        return consts.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return consts.get(node.attr, node.attr)
    if isinstance(node, ast.Call):
        return _literal_head(node.args[0], consts) if node.args else "?"
    if isinstance(node, ast.Subscript):
        return _literal_head(node.value, consts)
    return "?"


_ALIASES = {"python": "python", "python3": "python", "base": "python", "py": "python", "pip": "pip", "venv": "venv",
            "exe": "python", "sys.executable": "python", "executable": "python"}


def _module_consts(tree) -> dict:
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            name = node.targets[0].id
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                consts[name] = v.value.rsplit("/", 1)[-1]
            elif isinstance(v, ast.Call):
                fn = v.func
                if isinstance(fn, ast.Attribute) and fn.attr == "which" and v.args and isinstance(v.args[0], ast.Constant):
                    consts[name] = v.args[0].value
                elif isinstance(fn, ast.Name) and "rg" in fn.id.lower():
                    consts[name] = "rg"
    return consts


def _first_program(first, consts: dict, local_lists: dict | None = None) -> str:
    while isinstance(first, ast.BinOp) and isinstance(first.op, ast.Add):     # base + [...] → base
        first = first.left
    if isinstance(first, ast.Name) and local_lists and first.id in local_lists:
        first = local_lists[first.id]
    if isinstance(first, (ast.List, ast.Tuple)):
        return _literal_head(first.elts[0], consts) if first.elts else "?"
    return _literal_head(first, consts)


def _is_subprocess_call(node) -> bool:
    fn = node.func
    return ((isinstance(fn, ast.Attribute) and fn.attr in _SUBPROC and isinstance(fn.value, ast.Name) and fn.value.id == "subprocess")
            or (isinstance(fn, ast.Attribute) and fn.attr == "system" and isinstance(fn.value, ast.Name) and fn.value.id == "os"))


def _is_shell(node) -> bool:
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr == "system":
        return True
    for kw in node.keywords:
        if kw.arg == "shell" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
            return True
    return False


def _shell_spelling(node) -> str:
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr == "system":
        return "os.system"
    return next(f"shell={ast.unparse(kw.value)}" for kw in node.keywords if kw.arg == "shell")


def scan_subprocess(root: Path, rules: dict) -> tuple[list[str], int]:
    """Every program the engine runs. A direct call names it; a call whose command is a local
    list is resolved to that list's head; a call whose command is a parameter makes its function
    a runner, and every call of that runner is checked instead. A shell is refused by name — ``shell=True``
    on any call, or ``os.system`` — with no list to grow: every program the engine runs is argv (graphyos #41)."""
    allowed = set(rules.get("subprocess_targets", []))
    red, n = [], 0
    runners: dict[str, str] = {}          # function name -> module (a call to it is a subprocess call)
    modules: dict[Path, ast.Module] = {}
    for f in sorted(root.rglob("*.py")):
        try:
            modules[f] = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            red.append(f"{f}: unparseable ({exc})")

    def check_head(f: Path, lineno: int, head: str) -> None:
        token = _ALIASES.get(head, head)
        if token in allowed or head.lower().startswith("rg") and "rg" in allowed:
            return
        red.append(f"{f.relative_to(root.parent)}:{lineno}: subprocess target {head!r} is not in burden.json")

    # pass 1: direct calls, local lists, and the runners
    for f, tree in modules.items():
        consts = _module_consts(tree)
        modname = f.stem
        for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            params = {a.arg for a in func.args.args + func.args.kwonlyargs}
            qual = f"{modname}.{func.name}"
            local_lists = {}
            for node in ast.walk(func):
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                        and isinstance(node.value, (ast.List, ast.Tuple)) and node.value.elts:
                    local_lists[node.targets[0].id] = node.value
            for node in ast.walk(func):
                if not (isinstance(node, ast.Call) and _is_subprocess_call(node)):
                    continue
                n += 1
                if _is_shell(node):
                    red.append(f"{f.relative_to(root.parent)}:{node.lineno}: a shell over a string "
                               f"({_shell_spelling(node)}) — the engine runs argv only, never shell=True")
                    continue
                if not node.args:
                    continue
                first = node.args[0]
                if isinstance(first, ast.Name) and first.id in params:
                    runners[func.name] = modname
                    continue
                if isinstance(first, ast.Name) and first.id in local_lists:
                    first = local_lists[first.id]
                check_head(f, node.lineno, _first_program(first, consts))
    # pass 2: every call of a runner, anywhere in the package
    for f, tree in modules.items():
        consts = _module_consts(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _is_subprocess_call(node):     # direct calls were pass 1's
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            if name not in runners or not node.args:
                continue
            first = node.args[0]
            enclosing = next((fd for fd in ast.walk(tree) if isinstance(fd, (ast.FunctionDef, ast.AsyncFunctionDef))
                              and fd.lineno <= node.lineno <= (fd.end_lineno or fd.lineno)), None)
            local_lists = {}
            if enclosing:
                for a in ast.walk(enclosing):
                    if isinstance(a, ast.Assign) and len(a.targets) == 1 and isinstance(a.targets[0], ast.Name) \
                            and isinstance(a.value, (ast.List, ast.Tuple)) and a.value.elts:
                        local_lists[a.targets[0].id] = a.value
                head_name = first.left if isinstance(first, ast.BinOp) else first
                if isinstance(head_name, ast.Name) and head_name.id not in local_lists \
                        and head_name.id in {x.arg for x in enclosing.args.args}:
                    continue                          # a runner handing to a runner: its own callers are checked
            n += 1
            check_head(f, node.lineno, _first_program(first, consts, local_lists))
    return red, n


def check_docs(rules: dict) -> tuple[list[str], int]:
    tracked = subprocess.run(["git", "ls-files", "engine"], cwd=HERE, capture_output=True, text=True, check=True).stdout.split()
    docs = [t[len("engine/"):] for t in tracked if t.endswith(".md")]
    arm_glob = rules.get("arm_docs", "")
    allowed = rules.get("tracked_docs", [])
    red = []
    for d in docs:
        if fnmatch.fnmatch(d, arm_glob):
            text = (ENGINE / d).read_text(encoding="utf-8", errors="replace")
            if "<!-- graphy:arm " not in text:
                red.append(f"engine/{d}: an arm file without its generated region (graphy arms)")
            continue
        if any(fnmatch.fnmatch(d, pat) for pat in allowed):
            continue
        red.append(f"engine/{d}: a tracked document not declared in burden.json — a generated doc never travels in git")
    return red, len(docs)


def main() -> int:
    rules = load_rules()
    red: list[str] = []
    red += check_dependencies(ENGINE / "pyproject.toml", rules)
    wred, wnote = check_wheel(HERE / "dist", rules)
    red += wred
    hred, nh = scan_hosts(ENGINE / "graphy", rules)
    red += hred
    sred, ns = scan_subprocess(ENGINE / "graphy", rules)
    red += sred
    dred, nd = check_docs(rules)
    red += dred
    scrub = subprocess.run([sys.executable, str(HERE / "scrub.py"), "--tracked"], capture_output=True, text=True)
    if scrub.returncode != 0:
        red += [ln for ln in scrub.stdout.splitlines() if ": private token" in ln]
    scrub_note = "RED" if scrub.returncode != 0 else ("SKIPPED (no .private_key)" if scrub.stdout.startswith("SCRUB SKIPPED") else "OK")
    for r in red:
        print(f"BURDEN RED {r}")
    summary = (f"runtime deps 0 · extras {len(rules['extras'])} · {wnote} · hosts {nh} on the list of {len(rules['hosts'])} · "
               f"subprocess sites {ns} over {len(rules['subprocess_targets'])} program(s) · docs {nd} tracked · scrub {scrub_note}")
    if red:
        print(f"BURDEN RED: {len(red)} growth(s) — {summary}")
        return 3
    print(f"BURDEN OK: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
