#!/usr/bin/env python3
"""review — the CLI battery in front of the reviewer: set differences over a parse of the live tree.

    python3 review.py                 every check over this checkout; exit 0 clean · 1 findings · 2 a check could not run
    python3 review.py --diff <ref>    also severance: a symbol deleted since <ref> that a reader outside the diff still names
    python3 review.py --selftest      every check seeded red on its own fixture and green on the fixed one
    python3 review.py --json          the findings as one object

Every check answers a question a cold reviewer should never have to: does every command the docs
advertise parse against the argparse it names; does every dotted symbol the docs cite exist; is
every argparse dest read; does every path the router names sit on disk; is a template token still
unfilled; is every sha the record's newest section names an ancestor of HEAD; did a deletion leave
a caller behind; do the pages this engine emits hold their own contract. A check that cannot run
RAISES — a silent zero reads exactly like a clean tree — and every check is proven by use: the
selftest seeds a fixture that trips it and one that does not, and `gate-selftest` runs that proof
inside the flat run so a check that has stopped going red is itself a finding.

Nothing here is a guess: each finding names the file and line. stdlib only; the engine is imported
from `engine/` for its own parser and its own page check, never a third copy of either.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))


class CheckError(RuntimeError):
    """A check could not be evaluated. Never downgraded to an empty result."""


NOTES: dict[str, str] = {}      # check → what it judged on this run; a clean line names its denominator


class Finding(NamedTuple):
    check: str
    where: str          # path[:line], repo-relative
    what: str

    def line(self) -> str:
        return f"REVIEW RED {self.check:<24} {self.where}: {self.what}"


# ── the surfaces ──────────────────────────────────────────────────────────────────────────────────

# The documents a reader runs commands from and reads symbols in. RECON.md is the record: its history
# advertises flags that have since died, honestly, so only its newest section is a surface.
ADVERTISED = ("CLAUDE.md", "README.md", "engine/README.md", "engine/graphy/shell/README.md", "engine/graphy/shell/claude/GRAPHY.md",
              "engine/tenants/*/[A-Z]*.md", "engine/tenants/*/arms/*.md", ".claude/skills/*/SKILL.md")
CITING = ("CLAUDE.md", "README.md", "engine/README.md", "engine/graphy/shell/README.md", "engine/graphy/shell/claude/GRAPHY.md",
          "engine/tenants/graphy/GRAPHY.md", "engine/tenants/graphy/arms/*.md", ".claude/skills/*/SKILL.md")
ROOT_SCRIPTS = ("measure.py", "burden.py", "workflows.py", "scrub.py", "gallery.py", "review.py")
ARGPARSE_ROOTS = ("engine/graphy", ".claude/hooks") + ROOT_SCRIPTS
PAGE_GLOBS = ("engine/tenants/*/substrate/atlas/*.html", "engine/tenants/*/substrate/showcase/index.html",
              ".graphy/showcase/index.html")
TEMPLATE_TOKEN = re.compile(r"\b[A-Z][A-Z_]*_ROW(?:_\d*)?\b|\bTEMPLATE_TOKEN\b|<N>")
_SECTION = re.compile(r"^## (\d+) · ", re.M)
_HEX = re.compile(r"\b[0-9a-f]{7,40}\b")
_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_CMD_HEAD = re.compile(r"(?:^\s*|[;&|(`]\s*)(?:[\w./-]*/)?(?:graphy|(?:python3?|\$\w+)\s+-m\s+graphy)\s+(?=[a-z\[])")
_CITE = re.compile(r"`([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?:\(\))?`")
_FILE_TAIL = re.compile(r"\.(py|md|sh|json|jsonl|txt|svg|html|toml|yml|yaml|parquet|sqlite|csv|ts|js|log|tsv|whl)$")
_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(")
_QUERY = re.compile(r"""(?<!All)(?:querySelector|getElementById)\(\s*(['"])(.+?)\1\s*\)""")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise CheckError(f"git {' '.join(args)} failed in {repo}: {r.stderr.strip()[:200]}")
    return r.stdout


def _tracked(repo: Path, *patterns: str) -> list[Path]:
    out = _git(repo, "ls-files", "--", *patterns) if patterns else _git(repo, "ls-files")
    return [repo / p for p in out.split("\n") if p]


def _glob(repo: Path, patterns) -> list[Path]:
    found: list[Path] = []
    for pat in patterns:
        found += sorted(p for p in repo.glob(pat) if p.is_file())
    return found


def _rel(repo: Path, p: Path) -> str:
    return p.resolve().relative_to(repo.resolve()).as_posix()


def _last_section(text: str) -> tuple[int, str]:
    """RECON's newest section: (its first line number, its text). No section → the whole file from line 1."""
    heads = list(_SECTION.finditer(text))
    if not heads:
        return 1, text
    start = heads[-1].start()
    return text[:start].count("\n") + 1, text[start:]


def _surfaces(repo: Path, patterns, with_recon: bool) -> list[tuple[Path, int, str]]:
    """(path, first line number, text) per document — RECON contributes its newest section only."""
    out = [(p, 1, p.read_text(encoding="utf-8", errors="replace")) for p in _glob(repo, patterns)]
    recon = repo / "RECON.md"
    if with_recon and recon.is_file():
        first, text = _last_section(recon.read_text(encoding="utf-8", errors="replace"))
        out.append((recon, first, text))
    return out


def _uncommented(line: str) -> str:
    """The command before its comment: a `#` at the start or after whitespace ends it."""
    return re.split(r"(?:^|\s)#", line, 1)[0]


def _command_lines(text: str, first_line: int):
    """Every (line number, command text) a reader could run: lines of a shell fence (bash · sh ·
    console · none) less their comments; lines of a text fence only when the command opens the line
    (a text fence is a picture — its prose says `graphy` as a word); every inline code span."""
    fence = None
    for i, line in enumerate(text.split("\n"), first_line):
        s = line.strip()
        if s.startswith("```"):
            fence = None if fence is not None else s[3:].strip().split(" ")[0].lower()
            continue
        if fence is not None:
            if fence in ("", "bash", "sh", "shell", "console"):
                yield i, _uncommented(line)
            elif fence == "text" and _CMD_HEAD.match(s):
                yield i, re.split(r"\s{3,}", _uncommented(s))[0]     # a text fence's line: the command, then its description
            continue
        for m in _CODE_SPAN.finditer(line):
            yield i, m.group(1)


# ── the parser the docs advertise ─────────────────────────────────────────────────────────────────

_PARSER_CACHE: dict = {}


def _verbs() -> dict[str, set[str]]:
    """verb → every option string its subparser (and any nested one) accepts, from the engine's own
    argparse — `graphy.cli._build_parser`, never a list a hand keeps."""
    if _PARSER_CACHE:
        return _PARSER_CACHE
    from graphy import cli
    parser = cli._build_parser()
    top = {s for a in parser._actions for s in a.option_strings}

    def options(p) -> set[str]:
        opts = set(top)
        for a in p._actions:
            opts |= set(a.option_strings)
            if isinstance(a, argparse._SubParsersAction):
                for sub in a.choices.values():
                    opts |= options(sub)
        return opts

    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            for name, sub in a.choices.items():
                _PARSER_CACHE[name] = options(sub)
    if not _PARSER_CACHE:
        raise CheckError("graphy.cli._build_parser() declares no subcommands — the parse is broken, not the docs")
    return _PARSER_CACHE


def _tokens(command: str) -> list[str]:
    command = command.replace("\\|", " \u2016 ")          # a table's escaped alternative bar is neither a pipe nor a flag
    try:
        toks = shlex.split(command, comments=True)
    except ValueError:
        toks = command.split("#", 1)[0].split()
    out: list[str] = []
    for t in toks:
        if t in ("|", "||", "&&", ";", ">", ">>", "2>", "2>&1"):
            break
        t = t.strip("[]`").rstrip("\\")
        if t in ("\u2016", "…", "...", ""):
            continue
        out.append(t)
    return out


def check_advertised_argv(repo: Path) -> list[Finding]:
    """advertised-argv-parses: every `graphy <verb> …` / `python3 -m graphy <verb> …` a document
    advertises names a verb the engine's parser has, and every `--flag` on the line is one that verb
    accepts. Placeholders (`<abs>`, `[--sessions <abs>]`) are fine: the verb and the flags are the
    contract; a value is the reader's."""
    verbs = _verbs()
    found: list[Finding] = []
    seen = 0
    for path, first, text in _surfaces(repo, ADVERTISED, with_recon=True):
        rel = _rel(repo, path)
        for lineno, cmd in _command_lines(text, first):
            for m in _CMD_HEAD.finditer(cmd):
                toks = _tokens(cmd[m.end():])
                if not toks:
                    continue
                seen += 1
                for verb in re.split(r"\\?\|", toks[0]):
                    verb = verb.strip("[]")
                    if not verb or verb.startswith("<"):
                        continue
                    if verb not in verbs:
                        found.append(Finding("advertised-argv-parses", f"{rel}:{lineno}",
                                             f"`graphy {verb}` is not a verb the parser has"))
                        continue
                    for t in toks[1:]:
                        flag = t.split("=", 1)[0]
                        if not (flag.startswith("--") and len(flag) > 2 and flag[2].isalpha()) and \
                                not (re.fullmatch(r"-[A-Za-z]", flag)):
                            continue
                        if flag not in verbs[verb]:
                            found.append(Finding("advertised-argv-parses", f"{rel}:{lineno}",
                                                 f"`graphy {verb}` does not accept {flag}"))
    if not seen:
        raise CheckError("advertised-argv-parses found ZERO commands in the documents — the parse is broken, not the tree")
    NOTES["advertised-argv-parses"] = f"{seen} command(s) against {len(verbs)} verb(s)"
    return found


# ── the symbols the docs cite ─────────────────────────────────────────────────────────────────────

def _symbol_index(repo: Path) -> dict[str, set[str]]:
    """head → every dotted name the live tree defines under it: `graphy.<module>[.<Class>][.<name>]`
    for engine/graphy, `tests.<module>…` for engine/tests, `<script>.<name>` for a root script."""
    index: dict[str, set[str]] = {}

    def add(prefix: str, py: Path, dotted: str) -> None:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return
        names = index.setdefault(prefix, set())
        names.add(dotted)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(f"{dotted}.{node.name}")
                if isinstance(node, ast.ClassDef):
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            names.add(f"{dotted}.{node.name}.{sub.name}")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        names.add(f"{dotted}.{t.id}")

    for root, prefix in ((repo / "engine" / "graphy", "graphy"), (repo / "engine" / "tests", "tests")):
        if not root.is_dir():
            continue
        for py in sorted(root.rglob("*.py")):
            parts = list(py.relative_to(root).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            add(prefix, py, ".".join([prefix] + parts))
    for name in ROOT_SCRIPTS:
        py = repo / name
        if py.is_file():
            add(py.stem, py, py.stem)
    return index


def _resolve_cite(tok: str, index: dict[str, set[str]], called: bool = False) -> bool | None:
    """True resolves · False cited and absent · None not judged. A fully qualified token (`graphy.x.y`,
    `tests.x.y`) and a root script's (`measure.x`) are judged strictly. A bare module stem (`tenant.x`)
    is judged when the token is called (`x()`), when its first tail segment is a module-level name (so a
    bad deeper tail — `Store.methd` — is caught), and otherwise not at all: `tenant.data_home` or
    `query.limit` is an instance attribute or a receipt lane, not a citation of the module's namespace."""
    head = tok.split(".", 1)[0]
    if head in ("graphy", "tests"):
        return tok in index.get(head, set())
    if head in index:
        return tok in index[head]
    for prefix in ("graphy", "tests"):
        names = index.get(prefix, set())
        if f"{prefix}.{head}" in names:                 # a module of the package, cited by its bare stem
            if f"{prefix}.{tok}" in names:
                return True
            if called or f"{prefix}.{head}.{tok.split('.')[1]}" in names:
                return False
            return None
    return None


def check_cites(repo: Path) -> list[Finding]:
    """cites-nonexistent: every backticked dotted symbol a document names — `federated_store.compile_store`,
    `graphy.query`, `measure.native_boundary()`, `conftest.NO_FSYNC` — is defined in the live tree, the
    store's own input. A token whose head is no module of this tree is not judged."""
    index = _symbol_index(repo)
    if not index:
        raise CheckError("cites-nonexistent indexed ZERO modules under engine/ — the parse is broken, not the tree")
    found: list[Finding] = []
    judged = 0
    for path, first, text in _surfaces(repo, CITING, with_recon=True):
        rel = _rel(repo, path)
        for i, line in enumerate(text.split("\n"), first):
            for m in _CITE.finditer(line):
                tok = m.group(1)
                if _FILE_TAIL.search(tok):
                    continue
                verdict = _resolve_cite(tok, index, called=m.group(0).endswith("()`"))
                if verdict is None:
                    continue
                judged += 1
                if not verdict:
                    found.append(Finding("cites-nonexistent", f"{rel}:{i}", f"`{tok}` is not defined in the tree"))
    if not judged:
        raise CheckError("cites-nonexistent judged ZERO symbols — the documents or the parse are broken")
    NOTES["cites-nonexistent"] = f"{judged} symbol(s) against {sum(len(v) for v in index.values())} defined"
    return found


# ── argparse: every dest is read ──────────────────────────────────────────────────────────────────

_ARGS_ESCAPE = re.compile(r"\bvars\(|__dict__|parse_known_args|\*\*vars")


def _dest_of(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg == "dest" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    for kw in call.keywords:
        if kw.arg == "action" and isinstance(kw.value, ast.Constant) and kw.value.value in ("help", "version"):
            return None
    opts = [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    if not opts:
        return None
    for o in opts:
        if o.startswith("--"):
            return o[2:].replace("-", "_")
    first = opts[0]
    return (first.lstrip("-") or first).replace("-", "_") or None


def check_argparse_dests(repo: Path) -> list[Finding]:
    """argparse-dest-never-read: a flag the CLI accepts and then ignores — the contract on --help the
    code never honours. M = every dest a module declares; R = every attribute or string the module
    reads; the finding is M − R. A module that hands the namespace on whole (vars · __dict__ ·
    parse_known_args) is not judged."""
    found: list[Finding] = []
    scanned = 0
    files: list[Path] = []
    for root in ARGPARSE_ROOTS:
        p = repo / root
        if p.is_dir():
            files += sorted(f for f in p.rglob("*.py") if "/tests/" not in f"/{f.relative_to(repo).as_posix()}"
                            and not f.name.startswith("test_"))
        elif p.is_file():
            files.append(p)
    for path in files:
        rel = _rel(repo, path)
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            found.append(Finding("argparse-dest-never-read", rel, f"module does not parse: {type(exc).__name__}"))
            continue
        dests: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
                d = _dest_of(node)
                if d and d.isidentifier():
                    dests.setdefault(d, node.lineno)
        if not dests:
            continue
        scanned += 1
        if _ARGS_ESCAPE.search(src):
            continue
        read = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        read |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for d, line in sorted(dests.items(), key=lambda kv: kv[1]):
            if d not in read:
                found.append(Finding("argparse-dest-never-read", f"{rel}:{line}", f"add_argument dest {d!r} is never read"))
    if not scanned:
        raise CheckError("argparse-dest-never-read found ZERO modules declaring arguments — the parse is broken, not the tree")
    NOTES["argparse-dest-never-read"] = f"{scanned} module(s) declaring arguments"
    return found


# ── the router's paths ────────────────────────────────────────────────────────────────────────────

def _fence_after(text: str, heading: str) -> tuple[int, list[str]]:
    """The first fenced block after a `## heading`: (first line number of its body, its lines)."""
    lines = text.split("\n")
    at = next((i for i, l in enumerate(lines) if l.strip() == f"## {heading}" or l.strip().startswith(f"## {heading} ")), None)
    if at is None:
        raise CheckError(f"CLAUDE.md has no `## {heading}` section — the router's paths cannot be read")
    open_at = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("```")), None)
    if open_at is None:
        raise CheckError(f"CLAUDE.md `## {heading}` has no fenced block under it")
    body: list[str] = []
    for i in range(open_at + 1, len(lines)):
        if lines[i].startswith("```"):
            break
        body.append(lines[i])
    return open_at + 2, body


def _folder_entries(first: int, body: list[str], base: str = "") -> list[tuple[int, str]]:
    """(line, path) for every entry of a folder fence: the first field of each line (split on two or
    more spaces), a ` · ` list expanded, an indented line a child of the nearest less-indented dir."""
    out: list[tuple[int, str]] = []
    stack: list[tuple[int, str]] = []          # (indent, dir prefix)
    for i, line in enumerate(body, first):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        field = re.split(r"\s{2,}", line.strip(), 1)[0]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        prefix = stack[-1][1] if stack else base
        names = [n.strip().split(" ")[0] for n in field.split(" · ")]
        for k, n in enumerate(names):
            if not n or (k and not ("." in n or "/" in n)):
                continue                        # `roster · census · classify` is a symbol list, not a path list
            out.append((i, prefix + n))
        if len(names) == 1 and names[0].endswith("/"):
            stack.append((indent, prefix + names[0]))
    return out


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def _ignored(repo: Path, rel: str) -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=repo, capture_output=True)
    return r.returncode == 0


def check_paths(repo: Path) -> list[Finding]:
    """path-literal-names-nothing: every path CLAUDE.md's THE FOLDER and THE ENGINE MAP name is on
    disk or gitignored by name (a rebuilt product is absent on a fresh box, honestly); every glob
    burden.json's tracked_docs and arm_docs carry matches a file; every hook command in
    .claude/settings.json and .mcp.json names a file."""
    claude = repo / "CLAUDE.md"
    if not claude.is_file():
        raise CheckError("CLAUDE.md is absent — the router's paths cannot be read")
    text = claude.read_text(encoding="utf-8", errors="replace")
    found: list[Finding] = []
    entries: list[tuple[int, str]] = []
    first, body = _fence_after(text, "THE FOLDER")
    entries += _folder_entries(first, body)
    try:
        first, body = _fence_after(text, "THE ENGINE MAP")
        entries += _folder_entries(first, body, base="engine/graphy/")
    except CheckError:
        pass                                    # a router without an engine map names no engine paths
    if not entries:
        raise CheckError("CLAUDE.md THE FOLDER names ZERO paths — the parse is broken, not the tree")
    NOTES["path-literal-names-nothing"] = f"{len(entries)} path(s) the router names"
    for line, rel in entries:
        if (repo / rel).exists() or _ignored(repo, rel):
            continue
        found.append(Finding("path-literal-names-nothing", f"CLAUDE.md:{line}", f"{rel} is not on disk and not gitignored"))
    burden = repo / "burden.json"
    if burden.is_file():
        rules = json.loads(burden.read_text(encoding="utf-8"))
        docs = [p.relative_to(repo / "engine").as_posix() for p in (repo / "engine").rglob("*.md")]
        for pat in list(rules.get("tracked_docs", [])) + ([rules["arm_docs"]] if rules.get("arm_docs") else []):
            if not any(fnmatch.fnmatch(d, pat) for d in docs):
                found.append(Finding("path-literal-names-nothing", "burden.json", f"the doc pattern {pat!r} matches no file under engine/"))
    for name in (".claude/settings.json", ".mcp.json"):
        cfg = repo / name
        if not cfg.is_file():
            continue
        try:
            doc = json.loads(cfg.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CheckError(f"{name} is not JSON: {exc}") from exc
        for value in _strings(doc):
            for m in re.finditer(r"\$\{?CLAUDE_PROJECT_DIR\}?/([^\s\"']+)", value):
                rel = m.group(1)
                if not (repo / rel).exists():
                    found.append(Finding("path-literal-names-nothing", name, f"{rel} is not on disk"))
    return found


# ── the template token ────────────────────────────────────────────────────────────────────────────

def _docs(repo: Path) -> list[Path]:
    return [p for p in _tracked(repo, "*.md", "**/*.md")
            if not _rel(repo, p).startswith(("staging/", ".claude/skills/"))]


def check_template_tokens(repo: Path) -> list[Finding]:
    """template-token: a row marker a section template left unfilled (`REVIEW_ROW_62`, `<N>`) in a
    tracked document — the class that reached main twice (RECON §92, §97)."""
    docs = _docs(repo)
    if not docs:
        raise CheckError("template-token found ZERO tracked documents — the scan is broken, not the tree")
    found: list[Finding] = []
    NOTES["template-token"] = f"{len(docs)} tracked document(s)"
    for p in docs:
        rel = _rel(repo, p)
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            m = TEMPLATE_TOKEN.search(line)
            if m:
                found.append(Finding("template-token", f"{rel}:{i}", f"unfilled template token {m.group(0)!r}"))
    return found


# ── the shas the record names ─────────────────────────────────────────────────────────────────────

def check_sha_liveness(repo: Path) -> list[Finding]:
    """sha-liveness: every commit RECON's newest section names is an ancestor of HEAD — a token git
    resolves to a commit must be reachable; a token after the word `commit` that git cannot resolve
    is a finding too. A store generation or a digest is hex as well; git says which is which."""
    recon = repo / "RECON.md"
    if not recon.is_file():
        raise CheckError("RECON.md is absent — no record to check the shas of")
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=repo, capture_output=True, text=True)
    if shallow.stdout.strip() == "true":
        NOTES["sha-liveness"] = "SKIPPED — a shallow clone cannot answer ancestry (fetch-depth: 0 where it must)"
        return []
    first, text = _last_section(recon.read_text(encoding="utf-8", errors="replace"))
    found: list[Finding] = []
    seen: set[str] = set()
    for i, line in enumerate(text.split("\n"), first):
        for m in _HEX.finditer(line):
            tok = m.group(0)
            if tok.isdigit() or tok in seen:
                continue
            seen.add(tok)
            kind = subprocess.run(["git", "cat-file", "-t", tok], cwd=repo, capture_output=True, text=True)
            if kind.returncode == 0 and kind.stdout.strip() == "commit":
                anc = subprocess.run(["git", "merge-base", "--is-ancestor", tok, "HEAD"], cwd=repo, capture_output=True)
                if anc.returncode != 0:
                    found.append(Finding("sha-liveness", f"RECON.md:{i}", f"commit {tok} is not an ancestor of HEAD"))
            elif re.search(r"\bcommit\s+`?" + re.escape(tok), line):
                found.append(Finding("sha-liveness", f"RECON.md:{i}", f"commit {tok} does not resolve in this repository"))
    NOTES["sha-liveness"] = f"{len(seen)} hex token(s) in RECON's newest section"
    return found


# ── severance: a deletion that left a reader behind ───────────────────────────────────────────────

def _defs(src: str) -> set[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
            if isinstance(node, ast.ClassDef):
                out |= {f"{node.name}.{s.name}" for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return out


def _module_of(rel: str) -> str | None:
    p = Path(rel)
    if rel.startswith("engine/graphy/"):
        parts = list(p.relative_to("engine/graphy").with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(["graphy"] + parts)
    if "/" not in rel and rel.endswith(".py"):
        return p.stem
    return None


def _root_name(node) -> str | None:
    """The Name a receiver chain roots at: `a.K().m` → a, `K.m` → K, `x[0].f` → x."""
    while True:
        if isinstance(node, ast.Attribute):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Subscript):
            node = node.value
        else:
            return node.id if isinstance(node, ast.Name) else None


def _names_symbol(tree: ast.Module, module: str, qual: str) -> bool:
    """Does a Python file reach `module.qual`: it binds the module or the symbol by an import and uses
    the name THROUGH that binding — `a.f`, `a.K().m`, `K.m` after `from graphy.a import K` — never a
    bare attribute match (`con.close()` is sqlite3's, whatever `K.close` was)."""
    parts = qual.split(".")
    last, head = parts[-1], parts[0]
    stem = module.split(".")[-1]
    parent = module.rsplit(".", 1)[0] if "." in module else ""
    mod_aliases: set[str] = set()          # local names a chain to the module roots at
    sym_aliases: set[str] = set()          # local names bound to the symbol's head
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == module or a.name.startswith(module + "."):
                    mod_aliases.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            from_module = mod == module or (node.level and mod == stem)
            from_parent = mod == parent or (node.level and mod == "")
            for a in node.names:
                if from_module and a.name == head:
                    sym_aliases.add(a.asname or head)
                elif from_module and a.name == "*":
                    sym_aliases.add(head)
                elif from_parent and a.name == stem:
                    mod_aliases.add(a.asname or stem)
    if not (mod_aliases or sym_aliases):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == last:
            root = _root_name(node.value)
            if root in mod_aliases and last != head and _chain_has(node.value, head, mod_aliases):
                return True
            if root in mod_aliases and last == head:
                return True
            if root in sym_aliases and last != head:
                return True
        elif isinstance(node, ast.Name) and node.id == last and last == head and last in sym_aliases:
            return True
    return False


def _chain_has(node, head: str, mod_aliases: set[str]) -> bool:
    """For `a.K().m` with qual `K.m`: the chain below the attribute carries `K` off the module alias."""
    while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript)):
        if isinstance(node, ast.Attribute) and node.attr == head and _root_name(node.value) in mod_aliases:
            return True
        node = node.func if isinstance(node, ast.Call) else node.value
    return False


def _store_callers(repo: Path, module: str, qual: str) -> list[tuple[str, str]]:
    """(caller id, caller file) for every edge into `module.qual` in the graphy tenant's compiled
    store when the box has one; an absent store answers nothing and the text walk stands alone."""
    sub = repo / "engine" / "tenants" / "graphy" / "substrate"
    dbs = sorted(sub.glob(".mesh_store_*.sqlite")) if sub.is_dir() else []
    if not dbs:
        return []
    out: list[tuple[str, str]] = []
    con = sqlite3.connect(f"file:{dbs[-1]}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select e.src, n.file from edges e join nodes d on d.id = e.dst left join nodes n on n.id = e.src "
            "where d.dotted = ? and e.rel != 'contains'", (f"{module}.{qual}",)).fetchall()      # a read, not the owner
    finally:
        con.close()
    for src, file in rows:
        out.append((src, file or ""))
    return out


def diff_label(base: str) -> str:
    return base if len(base) <= 12 else base[:12]


def check_severance(repo: Path, base: str) -> list[Finding]:
    """severance: a function, class or method deleted or renamed since `base` that a file outside
    the diff still names — the reverse-callers class, mechanical. Readers: every tracked Python file
    outside the diff that imports the module and uses the name (AST), plus every caller the graphy
    tenant's store holds an edge from, confirmed against the live file."""
    status = _git(repo, "diff", "--name-status", "--no-renames", base, "--", "*.py")     # a move is a delete and an add
    changed: dict[str, str] = {}
    for line in status.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        code, path = parts[0][0], parts[-1]
        changed[path] = code
    deleted: list[tuple[str, str, str]] = []          # (rel, module, qual)
    for rel, code in sorted(changed.items()):
        module = _module_of(rel)
        if module is None:
            continue
        before = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=repo, capture_output=True, text=True)
        if before.returncode != 0:
            continue                                  # added since base: nothing to sever
        now = (repo / rel).read_text(encoding="utf-8", errors="replace") if (repo / rel).is_file() else ""
        for qual in sorted(_defs(before.stdout) - _defs(now)):
            deleted.append((rel, module, qual))
    found: list[Finding] = []
    NOTES["severance"] = f"{len(deleted)} symbol(s) deleted since {diff_label(base)} across {len(changed)} changed file(s)"
    if not deleted:
        return found
    sources = {p: p.read_text(encoding="utf-8", errors="replace")
               for p in _tracked(repo, "*.py", "**/*.py") if _rel(repo, p) not in changed and p.is_file()}
    trees: dict[Path, ast.Module | None] = {}                  # each reader parsed once, across every symbol
    for rel, module, qual in deleted:
        named: dict[str, str] = {}
        last = qual.split(".")[-1]
        for p, src in sources.items():
            if not re.search(r"\b" + re.escape(last) + r"\b", src):
                continue                                       # the bare name is a floor: no name, no read
            if p not in trees:
                try:
                    trees[p] = ast.parse(src)
                except SyntaxError:
                    trees[p] = None
            if trees[p] is not None and _names_symbol(trees[p], module, qual):
                named[_rel(repo, p)] = "imports the module and uses the name"
        for src, file in _store_callers(repo, module, qual):
            f = repo / "engine" / file if file else None
            if f is None or not f.is_file() or _rel(repo, f) in changed or _rel(repo, f) in named:
                continue
            if re.search(r"\b" + re.escape(qual.split(".")[-1]) + r"\b", f.read_text(encoding="utf-8", errors="replace")):
                named[_rel(repo, f)] = f"the store holds an edge from {src}"
        for reader, why in sorted(named.items()):
            found.append(Finding("severance", reader, f"still names {module}.{qual}, deleted from {rel} since {base} ({why})"))
    return found


# ── the pages this engine emits ───────────────────────────────────────────────────────────────────

def _pages(repo: Path) -> list[Path]:
    return sorted(set(_tracked(repo, "*.html", "**/*.html")) | set(_glob(repo, PAGE_GLOBS)))


def _selector_present(sel: str, html: str) -> bool:
    sel = sel.strip()
    if "," in sel:
        return all(_selector_present(part, html) for part in sel.split(","))
    m = re.fullmatch(r"(\w+)\.([\w-]+)", sel)
    if m:                                        # `g.node`: the tag carrying the class
        return re.search(r"<" + m.group(1) + r"\b[^>]*\bclass=\"[^\"]*\b" + re.escape(m.group(2)) + r"\b", html) is not None
    if sel.startswith("#"):
        return re.search(r'\bid="' + re.escape(sel[1:]) + '"', html) is not None
    if sel.startswith("."):
        return re.search(r'\bclass="[^"]*\b' + re.escape(sel[1:]) + r'\b[^"]*"', html) is not None
    m = re.fullmatch(r"(\w+)\[([\w-]+)(?:=\"([^\"]*)\")?\]", sel)
    if m:
        tag, attr, val = m.groups()
        pat = r"<" + tag + r"\b[^>]*\b" + re.escape(attr) + (r'="' + re.escape(val) + '"' if val is not None else "")
        return re.search(pat, html) is not None
    return re.search(r"<" + re.escape(sel) + r"\b", html) is not None      # a bare tag


def page_findings(path: Path, rel: str) -> list[Finding]:
    from graphy import sugiyama
    found = [Finding("visual", rel, r) for r in sugiyama.check_artifact(path)]
    html = path.read_text(encoding="utf-8", errors="replace")
    for sm in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S | re.I):
        base = html[:sm.start(1)].count("\n")
        for i, line in enumerate(sm.group(1).split("\n"), base + 1):
            outside = re.sub(r"--[\w-]+\s*:\s*[^;}]+", "", line)     # a token declaration is the one place a colour lives
            if not _COLOR.search(outside):
                continue
            found.append(Finding("visual", f"{rel}:{i}", f"colour literal outside the token block: `{line.strip()[:60]}`"))
    for sm in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S | re.I):
        for q in _QUERY.finditer(sm.group(1)):
            sel = q.group(2)
            if q.group(0).startswith("getElementById"):
                sel = "#" + sel
            if not _selector_present(sel, html):
                found.append(Finding("visual", rel, f"the script hooks {sel!r} and the page has no such element"))
    return found


