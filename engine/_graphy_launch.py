"""The console scripts' entry: refuse by name when the import name `graphy` resolves to something
that is not this install (graphyos #83).

It sits beside the `graphy` package, outside it, because a shadowing `graphy/__init__.py` earlier on
sys.path kills `from graphy.cli import main` before a line of the package runs. The spec is read, not
imported: the directory that won is named, and so is the engine it hid.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

INTENDED = Path(__file__).resolve().parent / "graphy" / "__init__.py"


def shadowing(spec, intended: Path = INTENDED) -> str | None:
    """The refusal when `spec` is not the intended package, or None when it is."""
    if spec is None:
        return f"the import name 'graphy' resolves to nothing; the engine should be at {intended.parent}"
    if spec.origin is None or spec.origin == "namespace":
        where = ", ".join(str(p) for p in (spec.submodule_search_locations or [])) or "?"
        return (f"the import name 'graphy' resolves to {where} — a directory with no __init__.py, "
                f"a namespace package — which shadows the engine installed at {intended.parent}")
    if Path(spec.origin).resolve() != intended:
        return (f"the import name 'graphy' resolves to {Path(spec.origin).parent}, "
                f"which shadows the engine installed at {intended.parent}")
    return None


def main() -> int:
    reason = shadowing(importlib.util.find_spec("graphy"))
    if reason:
        print(f"graphy: REFUSED — {reason}. Rename or remove that directory, or take its parent off "
              f"PYTHONPATH.", file=sys.stderr)
        return 2
    from graphy.cli import main as cli_main
    return cli_main()
