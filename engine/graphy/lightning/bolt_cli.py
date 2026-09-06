import argparse
import glob as shell_glob
import json
import sys
from pathlib import Path

_CORPUS_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".svelte", ".vue", ".rs", ".go",
    ".rb", ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".php", ".sh", ".yaml", ".yml", ".json", ".toml", ".md", ".html",
    ".css", ".scss", ".sql", ".log",
}


def _looks_explicitly_pathlike(value: str) -> bool:
    return (
        Path(value).is_absolute()
        or value.startswith(("./", "../", ".\\", "..\\"))
        or "/" in value
        or "\\" in value
    )


def _looks_like_missing_corpus(value: str) -> bool:
    return _looks_explicitly_pathlike(value) or Path(value).suffix.lower() in _CORPUS_SUFFIXES


def _validate_corpus(parser: argparse.ArgumentParser, value: str) -> str:
    path = Path(value)
    if not path.exists():
        parser.error(f"corpus path does not exist: {value!r}; lightning refuses to widen to the cwd")
    if not (path.is_dir() or path.is_file()):
        parser.error(f"corpus path is not a file or directory: {value!r}")
    return value


def _resolve_search_inputs(parser, args) -> tuple[list[str], str]:
    pos = list(args.pos)
    if args.corpus is not None:
        return pos, _validate_corpus(parser, args.corpus)
    candidates: list[tuple[int, str]] = []
    for index, value in enumerate(pos):
        path = Path(value)
        if path.is_dir():
            candidates.append((index, value))
        elif path.is_file() and (_looks_explicitly_pathlike(value) or value.endswith(".log")):
            candidates.append((index, value))
    if len(candidates) > 1:
        rendered = ", ".join(repr(value) for _, value in candidates)
        parser.error(f"ambiguous corpus: multiple positional values exist as paths ({rendered}); "
                     "choose it explicitly with --path PATH")
    if candidates:
        index, search_path = candidates[0]
        if len(pos) == 1:
            parser.error(f"{search_path!r} is a directory/file and no search term was supplied; "
                         "use --path PATH TERM, or use --path . if that literal is the term")
        pos.pop(index)
        return pos, search_path
    if len(pos) >= 2 and _looks_like_missing_corpus(pos[-1]):
        parser.error(f"corpus path does not exist: {pos[-1]!r}; pass a real path with --path")
    return pos, "."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="graphy.lightning",
        description="lightning: the ANALYSIS half of a two-stage unix pipe. rg DISCOVERS (which "
                    "files), lightning ANALYZES (the enclosing fn/class per hit). ripgrep + AST, "
                    "never a replacement for rg.",
        epilog="THE PIPE, for corpora --path skips by name (dot-dirs, data, docs, vendor):\n"
               "  set -o pipefail; rg -li '<term>' <path> | python3 -m graphy.lightning '<term>' --files-from -\n"
               "  -i is REQUIRED: this tool matches case-insensitively, bare rg does not.\n"
               "Memory doors (their own binaries): graphy.lightning.bloodhound · graphy.lightning.reseed_graph\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pos", nargs="*", help="search term(s) and optionally one existing corpus path")
    parser.add_argument("--path", "--root", dest="corpus", default=None, metavar="PATH",
                        help="explicit search corpus (recommended)")
    parser.add_argument("-r", "--regex", action="store_true", help="raw regex mode")
    parser.add_argument("--loose", action="store_true",
                        help="recall mode for boundary-less tokens: an optional separator between every "
                             "character pair ('mycustomers' matches 'my-customers')")
    parser.add_argument("-g", "--glob", default=None, help="file pattern filter; quote it (-g '*.py')")
    parser.add_argument("-n", "--max-files", type=int, default=None,
                        help="max result files (default: 20 · 500 for the census doors)")
    parser.add_argument("-C", "--context", type=int, default=5,
                        help="context radius for the block-anchored chunk (default 5)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--cooccur", "-c", action="store_true",
                        help="container-level co-occurrence (add --with for a 2nd term = bidirectional)")
    parser.add_argument("--with", dest="with_terms", action="append", default=None, metavar="TERM",
                        help="co-occurrence partner term(s)")
    parser.add_argument("--containers", action="store_true",
                        help="invert: term -> the enclosing functions/classes (over a log corpus: route -> count)")
    parser.add_argument("--test-mode", dest="test_mode", action="store_true",
                        help="(--containers / --stats) liveness counts LIVE-CODE referrers only; tests and "
                             "scratch classified separately, never as proof of life")
    parser.add_argument("--control", default=None, metavar="ROUTE",
                        help="(--containers, log corpora) validate the instrument first on a route known to hit")
    parser.add_argument("--stats", action="store_true", help="frequency stats only")
    parser.add_argument("--files-from", dest="files_from", default=None, metavar="PATH",
                        help="THE PIPE DOOR: the file list from stdin ('-') or a path (an `rg -l` list "
                             "or a recall envelope JSON). Bypasses IGNORE_DIRS entirely.")
    args = parser.parse_intermixed_args(argv)

    if args.glob and not shell_glob.has_magic(args.glob) and Path(args.glob).exists():
        parser.error(f"--glob received an existing path {args.glob!r}; quote the pattern, e.g. -g '*.sh'")

    pos, search_path = _resolve_search_inputs(parser, args)
    for p in pos:
        if Path(p).is_file():
            print(f"lightning: note — treating '{p}' as a TERM (a file of that name exists; "
                  f"prefix ./ to target it as the corpus)", file=sys.stderr)
    term = pos[0] if pos else ""
    extra_terms = pos[1:]
    if extra_terms:
        args.with_terms = (args.with_terms or []) + extra_terms
    if not term and not args.stats:
        parser.error("search term required")

    from .blitz_hunt import Lightning

    files_override = None
    if args.files_from:
        raw = sys.stdin.read() if args.files_from == "-" else Path(args.files_from).read_text(
            encoding="utf-8", errors="replace")
        if raw.lstrip().startswith("{"):
            from .files_from_envelope import files_from_envelope
            files_override = files_from_envelope(json.loads(raw), repo_root=Path(search_path).resolve())
        else:
            files_override = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    bolt = Lightning(search_path, files_override=files_override)

    if args.containers:
        from .extras.storm_cooccurrence import containers_json, containers_markdown
        kw = dict(file_pattern=args.glob, max_files=args.max_files or 500, regex=args.regex, loose=args.loose)
        if args.test_mode:
            from .extras.storm_cooccurrence import containers_test_mode, containers_test_mode_markdown
            print(json.dumps(containers_test_mode(bolt, term, **kw), indent=2) if args.json
                  else containers_test_mode_markdown(bolt, term, **kw))
            return 0
        control = None
        if args.control:
            cj = containers_json(bolt, args.control, **kw)
            c_count = sum(c["count"] for c in cj["containers"])
            control = {"route": args.control, "count": c_count,
                       "instrument": "VALID" if c_count > 0 else "DEAD"}
        if args.json:
            payload = containers_json(bolt, term, **kw)
            if control is not None:
                payload["control"] = control
            print(json.dumps(payload, indent=2))
        else:
            if control is not None:
                print(f"INSTRUMENT-{control['instrument']} — control {control['route']}: {control['count']} hits"
                      + ("" if control["instrument"] == "VALID" else "  (every zero below is NON-evidence)"))
            print(containers_markdown(bolt, term, **kw))
        return 0

    if args.cooccur:
        from .extras.storm_cooccurrence import storm_markdown
        print(storm_markdown(bolt, term, file_pattern=args.glob, max_files=args.max_files or 20,
                             search_path=search_path, with_terms=args.with_terms))
        return 0

    if args.stats:
        from .extras.stats import quick_stats
        stats = quick_stats(bolt, term)
        if args.test_mode:
            from .source_kind import classify_sources, liveness_verdict
            kinds = classify_sources(list(stats.get("by_file", {})), bolt.root_path)
            counts = {"live": 0, "test": 0, "slop": 0, "doc": 0}
            by_kind: dict = {"live": {}, "test": {}, "slop": {}, "doc": {}}
            for f, n in stats.get("by_file", {}).items():
                counts[kinds[f]] += n
                by_kind[kinds[f]][f] = n
            stats["by_kind"] = by_kind
            stats["liveness"] = {**counts, "verdict": liveness_verdict(counts)}
        print(json.dumps(stats, indent=2))
        return 0

    result = bolt.hunt(term, regex=args.regex, file_pattern=args.glob, max_files=args.max_files or 20,
                       context_lines=args.context, loose=args.loose)
    print(json.dumps(result.to_dict(), indent=2) if args.json else result.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