def check_pages(repo: Path) -> tuple[list[Finding], int]:
    """visual: every page this engine emitted on this box — the atlas pages, a showcase's index —
    holds `sugiyama.check_artifact`'s contract, keeps every colour literal inside the token block
    (both themes are the token block, so a literal outside it paints one theme and lies in the
    other), and binds every element its script hooks. No browser. Zero pages is a fresh box, said
    by name, never a clean count."""
    pages = _pages(repo)
    found: list[Finding] = []
    for p in pages:
        found += page_findings(p, _rel(repo, p))
    return found, len(pages)


# ── the battery ───────────────────────────────────────────────────────────────────────────────────

CHECKS = {
    "advertised-argv-parses": check_advertised_argv,
    "cites-nonexistent": check_cites,
    "argparse-dest-never-read": check_argparse_dests,
    "path-literal-names-nothing": check_paths,
    "template-token": check_template_tokens,
    "sha-liveness": check_sha_liveness,
}


def _seed(files: dict[str, str]) -> Path:
    """A fixture repository: the files, committed once, so every check reads it the way it reads this one."""
    root = Path(tempfile.mkdtemp(prefix="review-fixture-"))
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "fixture"]):
        _fixture_git(root, cmd)
    return root


def _fixture_env(root: Path) -> dict:
    """A fixture's git never reads this box's config: HOME is the fixture, the identity is literal."""
    return {**os.environ, "HOME": str(root), "GIT_CONFIG_GLOBAL": str(root / ".gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "review", "GIT_AUTHOR_EMAIL": "review@fixture",
            "GIT_COMMITTER_NAME": "review", "GIT_COMMITTER_EMAIL": "review@fixture"}


def _fixture_git(root: Path, cmd: list[str]) -> str:
    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, env=_fixture_env(root))
    if r.returncode != 0:
        raise CheckError(f"the fixture's `{' '.join(cmd)}` failed in {root}: {r.stderr.strip()[:200]}")
    return r.stdout


