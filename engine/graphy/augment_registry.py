from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from graphy._portable_flock import fcntl
from graphy.tenant import Tenant

_ADMITTED_ANCHOR = '    "admitted": {\n'


def _registry_path(tenant: Tenant) -> Path:
    return Path(tenant.join_keys)


def _lock_path(tenant: Tenant) -> Path:
    return Path(tenant.join_keys).parent / ".substrate_override_registry.lock"


def normalize_descriptor(*, slug: str, kind: str, owner: str, blurb: str, members: list,
                         axes: dict, producer: str, accept_cmd: str, supersedes: str = "—") -> dict:
    norm_axes = {a: {m: sorted(set(ets)) for m, ets in sorted(mmap.items())} for a, mmap in axes.items()}
    declared: dict[str, set] = {}
    for mmap in norm_axes.values():
        for m, ets in mmap.items():
            declared.setdefault(m, set()).update(ets)
    if not norm_axes or not members:
        raise ValueError(f"augment_descriptor {slug!r}: empty axes or members")
    axis_member_keys = set(declared)
    if set(members) != axis_member_keys:
        raise ValueError(f"augment_descriptor {slug!r}: members {sorted(set(members))} != union of axis member "
                         f"keys {sorted(axis_member_keys)} — a declared member has no axis, or an axis a stray member")
    for a, mmap in norm_axes.items():
        for m, ets in mmap.items():
            if not ets:
                raise ValueError(f"augment_descriptor {slug!r}: axis {a} member {m} declares no edge_types")
    return {
        "augment": True,
        "kind": kind, "owner": owner, "supersedes": supersedes, "blurb": blurb,
        "members": sorted(set(members)),
        "join_keys": sorted(norm_axes),
        "axes": {a: norm_axes[a] for a in sorted(norm_axes)},
        "declared_members": {m: sorted(declared[m]) for m in sorted(declared)},
        "producer": producer,
        "accept_cmd": accept_cmd,
        "freshness_policy": "member cursors (freshness_token/published_head/built_at_sha per member) "
                            "+ descriptor digest — NOT a wall clock",
    }


