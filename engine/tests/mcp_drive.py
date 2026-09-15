"""The production driver for graphyos #134, run by hand on a real host: a live `graphy mcp` process over an eaten repo,
a tool call, `graphy build` at the store's own path while that process is alive, and a tool call after it.

    python engine/tests/mcp_drive.py --graphy <the graphy command> <repo> <package>   → MCP DRIVE OK, else exit 1

Not collected by pytest (no `test_` prefix): it needs an eaten repo and the installed command, which is the point."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mcp_drive")
    ap.add_argument("--graphy", required=True, help="the graphy command to drive, as a user runs it")
    ap.add_argument("repo", type=Path)
    ap.add_argument("package")
    a = ap.parse_args(argv)
    graphy = shlex.split(a.graphy)
    desc = (a.repo / ".graphy" / "tenant.json").resolve()
    server = subprocess.Popen([*graphy, "mcp", "--repo", str(a.repo.resolve())], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

    def ask(rid: int, method: str, params: dict) -> dict:
        server.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        server.stdin.flush()
        return json.loads(server.stdout.readline())

    try:
        ask(0, "initialize", {"protocolVersion": "2025-06-18"})
        first = ask(1, "tools/call", {"name": "hunt", "arguments": {"symbol": a.package}})
        build = subprocess.run([*graphy, "build", "--tenant", str(desc), "--tenant-id", a.package],
                               capture_output=True, text=True, encoding="utf-8")
        second = ask(2, "tools/call", {"name": "hunt", "arguments": {"symbol": a.package}})
    finally:
        server.stdin.close()
        rc = server.wait(timeout=60)
    ok = (not first["result"]["isError"] and build.returncode == 0 and not second["result"]["isError"] and rc == 0)
    print(f"first call:  {first['result']['content'][0]['text'].splitlines()[0]}")
    print(f"build under the live server: exit {build.returncode} {(build.stdout + build.stderr).strip().splitlines()[-1:]}")
    print(f"second call: {second['result']['content'][0]['text'].splitlines()[0]}")
    print("MCP DRIVE OK" if ok else f"MCP DRIVE RED: server exit {rc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
