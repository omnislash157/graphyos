#!/usr/bin/env python3
"""review — the CLI battery in front of the reviewer: set differences over a parse of the live tree.

    python3 review.py                 every check over this checkout; exit 0 clean · 1 findings · 2 a check could not run
    python3 review.py --diff <ref>    also severance: a symbol deleted since <ref> that a reader outside the diff still names
    python3 review.py --selftest      every check seeded red on its own fixture and green on the fixed one
    python3 review.py --json          the findings as one object

Every check answers a question a cold reviewer should never have to: does every command the docs
advertise parse against the argparse it names; does every dotted symbol the docs cite exist; is
every argparse dest read; does every path the router names sit on disk; is a template token still
unfilled; is every sha the record's newest section names an ancestor of HEAD; does a stored answer's key
cover every module the code that computed it imports; did a deletion leave
a caller behind; does git check out every tracked byte as it holds it, on a client that would
rewrite line endings; do the pages this engine emits hold their own contract. A check that cannot run
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
    # the hooks are cited by RECON the same way (`march.gates_of`); a row that named a deleted `march.gate_of`
    # read clean because nothing indexed them (graphyos #116 round 3)
    for py in sorted((repo / ".claude" / "hooks").glob("*.py")):
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


REVIEW_ROW = re.compile(r"^\|\s*review round (\d+)\b")


def check_review_row_order(repo: Path) -> list[Finding]:
    """review-row-order: inside one RECON section, a `| review round N |` row never follows a row of a
    round at or past N. A section's rounds are its own rung's ledger, written in order; a row out of order
    was written into the wrong section — graphyos #127 review round 2, where a text replace matched the
    first identical `the gate` row and landed round 1 of #127 under #132's round 2 SHIP."""
    recon = repo / "RECON.md"
    if not recon.is_file():
        raise CheckError("RECON.md is absent — no record to read the review rows of")
    found: list[Finding] = []
    sections = rows = 0
    last = 0
    for i, line in enumerate(recon.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
        if re.match(r"^## \d+ ", line):
            sections, last = sections + 1, 0
            continue
        m = REVIEW_ROW.match(line)
        if m:
            rows += 1
            n = int(m.group(1))
            if n <= last:
                found.append(Finding("review-row-order", f"RECON.md:{i}",
                                     f"review round {n} follows round {last} in its section — a row written into the wrong section"))
            last = max(last, n)
    if not sections:
        raise CheckError("review-row-order found ZERO sections in RECON.md — the parse is broken, not the record")
    NOTES["review-row-order"] = f"{rows} review row(s) over {sections} section(s)"
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

    def walk(body) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(node.name)
                if isinstance(node, ast.ClassDef):
                    out.update(f"{node.name}.{s.name}" for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)))
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                # a def under a module-level try/if/with is still a module attribute a reader can name
                # (graphyos #122 round 1: `_NoFcntl` under `except ImportError:` deleted, severance said 0)
                for attr in ("body", "orelse", "finalbody"):
                    walk(getattr(node, attr, []) or [])
                for h in getattr(node, "handlers", []) or []:
                    walk(h.body)

    walk(tree.body)
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



# ── a stored answer's key covers the code that computed it ───────────────────────────────────────

def _module_path(repo: Path, dotted: str) -> Path | None:
    rel = dotted.replace(".", "/")
    for p in (repo / "engine" / f"{rel}.py", repo / "engine" / rel / "__init__.py"):
        if p.is_file():
            return p
    return None


def _literal_tuple(tree: ast.Module, name: str) -> tuple[int, list[str]] | None:
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets) and node.value is not None:
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return node.lineno, []
            return node.lineno, [str(v) for v in value]
    return None


def _literal_dict(tree: ast.Module, name: str) -> tuple[int, dict] | None:
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets) and node.value is not None:
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return node.lineno, {}
            return node.lineno, dict(value) if isinstance(value, dict) else {}
    return None


def _imports(repo: Path, dotted: str) -> set[str]:
    """Every graphy module a module can import: every Import and ImportFrom anywhere in it — top level, a
    function body, an `if`, a `try`'s handlers — with relative imports resolved against its package, and each
    parent package's `__init__` (importing `graphy.a.b` runs `graphy/__init__.py`). A lazy import runs when its
    function runs, and the door functions are where this codebase imports (graphyos #111 review round 5)."""
    p = _module_path(repo, dotted)
    if p is None:
        return set()
    pkg = dotted if p.name == "__init__.py" else dotted.rpartition(".")[0]
    out: set[str] = set()
    for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")[: len(pkg.split(".")) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            if mod.split(".")[0] != "graphy":
                continue
            out |= {c for c in {mod, *(f"{mod}.{a.name}" for a in node.names)} if _module_path(repo, c)}
        elif isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.split(".")[0] == "graphy" and _module_path(repo, a.name)}
        elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str) and node.args[0].value.split(".")[0] == "graphy"
              and ((isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                   or (isinstance(node.func, ast.Name) and node.func.id in ("import_module", "__import__")))):
            if _module_path(repo, node.args[0].value):     # importlib.import_module("graphy.x") · __import__("graphy.x")
                out.add(node.args[0].value)
    parts = dotted.split(".")
    out |= {".".join(parts[:k]) for k in range(1, len(parts)) if _module_path(repo, ".".join(parts[:k]))}
    return out - {dotted}


_PINNED = re.compile(r"^SOURCE_SHA\s*=\s*source_sha\(__file__\)", re.M)


def check_cache_key_closure(repo: Path) -> list[Finding]:
    """cache-key-closure: a module that keys stored answers by the code that computed them declares
    `RULE_ROOTS` (where the answer is computed), `RULE_MODULES` (what its key hashes) and `RULE_EXEMPT`
    (module → why it bears no rule; its imports are not followed). Every module the roots can import, lazily
    or not, is in exactly one of the two; neither names a module outside the closure; every key member pins
    `SOURCE_SHA = source_sha(__file__)` at import; every exemption carries its reason. graphyos #111 was
    REVISED for a key that described less than its inputs through four holes — the relations, the engine's
    rules, the disk read after import, and a lazy import this check first could not see."""
    declarers = []
    for p in sorted((repo / "engine" / "graphy").rglob("*.py")) if (repo / "engine" / "graphy").is_dir() else []:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        roots, modules = _literal_tuple(tree, "RULE_ROOTS"), _literal_tuple(tree, "RULE_MODULES")
        if roots or modules:
            declarers.append((p, roots, modules, _literal_dict(tree, "RULE_EXEMPT")))
    if not declarers:
        raise CheckError("cache-key-closure found ZERO modules declaring RULE_ROOTS / RULE_MODULES — "
                         "the stored doors key by nothing, or the scan is broken")
    found: list[Finding] = []
    judged = 0
    for p, roots, modules, exempt in declarers:
        rel = _rel(repo, p)
        if not roots or not modules or not roots[1] or not modules[1]:
            found.append(Finding("cache-key-closure", rel, "declares one of RULE_ROOTS / RULE_MODULES without the other, "
                                 "or not as a literal tuple of dotted module names"))
            continue
        ex_line, ex = exempt if exempt else (modules[0], {})
        for m, why in sorted(ex.items()):
            if not isinstance(why, str) or not why.strip():
                found.append(Finding("cache-key-closure", f"{rel}:{ex_line}", f"RULE_EXEMPT[{m!r}] carries no reason"))
        declared = set(modules[1])
        for m in sorted(declared & set(ex)):
            found.append(Finding("cache-key-closure", f"{rel}:{ex_line}", f"{m} is both keyed and exempt"))
        seen: set[str] = set()
        todo = list(roots[1])
        while todo:
            m = todo.pop()
            if m in seen:
                continue
            seen.add(m)
            if _module_path(repo, m) is None:
                found.append(Finding("cache-key-closure", f"{rel}:{roots[0]}", f"{m} is in the closure and names no module"))
                continue
            if m in ex:
                continue                       # declared rule-free: its own imports are not the key's
            todo += sorted(_imports(repo, m) - seen)
        judged += len(seen)
        for m in sorted(seen - declared - set(ex)):
            found.append(Finding("cache-key-closure", f"{rel}:{modules[0]}",
                                 f"{m} is importable from the rule roots and neither in RULE_MODULES nor RULE_EXEMPT — "
                                 f"an edit to it would serve a stored answer the new code never computed"))
        for m in sorted((declared | set(ex)) - seen):
            found.append(Finding("cache-key-closure", f"{rel}:{modules[0]}",
                                 f"{m} is declared and outside the roots' import closure — a stale declaration"))
        for m in sorted(declared & seen):
            mp = _module_path(repo, m)
            if mp is not None and not _PINNED.search(mp.read_text(encoding="utf-8")):
                found.append(Finding("cache-key-closure", _rel(repo, mp),
                                     "does not pin `SOURCE_SHA = source_sha(__file__)` at import — "
                                     "the key would read the disk, not the code this process runs"))
    NOTES["cache-key-closure"] = f"{len(declarers)} declaring module(s), {judged} module(s) in the closure"
    return found