def descriptor_digest(descriptor: dict) -> str:
    body = {k: v for k, v in descriptor.items() if k != "descriptor_digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def stamp_from_descriptor(descriptor: dict) -> dict:
    st = {k: v for k, v in descriptor.items() if k != "descriptor_digest"}
    st["descriptor_digest"] = descriptor_digest(descriptor)
    st["admitted_via"] = "augment_registry.register — one-time explicit, tenant-admission-gated"
    return st


def verify_registration(slug: str, descriptor: dict, *, tenant: Tenant | None = None) -> None:
    if tenant is None:
        raise ValueError("augment_registry.verify_registration: tenant is required — graphy resolves "
                         "identity only through a declared Tenant; absent tenant = refuse")
    reg = json.loads(_registry_path(tenant).read_text(encoding="utf-8"))
    stamp = reg.get("substrate_roster", {}).get("admitted", {}).get(slug)
    if stamp is None:
        raise RuntimeError(
            f"augment_registry.verify_registration: {slug!r} is NOT registered — run the one-time "
            f"`python -m graphy.augment_registry register --slug {slug}` first. "
            f"A build never installs the stamp.")
    want = stamp_from_descriptor(descriptor)
    if stamp != want:
        diff = sorted(k for k in set(stamp) | set(want) if stamp.get(k) != want.get(k))
        raise RuntimeError(
            f"augment_registry.verify_registration: {slug!r} committed stamp != descriptor (fields differ: {diff}). "
            f"A tampered/stale stamp cannot pass. Re-run `register` to update the committed stamp, then rebuild.")


def _entry_span(text: str, slug: str) -> tuple[int, int] | None:
    key = f'      {json.dumps(slug)}: {{'
    i = text.find(key)
    if i < 0:
        return None
    j = text.index("{", i + len(key) - 1)
    depth, k = 0, j
    while k < len(text):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return (i, k + 1)


def _entry_body(slug: str, stamp: dict) -> str:
    inner = json.dumps({slug: stamp}, indent=2, ensure_ascii=False).split("\n")[1:-1]
    return "\n".join("    " + ln for ln in inner)


def register(slug: str, descriptor: dict, *, tenant: Tenant | None = None,
             admission_predicate=None) -> dict:
    if tenant is None:
        raise ValueError("augment_registry.register: tenant is required — graphy resolves identity only "
                         "through a declared Tenant; absent tenant = refuse")
    if admission_predicate is None:
        raise ValueError("augment_registry.register: admission_predicate is required — a graphy tenant "
                         "supplies its own admission authority; there is no default governance path")
    if not admission_predicate(slug):
        raise RuntimeError(
            f"augment_registry.register: {slug!r} refused by the admission predicate — no default "
            f"governance path exists to fall back to. The tenant's admission authority must ADMIT the slug.")

    registry_path = _registry_path(tenant)
    lock_path = _lock_path(tenant)
    lock_path.touch(exist_ok=True)
    with open(lock_path, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            text = registry_path.read_text(encoding="utf-8")
            reg = json.loads(text)
            admitted = reg["substrate_roster"]["admitted"]
            stamp = stamp_from_descriptor(descriptor)
            if admitted.get(slug) == stamp:
                return {"registered": False, "reason": "byte-idempotent (stamp already current)", "slug": slug}

            span = _entry_span(text, slug)
            body = _entry_body(slug, stamp)
            if span is None:
                if _ADMITTED_ANCHOR not in text:
                    raise RuntimeError("augment_registry.register: admitted-block anchor not found")
                cut = text.index(_ADMITTED_ANCHOR) + len(_ADMITTED_ANCHOR)
                new_text = text[:cut] + body + ",\n" + text[cut:]
            else:
                new_text = text[:span[0]] + body + text[span[1]:]

            new_reg = json.loads(new_text)
            if new_reg["substrate_roster"]["admitted"].get(slug) != stamp:
                raise RuntimeError("augment_registry.register: post-write stamp mismatch — refusing to write")
            before = {k: v for k, v in admitted.items() if k != slug}
            after = {k: v for k, v in new_reg["substrate_roster"]["admitted"].items() if k != slug}
            if before != after:
                raise RuntimeError("augment_registry.register: a DIFFERENT admitted entry changed — refusing to write")

            tmp = registry_path.with_name(registry_path.name + f".tmp.{os.getpid()}")
            tmp.write_text(new_text, encoding="utf-8")
            os.replace(tmp, registry_path)
            return {"registered": True, "slug": slug, "op": "insert" if span is None else "replace",
                    "digest": stamp["descriptor_digest"]}
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def declared_from_stamp(stamp: dict) -> dict:
    members: dict[str, set] = {}
    for mmap in stamp.get("axes", {}).values():
        for m, ets in mmap.items():
            members.setdefault(m, set()).update(ets)
    return {"members": {m: {"edge_types": sorted(members[m])} for m in sorted(members)}}


def observed_from_index(stamp: dict, index: dict) -> dict:
    declared_schemes: dict[str, set] = {}
    for axis_node, mmap in stamp.get("axes", {}).items():
        sch = axis_node.split("://", 1)[0]
        for m in mmap:
            declared_schemes.setdefault(m, set()).add(sch)
    member_cursors: dict = {}
    missing: list = []
    complete = True
    for m in sorted(declared_schemes):
        row = index.get(m, {})
        present = set(row.get("own", [])) | set(row.get("out", []))
        member_cursors[m] = row.get("cursor")
        for sch in sorted(declared_schemes[m]):
            if sch not in present:
                missing.append(f"{m}: axis scheme {sch}:// not observed in member graph")
                complete = False
    return {"scheme_complete": complete, "member_cursors": member_cursors, "missing": sorted(missing)}


def collect_augment_stamps(*, tenant: Tenant | None = None) -> list[dict]:
    if tenant is None:
        raise ValueError("augment_registry.collect_augment_stamps: tenant is required — graphy resolves "
                         "identity only through a declared Tenant; absent tenant = refuse")
    reg = json.loads(_registry_path(tenant).read_text(encoding="utf-8"))
    out = []
    for slug, stamp in sorted(reg.get("substrate_roster", {}).get("admitted", {}).items()):
        if isinstance(stamp, dict) and stamp.get("augment") is True:
            out.append({"slug": slug, **stamp})
    return out


def _load_descriptor(slug: str, descriptor_modules: dict) -> dict:
    if slug not in descriptor_modules:
        raise SystemExit(f"augment_registry: no descriptor module for {slug!r} (known: {sorted(descriptor_modules)})")
    return importlib.import_module(descriptor_modules[slug]).descriptor()


def _load_predicate(dotted: str):
    module_name, _, func_name = dotted.rpartition(":")
    if not module_name or not func_name:
        raise SystemExit(f"augment_registry: --admission-predicate must be 'module:function', got {dotted!r}")
    return getattr(importlib.import_module(module_name), func_name)


def _cli_tenant(data_home: str, join_keys: str) -> Tenant:
    dh = Path(data_home).resolve()
    jk = Path(join_keys).resolve()
    return Tenant(
        root=dh.parent,
        data_home=dh,
        adapters=(),
        build_lanes={},
        join_keys=jk,
        cursor="declared-cli",
        policy="refuse",
        journal=dh / ".journal",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="augment_registry",
                                 description="one-time explicit augment self-registration (a build never writes the registry)")
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name for the registration — graphy resolves identity only through a declared Tenant.")
    ap.add_argument("--data-home", required=True, help="the tenant data_home (unused by this module; required for a complete declaration).")
    ap.add_argument("--join-keys", required=True, help="path to the tenant's substrate_override_registry.json.")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("register", help="install the augment's stamp ONCE — tenant-admission-gated, locked, atomic, byte-clean")
    r.add_argument("--slug", required=True)
    r.add_argument("--descriptor-module", required=True,
                   help="module exposing descriptor() for the slug (caller-supplied slug→module mapping)")
    r.add_argument("--admission-predicate", required=True,
                   help="'module:function' — the tenant's admission authority (slug) -> bool; no default governance path")
    v = sub.add_parser("verify", help="verify a slug's descriptor exactly matches its committed stamp (read-only)")
    v.add_argument("--slug", required=True)
    v.add_argument("--descriptor-module", required=True,
                   help="module exposing descriptor() for the slug (caller-supplied slug→module mapping)")
    args = ap.parse_args(argv)

    tenant = _cli_tenant(args.data_home, args.join_keys)

    if args.cmd == "register":
        desc = _load_descriptor(args.slug, {args.slug: args.descriptor_module})
        pred = _load_predicate(args.admission_predicate)
        print(json.dumps(register(args.slug, desc, tenant=tenant, admission_predicate=pred), indent=1))
        return 0
    if args.cmd == "verify":
        verify_registration(args.slug, _load_descriptor(args.slug, {args.slug: args.descriptor_module}), tenant=tenant)
        print(f"{args.slug}: registration VERIFIED (descriptor == committed stamp)")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
