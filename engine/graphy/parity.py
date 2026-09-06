
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

__all__ = [
    "ParityError",
    "Golden",
    "Harness",
    "load_golden",
    "json_equal",
    "REQUIRED_PROVENANCE",
]

REQUIRED_PROVENANCE = ("surface", "oracle_commit", "mint_command")


class ParityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Golden:

    surface: str
    oracle_commit: str
    mint_command: str
    payload: Any

    def __post_init__(self) -> None:
        for field_name in REQUIRED_PROVENANCE:
            value = getattr(self, field_name)
            if type(value) is not str:
                raise ParityError(
                    f"Golden.{field_name} must be a string, got "
                    f"{type(value).__name__}. A list is not a pinned commit and "
                    "an object is not a runnable mint command."
                )
            if not value.strip():
                raise ParityError(f"Golden.{field_name} must not be empty")

    @property
    def provenance(self) -> str:
        return f"{self.surface}@{self.oracle_commit}"


def load_golden(path: str | Path) -> Golden:
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ParityError(f"golden not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise ParityError(f"golden is not valid JSON: {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ParityError(f"golden must be a JSON object, got {type(raw).__name__}: {p}")

    for k in REQUIRED_PROVENANCE:
        v = raw.get(k)
        if not isinstance(v, str):
            raise ParityError(
                f"golden {p} field {k!r} must be a string, got "
                f"{type(v).__name__}. Stringifying a container here would mint "
                "valid-looking provenance out of an invalid shape."
            )
    missing = [k for k in REQUIRED_PROVENANCE if not raw[k].strip()]
    if missing:
        raise ParityError(
            f"golden {p} is missing required provenance {missing}. A golden minted "
            "from a broken oracle bakes the bug in permanently, so provenance is "
            "mandatory — and goldens are re-minted, never hand-edited."
        )
    if "payload" not in raw:
        raise ParityError(f"golden {p} declares provenance but carries no payload")

    return Golden(
        surface=raw["surface"].strip(),
        oracle_commit=raw["oracle_commit"].strip(),
        mint_command=raw["mint_command"].strip(),
        payload=raw["payload"],
    )


_JSON_SCALARS = (str, bool, int, float, type(None))


class _NotJson:

    __slots__ = ("reason",)

    def __init__(self, reason: str) -> None:
        self.reason = reason


_SUBCLASS_CONTAINER = "subclass container"


def _as_json(v: Any, flags: set[str]) -> Any:
    if isinstance(v, dict):
        if type(v) is not dict:
            flags.add(_SUBCLASS_CONTAINER)
        out: dict[str, Any] = {}
        for k, x in v.items():
            if type(k) is not str:
                return _NotJson(f"object key {k!r} of type {type(k).__name__}")
            got = _as_json(x, flags)
            if isinstance(got, _NotJson):
                return got
            out[k] = got
        return out
    if isinstance(v, list):
        if type(v) is not list:
            flags.add(_SUBCLASS_CONTAINER)
        items: list[Any] = []
        for x in v:
            got = _as_json(x, flags)
            if isinstance(got, _NotJson):
                return got
            items.append(got)
        return items
    if isinstance(v, float) and not math.isfinite(v):
        return _NotJson(f"non-finite float {v!r}")
    if type(v) in _JSON_SCALARS:
        return v
    return _NotJson(type(v).__name__)


def _witness(v: Any) -> Any:
    flags: set[str] = set()
    walked = _as_json(v, flags)
    if isinstance(walked, _NotJson):
        return walked
    if _SUBCLASS_CONTAINER not in flags:
        return walked
    try:
        plain = json.loads(json.dumps(v))
    except (TypeError, ValueError, RecursionError) as exc:
        return _NotJson(f"container subclass failed to serialize: {exc}")
    if not _eq(walked, plain):
        return _NotJson(
            "container subclass view disagrees with its serialized identity"
        )
    return walked


def json_equal(a: Any, b: Any) -> bool:
    a = _witness(a)
    b = _witness(b)
    if isinstance(a, _NotJson) or isinstance(b, _NotJson):
        return False
    return _eq(a, b)


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if type(a) is dict and type(b) is dict:
        return a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
    if type(a) is list and type(b) is list:
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    if type(a) in (dict, list) or type(b) in (dict, list):
        return False
    return a == b


class Harness:

    def __init__(self) -> None:
        self._producers: dict[str, Callable[[], Any]] = {}


    def register(self, surface: str, producer: Callable[[], Any]) -> None:
        key = str(surface).strip()
        if not key:
            raise ParityError("a producer must declare a non-empty parity surface")
        if not callable(producer):
            raise ParityError(f"producer for surface {key!r} is not callable")
        if key in self._producers:
            raise ParityError(
                f"surface {key!r} already has a producer; two producers for one "
                "surface means the surface has two authorities and neither is the oracle"
            )
        self._producers[key] = producer

    @property
    def surfaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._producers))


    def check(self, golden: Golden) -> None:
        if not self._producers:
            raise ParityError(
                "the parity harness has no tool wired to it — there is nothing to "
                "compare, so it fails RED by construction. An empty harness that "
                "reported success would certify the absence of a test as a pass."
            )

        producer = self._producers.get(golden.surface)
        if producer is None:
            raise ParityError(
                f"no producer declares surface {golden.surface!r} "
                f"(declared: {self.surfaces or '()'}). An undeclared parity surface "
                "is an unfalsifiable claim."
            )

        produced = producer()
        snapshot = _witness(produced)
        if isinstance(snapshot, _NotJson):
            raise ParityError(
                f"producer for surface {golden.surface!r} returned "
                f"{type(produced).__name__}, which is outside the JSON data "
                f"model ({snapshot.reason}). A value that supplies its own "
                "equality semantics cannot be a parity witness."
            )
        produced = snapshot
        if not json_equal(produced, golden.payload):
            raise ParityError(
                f"parity FAILED on surface {golden.surface!r} "
                f"(oracle {golden.oracle_commit}).\n"
                f"  remake : {produced!r}\n"
                f"  golden : {golden.payload!r}\n"
                f"  re-mint with: {golden.mint_command}"
            )

    def check_all(self, goldens: Iterable[Golden]) -> int:
        checked = 0
        for golden in goldens:
            self.check(golden)
            checked += 1
        if checked == 0:
            raise ParityError(
                "no goldens were checked — an empty parity run proves nothing "
                "and must not report success"
            )
        return checked
