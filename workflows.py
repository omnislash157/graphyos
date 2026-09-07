#!/usr/bin/env python3
"""workflows — every file under .github/workflows/ parsed and shaped, without a dependency.

    python3 workflows.py [DIR]      parse every *.yml under DIR (default .github/workflows); exit 3 naming file:line

A workflow file GitHub cannot parse runs zero jobs and the push reads `failure` with no job to
open — thirty pushes went by that way once (RECON.md §58) while the floor and the gate stayed green
on the box. The gate is the one place that runs on every change, so the gate parses the workflows.

The parser reads the YAML that workflows are written in and nothing more — block mappings and
sequences, plain and quoted scalars, flow `[a, b]` and `{k: v}`, block scalars `|` and `>` —
and it is strict where GitHub is strict: a plain scalar carrying `: ` is a mapping value and
refused (the fault that took the thirty pushes), a tab in indentation is refused, a duplicate key
is refused, a plain scalar that continues on the next line is refused (quote it or use `|`).
Every refusal carries the file and the line. Every value stays a string; the shape check reads
keys, never types.

The shape: the top level carries `name`, `on` and `jobs` and nothing GitHub does not know; every
job carries `runs-on` and `steps` (or `uses`, a reusable workflow); `needs` names a job that
exists; every step carries `uses` or `run` and only keys GitHub knows.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DIR = HERE / ".github" / "workflows"

TOP_KEYS = {"name", "run-name", "on", "permissions", "env", "defaults", "concurrency", "jobs"}
JOB_KEYS = {"name", "needs", "if", "runs-on", "permissions", "environment", "concurrency", "outputs", "env",
            "defaults", "steps", "timeout-minutes", "strategy", "continue-on-error", "container", "services",
            "uses", "with", "secrets"}
STEP_KEYS = {"id", "if", "name", "uses", "run", "working-directory", "shell", "with", "env",
             "continue-on-error", "timeout-minutes"}


class WorkflowError(Exception):
    """A refusal with its line: `str(exc)` reads `line N: why`."""

    def __init__(self, line: int, why: str):
        super().__init__(f"line {line}: {why}")
        self.line = line
        self.why = why


# ── the parser ───────────────────────────────────────────────────────────────────────────────

def _strip_comment(s: str) -> str:
    """Drop a ` #…` comment outside quotes. A `#` glued to text is text (`a#b`)."""
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote and not (quote == '"' and i > 0 and s[i - 1] == "\\"):
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


def _lines(text: str) -> list[tuple[int, int, str]]:
    """(lineno, indent, content) for every line that carries content; a tab in the indent refuses."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        if raw.strip() == "" or raw.lstrip().startswith("#"):
            continue
        stripped = raw.lstrip(" ")
        if stripped.startswith("\t"):
            raise WorkflowError(n, "a tab in the indentation — YAML indents with spaces")
        out.append((n, len(raw) - len(stripped), _strip_comment(stripped.rstrip())))
    return out


def _scalar(s: str, line: int) -> str:
    """A scalar on one line: quoted, flow, or plain. Plain carrying `: ` is a mapping value — refused."""
    s = s.strip()
    if s == "":
        return ""
    if s[0] == '"':
        return _double(s, line)
    if s[0] == "'":
        return _single(s, line)
    if s[0] in "[{":
        return _flow(s, line)
    if ": " in s or s.endswith(":"):
        raise WorkflowError(line, f"mapping values are not allowed here — the plain scalar {s!r} carries ': '; quote it")
    if s[0] in "&*!%@`|>":
        raise WorkflowError(line, f"the plain scalar {s!r} starts with {s[0]!r}, which YAML reads as syntax; quote it")
    return s


def _double(s: str, line: int) -> str:
    out, i = [], 1
    while i < len(s):
        ch = s[i]
        if ch == "\\":
            if i + 1 >= len(s):
                raise WorkflowError(line, "a backslash ends the line inside a double-quoted scalar")
            esc = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\", " ": " ", "/": "/"}.get(esc, "\\" + esc))
            i += 2
            continue
        if ch == '"':
            rest = s[i + 1:].strip()
            if rest:
                raise WorkflowError(line, f"text after the closing quote: {rest!r}")
            return "".join(out)
        out.append(ch)
        i += 1
    raise WorkflowError(line, "an unclosed double-quoted scalar")


