#!/usr/bin/env python3
"""scrub — the prose scrub that never names what it scrubs.

The private markers are words that must not travel. A tracked list of them would itself travel,
so the list is keyed: `.private_markers.sha256` holds an HMAC-SHA256 of each marker, normalized
to lowercase alphanumerics with every space and underscore removed, under a key that lives only
in `.private_key` beside this file — gitignored, never tracked, written once by `--keygen`. A
plain hash of a word is reversible by a wordlist (a company name is a public fact); a keyed one
is not without the key. A file is scanned as the same normalized tokens, single and adjacent-pair,
and a hit is a token whose keyed digest is in the list. The digests name nothing; the local
operator regenerates them with `scrub.py --hash <word>…`.

A box without the key (CI) cannot run the hashed sweep and says so: `SCRUB SKIPPED`, exit 0 —
the words are absent from the tree, which the sweep proves on the operator's box, where the gate
and the census run before every cut.

    scrub.py <file>…            print each hit as <file>:<line>; exit 3 when any
    scrub.py --tracked          every git-tracked file outside staging/ (the public cut's tripwire)
    scrub.py --tree <dir>       every file under a directory, skipping build and substrate dirs
    scrub.py --issues <o>/<r>   every issue and pull request on GitHub — title, body, each comment — named
                                `#N body:<line>`; refuses when the fetch fails, never a clean zero (off-box: gh)
    scrub.py --text <file|->    one draft before it is posted, the same digests
    scrub.py --gh-hook          the PreToolUse hook: a gh post — `issue|pr create|new|comment|edit|close|reopen`,
                                `pr review|merge`, `release create|new|edit`, `label|repo create|edit`, `issue develop`,
                                `project item-create`, `workflow run` — whose posted words carry a marker, or whose
                                body the hook cannot read, is blocked (exit 2) before it posts
    scrub.py --hash <word>…     print the keyed digests for words (to write the list)
    scrub.py --keygen           write a fresh key to .private_key; refuses when one stands
    scrub.py --key <path> …     read the key from another path (first), for a checkout that has none
"""
from __future__ import annotations

import hmac
import json
import re
import secrets
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIST = HERE / ".private_markers.sha256"
KEY = HERE / ".private_key"
_TOKEN = re.compile(r"[a-z0-9]+")
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "substrate", "venv", ".venv"}
_SKIP_FILE_PREFIX = ("tenant.",)


def load_key(path: Path | None = None) -> bytes | None:
    """The key's bytes, or None when the box has no key file (or an empty one)."""
    path = KEY if path is None else path
    if not path.is_file():
        return None
    key = path.read_text(encoding="utf-8").strip()
    return key.encode("utf-8") or None


_PRIMED: dict[bytes, hmac.HMAC] = {}
_SEEN: dict[tuple[bytes, str], str] = {}


def keyed(word: str, key: bytes) -> str:
    """HMAC-SHA256 of a token under the key. The keyed state is primed once per key and copied per
    token, and a token's digest is remembered — a sweep sees the same few thousand tokens over and
    over, so the keyed sweep costs no more than the plain hash it replaced."""
    k = (key, word)
    d = _SEEN.get(k)
    if d is None:
        h = _PRIMED.get(key)
        if h is None:
            h = _PRIMED[key] = hmac.new(key, b"", "sha256")
        h = h.copy()
        h.update(word.encode("utf-8"))
        d = _SEEN[k] = h.hexdigest()
    return d


def norm_hash(word: str, key: bytes) -> str:
    w = re.sub(r"[\s_]+", "", word.lower())
    return keyed(w, key)