def _catches(handler: ast.ExceptHandler) -> set[str]:
    t = handler.type
    if t is None:
        return {"*"}
    names = t.elts if isinstance(t, ast.Tuple) else [t]
    out = set()
    for n in names:
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add("." + n.attr)
    return out


def _guard_holds(tr: ast.Try) -> bool:
    """A try protects a cache write when its handlers that do NOT re-raise catch everything (bare ·
    Exception · BaseException), or catch OSError and a driver's base `.Error` — exactly `Error`: a
    `json.JSONDecodeError` beside OSError leaves duckdb's IOException (disk full) through."""
    caught: set[str] = set()
    for h in tr.handlers:
        if any(isinstance(n, ast.Raise) for n in ast.walk(h)):
            continue
        caught |= _catches(h)
    return bool(caught & {"*", "Exception", "BaseException"}) or ("OSError" in caught and ".Error" in caught)


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def check_cache_write_guarded(repo: Path) -> list[Finding]:
    """cache-write-guarded: a module declaring `CACHE_WRITERS` names the functions that land rows in a cache.
    Every use of one anywhere in the engine — a call, or the writer passed on as a value (`partial`, a callback),
    by its name, an attribute, an `as` alias or `getattr(module, "name")` — sits lexically inside a `try` in the SAME scope whose handlers,
    not re-raising, catch everything or OSError and the driver's `.Error`. A nested def or lambda starts with no
    guard: it runs where it is called, not where it is written. A read-only or full store made `blast` compute
    its answer and then refuse (graphyos #111 review round 4); round 6 found the first cut credited a re-raise,
    a `JSONDecodeError`, a nested def and an alias."""
    root = repo / "engine" / "graphy"
    files = sorted(root.rglob("*.py")) if root.is_dir() else []
    writers: set[str] = set()
    for p in files:
        hit = _literal_tuple(ast.parse(p.read_text(encoding="utf-8")), "CACHE_WRITERS")
        if hit:
            writers |= set(hit[1])
    if not writers:
        raise CheckError("cache-write-guarded found ZERO declared CACHE_WRITERS — the store's writers are undeclared, or the scan is broken")
    found: list[Finding] = []
    uses = 0
    for p in files:
        rel = _rel(repo, p)
        tree = ast.parse(p.read_text(encoding="utf-8"))
        names = set(writers)                      # a bare name, or an `as` alias / a plain rebinding of one
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                names |= {a.asname for a in n.names if a.name in writers and a.asname}
        for n in ast.walk(tree):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                    and ((isinstance(n.value, ast.Name) and n.value.id in names)
                         or (isinstance(n.value, ast.Attribute) and n.value.attr in writers))):
                names.add(n.targets[0].id)
        alias_rhs = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Name, ast.Attribute))
                     and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names}

        def visit(node, guarded: bool):
            nonlocal uses
            if isinstance(node, _SCOPES):
                if isinstance(node, ast.Lambda):
                    visit(node.body, False)
                    return
                for child in node.body:
                    visit(child, False)
                for dec in node.decorator_list:
                    visit(dec, guarded)
                return
            if isinstance(node, ast.Try):
                holds = _guard_holds(node)
                for child in node.body:
                    visit(child, guarded or holds)
                for child in node.handlers + node.orelse + node.finalbody:
                    visit(child, guarded)
                return
            use = None
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant) and node.args[1].value in writers):
                use = node.args[1].value                 # getattr(module, "store_x")
            elif isinstance(node, ast.Name) and node.id in names and isinstance(node.ctx, ast.Load) and id(node) not in alias_rhs:
                use = node.id
            elif isinstance(node, ast.Attribute) and node.attr in writers and isinstance(node.ctx, ast.Load) and id(node) not in alias_rhs:
                use = node.attr
            if use is not None:
                uses += 1
                if not guarded:
                    found.append(Finding("cache-write-guarded", f"{rel}:{node.lineno}",
                                         f"{use} lands cache rows outside a try (in its own scope) whose non-re-raising handlers "
                                         f"catch OSError and the driver's Error — a read-only or full store would cost the answer"))
                return
            for child in ast.iter_child_nodes(node):
                visit(child, guarded)

        visit(tree, False)
    if not uses:
        raise CheckError(f"cache-write-guarded found ZERO uses of {sorted(writers)} — nothing lands rows, or the scan is broken")
    NOTES["cache-write-guarded"] = f"{len(writers)} writer(s), {uses} use(s)"
    return found


def check_data_home_by_descriptor(repo: Path) -> list[Finding]:
    """data-home-by-descriptor: a data home is a generation the descriptor names (`substrate.gen-<token>/`), never a
    path spelled in code. A module declaring `DATA_HOME_DECLARERS` names the functions that mint the substrate's
    name; anywhere else in the engine a path built on the literal segment `substrate` — `x / "substrate"`,
    `Path("….graphy/substrate…")`, `.joinpath("substrate")` — reads a directory no descriptor serves. Found while
    building #98's generations: `showcase`, `shell install` and the gate each read `.graphy/substrate/ring.json`."""
    root = repo / "engine" / "graphy"
    files = sorted(root.rglob("*.py")) if root.is_dir() else []
    declarers: set[str] = set()
    for p in files:
        hit = _literal_tuple(ast.parse(p.read_text(encoding="utf-8")), "DATA_HOME_DECLARERS")
        if hit:
            declarers |= set(hit[1])
    if not declarers:
        raise CheckError("data-home-by-descriptor found ZERO declared DATA_HOME_DECLARERS — the substrate's name is minted nowhere, or the scan is broken")

    def names_substrate(node) -> bool:
        if isinstance(node, ast.JoinedStr):           # f"{home}/substrate/…" — review round 2 of #98
            return any(names_substrate(v) for v in node.values)
        return (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and "substrate" in node.value.replace("\\", "/").split("/"))

    found: list[Finding] = []
    for p in files:
        rel = _rel(repo, p)
        tree = ast.parse(p.read_text(encoding="utf-8"))

        def visit(node, where: str | None):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                where = where or node.name
            hit = None
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and (names_substrate(node.left) or names_substrate(node.right)):
                hit = node
            elif isinstance(node, ast.JoinedStr) and names_substrate(node) and any(isinstance(v, ast.FormattedValue) for v in node.values):
                hit = node
            elif isinstance(node, ast.Call) and any(names_substrate(a) for a in node.args) and (
                    (isinstance(node.func, ast.Name) and node.func.id in ("Path", "PurePath"))
                    or (isinstance(node.func, ast.Attribute) and node.func.attr in ("joinpath", "Path"))):
                hit = node
            if hit is not None and where not in declarers:
                found.append(Finding("data-home-by-descriptor", f"{rel}:{hit.lineno}",
                                     f"a path built on the literal `substrate` in {where or 'module scope'} — read the data home "
                                     f"the descriptor serves (`cli.served_data_home`), or declare the minting function in DATA_HOME_DECLARERS"))
                return
            for child in ast.iter_child_nodes(node):
                visit(child, where)

        visit(tree, None)
    NOTES["data-home-by-descriptor"] = f"{len(files)} module(s), {len(declarers)} declarer(s)"
    return found