def _single(s: str, line: int) -> str:
    out, i = [], 1
    while i < len(s):
        ch = s[i]
        if ch == "'":
            if s[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
                continue
            rest = s[i + 1:].strip()
            if rest:
                raise WorkflowError(line, f"text after the closing quote: {rest!r}")
            return "".join(out)
        out.append(ch)
        i += 1
    raise WorkflowError(line, "an unclosed single-quoted scalar")


def _flow(s: str, line: int):
    """`[a, "b", [c]]` and `{k: v, k2: v2}` on one line."""
    pos = 0

    def skip_ws():
        nonlocal pos
        while pos < len(s) and s[pos] == " ":
            pos += 1

    def item(stop: str):
        nonlocal pos
        skip_ws()
        if pos >= len(s):
            raise WorkflowError(line, f"an unclosed flow collection: {s!r}")
        ch = s[pos]
        if ch in "[{":
            return collection()
        if ch in "'\"":
            start, q = pos, ch
            pos += 1
            while pos < len(s):
                if s[pos] == q:
                    if q == "'" and s[pos + 1:pos + 2] == "'":
                        pos += 2
                        continue
                    if q == '"' and s[pos - 1] == "\\":
                        pos += 1
                        continue
                    break
                pos += 1
            if pos >= len(s):
                raise WorkflowError(line, f"an unclosed quote inside {s!r}")
            pos += 1
            return _scalar(s[start:pos], line)
        start = pos
        while pos < len(s) and s[pos] not in stop:
            pos += 1
        text = s[start:pos].strip()
        if ": " in text or text.endswith(":"):
            raise WorkflowError(line, f"mapping values are not allowed here — {text!r} inside {s!r}; quote it")
        return text

    def collection():
        nonlocal pos
        open_ch = s[pos]
        close = "]" if open_ch == "[" else "}"
        pos += 1
        out = [] if open_ch == "[" else {}
        while True:
            skip_ws()
            if pos >= len(s):
                raise WorkflowError(line, f"an unclosed flow collection: {s!r}")
            if s[pos] == close:
                pos += 1
                return out
            if open_ch == "[":
                out.append(item(",]"))
            else:
                key = item(":,}")
                skip_ws()
                if pos < len(s) and s[pos] == ":":
                    pos += 1
                    val = item(",}")
                else:
                    val = ""
                if key in out:
                    raise WorkflowError(line, f"duplicate key {key!r} inside {s!r}")
                out[key] = val
            skip_ws()
            if pos < len(s) and s[pos] == ",":
                pos += 1
            elif pos < len(s) and s[pos] != close:
                raise WorkflowError(line, f"expected ',' or '{close}' at column {pos + 1} of {s!r}")

    val = collection()
    skip_ws()
    if pos != len(s):
        raise WorkflowError(line, f"text after the flow collection: {s[pos:]!r}")
    return val


def _split_key(content: str, line: int) -> tuple[str, str] | None:
    """`key: value` / `key:` → (key, rest); None when the line is not a mapping entry."""
    if content[0] in "'\"":
        q = content[0]
        i = 1
        while i < len(content):
            if content[i] == q and not (q == '"' and content[i - 1] == "\\"):
                if q == "'" and content[i + 1:i + 2] == "'":
                    i += 2
                    continue
                break
            i += 1
        if i >= len(content):
            return None
        key = _scalar(content[:i + 1], line)
        rest = content[i + 1:]
        if key != "" and (rest == ":" or rest.startswith(": ")):
            return key, rest[1:].strip()
        return None
    if content.endswith(":") and ": " not in content:
        key = content[:-1]
    elif ": " in content:
        key, _, rest = content.partition(": ")
        if "'" in key or '"' in key or "[" in key or "{" in key or not _is_key(key.strip()):
            return None
        return key.strip(), rest.strip()
    else:
        return None
    if "'" in key or '"' in key or "[" in key or "{" in key or not _is_key(key.strip()):
        return None
    return key.strip(), ""


def _is_key(key: str) -> bool:
    """A plain key is non-empty and not a sequence entry."""
    return key != "" and key != "-" and not key.startswith("- ")


class _Parser:
    def __init__(self, text: str):
        self.lines = _lines(text)
        self.i = 0

    def peek(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse(self):
        if not self.lines:
            return {}
        doc = self.node(self.lines[0][1])
        if self.i < len(self.lines):
            n, ind, content = self.lines[self.i]
            raise WorkflowError(n, f"bad indentation: {content!r} at column {ind + 1} belongs to nothing above it")
        return doc

    def node(self, indent: int):
        n, ind, content = self.peek()
        if ind != indent:
            raise WorkflowError(n, f"bad indentation: expected column {indent + 1}, got {ind + 1}")
        if content == "-" or content.startswith("- "):
            return self.sequence(indent)
        if _split_key(content, n) is not None:
            return self.mapping(indent)
        raise WorkflowError(n, f"a plain scalar where a mapping or sequence was expected: {content!r}")

    def block_scalar(self, header: str, indent: int, line: int) -> str:
        """`|` / `>` with chomping (`-` `+`) and an optional explicit indent digit."""
        style, rest = header[0], header[1:]
        if rest and not all(c in "+-0123456789" for c in rest):
            raise WorkflowError(line, f"text after the block scalar indicator: {header!r}")
        raws = self.text.splitlines()
        body, k = [], line          # line numbers are 1-based; raws[line] is the next line
        block_indent = None
        while k < len(raws):
            raw = raws[k]
            if raw.strip() == "":
                body.append("")
                k += 1
                continue
            width = len(raw) - len(raw.lstrip(" "))
            if block_indent is None:
                if width <= indent:
                    break
                block_indent = width
            if width < block_indent:
                if width > indent:
                    raise WorkflowError(k + 1, f"a block scalar line less indented than its first line: {raw.strip()!r}")
                break
            body.append(raw[block_indent:])
            k += 1
        while self.i < len(self.lines) and self.lines[self.i][0] <= k:
            self.i += 1
        while body and body[-1] == "":
            body.pop()
        text = "\n".join(body)
        if style == ">":
            text = " ".join(ln if ln else "\n" for ln in body)
        return text + ("" if rest.endswith("-") else "\n") if body else ""

    def value(self, rest: str, indent: int, line: int):
        """The value after `key: ` or `- `: inline, block scalar, or a nested block on the next lines."""
        if rest == "":
            nxt = self.peek()
            if nxt is None or nxt[1] <= indent:
                if nxt is not None and nxt[1] == indent and (nxt[2] == "-" or nxt[2].startswith("- ")):
                    return self.sequence(indent)          # a sequence at the key's own indent
                return None
            return self.node(nxt[1])
        if rest[0] in "|>":
            return self.block_scalar(rest, indent, line)
        val = _scalar(rest, line)
        nxt = self.peek()
        if nxt is not None and nxt[1] > indent:
            raise WorkflowError(nxt[0], f"a plain scalar continues on the next line ({nxt[2]!r}) — quote it or use |")
        return val

    def mapping(self, indent: int) -> dict:
        out = {}
        while True:
            cur = self.peek()
            if cur is None or cur[1] < indent:
                return out
            n, ind, content = cur
            if ind > indent:
                raise WorkflowError(n, f"bad indentation: {content!r} at column {ind + 1}, the mapping is at column {indent + 1}")
            if content == "-" or content.startswith("- "):
                return out                     # a sequence at the same indent closes the mapping (the caller decides)
            kv = _split_key(content, n)
            if kv is None:
                raise WorkflowError(n, f"mapping values are not allowed here — {content!r} is not `key: value`")
            key, rest = kv
            if key in out:
                raise WorkflowError(n, f"duplicate key {key!r}")
            self.i += 1
            out[key] = self.value(rest, indent, n)

    def sequence(self, indent: int) -> list:
        out = []
        while True:
            cur = self.peek()
            if cur is None or cur[1] < indent:
                return out
            n, ind, content = cur
            if ind > indent:
                raise WorkflowError(n, f"bad indentation: {content!r} at column {ind + 1}, the sequence is at column {indent + 1}")
            if not (content == "-" or content.startswith("- ")):
                return out
            rest = content[1:].lstrip(" ")
            if rest == "":
                self.i += 1
                nxt = self.peek()
                out.append(self.node(nxt[1]) if nxt is not None and nxt[1] > indent else None)
                continue
            inner = indent + (len(content) - len(rest))
            if _split_key(rest, n) is not None:
                self.lines[self.i] = (n, inner, rest)      # `- key: v` is a mapping at the content's column
                out.append(self.mapping(inner))
                continue
            self.i += 1
            out.append(self.value(rest, indent, n))


def parse(text: str):
    p = _Parser(text)
    p.text = text
    return p.parse()


# ── the shape ────────────────────────────────────────────────────────────────────────────────

def check_shape(doc) -> list[str]:
    red = []
    if not isinstance(doc, dict):
        return ["the document is not a mapping"]
    for k in ("name", "on", "jobs"):
        if k not in doc:
            red.append(f"no top-level {k!r}")
    for k in doc:
        if k not in TOP_KEYS:
            red.append(f"top-level key {k!r} is not one GitHub knows")
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return red + ["'jobs' is not a mapping of at least one job"]
    for jid, job in jobs.items():
        if not isinstance(job, dict):
            red.append(f"job {jid!r} is not a mapping")
            continue
        for k in job:
            if k not in JOB_KEYS:
                red.append(f"job {jid!r}: key {k!r} is not one GitHub knows")
        if "uses" in job:
            continue
        for k in ("runs-on", "steps"):
            if k not in job:
                red.append(f"job {jid!r} has no {k!r}")
        needs = job.get("needs")
        for dep in ([needs] if isinstance(needs, str) else needs or []):
            if dep not in jobs:
                red.append(f"job {jid!r} needs {dep!r}, which is not a job")
        steps = job.get("steps")
        if steps is None:
            continue
        if not isinstance(steps, list) or not steps:
            red.append(f"job {jid!r}: 'steps' is not a sequence of at least one step")
            continue
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                red.append(f"job {jid!r} step {i} is not a mapping")
                continue
            if ("uses" in step) == ("run" in step):
                red.append(f"job {jid!r} step {i}: a step carries exactly one of 'uses' and 'run'")
            for k in step:
                if k not in STEP_KEYS:
                    red.append(f"job {jid!r} step {i}: key {k!r} is not one GitHub knows")
    return red


def check_file(path: Path) -> tuple[list[str], str]:
    """The refusals for one file, each `file:line: why` or `file: why`, and a one-line note."""
    try:
        doc = parse(path.read_text(encoding="utf-8"))
    except WorkflowError as exc:
        return [f"{path}:{exc.line}: {exc.why}"], "unparseable"
    red = [f"{path}: {r}" for r in check_shape(doc)]
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    nj = len(jobs) if isinstance(jobs, dict) else 0
    ns = sum(len(j.get("steps") or []) for j in jobs.values() if isinstance(j, dict)) if isinstance(jobs, dict) else 0
    return red, f"{nj} job(s) · {ns} step(s)"


def check_dir(d: Path) -> tuple[list[str], list[str]]:
    red, notes = [], []
    files = sorted(p for p in d.iterdir() if p.suffix in (".yml", ".yaml")) if d.is_dir() else []
    for f in files:
        r, note = check_file(f)
        red += r
        notes.append(f"{f.name}: {note}")
    if not files:
        red.append(f"{d}: no workflow file to parse")
    return red, notes


def main(argv: list[str]) -> int:
    d = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_DIR
    red, notes = check_dir(d)
    for r in red:
        print(f"WORKFLOWS RED {r}")
    for n in notes:
        print(f"  {n}")
    if red:
        print(f"WORKFLOWS RED: {len(red)} refusal(s) over {len(notes)} file(s) under {d}")
        return 3
    print(f"WORKFLOWS OK: {len(notes)} file(s) under {d} parse and carry name · on · jobs, every step uses or runs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
