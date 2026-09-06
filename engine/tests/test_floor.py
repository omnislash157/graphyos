
from __future__ import annotations

import graphy


def test_package_imports_and_is_versioned():
    assert graphy.__version__


def test_exports_the_parity_surface():
    for name in ("Golden", "Harness", "ParityError", "load_golden"):
        assert hasattr(graphy, name), f"graphy does not export {name}"
        assert name in graphy.__all__


def test_no_ambient_tenant_is_exported():
    for forbidden in ("ROOT", "DATA_HOME", "TENANT", "DEFAULT_TENANT", "REPO_ROOT"):
        assert not hasattr(graphy, forbidden), (
            f"graphy exports an ambient {forbidden} — an engine that defaults to a "
            "tenant is the defect the descriptor (P2) exists to prevent"
        )