_PAGE_OK = """<!DOCTYPE html><html><head><style>
    :root { --paper: #FAFAF7; --ink: #1F2933; }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --paper: #1E2028; --ink: #E0E0E0; } }
    :root[data-theme="dark"] { --paper: #1E2028; --ink: #E0E0E0; }
    body { background: var(--paper); color: var(--ink); }
    .node rect { fill: var(--paper); }
</style></head><body><svg viewBox="0 0 100 100"><g class="node"><rect x="1" y="1" width="10" height="10"/></g></svg>{script}</body></html>
"""


def fixtures() -> dict[str, tuple[dict[str, str], dict[str, str]]]:
    """check → (a repository that trips it, the fixed one)."""
    return {
        "advertised-argv-parses": (
            {"README.md": "```bash\ngraphy walk --tenant <descriptor> --tenant-id <name> --seed <id> --no-such-flag\n```\n"},
            {"README.md": "```bash\ngraphy walk --tenant <descriptor> --tenant-id <name> --seed <id> --target <id>\n```\n"
                          "and inline `python3 -m graphy check --tenant t.json --tenant-id x` too\n"}),
        "cites-nonexistent": (
            {"engine/graphy/m.py": "def f():\n    pass\n", "CLAUDE.md": "the walk is `m.g()` and `graphy.m.h` and `m.f.nope`\n"},
            {"engine/graphy/m.py": "def f():\n    pass\n", "CLAUDE.md": "the walk is `m.f` and `graphy.m.f` and `os.fsync` and `m.attr_of_an_instance`\n"}),
        "argparse-dest-never-read": (
            {"engine/graphy/x.py": "import argparse\np = argparse.ArgumentParser()\np.add_argument('--depth')\np.add_argument('--out')\n"
                                   "a = p.parse_args()\nprint(a.out)\n"},
            {"engine/graphy/x.py": "import argparse\np = argparse.ArgumentParser()\np.add_argument('--depth')\np.add_argument('--out')\n"
                                   "a = p.parse_args()\nprint(a.out, a.depth)\n"}),
        "path-literal-names-nothing": (
            {"CLAUDE.md": "## THE FOLDER\n\n```text\nreal.py      here\nghost.py     gone\nengine/      the product\n  graphy/    the package\n```\n",
             "real.py": "", "engine/graphy/__init__.py": ""},
            {"CLAUDE.md": "## THE FOLDER\n\n```text\nreal.py · other.sh   here\n.venv/       gitignored\nengine/      the product\n  graphy/    the package\n```\n",
             "real.py": "", "other.sh": "", ".gitignore": ".venv/\n", "engine/graphy/__init__.py": ""}),
        "template-token": (
            {"RECON.md": "| the review | REVIEW_ROW_62 |\n"},
            {"RECON.md": "| the review | four findings, every one fixed |\n"}),
        "sha-liveness": (
            {"RECON.md": "## 1 · x (2026-01-01)\n\nlanded at commit deadbeef0\n"},
            {"RECON.md": "## 1 · x (2026-01-01)\n\nthe store generation 24eecb50371f9e1d is not a commit\n"}),
        "severance": (
            {"engine/graphy/a.py": "def f():\n    pass\n\ndef g():\n    pass\n", "engine/graphy/b.py": "from graphy.a import f\nf()\n",
             "engine/graphy/c.py": "from graphy import a\na.f()\nimport sqlite3\nsqlite3.connect(':memory:').g()\n"},
            {"engine/graphy/a.py": "def f():\n    pass\n\ndef g():\n    pass\n", "engine/graphy/b.py": "from graphy.a import f\nf()\n",
             "engine/graphy/c.py": "from graphy import a\na.f()\nimport sqlite3\nsqlite3.connect(':memory:').g()\n"}),
        "visual": (
            {"engine/tenants/t/substrate/atlas/X.html": _PAGE_OK.replace(".node rect { fill: var(--paper); }", ".node rect { fill: #FF0000; }")
                                                       .replace("{script}", '<script>document.querySelector("#missing");</script>')},
            {"engine/tenants/t/substrate/atlas/X.html": _PAGE_OK.replace("{script}", "")}),
    }