def check_cursor_exclude_by_tenant(repo: Path) -> list[Finding]:
    """cursor-exclude-by-tenant: the cursor a store is built at and the drift `check` measures must agree on what is dirt,
    so every `repo_cursor(` / `cursor_drift(` call in the engine passes `exclude=` as a call to a function the module
    declaring `CURSOR_EXCLUDERS` names. Review round 2 of #98: rebuild excluded `(desc.parent,)` while check excluded the
    data home, so a `substrate.gen-*` beside a gitignored `substrate/` read CHECK RED on every rebuild."""
    root = repo / "engine" / "graphy"
    files = sorted(root.rglob("*.py")) if root.is_dir() else []
    excluders: set[str] = set()
    declaring: set[Path] = set()
    for p in files:
        hit = _literal_tuple(ast.parse(p.read_text(encoding="utf-8")), "CURSOR_EXCLUDERS")
        if hit:
            excluders |= set(hit[1])
            declaring.add(p)
    if not excluders:
        raise CheckError("cursor-exclude-by-tenant found ZERO declared CURSOR_EXCLUDERS — the exclusion is undeclared, or the scan is broken")
    found: list[Finding] = []
    calls = 0
    for p in files:
        if p in declaring:
            continue                                   # the declarer composes the primitives itself
        rel = _rel(repo, p)
        tree = ast.parse(p.read_text(encoding="utf-8"))
        cursor_fns = {"repo_cursor": "repo_cursor", "cursor_drift": "cursor_drift"}
        for n in ast.walk(tree):                     # `from graphy.cartograph import repo_cursor as rc` — review round 3 of #98
            if isinstance(n, ast.ImportFrom):
                cursor_fns.update({a.asname: a.name for a in n.names if a.name in ("repo_cursor", "cursor_drift") and a.asname})
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if (isinstance(f, ast.Call) and isinstance(f.func, ast.Name) and f.func.id == "getattr" and len(f.args) >= 2
                    and isinstance(f.args[1], ast.Constant) and f.args[1].value in ("repo_cursor", "cursor_drift")):
                name = f.args[1].value                   # getattr(cartograph, "repo_cursor")(…)
            else:
                name = cursor_fns.get(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None)
            if name not in ("repo_cursor", "cursor_drift"):
                continue
            calls += 1
            exc = next((k.value for k in node.keywords if k.arg == "exclude"), None)
            if exc is None and len(node.args) >= (2 if name == "repo_cursor" else 3):
                exc = node.args[1 if name == "repo_cursor" else 2]
            fn = exc.func if isinstance(exc, ast.Call) else None
            fname = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            if fname not in excluders:
                found.append(Finding("cursor-exclude-by-tenant", f"{rel}:{node.lineno}",
                                     f"{name}( excludes {ast.unparse(exc) if exc is not None else 'nothing'} — ask one of "
                                     f"{sorted(excluders)} so the build and the check agree on what is dirt"))
    if not calls:
        raise CheckError("cursor-exclude-by-tenant found ZERO cursor calls outside the declarer — the scan is broken")
    NOTES["cursor-exclude-by-tenant"] = f"{calls} cursor call(s), {len(excluders)} excluder(s)"
    return found


def check_generation_identity(repo: Path) -> list[Finding]:
    """generation-identity: whether a directory is a generation of a substrate is answered in ONE place — the module
    declaring `GENERATION_IDENTITY` (`generation_name` builds the name, `generation_of` reads it). Anywhere else in the
    engine a use of `GENERATION_INFIX`, or a string holding `.gen-` that is not a docstring, is a second spelling.
    Review round 4 of #98: `_of_family` took a strict regex, `_excluded` a `startswith`, `generation_base` a
    `partition`, and `refresh.plan_for` named its sibling after a generation token — the three disagreed on it."""
    root = repo / "engine" / "graphy"
    files = sorted(root.rglob("*.py")) if root.is_dir() else []
    declaring = [p for p in files if _literal_tuple(ast.parse(p.read_text(encoding="utf-8")), "GENERATION_IDENTITY")]
    if not declaring:
        raise CheckError("generation-identity found ZERO declared GENERATION_IDENTITY — the predicate is undeclared, or the scan is broken")
    found: list[Finding] = []
    for p in files:
        if p in declaring:
            continue
        rel = _rel(repo, p)
        tree = ast.parse(p.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for n in ast.walk(tree):
            what = None
            if isinstance(n, ast.Name) and n.id == "GENERATION_INFIX" and isinstance(n.ctx, ast.Load):
                what = "GENERATION_INFIX"
            elif isinstance(n, ast.Attribute) and n.attr == "GENERATION_INFIX":
                what = "GENERATION_INFIX"
            elif isinstance(n, ast.alias) and n.name == "GENERATION_INFIX":
                what = "an import of GENERATION_INFIX"
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and ".gen-" in n.value and id(n) not in docs:
                what = f"the literal {n.value!r}"
            if what:
                found.append(Finding("generation-identity", f"{rel}:{getattr(n, 'lineno', 0)}",
                                     f"{what} spells generation identity outside {', '.join(_rel(repo, d) for d in declaring)} — "
                                     f"ask generation_name / generation_of"))
    NOTES["generation-identity"] = f"{len(files)} module(s), {len(declaring)} declarer(s)"
    return found


_HOST_PY = re.compile(
    r"(?:^|[;&|(`]|\$\()\s*"                                                    # command position: line start, after ; & | ( ` $(
    r"(?:(?:if|then|do|else|elif|while|until|exec|time|env|command|sudo|nohup|!|timeout\s+\S+|[A-Za-z_]\w*=\S*)\s+)*"
    r"(?:((?:/usr(?:/local)?)?/bin/)|(?<![\w/.$\"-]))(python(?:3(?:\.\d+)?)?)"          # bare, or a SYSTEM path — a venv's interpreter is its own
    r"(?:\s+-[WX]\s+\S+|\s+-[A-Za-z]+)*\s+-m\s*([A-Za-z_][\w.]*)")


def check_host_interpreter(repo: Path) -> list[Finding]:
    """host-interpreter: a tracked shell script (outside staging/) runs `python3 -m <module>` on the HOST interpreter
    only for a standard-library module. Anything else is this box's site-packages standing in for the script's
    own: the gate ran `python3 -m pytest` on the march's floor, green here where pytest is installed system-wide and
    red on every CI runner for eight commits (found while marching #88)."""
    import subprocess as sp
    listed = sp.run(["git", "-C", str(repo), "ls-files", "*.sh"], capture_output=True, text=True)
    if listed.returncode != 0:
        raise CheckError(f"host-interpreter could not list tracked shell scripts: {listed.stderr.strip()[:200]}")
    scripts = [repo / f for f in listed.stdout.splitlines() if f and not f.startswith("staging/")]
    workflows = sorted((repo / ".github" / "workflows").glob("*.y*ml"))       # a `run:` body is the same host (round 1)
    stdlib = set(sys.stdlib_module_names)
    found: list[Finding] = []
    for p in scripts + workflows:
        # a workflow's interpreter is the job's own (setup-python): pip, and whatever the file pip-installs before
        # the line, are its own; a script's host interpreter owns only the standard library
        own = {"pip"} if p in workflows else set()
        owns_all = False
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if p in workflows:
                line = re.sub(r"^\s*(?:-\s+)?run:\s*\|?\s*", "", line)
            for m in _HOST_PY.finditer(line):
                if not owns_all and m.group(3).split(".")[0] not in stdlib | own:
                    found.append(Finding("host-interpreter", f"{_rel(repo, p)}:{i}",
                                         f"`{m.group(1) or ''}{m.group(2)} -m {m.group(3)}` runs on the host interpreter's site-packages — run it with the "
                                         f"script's own interpreter (the gate's fresh venv, `$PY`), or it is green only where the host has it"))
            if p in workflows and not owns_all:
                for inst in re.finditer(r"\bpip\s+install\b([^&;|]*)", line):
                    args = inst.group(1).split()
                    if any(a in ("-e", "--editable", "-r", "--requirement") or "/" in a or "[" in a or a.strip("'\"").startswith(".")
                           for a in args):
                        owns_all = True             # a local tree, extras or a requirements file: its modules cannot be read off the line
                        break
                    own |= {re.split(r"[\[<>=!~ ]", t.strip("'\""))[0].replace("-", "_") for t in args if not t.startswith("-")}
    NOTES["host-interpreter"] = f"{len(scripts)} tracked script(s), {len(workflows)} workflow(s)"
    return found


_GH_STUB = """#!/usr/bin/env python3
import os, sys
log = open(os.environ["GH_STUB_LOG"], "a")
args, words, skip = sys.argv[1:], [], False
for i, a in enumerate(args):
    if skip:
        skip = False
        continue
    flag, eq, val = a.partition("=")
    if a.startswith("-F") and len(a) > 2 and not a.startswith("--"):
        flag, eq, val = "-F", "=", a[3:] if a[2] == "=" else a[2:]   # pflag strips the `=` of -F=path
    if flag in ("-R", "--repo"):
        skip = not eq
        continue
    if a == "--json" and args[:2] == ["workflow", "run"]:
        words.append(sys.stdin.read())
        continue
    if flag in ("--body-file", "-F", "--notes-file") or (flag.startswith("--") and flag.endswith("-file")):
        path = val if eq else (args[i + 1] if i + 1 < len(args) else "")
        skip = not eq
        try:
            words.append(sys.stdin.read() if path in ("-", "/dev/stdin") else open(path).read())
        except OSError:
            pass
        continue
    words.append(a)
log.write("\\n".join(words) + "\\n")
"""


def _bash_posts(command: str, cwd: Path, work: Path) -> str | None:
    """What a command hands to `gh`, as bash runs it with a stub `gh` first on a PATH of system directories: its argv
    and every body it reads, or None when bash cannot be run here."""
    import os
    import subprocess as sp
    stub = work / "stub-bin"
    stub.mkdir(exist_ok=True)
    gh = stub / "gh"
    if not gh.exists():
        gh.write_text(_GH_STUB, encoding="utf-8")
        gh.chmod(0o755)
    log = work / "posted.log"
    log.write_text("", encoding="utf-8")
    env = {"PATH": f"{stub}:/usr/local/bin:/usr/bin:/bin", "HOME": str(work), "GH_STUB_LOG": str(log), "LANG": "C.UTF-8"}
    try:
        sp.run(["bash", "-c", command], cwd=cwd, env=env, stdin=sp.DEVNULL, stdout=sp.DEVNULL, stderr=sp.DEVNULL, timeout=10)
    except (OSError, sp.SubprocessError):
        return None
    return log.read_text(encoding="utf-8", errors="replace")


_OUTPUT_LOGGER_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "exception", "log"}


