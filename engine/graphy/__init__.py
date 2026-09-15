
from __future__ import annotations

from graphy.ir import (
    SCHEMA_VERSION,
    Edge,
    Evidence,
    IRError,
    Node,
    Provenance,
    Vocabulary,
    PYTHON_AST_VOCABULARY,
    validate_graph,
)
from graphy.parity import Golden, Harness, ParityError, load_golden
from graphy.tenant import REQUIRED_FIELDS, Tenant, TenantError

__version__ = "0.2.7"

__all__ = [
    "Golden",
    "Harness",
    "ParityError",
    "load_golden",
    "SCHEMA_VERSION",
    "IRError",
    "Node",
    "Edge",
    "Provenance",
    "Evidence",
    "validate_graph",
    "Vocabulary",
    "PYTHON_AST_VOCABULARY",
    # The multi-lane rebuild, public because a tenant with its own producers had to assemble it
    # from cli._clear_substrate, cartograph.repo_cursor and _portable_flock (graphyos #71).
    "Lane",
    "RebuildError",
    "clear_substrate",
    "repo_cursor",
    "Tenant",
    "TenantError",
    "REQUIRED_FIELDS",
    "__version__",
]


# The rebuild lane is exported LAZILY (PEP 562). Importing it at module scope would pull
# `graphy.cartograph` into every `import graphy`, and the cost of importing this package is a
# measured invariant — `graphy.cli` loads five modules and no verb lane, so `--help` never pays for
# a door it will not open. `graphy.Lane` resolves on first touch instead (graphyos #71).
_LAZY = {"Lane": "rebuild", "RebuildError": "rebuild", "clear_substrate": "rebuild",
         "repo_cursor": "rebuild"}


def __getattr__(name: str):
    where = _LAZY.get(name)
    if where is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    return getattr(importlib.import_module(f"{__name__}.{where}"), name)


def __dir__():
    return sorted(set(globals()) | set(_LAZY))
