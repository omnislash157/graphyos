#!/usr/bin/env python3
"""The thirty-second demo: a blast-radius question on FastAPI, three ways.

    1. graphy alone            the compiled store answers, no model at all — the ground truth
    2. a cold small model      Claude Haiku 4.5 with graphy's five tools and nothing else
    3. a frontier model        Claude Opus 5 with the relevant source files stuffed into context, no tools

Run it from the repo root after the tenant is built (bash engine/tenants/fastapi/rebuild.sh):

    ANTHROPIC_API_KEY=… .venv/bin/python engine/tenants/fastapi/demo.py [--question "…"] [--symbol …]

Two runners: `--runner sdk` (the default when ANTHROPIC_API_KEY is set) drives the Anthropic SDK with
graphy's tools in-process; `--runner claude-code` drives `claude -p` on your Claude Code login, with
the MCP server as the small model's only tool — the same server any client points at. Without a key
or a login only the first way runs, and it says so. Every answer is scored the same way: the
share of the store's dependents (the exact functions the blast door lists) the answer names.
Prices are the API's; the script prints tokens and wall time, never a cost it did not measure.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent.parent
sys.path.insert(0, str(ENGINE))

from graphy import doors, mcp  # noqa: E402
from graphy import federated_store as fstore  # noqa: E402
from graphy.cli import _load_tenant, _roster  # noqa: E402

SMALL = "claude-haiku-4-5"
FRONTIER = "claude-opus-5"
STUFF = ("fastapi/routing.py", "starlette/concurrency.py", "starlette/responses.py")
SYSTEM_TOOLS = ("You answer questions about the FastAPI codebase and its import ring using the graphy tools, "
                "which walk a compiled graph of the code's structure. Answer ONLY from tool results. Name the "
                "exact functions and methods the tools return, with the call chain. Do not guess at code you "
                "have not seen in a tool result.")
SYSTEM_STUFF = ("You answer questions about the FastAPI codebase from the source files provided. Name the exact "
                "functions and methods affected, with the call chain, as precisely as you can.")


def _tail(node_id: str) -> str:
    return node_id.split("/", 3)[-1]


def score(answer: str, truth: list[str]) -> tuple[int, list[str]]:
    hits = [t for t in truth if t.split(".")[-1] in answer]
    return len(hits), [t for t in truth if t not in hits]


def ground_truth(tools: mcp.Doors, symbol: str, depth: int) -> tuple[str, list[str], float]:
    t0 = time.perf_counter()
    text = tools.blast(symbol, depth=depth, limit=50)
    dt = time.perf_counter() - t0
    c = tools._counted()
    seed = doors.resolve(c, symbol)
    b = doors.blast(c, seed, depth)
    truth = sorted({_tail(r.node) for r in b.own + b.ring})
    return text, truth, dt


def run_small(client, tools: mcp.Doors, question: str) -> tuple[str, dict]:
    defs = [{"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]} for t in mcp.TOOLS]
    messages = [{"role": "user", "content": question}]
    calls, usage = [], {"input": 0, "output": 0}
    t0 = time.perf_counter()
    for _ in range(12):
        r = client.messages.create(model=SMALL, max_tokens=4096, system=SYSTEM_TOOLS, tools=defs, messages=messages)
        usage["input"] += r.usage.input_tokens
        usage["output"] += r.usage.output_tokens
        uses = [b for b in r.content if b.type == "tool_use"]
        if r.stop_reason != "tool_use" or not uses:
            break
        messages.append({"role": "assistant", "content": r.content})
        results = []
        for u in uses:
            calls.append(f"{u.name}({json.dumps(u.input)})")
            try:
                out, err = tools.call(u.name, dict(u.input)), False
            except mcp.ToolError as exc:
                out, err = str(exc), True
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": out, "is_error": err})
        messages.append({"role": "user", "content": results})
    text = "".join(b.text for b in r.content if b.type == "text")
    return text, {**usage, "calls": calls, "seconds": time.perf_counter() - t0, "stop": r.stop_reason}


def run_frontier(client, site_packages: Path, question: str) -> tuple[str, dict]:
    parts = []
    for rel in STUFF:
        p = site_packages / rel
        parts.append(f"===== {rel} =====\n{p.read_text(encoding='utf-8', errors='replace')}")
    stuffed = "\n\n".join(parts)
    t0 = time.perf_counter()
    with client.messages.stream(model=FRONTIER, max_tokens=16000, system=SYSTEM_STUFF,
                                messages=[{"role": "user", "content": f"{stuffed}\n\n{question}"}]) as s:
        r = s.get_final_message()
    text = "".join(b.text for b in r.content if b.type == "text")
    return text, {"input": r.usage.input_tokens, "output": r.usage.output_tokens,
                  "seconds": time.perf_counter() - t0, "stop": r.stop_reason, "stuffed_bytes": len(stuffed)}


BUILTINS = "Read,Grep,Glob,Bash,Edit,Write,MultiEdit,NotebookEdit,Agent,WebFetch,WebSearch,TodoWrite,Skill"


def _claude(prompt: str, model: str, extra: list[str], cwd: Path) -> tuple[str, dict]:
    """One `claude -p` run from a directory that carries no hooks (this repo's Stop hook would hold it)."""
    t0 = time.perf_counter()
    out = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json",
                          "--disallowedTools", *BUILTINS.split(","), *extra],
                         input=prompt, capture_output=True, text=True, cwd=str(cwd), timeout=900)
    dt = time.perf_counter() - t0
    if out.returncode != 0:
        raise RuntimeError(f"claude -p exited {out.returncode}: {out.stderr.strip()[:400]}")
    r = json.loads(out.stdout)
    u = r.get("usage") or {}
    return str(r.get("result", "")), {"input": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
                                      "output": u.get("output_tokens", 0), "seconds": dt,
                                      "stop": r.get("subtype", "?"), "turns": r.get("num_turns")}