def _import_time_statements(body):
    """Every simple statement that runs when the module is imported: the module body, and the bodies of if · try ·
    with · for · while · match · class blocks under it, each yielded once — never a def, whose body runs later,
    after an entry point's `utf8_streams`."""
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        blocks = []
        for value in (getattr(stmt, f) for f in stmt._fields):
            if isinstance(value, list) and value and all(isinstance(v, ast.stmt) for v in value):
                blocks.append(value)
            elif isinstance(value, list) and value and all(isinstance(getattr(v, "body", None), list) for v in value):
                blocks.extend(v.body for v in value)           # except handlers · match cases
        if blocks:
            for block in blocks:
                yield from _import_time_statements(block)
        else:
            yield stmt


def _walk_import_time(node):
    """`ast.walk` that never enters a lambda — the one function body a simple statement can carry."""
    if isinstance(node, ast.Lambda):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_import_time(child)


def _writes_output(call: ast.Call) -> str | None:
    """`print(...)` · `<logger>.<level>(...)` · `logging.<level>(...)` · `sys.stdout|stderr.write(...)` — what it is, or None."""
    f = call.func
    if isinstance(f, ast.Name) and f.id == "print":
        return "print"
    if isinstance(f, ast.Attribute):
        if f.attr in _OUTPUT_LOGGER_METHODS:
            return f"{ast.unparse(f.value)}.{f.attr}"
        if f.attr == "write" and isinstance(f.value, ast.Attribute) and f.value.attr in ("stdout", "stderr") \
                and isinstance(f.value.value, ast.Name) and f.value.value.id == "sys":
            return f"sys.{f.value.attr}.write"
    return None


def check_import_time_glyph(repo: Path) -> list[Finding]:
    """import-time-glyph: a line printed while a module IMPORTS runs before any entry point's `utf8_streams` has made
    the streams utf-8, so a glyph in it is the cp1252 crash #123 fixed, one hop earlier. Review round 2 of #123:
    `lightning/ripgrep.py` warned `ripgrep not found … —` at module level whenever rg was absent — windows-latest's
    condition — and the em-dash reached a cp1252 stderr before `main`. A print, a logger call or a `sys.std*.write`
    at import time whose string literals carry a non-ASCII character is a finding; the same call inside a def is not."""
    root = repo / "engine" / "graphy"
    files = sorted(root.rglob("*.py")) if root.is_dir() else []
    if not files:
        raise CheckError("import-time-glyph found ZERO modules under engine/graphy — the scan is broken")
    found: list[Finding] = []
    calls = 0
    for p in files:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for stmt in _import_time_statements(tree.body):
            for n in _walk_import_time(stmt):
                if not isinstance(n, ast.Call) or (what := _writes_output(n)) is None:
                    continue
                calls += 1
                glyphs = {ch for a in list(n.args) + [k.value for k in n.keywords] for c in ast.walk(a)
                          if isinstance(c, ast.Constant) and isinstance(c.value, str) for ch in c.value if ord(ch) > 127}
                if glyphs:
                    found.append(Finding("import-time-glyph", f"{_rel(repo, p)}:{n.lineno}",
                                         f"{what} at import time carries {''.join(sorted(glyphs))!r} — it runs before any "
                                         f"entry point's utf8_streams; make it lazy (print from the call that needs it)"))
    NOTES["import-time-glyph"] = f"{len(files)} module(s), {calls} import-time output call(s)"
    return found


def _splice_of(node: ast.AST) -> str | None:
    """How a piece of text was built by splicing a value in, when it was: an f-string, a `%` format,
    `.format()` or `.replace()`, or the shell installer's text filler `_fill()`."""
    if isinstance(node, ast.JoinedStr):
        return "an f-string"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return "a % format"
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("format", "replace"):
            return f"`.{f.attr}()`"
        if isinstance(f, ast.Name) and f.id == "_fill":
            return "`_fill()`"
    return None


def check_json_template_spliced(repo: Path) -> list[Finding]:
    """json-template-spliced: a `json.loads(...)` over text a value was just spliced into — an f-string, `%`,
    `.format()`, `.replace()`, or `_fill()` (the shell installer's text filler) — is JSON nothing escaped the
    value into: a Windows interpreter path (`C:\\venv`) or a quote in it writes a file the harness cannot parse
    (`Invalid \\escape: line 8 column 29`, the wiring `shell install` wrote on windows-latest, graphyos #125).
    A template filled into JSON goes through a filler that `json.dumps` each value (`shell.install._fill_json`)."""
    root = repo / "engine" / "graphy"
    files = sorted(root.rglob("*.py")) if root.is_dir() else []
    if not files:
        raise CheckError("json-template-spliced found ZERO modules under engine/graphy — the scan is broken")
    found: list[Finding] = []
    loads = 0
    for p in files:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "loads"
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "json" and n.args):
                continue
            loads += 1
            how = _splice_of(n.args[0])
            if how:
                found.append(Finding("json-template-spliced", f"{_rel(repo, p)}:{n.lineno}",
                                     f"json.loads over text built by {how} — a value spliced raw into JSON; escape each "
                                     f"one with json.dumps (a filler like shell.install._fill_json), never splice it"))
    NOTES["json-template-spliced"] = f"{len(files)} module(s), {loads} json.loads call(s)"
    return found