def load_list(path: Path | None = None) -> frozenset[str]:
    path = LIST if path is None else path
    if not path.is_file():
        sys.exit(f"SCRUB REFUSED: no marker list at {path} — the scrub cannot run without one; "
                 f"write it with `scrub.py --hash <word>…` (the words never travel, their keyed digests do)")
    return frozenset(ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#"))


def hits_in(path: Path, hashes: frozenset[str], key: bytes) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return hits_in_text(text, hashes, key)


def hits_in_text(text: str, hashes: frozenset[str], key: bytes) -> list[tuple[int, str]]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        toks = _TOKEN.findall(line.lower())
        cands = toks + [a + b for a, b in zip(toks, toks[1:])]
        for c in cands:
            if keyed(c, key) in hashes:
                out.append((n, c))
                break
    return out


def tracked_outside_staging() -> list[Path]:
    files = subprocess.run(["git", "ls-files"], cwd=HERE, capture_output=True, text=True, check=True).stdout.split("\n")
    return [HERE / f for f in files if f and not f.startswith("staging/") and (HERE / f).is_file()]


def tree(root: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts[:-1])
        if parts & _SKIP_DIRS or any(part.startswith("substrate.") or part.endswith(".egg-info") for part in parts):
            continue
        if p.name.startswith(_SKIP_FILE_PREFIX) and p.name.endswith(".json"):
            continue
        out.append(p)
    return out


class FetchError(Exception):
    """The surface could not be read whole: a refusal, never a clean zero."""


def fetch_surface(repo: str) -> list[tuple[str, str]]:
    """(label, text) for every issue and pull request of `repo`, open or closed: its title, its body and each
    comment. The tracker is public and permanent, and it is where a project's evidence gets written (#91)."""
    out: list[tuple[str, str]] = []
    for kind in ("issue", "pr"):
        proc = subprocess.run(["gh", kind, "list", "--repo", repo, "--state", "all", "--limit", "5000",
                               "--json", "number,title,body,comments"], capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise FetchError(f"`gh {kind} list --repo {repo}` exited {proc.returncode}: {(proc.stderr or '').strip()[:200]}")
        try:
            rows = json.loads(proc.stdout)
        except ValueError as exc:
            raise FetchError(f"`gh {kind} list --repo {repo}` did not answer JSON ({exc})") from exc
        if not isinstance(rows, list):
            raise FetchError(f"`gh {kind} list --repo {repo}` answered {type(rows).__name__}, not a list")
        if len(rows) >= 5000:
            raise FetchError(f"`gh {kind} list --repo {repo}` answered its whole limit of 5000 — the read may be partial")
        for r in rows:
            n = r.get("number")
            tag = "#" if kind == "issue" else "PR #"
            out.append((f"{tag}{n} title", r.get("title") or ""))
            out.append((f"{tag}{n} body", r.get("body") or ""))
            for i, c in enumerate(r.get("comments") or [], 1):
                out.append((f"{tag}{n} comment {i}", (c or {}).get("body") or ""))
    return out


_GH_WORD = re.compile(r"(?<![\w.-])gh\b")
_POST_VERB = re.compile(r"\b(?:create|new|comment|edit|close|reopen|review|merge|develop|item-create|workflow)\b")
_POSTS = {("issue", v) for v in ("create", "new", "comment", "edit", "close", "reopen")} | \
         {("pr", v) for v in ("create", "new", "comment", "edit", "close", "reopen", "review", "merge")} | \
         {("release", "create"), ("release", "new"), ("release", "edit"), ("label", "create"), ("label", "edit"),
          ("repo", "create"), ("repo", "edit"),           # `new` is gh's own alias of create (#91 round 7); a repo's description travels
          ("issue", "develop"), ("project", "item-create"), ("workflow", "run")}   # a branch name, a project item, a run's inputs travel (round 8)
_TEXT_FLAGS = {"--title", "-t", "--body", "-b", "--comment", "-c", "--notes", "-n", "--subject"}
_FILE_FLAGS = {"--body-file", "-F", "--notes-file"}
_REPO_FLAGS = {"-R", "--repo"}
_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&"}
_SHELLS = {"sh", "bash", "zsh", "dash"}
_PREFIX_WORDS = {"if", "while", "until", "function", "do", "then", "else", "elif", "time", "env", "nohup", "nice", "command",
                 "builtin", "exec", "sudo", "!", "{"}
_PREFIX_VALUE_FLAGS = {"nice": {"-n"}, "sudo": {"-u", "-g", "-C", "-p", "-h", "-r", "-t", "-U"}, "env": {"-u", "-C", "-S"},
                       "command": {"-v", "-V"}, "exec": {"-a"}}   # a prefix word's own flags that take the next word (round 14)
_REDIRECT = re.compile(r"(\d*|&)(>&|<&|>>?|>\||<)(\S*)")
_UNREADABLE_RUNNERS = {"xargs", "parallel"}


class CouldNotTell(Exception):
    """A posted body the hook cannot read: the post is refused, never let through unscrubbed."""


_DELIM = re.compile(r"<<(-?)[ \t]*((?:'[^'\n]*'|\"[^\"\n]*\"|\\.|[^\s;&|()<>'\"\\])+)")


def _delimiter(raw: str) -> tuple[str, bool]:
    """A heredoc delimiter as bash reads it: quotes and backslashes removed; any of them makes the body literal."""
    quoted = any(ch in raw for ch in "'\"\\")
    text = re.sub(r"'([^']*)'|\"([^\"]*)\"|\\(.)", lambda m: next(g for g in m.groups() if g is not None), raw)
    return text, quoted


def _heredoc_body(s: str, j: int, delim: str, tabs: bool) -> tuple[str, int]:
    """The body from index j to the line that is exactly the delimiter (leading tabs removed only under `<<-`), and the
    index past that line. Bash's end line is exact: ` EOF` and `EOF ` are body lines (#91 round 5)."""
    body, n = [], len(s)
    while True:
        if j > n or (j == n and not body and delim):
            raise CouldNotTell(f"a heredoc never reaches its `{delim}`")
        k = s.find("\n", j)
        k = n if k < 0 else k
        line = s[j:k]
        if (line.lstrip("\t") if tabs else line) == delim:
            return "\n".join(body), k + 1
        if k >= n:
            raise CouldNotTell(f"a heredoc never reaches its `{delim}`")
        body.append(line)
        j = k + 1


def _heredoc_at(s: str, k: int) -> tuple[int, str, bool, int]:
    """At `<<` in s: (index past the opener token, body, delimiter quoted, index past the end line). The body starts on
    the line after the opener's line."""
    m = _DELIM.match(s, k)
    if not m or s.startswith("<<<", k):
        raise CouldNotTell("a heredoc names no delimiter")
    delim, quoted = _delimiter(m.group(2))
    nl = s.find("\n", m.end())
    if nl < 0:
        raise CouldNotTell("a heredoc opens on the last line and has no body")
    body, end = _heredoc_body(s, nl + 1, delim, m.group(1) == "-")
    return m.end(), body, quoted, end


def _substitutions(word: str) -> list[str]:
    """The command inside every `$(…)` and every backtick pair of a word, outermost first — a post standing there
    is a command bash runs, whatever the word around it is for (#91 round 10)."""
    out, i, n = [], 0, len(word)
    while i < n:
        if word.startswith("$(", i) and not word.startswith("$((", i):
            try:
                k = _close_paren(word, i + 1)
            except CouldNotTell:
                break
            out.append(word[i + 2:k])
            i = k + 1
        elif word[i] == "`":
            k = word.find("`", i + 1)
            if k < 0:
                break
            out.append(word[i + 1:k])
            i = k + 1
        else:
            i += 1
    return out


def _close_paren(s: str, p: int) -> int:
    """The `)` closing the `(` at p. A heredoc inside is jumped whole by bash's rules — its body is prose, and a `1)`
    in a list is not shell."""
    depth, k = 0, p
    while k < len(s):
        if s.startswith("<<", k) and not s.startswith("<<<", k) and _DELIM.match(s, k):
            opener_end, _body, _q, end = _heredoc_at(s, k)
            rest = s[opener_end:s.find("\n", opener_end)]           # the opener line after the delimiter is still code
            depth += rest.count("(") - rest.count(")")
            if depth <= 0 and ")" in rest:
                return opener_end + rest.index(")")
            k = end
            continue
        depth += {"(": 1, ")": -1}.get(s[k], 0)
        if depth == 0:
            return k
        k += 1
    raise CouldNotTell("a `$(` never closes")


class _Parsed:
    """A command as bash words: each word's text, whether the shell builds it (`built`), whether its first character
    was unquoted (`bare` — only a bare `>` or `<` is a redirection), and every heredoc the command opens, each with
    the index of the first word of the segment it feeds and whether its delimiter was quoted."""

    def __init__(self):
        self.words: list[str] = []
        self.built: list[bool] = []
        self.bare: list[bool] = []
        self.heredocs: list[tuple[int, str, bool]] = []      # (word index at the opener, body, delimiter quoted)


def _words(command: str) -> _Parsed:
    """Bash words, quote-aware: single quotes literal, a word marked built when a `$…` or a backtick sits outside
    them, and a heredoc recognised only at an UNQUOTED `<<` — its body is text for the command it feeds, never words
    of this one (#91 round 4: a quoted body that quotes a heredoc repro had its lines cut out unscrubbed)."""
    s = command
    out = _Parsed()
    cur: list[str] = []
    state = {"has": False, "expand": False, "bare": False}
    pending: list[tuple[int, str, bool, bool]] = []            # (word index, delimiter, quoted, strip tabs)

    def push():
        if state["has"]:
            out.words.append("".join(cur))
            out.built.append(state["expand"])
            out.bare.append(state["bare"])
        cur.clear()
        state.update(has=False, expand=False, bare=False)

    def lit(text: str, unquoted: bool):
        if not state["has"]:
            state["bare"] = unquoted
        cur.append(text)
        state["has"] = True

    def dollar(at: int) -> int | None:
        """At a `$` the shell expands — anything but a `$` before whitespace, the end or a closing quote."""
        nxt = s[at + 1] if at + 1 < len(s) else ""
        if nxt == "(":
            k = _close_paren(s, at + 1)
            lit(s[at:k + 1], False)
            state["expand"] = True
            return k + 1
        if nxt == "" or nxt.isspace() or nxt == '"':
            return None
        lit("$", False)
        state["expand"] = True
        return at + 1

    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\n":
            push()
            j = i + 1
            for idx, delim, quoted, tabs in pending:            # bodies follow the line that opened them, in order
                body, j = _heredoc_body(s, j, delim, tabs)
                out.heredocs.append((idx, body, quoted))
            pending.clear()
            if out.words and out.words[-1] not in _SEPARATORS:
                out.words.append(";")                            # a newline ends a command
                out.built.append(False)
                out.bare.append(True)
            i = j
        elif c in " \t":
            push()
            i += 1
        elif c == "&" and s[i:i + 2] != "&&" and (
                (state["has"] and state["bare"] and re.fullmatch(r"\d*(?:>>?|<)", "".join(cur))) or s[i + 1:i + 2] == ">"):
            lit("&", True)                                       # `2>&1` · `>& F` · `&> F`: one redirection word (round 9)
            i += 1
        elif c in ";&|()":
            push()
            op = s[i:i + 2] if s[i:i + 2] in ("&&", "||", ";;", "|&") else c
            out.words.append(op)
            out.built.append(False)
            out.bare.append(True)
            i += len(op)
        elif c == "<" and s.startswith("<<", i) and not s.startswith("<<<", i):
            push()
            m = _DELIM.match(s, i)
            if not m:
                raise CouldNotTell("a heredoc names no delimiter")
            delim, quoted = _delimiter(m.group(2))
            seg = len(out.words)
            while seg > 0 and out.words[seg - 1] not in _SEPARATORS:
                seg -= 1
            pending.append((seg, delim, quoted, m.group(1) == "-"))
            i = m.end()
        elif c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                raise CouldNotTell("the command does not parse as shell words (an unclosed ')")
            lit(s[i + 1:j], False)
            i = j + 1
        elif c == "\\":
            if s[i + 1:i + 2] == "\n":                            # a line continuation joins the words
                i += 2
                continue
            lit(s[i + 1:i + 2], False)
            i += 2
        elif c == '"':
            j = i + 1
            if not state["has"]:
                state["bare"] = False
            state["has"] = True
            while j < n and s[j] != '"':
                if s[j] == "\\" and j + 1 < n:
                    if s[j + 1] != "\n":                          # inside double quotes a backslash-newline vanishes
                        cur.append(s[j + 1])
                    j += 2
                elif s[j] == "$" and (k := dollar(j)) is not None:
                    j = k
                elif s[j] == "`":
                    k = s.find("`", j + 1)
                    k = n - 1 if k < 0 else k
                    cur.append(s[j:k + 1])
                    state["expand"] = True
                    j = k + 1
                else:
                    cur.append(s[j])
                    j += 1
            if j >= n:
                raise CouldNotTell('the command does not parse as shell words (an unclosed ")')
            i = j + 1
        elif c == "$" and (k := dollar(i)) is not None:
            i = k
        elif c == "`":
            k = s.find("`", i + 1)
            k = n - 1 if k < 0 else k
            lit(s[i:k + 1], False)
            state["expand"] = True
            i = k + 1
        elif c == "#" and not state["has"]:
            k = s.find("\n", i)
            i = n if k < 0 else k
        else:
            lit(c, True)
            i += 1
    push()
    if pending:
        raise CouldNotTell("a heredoc opens on the last line and has no body")
    return out


def _expand(text: str, env: dict, here: Path | None) -> str:
    """What bash would put in a word the shell builds, when that is statically readable: `$NAME`/`${NAME}` for a name
    this command assigns (or `HOME`/`PWD`), and `$(cat F)` · `$(<F)` · `` `cat F` `` as F's bytes. The hook's own
    environment is never read for anything else — it is not the Bash tool's shell (#91 round 3). Anything else —
    another command's output, a positional or special parameter, an unset name — is CouldNotTell."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "$" and text[i + 1:i + 2] == "(":
            k = _close_paren(text, i + 1)
            out.append(_substitute(text[i + 2:k], env, here))
            i = k + 1
        elif c == "`":
            k = text.find("`", i + 1)
            if k < 0:
                raise CouldNotTell("a backtick never closes")
            out.append(_substitute(text[i + 1:k], env, here))
            i = k + 1
        elif c == "$" and (m := re.match(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))", text[i:])):
            name = m.group(1) or m.group(2)
            if name not in env:
                raise CouldNotTell(f"${name} is not set by this command")
            out.append(env[name])
            i += m.end()
        elif c == "$" and i + 1 < n and not text[i + 1].isspace():
            raise CouldNotTell(f"`${text[i + 1]}` is a parameter the hook cannot see")
        else:
            out.append(c)
            i += 1
    return "".join(out)


_WRITTEN, _UNKNOWN_WRITER = "\0written", "\0unknown"   # keys no shell name can spell: what the command wrote so far


def _mark_writer(env: dict, who: str) -> None:
    """A command that may write anything ran: the holder is shared with every walk of this shell (#91 round 11)."""
    h = env[_UNKNOWN_WRITER]
    h[0] = h[0] or who


def child_env(env: dict) -> dict:
    """What a child shell inherits: the directory and this command's writes so far — never an unexported name (round 12)."""
    return {k: env[k] for k in ("HOME", "PWD", _WRITTEN, _UNKNOWN_WRITER) if k in env}


def _nested(script: str, where: str | None, depth: int, env: dict | None = None) -> list[tuple[str, str]]:
    """A script inside a shell, an eval or a substitution: walked; past the depth cap, refused when it could post."""
    if depth >= 3:
        if _GH_WORD.search(script) and _POST_VERB.search(script):
            raise CouldNotTell("a post nested more than three shells deep cannot be read")
        return []
    return posted_texts(script, where, depth, env)


def _read(path: str, here: Path | None, env: dict | None = None) -> str:
    """A file's bytes as bash would find them when the post runs: a file this command wrote earlier is its written
    content when that is known (`cat > F <<EOF`), and CouldNotTell otherwise (#91 round 6)."""
    import os
    p = Path(os.path.expanduser(path))
    if not p.is_absolute():
        if here is None:
            raise CouldNotTell(f"{path} is relative to a directory the hook could not follow")
        p = here / p
    p = Path(os.path.normpath(p))
    if env is not None:
        if env.get(_UNKNOWN_WRITER, [""])[0]:
            raise CouldNotTell(f"{path} is read after `{env[_UNKNOWN_WRITER][0]}` runs, which may write it")
        for target, content in (env.get(_WRITTEN) or {}).items():
            if p == target or target in p.parents:
                if content is None or target != p:
                    raise CouldNotTell(f"{path} is written earlier in this command in a way the hook cannot read")
                return content
    return p.read_text(encoding="utf-8", errors="replace")


def _substitute(inner: str, env: dict, here: Path | None) -> str:
    h = re.match(r"\s*cat\s+(?=<<[^<])", inner)
    if h:                                                        # $(cat <<EOF … EOF): the body, by bash's end line
        opener_end, body, quoted, end = _heredoc_at(inner, h.end())
        if inner[opener_end:inner.find("\n", opener_end)].strip() or inner[end:].strip():
            raise CouldNotTell(f"`$({inner.strip()[:40]})` does more than cat one heredoc")
        return body if quoted else _expand(body, env, here)
    m = re.fullmatch(r"\s*(?:cat\s+|<\s*)(\S+)\s*", inner)
    if not m:
        raise CouldNotTell(f"`$({inner.strip()[:40]})` posts another command's output, which the hook cannot read")
    path = _expand(m.group(1).strip("'\""), env, here)
    try:
        return _read(path, here, env)
    except OSError as exc:
        raise CouldNotTell(f"`$({inner.strip()[:40]})` reads a file that cannot be read ({type(exc).__name__})") from exc


_STDIN_PATHS = re.compile(r"-|/dev/stdin|/dev/fd/\d+|/proc/(?:self|\d+)/fd/\d+")


def posted_texts(command: str, cwd: str | None, _depth: int = 0, _env: dict | None = None) -> list[tuple[str, str]]:
    """The words a `gh` post in this command would send, read statically from its shell words; a word it cannot read
    refuses the post (CouldNotTell), never passes it. A post is any word named `gh` whose group and verb — after
    `-R`/`--repo` wherever they sit, and expanded when the shell builds them — is an issue, pr or release post; `sh -c`,
    `eval` and a heredoc fed to a shell are read the same way. EVERY word after that head travels and is scrubbed, no
    flag's arity assumed, except its envelope: a `--repo` value, a body-file path (whose file is read instead — the
    segment's heredoc for `-`, `/dev/stdin`, `/dev/fd/N`), and a bare redirection with its target. A word the shell
    builds is expanded when static (`$NAME` this command assigns, `HOME`, `PWD`, `$(cat F)`) and refused otherwise.

    The limit, by name: this reads the command the Bash tool was handed, not what runs — a post from a script file, a
    sourced file, a function defined in an earlier call, `$cmd` as the command word, `env -S`, a subprocess, `gh api`,
    `gh pr create --fill`, or an editor is not seen; an argv-level `gh` shim is the complete form (#131)."""
    import os
    here: Path | None = Path(cwd or os.getcwd())
    # a `$(…)` runs in this shell; `~` is bash's `$HOME`, which Python's expanduser ignores on Windows (graphyos #127)
    env = dict(_env) if _env is not None else {"HOME": os.environ.get("HOME") or os.path.expanduser("~"), "PWD": str(here)}
    texts: list[tuple[str, str]] = []
    parsed = _words(command)
    tokens, built, bare = parsed.words, parsed.built, parsed.bare

    def seg_end(start: int) -> int:
        k = start
        while k < len(tokens) and tokens[k] not in _SEPARATORS:
            k += 1
        return k

    def heredocs_of(start: int) -> list[tuple[str, bool]]:
        return [(body, quoted) for idx, body, quoted in parsed.heredocs if idx == start]

    def word_text(label: str, val: str, expands: bool) -> None:
        if expands:
            try:
                texts.append((label, _expand(val, env, here)))
            except CouldNotTell as exc:
                raise CouldNotTell(f"{label} is built by the shell and {exc} — write the body to a file and pass --body-file") from exc
        else:
            texts.append((label, val))

    def body_file(flag: str, val: str, expands: bool, seg: int) -> None:
        path = _expand(val, env, here) if expands else val
        if _STDIN_PATHS.fullmatch(path):
            fed = heredocs_of(seg_origin)
            if not fed:
                raise CouldNotTell(f"{flag} {path} reads the body from a pipe the hook cannot see — write it to a file")
            for body, quoted in fed:
                texts.append(("a heredoc", body if quoted else _expand(body, env, here)))
            return
        try:
            texts.append((val, _read(path, here, env)))
        except OSError as exc:
            raise CouldNotTell(f"{flag} {val} cannot be read ({type(exc).__name__})") from exc

    # B15 (#91 round 6): a name resolves only through a plain top-level assignment in a segment of nothing but
    # assignments; assigned anywhere else — in a branch, a loop, a brace or subshell, by export/read/for, with +=,
    # or as a prefix to a command (which never persists) — it is tainted, and a use of it refuses.
    # B18 · B19 (round 7): the blocks are a stack, so `)` closes only a subshell, `fi` only an `if`, and a closed block
    # returns to the top level; an assignment bash may skip (after `&&` · `||`) or run in a subshell (in a pipeline,
    # backgrounded) is conditional — with any other assignment to the same name, bash's value is not knowable: tainted.
    persistent, tainted = set(), set()
    stack: list[str] = []
    opens = {"if", "for", "while", "until", "case", "select", "{", "("}
    closes = {"fi": {"if"}, "done": {"for", "while", "until", "select"}, "esac": {"case"}, "}": {"{"}, ")": {"("}}
    counts: dict[str, int] = {}
    conditional: set[str] = set()
    k, before = 0, ""
    while k < len(tokens):
        start = k
        while k < len(tokens) and tokens[k] not in _SEPARATORS - {"(", ")"}:
            k += 1
        segment = list(range(start, k))
        after = tokens[k] if k < len(tokens) else ""
        assigns = []                                   # the leading bare NAME= / NAME+= words
        for x in segment:
            m = re.match(r"([A-Za-z_]\w*)(\+?)=", tokens[x]) if bare[x] else None
            if not m:
                break
            assigns.append((x, m))
        rest = segment[len(assigns):]
        for x, m in assigns:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
            if before in ("&&", "||", "|", "|&") or after in ("|", "|&", "&"):
                conditional.add(m.group(1))
            if not stack and not rest and not m.group(2):
                persistent.add(x)
            else:
                tainted.add(m.group(1))
        for pos, x in enumerate(rest):
            w = tokens[x]
            if w in ("export", "declare", "local", "readonly", "typeset", "read", "unset", "mapfile", "readarray", "for", "select"):
                for y in rest[pos + 1:]:
                    nm = re.match(r"([A-Za-z_]\w*)", tokens[y])
                    if nm and not tokens[y].startswith("-"):
                        tainted.add(nm.group(1))
                        if w in ("for", "select"):
                            break
            m = re.match(r"([A-Za-z_]\w*)\+?=", w) if bare[x] else None
            if m and pos > 0 and tokens[rest[pos - 1]] in opens | set(closes) | {"!", "time", "then", "else", "do", "function"}:
                tainted.add(m.group(1))
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
            if w in opens:
                stack.append(w)
            elif w in closes and stack and stack[-1] in closes[w]:
                stack.pop()
        if after == "(":
            stack.append("(")
        elif after == ")" and stack and stack[-1] == "(":
            stack.pop()
        before = after
        k += 1
    tainted |= {n for n in conditional if counts.get(n, 0) > 1}
    for name in tainted:
        env.pop(name, None)
    env.setdefault(_WRITTEN, {})
    env.setdefault(_UNKNOWN_WRITER, [""])

    def writes_of(start: int) -> None:
        """B16: what a segment writes before a later post reads it. `cat > F <<EOF` is the heredoc body; any other
        write is unknown content; an interpreter or script runner may write anything."""
        end = seg_end(start)
        # the command word follows the block openers, keywords and prefix words (B26 · B29), `NAME=VALUE` words, a prefix
        # word's flag and its separated value, and any redirect standing before it (B28: `( … ) > F` heads a segment)
        skipped, x, cmd = set(), start, None
        while x < end:
            w = tokens[x]
            if w in _PREFIX_WORDS or (bare[x] and re.match(r"[A-Za-z_]\w*\+?=", w)):
                skipped.add(x)
                if w == "function" and x + 1 < end:        # `function f { … }`: the name is not the command
                    skipped.add(x + 1)
                    x += 1
            elif w.startswith("-") and x > start and tokens[x - 1] in _PREFIX_WORDS:
                skipped.add(x)
                if w in _PREFIX_VALUE_FLAGS.get(tokens[x - 1], ()) and x + 1 < end:
                    skipped.add(x + 1)
                    x += 1
            elif bare[x] and (r := _REDIRECT.fullmatch(w)):
                if not r.group(3):
                    x += 1                                 # the target is read by the write scan below
            else:
                cmd = x
                break
            x += 1
        name = Path(tokens[cmd]).name if cmd is not None else ""   # `gh issue view 1 > F` (round 8) marks F like any other redirect
        if name in ("python", "python3", "perl", "ruby", "node", "awk", "make", "sh", "bash", "zsh", "dash", "source", ".", "xargs", "eval") \
                or re.fullmatch(r"python3\.\d+", name):
            _mark_writer(env, name)
        args, x = [], start
        while x < end:
            if x == cmd or x in skipped:
                x += 1
                continue
            w = tokens[x]
            r = bare[x] and _REDIRECT.fullmatch(w)
            if r:
                target = r.group(3) or (tokens[x + 1] if x + 1 < end else "")
                if r.group(2) in ("<&", "<") or (r.group(2) == ">&" and re.fullmatch(r"\d+|-", target)):   # a read, or a descriptor: no file written
                    x += 1 if r.group(3) else 2                # a descriptor duplicated or closed: no file written
                    continue
                try:
                    path = _expand(target, env, here) if (built[x + 1] if not r.group(3) and x + 1 < end else built[x]) else target
                    where = Path(os.path.normpath((here or Path("/")) / os.path.expanduser(path))) if here is not None or path.startswith("/") else None
                except CouldNotTell:
                    where = None
                if where is None:
                    _mark_writer(env, f"{name} >")
                else:
                    fed = heredocs_of(seg_origin)
                    known = name == "cat" and r.group(2) == ">" and not args and len(fed) == 1
                    env[_WRITTEN][where] = (fed[0][0] if fed[0][1] else _expand(fed[0][0], env, here)) if known else None
                x += 1 if r.group(3) else 2
                continue
            args.append((w, built[x]))
            x += 1
        if name in ("tee", "cp", "mv", "install", "ln", "rsync", "dd", "sed", "truncate", "patch"):
            targets = [a for a, _b in args if not a.startswith("-")]
            if name in ("cp", "mv", "install", "ln", "rsync"):
                targets = targets[-1:]
            if name == "dd":
                targets = [a[3:] for a, _b in args if a.startswith("of=")]
            if name == "sed" and not any(a.startswith("-i") for a, _b in args):
                targets = []
            for t in targets:
                try:
                    env[_WRITTEN][Path(os.path.normpath((here or Path("/")) / os.path.expanduser(t)))] = None
                except (TypeError, ValueError):
                    _mark_writer(env, name)

    i, seg_start, seg_origin = 0, 0, 0
    subshells: list[Path | None] = []                  # B20 (round 8): a `cd` inside `( … )` ends with the subshell
    previous: Path | None = None                       # `cd -` returns here; pushd/popd walk their own stack
    pushed: list[Path | None] = []
    while i < len(tokens):
        tok = tokens[i]
        if tok in _SEPARATORS:
            if tok == "(":
                subshells.append(here)
            elif tok == ")" and subshells:
                here = subshells.pop()
                env["PWD"] = str(here) if here is not None else ""
            seg_start = seg_origin = i + 1
            i += 1
            continue
        if i == seg_origin:
            writes_of(i)                             # this segment's writes precede every later read
        if built[i]:                                       # B23: `URL=$(gh issue create …)` — the post inside a word
            for inner in _substitutions(tok):
                texts += _nested(inner, str(here) if here is not None else None, _depth + 1, env)
        if i == seg_start and bare[i] and (a := re.fullmatch(r"([A-Za-z_]\w*)\+?=(.*)", tok, re.S)):
            if i in persistent and a.group(1) not in tainted:
                try:
                    val = a.group(2)
                    if val == "~" or val.startswith("~/"):
                        val = env.get("HOME", "") + val[1:]                # `B=~/x`: bash expands the tilde
                    env[a.group(1)] = _expand(val, env, here) if built[i] else val
                except CouldNotTell:
                    env.pop(a.group(1), None)         # set from something unreadable: a later use of it refuses
            seg_start = i + 1                        # `A=1 B=2 cmd`: the command word follows the assignments
            i += 1
            continue
        if tok in ("cd", "pushd", "popd") and (tok == "popd" or (i + 1 < len(tokens) and tokens[i + 1] not in _SEPARATORS)):
            was = here
            if tok == "popd":
                here = pushed.pop() if pushed else None
            elif tokens[i + 1] == "-" and not built[i + 1]:
                here = previous
            else:
                try:
                    target = _expand(tokens[i + 1], env, here) if built[i + 1] else tokens[i + 1]
                    here = (here / os.path.expanduser(target)).resolve() if here is not None else None
                except CouldNotTell:
                    here = None                      # a later relative body file refuses; a read never does
                if tok == "pushd":
                    pushed.append(was)
            previous = was
            env["PWD"] = str(here) if here is not None else ""
        where = str(here) if here is not None else None
        if Path(tok).name in _SHELLS:
            k, end, has_c = i + 1, seg_end(i), False
            while k < end and tokens[k][:1] in "-+" and len(tokens[k]) > 1:   # every option, however many (round 5)
                w = tokens[k]
                if not w.startswith("--") and "c" in w[1:]:
                    has_c = True
                k += 2 if not w.startswith("--") and w[-1] in "oO" else 1   # -o / -euo take the next word
            if has_c and k < end:
                script = _expand(tokens[k], env, here) if built[k] else tokens[k]
                texts += _nested(script, where, _depth + 1, child_env(env))
            elif not has_c:
                for body, quoted in heredocs_of(seg_origin):   # a heredoc fed to a shell is its script
                    texts += _nested(body if quoted else _expand(body, env, here), where, _depth + 1, child_env(env))
        if tok == "eval":
            script = " ".join(_expand(w, env, here) if built[k] else w for k, w in enumerate(tokens[i + 1:seg_end(i)], i + 1))
            texts += _nested(script, where, _depth + 1, env)
        if Path(tok).name == "gh":
            j, head = i + 1, []
            while j < len(tokens) and tokens[j] not in _SEPARATORS and len(head) < 2:
                w = tokens[j]
                if w in _REPO_FLAGS:
                    j += 2
                    continue
                if w.startswith("--repo=") or (w.startswith("-R") and len(w) > 2):
                    j += 1
                    continue
                try:
                    head.append(_expand(w, env, here) if built[j] else w)   # a built group or verb expands, or refuses
                except CouldNotTell:
                    if any(p[:len(head)] == tuple(head) for p in _POSTS):   # a post could still be spelled here
                        raise
                    head.append(w)                                          # `gh api …/$id/…`: no post starts so (round 9)
                j += 1
            if tuple(head) in _POSTS:
                if any(Path(w).name in _UNREADABLE_RUNNERS for w in tokens[seg_start:i]):
                    raise CouldNotTell(f"`gh {' '.join(head)}` is run by {tokens[seg_start]}, which supplies words the hook cannot see")
                while j < len(tokens) and tokens[j] not in _SEPARATORS:
                    w, expands = tokens[j], built[j]
                    redirect = bare[j] and re.fullmatch(r"\d*(?:>&|<&|&>>?|>>?|<|>\|)(\S*)", w)
                    if redirect:                                # a bare redirection and its target never travel
                        j += 1 if redirect.group(1) else 2
                        continue
                    flag, eq, val = w.partition("=")
                    if flag in _REPO_FLAGS:
                        j += 1 if eq else 2
                        continue
                    if w == "--json" and tuple(head) == ("workflow", "run"):
                        body_file("--json", "-", False, seg_origin)   # a run's inputs come from stdin (round 9)
                    elif flag in _FILE_FLAGS or re.fullmatch(r"--[\w-]+-file", flag):   # any --…-file names a file
                        if not eq:
                            j += 1
                            val, expands = (tokens[j], built[j]) if j < len(tokens) and tokens[j] not in _SEPARATORS else ("", False)
                        body_file(flag, val, expands, seg_origin)
                    elif w.startswith("-F") and not w.startswith("--") and len(w) > 2:
                        body_file("-F", w[2:], expands, seg_origin)
                    else:
                        label = "the post's words"
                        if bare[j] and (w == "~" or w.startswith("~/")):   # bash expands a bare tilde (round 15)
                            w = env.get("HOME", "") + w[1:]
                        word_text(label, w, expands)
                        if w.startswith("-") and not w.startswith("--") and len(w) > 2:
                            word_text(label, w[2:], expands)        # -bVALUE: the value alone, as the scrub tokenizes it
                    j += 1
            i = j
            continue
        i += 1
    return texts


def gh_hook(stdin_text: str, hashes: frozenset[str], key: bytes | None) -> int:
    """PreToolUse: block a post to a public GitHub surface whose posted words carry a marker, or whose body the hook
    cannot read (exit 2, the location named, the word never). Not a post, or nothing to scrub with (no key): allowed."""
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except ValueError:
        return 0
    if payload.get("tool_name") != "Bash" or key is None:
        return 0
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not (_GH_WORD.search(command) and _POST_VERB.search(command)):
        return 0
    try:
        texts = posted_texts(command, payload.get("cwd"))
    except CouldNotTell as exc:
        print(f"SCRUB REFUSED: this post to GitHub could not be scrubbed — {exc}. The tracker is public and permanent; "
              f"a body the scrub cannot read is never posted unread", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — a crash is exit 1, which lets the post through: refuse instead
        print(f"SCRUB REFUSED: the hook failed reading this post ({type(exc).__name__}: {exc}) — never posted unscrubbed",
              file=sys.stderr)
        return 2
    hits = [(label, line) for label, text in texts for line, _ in hits_in_text(text, hashes, key)]
    if not hits:
        return 0
    where = " · ".join(f"{label} line {line}" for label, line in hits[:8])
    print(f"SCRUB REFUSED: this post to GitHub carries {len(hits)} private token(s) — {where}. The tracker is public and "
          f"permanent; reword it (the scrub never names the word — `python3 scrub.py --text <draft>` checks a rewrite)",
          file=sys.stderr)
    return 2


def keygen(path: Path | None = None) -> int:
    path = KEY if path is None else path
    if path.exists():
        print(f"SCRUB REFUSED: a key already stands at {path} — a new key makes every digest in "
              f"{LIST.name} stale; move it aside by hand and rewrite the list with --hash")
        return 2
    path.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
    path.chmod(0o600)
    print(f"SCRUB: key written to {path} (never tracked) — now `scrub.py --hash <word>…` writes the list")
    return 0


def main(argv: list[str]) -> int:
    key_path = None
    if argv[:1] == ["--key"]:          # another box's key file, by path — never copied (sync_public.sh scrubs the public checkout under this box's key)
        key_path, argv = Path(argv[1]).resolve(), argv[2:]
    if argv[:1] == ["--keygen"]:
        return keygen(key_path)
    key = load_key(key_path)
    if argv[:1] == ["--hash"]:
        if key is None:
            print(f"SCRUB REFUSED: no key at {key_path or KEY} — the digests are keyed; `scrub.py --keygen` writes one")
            return 2
        for w in argv[1:]:
            print(norm_hash(w, key))
        return 0
    hashes = load_list()
    if argv[:1] == ["--gh-hook"]:
        return gh_hook(sys.stdin.read(), hashes, key)
    if argv[:1] in (["--issues"], ["--text"]):
        if len(argv) < 2:
            print(f"SCRUB REFUSED: {argv[0]} names what to read — `--issues <owner>/<repo>` or `--text <file|->`")
            return 2
        if key is None:
            print(f"SCRUB SKIPPED: no key at {key_path or KEY} — the keyed sweep needs the operator's key")
            return 0
        if argv[0] == "--text":
            try:
                surfaces = [("<stdin>" if argv[1] == "-" else argv[1],
                             sys.stdin.read() if argv[1] == "-" else Path(argv[1]).read_text(encoding="utf-8", errors="replace"))]
            except OSError as exc:
                print(f"SCRUB REFUSED: {argv[1]} cannot be read ({type(exc).__name__}) — never a clean zero")
                return 2
        else:
            try:
                surfaces = fetch_surface(argv[1])
            except (FetchError, OSError, subprocess.SubprocessError) as exc:
                print(f"SCRUB REFUSED: {argv[1]} could not be read whole ({exc}) — never a clean zero")
                return 2
        n = 0
        for label, text in surfaces:
            for line, _tok in hits_in_text(text, hashes, key):
                print(f"{label}:{line}: private token")
                n += 1
        if n:
            print(f"SCRUB RED: {n} hit(s) in {len(surfaces)} surface(s)")
            return 3
        print(f"SCRUB OK: {len(surfaces)} surface(s), no private token")
        return 0
    if argv[:1] == ["--tracked"]:
        files = tracked_outside_staging()
    elif argv[:1] == ["--tree"]:
        files = tree(Path(argv[1]).resolve())
    else:
        files = [Path(a) for a in argv]
    if key is None:
        print(f"SCRUB SKIPPED: no key at {key_path or KEY} — the keyed sweep over {len(files)} file(s) needs the operator's key; "
              f"it runs on the operator's box, never here")
        return 0
    n = 0
    for f in files:
        for line, tok in hits_in(f, hashes, key):
            print(f"{f}:{line}: private token")
            n += 1
    if n:
        print(f"SCRUB RED: {n} hit(s) in {len(files)} file(s)")
        return 3
    print(f"SCRUB OK: {len(files)} file(s), no private token")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
