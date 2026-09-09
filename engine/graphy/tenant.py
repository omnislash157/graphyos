
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

__all__ = ["Tenant", "TenantError", "REQUIRED_FIELDS", "POLICY_VALUES", "LANE_KINDS"]

REQUIRED_FIELDS = (
    "root",
    "data_home",
    "adapters",
    "build_lanes",
    "join_keys",
    "cursor",
    "policy",
    "journal",
)

POLICY_VALUES = ("refuse", "warn")

LANE_KINDS = (
    "walk-time-auto",
    "on-demand",
    "static-dep",
    "parked",
    "known-builder",
    "scrape",
    "pulled",
    "ORPHANED",
)

_PATH_FIELDS = ("root", "data_home", "join_keys", "journal")


class TenantError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tenant:

    root: Path
    data_home: Path
    adapters: tuple[str, ...]
    build_lanes: Mapping[str, tuple[str | None, str]]
    join_keys: Path
    cursor: str
    policy: str
    journal: Path

    def __post_init__(self) -> None:
        if self.policy not in POLICY_VALUES:
            raise TenantError(
                f"policy must be exactly 'refuse' or 'warn', got {self.policy!r}. "
                "'heal' was removed in R1 — a query never compiles."
            )

        for name in _PATH_FIELDS:
            value = getattr(self, name)
            if not str(value).strip():
                raise TenantError(f"{name} must not be empty — an empty path is cwd")
            object.__setattr__(self, name, Path(value))
        for name in ("root", "data_home"):
            if not getattr(self, name).is_absolute():
                raise TenantError(
                    f"{name} must be absolute — a relative {name} would resolve "
                    "against the current directory, which is an ambient fallback"
                )

        if not isinstance(self.build_lanes, Mapping):
            raise TenantError(
                f"build_lanes must be a mapping of graph_class -> (command, "
                f"kind), got {type(self.build_lanes).__name__}"
            )
        for graph_class, entry in self.build_lanes.items():
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TenantError(
                    f"build_lanes[{graph_class!r}] must be a (command, kind) "
                    f"2-tuple, got {entry!r}"
                )
            command, kind = entry
            if command is not None and not isinstance(command, str):
                raise TenantError(
                    f"build_lanes[{graph_class!r}] command must be a string or "
                    f"None, got {type(command).__name__}"
                )
            if kind not in LANE_KINDS:
                raise TenantError(
                    f"build_lanes[{graph_class!r}] has unknown lane kind {kind!r} "
                    f"— want one of {LANE_KINDS}"
                )

    def resolve(self, path: str | Path, *, base: str = "root") -> Path:
        if base == "root":
            anchor = self.root
        elif base == "data_home":
            anchor = self.data_home
        else:
            raise TenantError(
                f"resolve base must be 'root' or 'data_home', got {base!r}"
            )

        p = Path(path)
        if not p.is_absolute():
            p = anchor / p

        try:
            real = p.resolve()
        except (OSError, RuntimeError) as exc:
            raise TenantError(
                f"{path!s} could not be resolved under {base} {anchor}: {exc}"
            ) from exc
        real_anchor = anchor.resolve()
        if real != real_anchor and real_anchor not in real.parents:
            raise TenantError(
                f"{path!s} resolves outside {base} {real_anchor} — a tenant "
                "resolves paths only under its own root and data_home"
            )
        return real


def cli_tenant(data_home: str, join_keys: str, tenant_id: str, lanes: tuple = ()) -> "Tenant":
    """The descriptor a module's own main constructs from its declared flags — one constructor for the
    six mains that used to carry a copy each. The receipt name is read and kept: a blank one refuses
    here, at the door, the way `open_for` refuses it; the declaration is stamped as the cursor
    `cli:<name>`, so anything the Tenant signs carries who declared it. A lane is `KEY:KIND`."""
    if not tenant_id or not tenant_id.strip():
        raise TenantError("--tenant-id must not be empty — graphy resolves identity only through a declared "
                          "Tenant, and the receipt name is part of that declaration")
    dh = Path(data_home).resolve()
    jk = Path(join_keys).resolve()
    build_lanes: dict = {}
    for pair in lanes:
        key, sep, kind = str(pair).partition(":")
        if not sep or not key or not kind:
            raise ValueError(f"--lane {pair!r} does not match KEY:KIND — the lane declares both halves")
        build_lanes[key] = (None, kind)
    return Tenant(root=dh.parent, data_home=dh, adapters=(), build_lanes=build_lanes, join_keys=jk,
                  cursor=f"cli:{tenant_id.strip()}", policy="refuse", journal=dh / ".journal")