def run_small_cc(question: str, scratch: Path) -> tuple[str, dict]:
    cfg = scratch / "graphy.mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"graphy": {"command": "bash", "args": [str(HERE / "mcp.sh")]}}}), encoding="utf-8")
    text, meta = _claude(f"{SYSTEM_TOOLS}\n\n{question}", "haiku",
                         ["--mcp-config", str(cfg), "--strict-mcp-config", "--allowedTools", "mcp__graphy__*"], scratch)
    meta["calls"] = [f"{meta.get('turns')} turn(s) through the MCP server; tokens include Claude Code's own cached prompt"]
    return text, meta


def run_frontier_cc(site_packages: Path, question: str, scratch: Path) -> tuple[str, dict]:
    parts = [f"===== {rel} =====\n{(site_packages / rel).read_text(encoding='utf-8', errors='replace')}" for rel in STUFF]
    stuffed = "\n\n".join(parts)
    text, meta = _claude(f"{SYSTEM_STUFF}\n\n{stuffed}\n\n{question}", "opus", ["--strict-mcp-config"], scratch)
    meta["stuffed_bytes"] = len(stuffed)
    return text, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", default="iterate_in_threadpool")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--question", default=None)
    ap.add_argument("--no-models", action="store_true", help="the store only, even with a key")
    ap.add_argument("--runner", choices=("sdk", "claude-code"), default=None,
                    help="sdk (ANTHROPIC_API_KEY) or claude-code (`claude -p` on your login); default: sdk if a key is set, else claude-code if `claude` is on PATH")
    args = ap.parse_args(argv)
    question = args.question or (
        f"`{args.symbol}` in Starlette is about to change its signature. What in FastAPI breaks, "
        f"and through which call chain? Name the exact functions and methods, nearest first.")

    tenant = _load_tenant(str(HERE / "tenant.json"))
    tools = mcp.open_tools(tenant, "fastapi", _roster(tenant))
    print(f"QUESTION: {question}\n")
    text, truth, dt = ground_truth(tools, args.symbol, args.depth)
    print(f"── 1 · graphy alone, no model ({dt * 1000:.0f} ms, store generation {tools.generation})")
    print(text)
    print(f"   TRUTH: {len(truth)} dependent(s) within {args.depth} hops: {', '.join(truth)}\n")

    key = os.environ.get("ANTHROPIC_API_KEY")
    runner = args.runner or ("sdk" if key else "claude-code" if shutil.which("claude") else None)
    if args.no_models or runner is None:
        print("MODELS SKIPPED: no ANTHROPIC_API_KEY and no `claude` on PATH — ways 2 and 3 need one (BYO key or login)")
        print("DEMO OK: graphy alone")
        return 0
    scratch = Path(tempfile.mkdtemp(prefix="graphy-demo-"))
    client = None
    if runner == "sdk":
        try:
            import anthropic
        except ImportError:
            print("MODELS SKIPPED: pip install anthropic — the sdk runner needs it (or --runner claude-code)")
            return 0
        client = anthropic.Anthropic()
    print(f"RUNNER: {runner}\n")
    try:
        small_text, small = run_small(client, tools, question) if runner == "sdk" else run_small_cc(question, scratch)
    except Exception as exc:  # noqa: BLE001 — a billing or login failure is the demo's honest end
        print(f"MODELS FAILED: {type(exc).__name__}: {str(exc)[:300]}")
        print("DEMO OK: graphy alone")
        return 0
    hit, missed = score(small_text, truth)
    print(f"── 2 · {SMALL} + graphy tools ({small['seconds']:.1f} s · {small['input']} in / {small['output']} out · "
          f"{len(small['calls'])} tool call(s) · stop={small['stop']})" if runner == "sdk" else
          f"── 2 · {SMALL} + the graphy MCP server, no other tools ({small['seconds']:.1f} s · {small['input']} in / {small['output']} out · stop={small['stop']})")
    for c in small["calls"]:
        print(f"   ⟶ {c}")
    print(small_text.strip())
    print(f"   SCORE: {hit}/{len(truth)} of the store's dependents named" + (f"; missed {', '.join(missed)}" if missed else "") + "\n")

    ring = json.loads((HERE / "substrate" / "ring.json").read_text(encoding="utf-8"))
    sp = Path(os.environ.get("GRAPHY_CORPUS_SITE_PACKAGES") or ring.get("site_packages") or "")
    if not all((sp / rel).is_file() for rel in STUFF):
        print(f"── 3 · {FRONTIER} + stuffed source: SKIPPED — the corpus site-packages is not on this box ({sp}); "
              f"set GRAPHY_CORPUS_SITE_PACKAGES")
        print("DEMO OK: ways 1 and 2")
        return 0
    big_text, big = run_frontier(client, sp, question) if runner == "sdk" else run_frontier_cc(sp, question, scratch)
    hit2, missed2 = score(big_text, truth)
    print(f"── 3 · {FRONTIER} + {len(STUFF)} source files stuffed ({big['seconds']:.1f} s · {big['input']} in / "
          f"{big['output']} out · {big['stuffed_bytes'] // 1024} KB of source · no tools · stop={big['stop']})")
    print(big_text.strip())
    print(f"   SCORE: {hit2}/{len(truth)} of the store's dependents named" + (f"; missed {', '.join(missed2)}" if missed2 else "") + "\n")

    print("┌────────────────────────────────┬──────────┬───────────┬──────────┬────────────┐")
    print("│ way                            │ seconds  │ tokens in │ tok out  │ dependents │")
    print("├────────────────────────────────┼──────────┼───────────┼──────────┼────────────┤")
    print(f"│ graphy alone                   │ {dt:8.2f} │ {0:9d} │ {0:8d} │ {len(truth):3d}/{len(truth):<6d} │")
    print(f"│ {SMALL + ' + graphy':<30} │ {small['seconds']:8.1f} │ {small['input']:9d} │ {small['output']:8d} │ {hit:3d}/{len(truth):<6d} │")
    print(f"│ {FRONTIER + ' + source':<30} │ {big['seconds']:8.1f} │ {big['input']:9d} │ {big['output']:8d} │ {hit2:3d}/{len(truth):<6d} │")
    print("└────────────────────────────────┴──────────┴───────────┴──────────┴────────────┘")
    print("DEMO OK: three ways")
    return 0


if __name__ == "__main__":
    sys.exit(main())