def check_specimen_corpus(repo: Path) -> list[Finding]:
    """specimen-corpus: every line of `review_specimens/<door>.tsv` replayed against its door, the exit code it must
    give. A review round's blocker lands as a line here — the battery compounds without a new check per round: #91's
    hook went through three REVISE rounds, each finding post forms the last cut read wrong, and each specimen is a
    line. Doors: `gh_hook.tsv` → `scrub.gh_hook` under a fixture key (no box key needed, never the real markers)."""
    import importlib.util
    import json
    corpus = repo / "review_specimens" / "gh_hook.tsv"
    scrub_py = repo / "scrub.py"
    if not corpus.is_file() or not scrub_py.is_file():
        raise CheckError(f"specimen-corpus has no {corpus.relative_to(repo)} or no scrub.py — the corpus is the battery's memory")
    spec = importlib.util.spec_from_file_location("scrub_under_review", scrub_py)
    scrub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scrub)
    work = Path(tempfile.mkdtemp(prefix="specimens-"))
    try:
        word = "zorblaxquux"
        key = b"0123456789abcdef" * 2
        hashes = frozenset({scrub.norm_hash(word, key)})
        home = work / f"{word}-home"
        home.mkdir()
        (home / "clean.md").write_text("a public sentence\n", encoding="utf-8")
        (home / "body.md").write_text(f"fine\n{word}\n", encoding="utf-8")
        subs = {"{M}": word, "{HOME}": str(home), "{CLEAN}": str(home / "clean.md"), "{DIRTY}": str(home / "body.md")}
        found: list[Finding] = []
        n = 0
        for i, line in enumerate(corpus.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3 or parts[0] not in ("0", "2") or parts[1] not in ("-", "home"):
                found.append(Finding("specimen-corpus", f"{corpus.relative_to(repo)}:{i}", "a line is not `expect<TAB>cwd<TAB>command` (expect 0|2, cwd -|home)"))
                continue
            (home / "clean.md").write_text("a public sentence\n", encoding="utf-8")   # a line may rewrite a fixture:
            (home / "body.md").write_text(f"fine\n{word}\n", encoding="utf-8")       # every line starts from the same two
            command = re.sub(r"\\(n|\\)", lambda m: "\n" if m.group(1) == "n" else "\\", parts[2])
            for k, v in subs.items():
                command = command.replace(k, v)
            payload = {"tool_name": "Bash", "tool_input": {"command": command}}
            if parts[1] == "home":
                payload["cwd"] = str(home)
            import contextlib
            import io
            with contextlib.redirect_stderr(io.StringIO()):
                got = scrub.gh_hook(json.dumps(payload), hashes, key)
            n += 1
            where = f"{corpus.relative_to(repo)}:{i}"
            if str(got) != parts[0]:
                found.append(Finding("specimen-corpus", where, f"gh_hook exits {got}, the specimen says {parts[0]}: {parts[2][:90]}"))
            # the oracle: what bash itself would post, through a gh that only logs (round 5 of #91 — four rounds of the
            # parser disagreeing with bash are one class, and bash is the only judge of it)
            posted = _bash_posts(command, home if parts[1] == "home" else work, work)
            if posted is None:
                found.append(Finding("specimen-corpus", where, f"the bash oracle could not run this line (no bash, a timeout or an OSError): {parts[2][:80]}"))
                continue
            if scrub.hits_in_text(posted, hashes, key):
                if got != 2:
                    found.append(Finding("specimen-corpus", where, f"bash posts the marker and gh_hook exits {got} — fail-open: {parts[2][:80]}"))
                if parts[0] == "0":
                    found.append(Finding("specimen-corpus", where, f"the specimen says 0 but bash posts the marker: {parts[2][:80]}"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not n:
        raise CheckError("specimen-corpus replayed ZERO specimens — the corpus is empty, or every line is malformed")
    NOTES["specimen-corpus"] = f"{n} specimen(s) replayed"
    return found


# ── the battery ───────────────────────────────────────────────────────────────────────────────────

# ── the byte git checks out ───────────────────────────────────────────────────────────────────────

REWRITING_ATTRS = ("text", "ident", "working-tree-encoding", "filter")   # the attributes under which a checkout is not the blob


def _rewrite_attrs(repo: Path, files: list[str], cached: bool) -> dict[str, dict[str, str]]:
    """Every attribute that makes git write a working file that is not the blob it holds — `text`
    (line endings), `ident` (`$Id$` expansion), `working-tree-encoding` (a transcode), `filter` (a
    clean/smudge program, git-lfs's for one) — per tracked file, read from the rule files that SHIP:
    the index's (`--cached`, what a commit holds) or the worktree's (what `git add -A` will commit),
    never this box's: the user's file is pointed at /dev/null and the system's is switched off."""
    cmd = ["git", "-c", "core.attributesFile=/dev/null", "check-attr", *(["--cached"] if cached else []), *REWRITING_ATTRS, "-z", "--stdin"]
    r = subprocess.run(cmd, cwd=repo, input="\0".join(files) + "\0", capture_output=True, text=True,
                       env={**os.environ, "GIT_ATTR_NOSYSTEM": "1"})
    if r.returncode != 0:
        raise CheckError(f"git check-attr{' --cached' if cached else ''} failed in {repo}: {r.stderr.strip()[:200]}")
    parts = r.stdout.split("\0")
    triples = [parts[i:i + 3] for i in range(0, len(parts) - 2, 3)]
    out: dict[str, dict[str, str]] = {}
    for path, attr, value in triples:
        out.setdefault(path, {})[attr] = value
    if len(out) != len(files) or any(set(v) != set(REWRITING_ATTRS) for v in out.values()):
        unmerged = [f for f in _git(repo, "ls-files", "-u", "-z").split("\0") if f]
        if unmerged:
            raise CheckError(f"the index holds {len(unmerged)} unmerged entr{'y' if len(unmerged) == 1 else 'ies'} — resolve the merge, then the attributes can be read")
        raise CheckError(f"git check-attr answered {len(out)} of {len(files)} tracked file(s) — the parse is broken")
    return out


def _rewrites(attrs: dict[str, str]) -> str | None:
    """Why git would write this file differently from the blob, or None: `text` anything but `unset`,
    `ident` or `filter` switched on, a `working-tree-encoding` that is not off (`unset`, round 5's
    innocent: `-working-tree-encoding` is the switch the attribute exists for) and not UTF-8."""
    if attrs["text"] != "unset":
        return f"`text` is {attrs['text']}: a core.autocrlf client rewrites its line endings on checkout"
    for a in ("ident", "filter"):
        if attrs[a] not in ("unspecified", "unset"):
            return f"`{a}` is {attrs[a]}: git writes the checkout through it, not the blob"
    enc = attrs["working-tree-encoding"]
    if enc not in ("unspecified", "unset") and enc.lower().replace("-", "") != "utf8":     # git's own no-op spellings
        return f"`working-tree-encoding` is {enc}: git transcodes the checkout"
    return None


def check_eol_rewritable(repo: Path) -> list[Finding]:
    """eol-rewritable: every tracked file reads `text: unset` from `git check-attr` — a client with
    core.autocrlf (Git for Windows' default) rewrites the line endings of every tracked file whose
    `text` attribute nobody set, and a shard is content-addressed: on windows-latest the golden
    fixture's nodes.json came out CRLF and its digest no longer matched its PROVENANCE, and the same
    checkout corrupts docs/pillars.svg, CHANGELOG.md and every arm region the gate compares byte for
    byte (graphyos #126). `.gitattributes` says `* -text`; this reads what git will actually do, file
    by file, so a rule narrowed or a file it no longer covers is named, never found on a runner.
    Round 4 found `ident`, `working-tree-encoding` and `filter` rewrite a checkout the same way while `text`
    reads `unset`, so the reads cover every attribute under which a checkout is not the blob (`REWRITING_ATTRS`).
    It asks git, never a hand-built list of git's sources — every review round of #126 found the next
    one (an untracked rule file, a global one, a linked worktree's common dir, a worktree edit the
    next `add -A` ships). Two reads over every tracked file, the box's own sources off in both: the
    index's rules (`--cached`, what a commit holds) and the worktree's (what `git add -A` will commit);
    a file not `unset` in the index, or answered differently by the two, is the finding by name. An
    untracked, unignored `.gitattributes` is named as a cause, and one deleted from the worktree (both
    reads fall back to the index's copy, and the next `add -A` ships the deletion) is a finding; `<git-dir>/info/attributes` (located by
    `git rev-parse --git-path`, so a linked worktree's common dir is read) applies to both reads and
    ships with neither, so a non-empty one is a finding. And no tracked file holds CRLF in the index
    (`git ls-files --eol` `i/crlf`): `-text` also stops git normalising a CRLF a Windows editor commits,
    and the svg's `cmp` would find it late."""
    files = [f for f in _git(repo, "ls-files", "-z").split("\0") if f]
    if not files:
        raise CheckError("eol-rewritable found ZERO tracked files — the listing is broken, not the tree")
    found: list[Finding] = []
    loose = [f for f in _git(repo, "ls-files", "-o", "--exclude-standard", "-z").split("\0") if f.rsplit("/", 1)[-1] == ".gitattributes"]
    for rel in loose:
        found.append(Finding("eol-rewritable", rel, "a rule file git reads here that no clone will: it is not tracked — `git add` it"))
    gone = [f for f in _git(repo, "ls-files", "-d", "-z").split("\0") if f.rsplit("/", 1)[-1] == ".gitattributes"]
    for rel in gone:
        # absent from the worktree, git reads the index's copy for both reads — the deletion the next add -A ships is invisible to them
        found.append(Finding("eol-rewritable", rel, "a rule file deleted from the worktree: git still reads the index's copy here, and the next `git add -A` ships the deletion"))
    info = repo / _git(repo, "rev-parse", "--git-path", "info/attributes").strip()
    if info.is_file() and info.read_text(encoding="utf-8", errors="replace").strip():
        found.append(Finding("eol-rewritable", info.as_posix(), "a rule file only this box holds, read for the index and the worktree alike: every attribute this tree needs lives in a tracked `.gitattributes`"))
    index = _rewrite_attrs(repo, files, cached=True)
    worktree = _rewrite_attrs(repo, files, cached=False)
    NOTES["eol-rewritable"] = f"{len(files)} tracked file(s) × {len(REWRITING_ATTRS)} attribute(s), the index's and the worktree's rules"
    for path in files:
        why = _rewrites(index[path])
        if why:
            found.append(Finding("eol-rewritable", path, f"{why} (the index's rules) — a tracked `.gitattributes` must leave every byte as the blob holds it: the shard digests, the svg and the changelog are byte checks"))
            continue
        if worktree[path] != index[path]:
            diff = ", ".join(f"`{a}` {index[path][a]} → {worktree[path][a]}" for a in REWRITING_ATTRS if index[path][a] != worktree[path][a])
            found.append(Finding("eol-rewritable", path, f"the index's rules and this checkout's answer differently ({diff}): a clone and this box do not hold the same bytes, and what the next commit ships is whichever rule file it adds"))
    for row in _git(repo, "ls-files", "--eol", "-z").split("\0"):
        if row.startswith("i/crlf"):
            found.append(Finding("eol-rewritable", row.split("\t", 1)[1],
                                 "the index holds CRLF: `-text` stops git normalising it, so every host checks out the CRLF — commit it LF"))
    return found


CHECKS = {
    "advertised-argv-parses": check_advertised_argv,
    "cites-nonexistent": check_cites,
    "argparse-dest-never-read": check_argparse_dests,
    "path-literal-names-nothing": check_paths,
    "template-token": check_template_tokens,
    "review-row-order": check_review_row_order,
    "sha-liveness": check_sha_liveness,
    "cache-key-closure": check_cache_key_closure,
    "cache-write-guarded": check_cache_write_guarded,
    "data-home-by-descriptor": check_data_home_by_descriptor,
    "cursor-exclude-by-tenant": check_cursor_exclude_by_tenant,
    "generation-identity": check_generation_identity,
    "host-interpreter": check_host_interpreter,
    "import-time-glyph": check_import_time_glyph,
    "json-template-spliced": check_json_template_spliced,
    "specimen-corpus": check_specimen_corpus,
    "eol-rewritable": check_eol_rewritable,
}


def _seed(files: dict[str, str]) -> Path:
    """A fixture repository: the files, committed once, so every check reads it the way it reads this one."""
    root = Path(tempfile.mkdtemp(prefix="review-fixture-"))
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")     # the bytes as written: text mode would commit CRLF on Windows
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
        "review-row-order": (
            {"RECON.md": "## 1 · a\n\n| review round 1 | REVISE |\n| review round 2 | SHIP |\n| review round 1 | REVISE |\n\n## 2 · b\n"},
            {"RECON.md": "## 1 · a\n\n| review round 1 | REVISE |\n| review round 2 | SHIP |\n\n## 2 · b\n\n| review round 1 | REVISE |\n"}),
        "sha-liveness": (
            {"RECON.md": "## 1 · x (2026-01-01)\n\nlanded at commit deadbeef0\n"},
            {"RECON.md": "## 1 · x (2026-01-01)\n\nthe store generation 24eecb50371f9e1d is not a commit\n"}),
        "cache-key-closure": (
            # red: e absent (a lazy import inside a root function), rel absent (a relative import), gone stale,
            # d unpinned, an exemption with no reason, dyn absent (a literal import_module) — six findings
            {"engine/graphy/__init__.py": "", "engine/graphy/_shared.py": "def source_sha(f):\n    return f\nSOURCE_SHA = source_sha(__file__)\n",
             "engine/graphy/t.py": "RULE_ROOTS = ('graphy.d',)\nRULE_MODULES = ('graphy.d', 'graphy._shared', 'graphy.gone')\nRULE_EXEMPT = {'graphy': ''}\n",
             "engine/graphy/d.py": "from graphy._shared import source_sha\nfrom .rel import z\ndef blast():\n    from graphy.e import x\n"
                                   "    import importlib\n    importlib.import_module('graphy.dyn')\n",
             "engine/graphy/rel.py": "", "engine/graphy/e.py": "", "engine/graphy/dyn.py": ""},
            {"engine/graphy/__init__.py": "", "engine/graphy/_shared.py": "def source_sha(f):\n    return f\nSOURCE_SHA = source_sha(__file__)\n",
             "engine/graphy/t.py": "RULE_ROOTS = ('graphy.d',)\nRULE_MODULES = ('graphy.d', 'graphy._shared', 'graphy.e', 'graphy.rel', 'graphy.dyn')\n"
                                   "RULE_EXEMPT = {'graphy': 'the package re-exports; no rule'}\n",
             "engine/graphy/d.py": "from graphy._shared import source_sha\nSOURCE_SHA = source_sha(__file__)\nfrom .rel import z\ndef blast():\n    from graphy.e import x\n"
                                   "    __import__('graphy.dyn')\n",
             "engine/graphy/dyn.py": "from graphy._shared import source_sha\nSOURCE_SHA = source_sha(__file__)\n",
             "engine/graphy/rel.py": "from graphy._shared import source_sha\nSOURCE_SHA = source_sha(__file__)\n", "engine/graphy/e.py": "from graphy._shared import source_sha\nSOURCE_SHA = source_sha(__file__)\n"}),
        "cache-write-guarded": (
            # red: bare call · a JSONDecodeError beside OSError · a re-raise · a nested def · an alias · a partial · a getattr — seven
            {"engine/graphy/t.py": "CACHE_WRITERS = ('store_x',)\ndef store_x():\n    pass\n",
             "engine/graphy/u.py": "import json, functools, duckdb\nfrom graphy.t import store_x, store_x as sx\nfrom graphy import t\n"
                                   "def a():\n    store_x()\n"
                                   "def b():\n    try:\n        t.store_x()\n    except (OSError, json.JSONDecodeError):\n        pass\n"
                                   "def c():\n    try:\n        store_x()\n    except (OSError, duckdb.Error):\n        raise\n"
                                   "def d():\n    try:\n        def later():\n            store_x()\n    except Exception:\n        pass\n    later()\n"
                                   "def e():\n    sx()\n"
                                   "def f():\n    return functools.partial(store_x)\n"
                                   "def g():\n    getattr(t, 'store_x')()\n"},
            {"engine/graphy/t.py": "CACHE_WRITERS = ('store_x',)\ndef store_x():\n    pass\n",
             "engine/graphy/u.py": "import functools, duckdb\nfrom graphy.t import store_x as sx\nfrom graphy import t\n"
                                   "def a():\n    try:\n        t.store_x()\n    except (OSError, duckdb.Error) as exc:\n        return exc\n"
                                   "def b():\n    try:\n        sx()\n        functools.partial(sx)()\n    except Exception:\n        pass\n"
                                   "def c():\n    try:\n        pass\n    except OSError:\n        raise\n"}),
        "data-home-by-descriptor": (
            # red: a `/ "substrate"` join · a Path over ".graphy/substrate/ring.json" · a joinpath — three, outside the declarer
            {"engine/graphy/cli.py": "DATA_HOME_DECLARERS = ('_eat_run',)\ndef _eat_run(home):\n    return home / 'substrate'\n",
             "engine/graphy/gate.py": "from pathlib import Path\ndef main(repo):\n    a = repo / '.graphy' / 'substrate' / 'ring.json'\n"
                                      "    b = Path('.graphy/substrate/ring.json')\n    c = open(f'{repo}/substrate/ring.json')\n    return repo.joinpath('substrate')\n"},
            {"engine/graphy/cli.py": "DATA_HOME_DECLARERS = ('_eat_run',)\ndef _eat_run(home):\n    return home / 'substrate'\n",
             "engine/graphy/gate.py": "def main(desc, served):\n    print('no tenant under .graphy/substrate')\n    return served(desc) / 'ring.json'\n"}),
        "cursor-exclude-by-tenant": (
            # red: a bare tuple · no exclude at all · a positional tuple to cursor_drift · an alias · a getattr — five
            {"engine/graphy/cartograph.py": "CURSOR_EXCLUDERS = ('cursor_exclude',)\ndef repo_cursor(r, exclude=()):\n    return r\n"
                                            "def cursor_drift(c, r, exclude=()):\n    return repo_cursor(r, exclude)\ndef cursor_exclude(d, h):\n    return (h,)\n",
             "engine/graphy/rebuild.py": "from graphy.cartograph import repo_cursor, cursor_drift\ndef run(root, desc):\n"
                                         "    repo_cursor(root, exclude=(desc.parent,))\n    repo_cursor(root)\n    cursor_drift('c', root, (desc,))\n"
                                         "from graphy.cartograph import repo_cursor as rc\nfrom graphy import cartograph\n"
                                         "def other(root):\n    rc(root)\n    getattr(cartograph, 'cursor_drift')('c', root)\n"},
            {"engine/graphy/cartograph.py": "CURSOR_EXCLUDERS = ('cursor_exclude',)\ndef repo_cursor(r, exclude=()):\n    return r\n"
                                            "def cursor_drift(c, r, exclude=()):\n    return repo_cursor(r, exclude)\ndef cursor_exclude(d, h):\n    return (h,)\n",
             "engine/graphy/rebuild.py": "from graphy import cartograph\nfrom graphy.cartograph import repo_cursor\ndef run(root, desc, sub):\n"
                                         "    repo_cursor(root, exclude=cartograph.cursor_exclude(desc, sub))\n    cartograph.cursor_drift('c', root, cartograph.cursor_exclude(desc, sub))\n"}),
        "generation-identity": (
            # red: an imported infix used in startswith · a literal '.gen-' partition · a sibling named after the token — three
            {"engine/graphy/_shared.py": "GENERATION_INFIX = '.gen-'\nGENERATION_IDENTITY = ('generation_of',)\ndef generation_of(n):\n    return n\n",
             "engine/graphy/cli.py": "from graphy._shared import GENERATION_INFIX\ndef fam(sub, home):\n    return home.name.startswith(sub.name + GENERATION_INFIX)\n",
             "engine/graphy/cartograph.py": "def base(p):\n    return p.name.partition('.gen-')[0]\n"},
            {"engine/graphy/_shared.py": "GENERATION_INFIX = '.gen-'\nGENERATION_IDENTITY = ('generation_of',)\ndef generation_of(n):\n    return n\n",
             "engine/graphy/cli.py": "from graphy._shared import generation_of\ndef fam(sub, home):\n    \"\"\"`<substrate>.gen-<token>` is its own.\"\"\"\n    return generation_of(home.name) == sub.name\n",
             "engine/graphy/cartograph.py": "def base(p):\n    return p\n"}),
        "host-interpreter": (
            # red: the gate's march floor · cd-chained · after then · indented · if-led · env-assigned · versioned · absolute ·
            # a flag before -m · a timeout-led -W flag · a workflow run: — eleven
            {"gate.sh": "#!/usr/bin/env bash\npython3 -m pytest -q x.py\ncd engine && python3 -m graphy check\nif true; then python3 -m build; fi\n"
                        "f() {\n  python3 -m pytest\n}\nif python3 -m pytest; then :; fi\nPYTHONPATH=engine python3 -m graphy\n"
                        "python3.12 -m pytest\n/usr/bin/python3 -m twine check\npython3 -u -m graphy\ntimeout 5 python3 -W ignore -m pytest\n",
             ".github/workflows/ci.yml": "name: ci\non: push\njobs:\n  g:\n    steps:\n      - run: python -m pytest -q\n      - run: pip install build\n"},
            {".github/workflows/ci.yml": "name: ci\non: push\njobs:\n  g:\n    steps:\n      - run: python -m venv .venv && .venv/bin/pip install x\n"
                                         "      - run: |\n          python -m pip install --upgrade pip build twine\n          python -m build --outdir dist engine\n"
                                         "      - run: pip install -e \"engine[dev,typescript]\"\n      - run: python -m pytest -q && python -m graphy --help\n",
             "gate.sh": "#!/usr/bin/env bash\n\"$PY\" -m pytest -q x.py\npython3 -m venv v && v/bin/python -m pytest\n$HERE/.venv/bin/python -m pytest\n"
                        "  python3 -m json.tool a\n# python3 -m pytest in a comment\n"
                        "python3 - <<'X'\ncmd = f\"python3 -m graphy pull {n}\"\nX\n"}),
        "import-time-glyph": (
            # red: the specimen (a logger.warning under a module-level if) · a print in a try · a class-body print ·
            # a sys.stderr.write in an else · a logging.error with the glyph in an f-string — five
            {"engine/graphy/rg.py": "import logging, sys\nlogger = logging.getLogger(__name__)\nRG = None\nif RG is None:\n"
                                    "    logger.warning('ripgrep not found — the slow fallback')\n"
                                    "try:\n    import fcntl\nexcept ImportError:\n    print('no fcntl · windows')\n"
                                    "class K:\n    print('→ built')\n"
                                    "if RG:\n    pass\nelse:\n    sys.stderr.write('✗ no rg\\n')\n"
                                    "logging.error(f'{RG} ⚠')\n"},
            {"engine/graphy/rg.py": "import logging, sys\nlogger = logging.getLogger(__name__)\nRG = None\n"
                                    "def warn():\n    if RG is None:\n        logger.warning('ripgrep not found — the slow fallback')\n"
                                    "print('ascii only at import')\nlogger.info('%s', 'plain')\n"
                                    "class K:\n    def m(self):\n        print('→ built')\n"
                                    "X = lambda: print('· lazy')\n"}),
        "json-template-spliced": (
            # red: the specimen (`json.loads(_fill(template, values))`) · a `.replace()` splice · a `%` format · an f-string — four
            {"engine/graphy/w.py": "import json\ndef _fill(t, values):\n    for k, v in values.items():\n        t = t.replace('{{' + k + '}}', str(v))\n"
                                   "    return t\ndef a(t, values):\n    return json.loads(_fill(t, values))\n"
                                   "def b(t, v):\n    return json.loads(t.replace('{{x}}', v))\n"
                                   "def c(v):\n    return json.loads('{\"a\": \"%s\"}' % v)\n"
                                   "def d(v):\n    return json.loads(f'{{\"a\": \"{v}\"}}')\n"},
            {"engine/graphy/w.py": "import json\ndef _fill_json(t, values):\n    for k, v in values.items():\n"
                                   "        t = t.replace('{{' + k + '}}', json.dumps(str(v))[1:-1])\n    return t\n"
                                   "def a(t, values):\n    return json.loads(_fill_json(t, values))\n"
                                   "def e(p):\n    return json.loads(p.read_text(encoding='utf-8'))\n"
                                   "def f(v):\n    return json.dumps({'a': v})\n"}),
        "specimen-corpus": (
            # red: a clean post the corpus wrongly says refuses · a malformed line · a line saying 0 that bash shows posting the marker
            {"scrub.py": (HERE / "scrub.py").read_text(encoding="utf-8"),
             "review_specimens/gh_hook.tsv": "# corpus\n2\t-\tgh issue create --title t --body \"a public sentence\"\n0\tnowhere\tgh issue view 1\n"
                                             "0\t-\tgh issue comment 1 -b {M}\n"},   # + the oracle: bash posts the marker, the line says 0
            {"scrub.py": (HERE / "scrub.py").read_text(encoding="utf-8"),
             "review_specimens/gh_hook.tsv": "# corpus\n0\t-\tgh issue create --title t --body \"a public sentence\"\n2\t-\tgh issue comment 1 -b {M}\n"}),
        "eol-rewritable": (
            # red: a rule narrowed to the shard leaves the svg rewritable (the attribute), a `-text` file with `ident` on is
            # rewritten on every clone all the same (round 4: `$Id$` expanded, `text` unset), a CRLF file sits in the index,
            # and _run_fixture drops an UNTRACKED `docs/.gitattributes` covering the svg (round 1: green on the box, red on a
            # clone) and points the repo's core.attributesFile at a box-only `* -text` (round 2: the same, through git's
            # global source) — the svg must still be named, from the index's rules alone.
            # green: the blanket rule tracked, and a `* text=auto` under a gitignored .venv/ that git never reads (round 2's
            # false red: a stranger's checkout under staging/ or a venv must not turn the gate red)
            {"engine/tests/fixtures/g/nodes.json": "{}\n", "engine/tests/fixtures/g/PROVENANCE.json": "{}\n",
             "docs/pillars.svg": "<svg/>\n", "notes.txt": "a\r\nb\r\n", "probe.txt": "id: $Id$\n",
             ".gitattributes": "engine/tests/fixtures/** -text\nprobe.txt -text ident\n"},
            {"engine/tests/fixtures/g/nodes.json": "{}\n", "engine/tests/fixtures/g/PROVENANCE.json": "{}\n",
             "docs/pillars.svg": "<svg/>\n", ".gitignore": ".venv/\n", ".venv/probe/.gitattributes": "* text=auto\n",
             # round 5's innocent: every rewriting attribute switched OFF by name, and git's own no-op encoding — 0 findings
             ".gitattributes": "* -text\ndocs/pillars.svg -text -working-tree-encoding -ident -filter\n"
                               "engine/tests/fixtures/g/nodes.json -text working-tree-encoding=UTF-8\n"}),
        "severance": (
            {"engine/graphy/a.py": "try:\n    import fcntl\nexcept ImportError:\n    def f():\n        pass\n\ndef g():\n    pass\n", "engine/graphy/b.py": "from graphy.a import f\nf()\n",
             "engine/graphy/c.py": "from graphy import a\na.f()\nimport sqlite3\nsqlite3.connect(':memory:').g()\n"},
            {"engine/graphy/a.py": "try:\n    import fcntl\nexcept ImportError:\n    def f():\n        pass\n\ndef g():\n    pass\n", "engine/graphy/b.py": "from graphy.a import f\nf()\n",
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
    if check == "eol-rewritable" and red:
        # a rule file written and never added, and a global one the repo's own config points at: git reads
        # both on this box, no clone ever will — the svg must be named from the index's rules regardless
        (root / "docs" / ".gitattributes").write_text("* -text\n", encoding="utf-8")
        (root / "box_only_attributes").write_text("* -text\n", encoding="utf-8")
        _fixture_git(root, ["git", "config", "core.attributesFile", str(root / "box_only_attributes")])
        # round 3's two: a linked worktree (`.git` a file) whose common dir holds a box-only `* -text` — the
        # index reads unset there and the finding is the info file, located by git and not by a built path;
        # and a worktree whose rule is narrower than the index's — the index says unset, the next add -A
        # ships the narrowing, and only the second read sees it
        wt = root.parent / (root.name + "-wt")
        shutil.rmtree(wt, ignore_errors=True)
        _fixture_git(root, ["git", "worktree", "add", "-q", str(wt), "HEAD"])
        (root / ".git" / "info").mkdir(exist_ok=True)
        (root / ".git" / "info" / "attributes").write_text("* -text\n", encoding="utf-8")
        w2 = _seed({"a.json": "{}\n", "b.svg": "<svg/>\n", ".gitattributes": "* -text\n"})
        (w2 / ".gitattributes").write_text("a.json -text\n", encoding="utf-8")
        # and the rule file DELETED from the worktree, index intact: both reads fall back to the index's copy
        w3 = _seed({"a.json": "{}\n", ".gitattributes": "* -text\n"})
        (w3 / ".gitattributes").unlink()
        try:
            wt_found = check_eol_rewritable(wt)
            w2_found = check_eol_rewritable(w2)
            w3_found = check_eol_rewritable(w3)
        finally:
            _fixture_git(root, ["git", "worktree", "remove", "--force", str(wt)])
            shutil.rmtree(w2, ignore_errors=True)
            shutil.rmtree(w3, ignore_errors=True)
        if not any(f.where.endswith("info/attributes") for f in wt_found):
            raise CheckError("eol-rewritable's worktree fixture: the common dir's info/attributes was not named")
        if not any("this checkout's answer differently" in f.what for f in w2_found):
            raise CheckError("eol-rewritable's narrowed-worktree fixture: the index/worktree disagreement was not named")
        if not any("deleted from the worktree" in f.what for f in w3_found):
            raise CheckError("eol-rewritable's deleted-rule fixture: the deletion was not named")
        (root / ".git" / "info" / "attributes").unlink()
        root_found = CHECKS[check](root)
        if not any(f.what.startswith("`ident`") for f in root_found):
            raise CheckError("eol-rewritable's ident fixture: a `-text` file with `ident` on was not named")
        return root_found + wt_found + w2_found + w3_found
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