def _run_fixture(check: str, root: Path, red: bool) -> list[Finding]:
    if check == "severance":
        a = root / "engine" / "graphy" / "a.py"
        # red: f is deleted and b.py and c.py still name it through their imports (two readers);
        # green: g is deleted — c.py imports the module and calls sqlite3's own `.g()`, which is not a read of graphy.a.g
        a.write_text("def g():\n    pass\n" if red else "def f():\n    pass\n", encoding="utf-8")
        return check_severance(root, "HEAD")
    if check == "visual":
        found, n = check_pages(root)
        if n == 0:
            raise CheckError("the visual fixture holds no page — the glob is broken")
        return found
    if check == "sha-liveness" and red:
        # a commit that resolves and is not an ancestor: an orphan branch, then back to the first
        branch = _fixture_git(root, ["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        _fixture_git(root, ["git", "checkout", "-q", "--orphan", "side"])
        _fixture_git(root, ["git", "commit", "-q", "--allow-empty", "-m", "side"])
        side = _fixture_git(root, ["git", "rev-parse", "HEAD"]).strip()
        _fixture_git(root, ["git", "checkout", "-q", branch])
        recon = root / "RECON.md"
        recon.write_text(recon.read_text(encoding="utf-8") + f"and the sibling at {side[:12]}\n", encoding="utf-8")
    return CHECKS[check](root)


def selftest() -> list[tuple[str, int, int]]:
    """(check, findings on the red fixture, findings on the green one) for every check with a fixture.
    A check is proven when the red count is ≥ 1 and the green count is 0."""
    out: list[tuple[str, int, int]] = []
    live = dict(NOTES)                          # the fixtures write their own denominators; the live run keeps its
    for check, (red_files, green_files) in fixtures().items():
        counts = []
        for files, red in ((red_files, True), (green_files, False)):
            root = _seed(files)
            try:
                counts.append(len(_run_fixture(check, root, red)))
            finally:
                shutil.rmtree(root, ignore_errors=True)
        out.append((check, counts[0], counts[1]))
    NOTES.clear()
    NOTES.update(live)
    return out


def check_gate_selftest(repo: Path) -> list[Finding]:
    """gate-selftest: every check still goes red on its seeded fixture and green on the fixed one —
    `never fired` and `cannot fire` are indistinguishable without a positive control."""
    found: list[Finding] = []
    for check, red, green in selftest():
        if red < 1:
            found.append(Finding("gate-selftest", "review.py", f"{check} no longer goes red on its fixture"))
        if green:
            found.append(Finding("gate-selftest", "review.py", f"{check} reports {green} finding(s) on its fixed fixture"))
    return found


def run(repo: Path, diff: str | None) -> tuple[dict[str, list[Finding]], dict[str, str]]:
    results: dict[str, list[Finding]] = {}
    notes: dict[str, str] = {}
    NOTES.clear()
    for name, fn in CHECKS.items():
        results[name] = fn(repo)
    if diff:
        results["severance"] = check_severance(repo, diff)
    else:
        notes["severance"] = "not run (no --diff <ref>)"
    found, n = check_pages(repo)
    results["visual"] = found
    NOTES["visual"] = f"{n} page(s)" if n else "SKIPPED — no page emitted on this box (an atlas or a showcase writes one)"
    results["gate-selftest"] = check_gate_selftest(repo)
    NOTES["gate-selftest"] = f"{len(fixtures())} check(s) seeded red and green"
    notes.update({k: v for k, v in NOTES.items() if k in results})
    return results, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="review", description="the CLI battery in front of the reviewer — set differences over a parse of the live tree")
    ap.add_argument("--diff", metavar="REF", default=None, help="also run severance against this git ref")
    ap.add_argument("--selftest", action="store_true", help="seed every check red on its fixture and green on the fixed one")
    ap.add_argument("--json", action="store_true", help="the findings as one object")
    ap.add_argument("--repo", default=str(HERE), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        if args.selftest:
            rows = selftest()
            bad = [r for r in rows if r[1] < 1 or r[2]]
            for check, red, green in rows:
                print(f"{'FAIL' if red < 1 or green else ' ok '} {check:<28} red={red} green={green}")
            if bad:
                print(f"REVIEW SELFTEST FAILED: {len(bad)} of {len(rows)} check(s) — a check that cannot go red is decoration")
                return 1
            print(f"REVIEW SELFTEST OK: {len(rows)} check(s), each red on its fixture")
            return 0
        results, notes = run(repo, args.diff)
    except CheckError as exc:
        print(f"REVIEW REFUSED: {exc}", file=sys.stderr)
        return 2
    total = sum(len(v) for v in results.values())
    if args.json:
        print(json.dumps({"findings": total, "checks": {k: [f._asdict() for f in v] for k, v in results.items()}, "notes": notes}, indent=1))
    else:
        for name, found in results.items():
            note = f"  ({notes[name]})" if name in notes else ""
            print(f"{'FAIL' if found else ' ok '} {name:<28} {len(found)}{note}")
            for f in found:
                print("  " + f.line())
        if "severance" not in results:
            print(f" --  {'severance':<28} {notes['severance']}")
    ran = len(results)
    if total:
        print(f"REVIEW FINDINGS: {ran} check(s) · {total} finding(s)")
        return 1
    print(f"REVIEW OK: {ran} check(s) · 0 finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
