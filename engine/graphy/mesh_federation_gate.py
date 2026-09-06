#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from graphy._portable_flock import fcntl
from graphy.cartograph import resolve_graph
from graphy.tenant import Tenant

CORE_NAMES: frozenset = frozenset()

_SRC_RE = re.compile(rb'"src":\s*"([A-Za-z0-9_]+)://')
_DST_RE = re.compile(rb'"dst":\s*"([A-Za-z0-9_]+)://')
_CHUNK = 4 * 1024 * 1024
_OVERLAP = 256


REGISTRY_CODE_JOIN_EDGES = {
    "touched", "stamped", "calls", "inherits", "imports",
    "reads_table", "reads_view", "uses_sql_fn", "documented_by", "mentions",
}


def _parked() -> set[str]:
    return set()


_REG_CACHE: dict | None = None
_REG_CACHE_KEY: tuple | None = None


def _join_keys_path(tenant: Tenant) -> Path:
    return Path(tenant.join_keys)


def _index_path(tenant: Tenant) -> Path:
    return Path(tenant.data_home) / ".federation_scheme_index.json"


def _index_lock_path(tenant: Tenant) -> Path:
    return Path(tenant.data_home) / ".federation_scheme_index.lock"


def _baseline_path(tenant: Tenant) -> Path:
    return Path(tenant.data_home) / ".federation_graphdir_baseline.txt"


def _write_baseline(tenant: Tenant, dirs: list) -> Path:
    baseline = _baseline_path(tenant)
    tmp = baseline.with_name(baseline.name + f".tmp.{os.getpid()}")
    tmp.write_text("\n".join(dirs) + "\n", encoding="utf-8")
    os.replace(tmp, baseline)
    return baseline


def _registry(tenant: Tenant) -> dict:
    global _REG_CACHE, _REG_CACHE_KEY
    jk = _join_keys_path(tenant)
    key = (jk, jk.stat().st_mtime_ns)
    if _REG_CACHE is not None and _REG_CACHE_KEY == key:
        return _REG_CACHE
    d = json.loads(jk.read_text())
    aliases = {k: v for k, v in d.get("alias_overrides", {}).items() if not str(k).startswith("_")}
    lit = d.get("registered_joins", {}).get("literal_joins", [])
    lit_schemes = {str(x).split("://", 1)[0] for x in lit if "://" in str(x)}
    admitted = d["substrate_roster"].get("admitted", {})
    _REG_CACHE = {"aliases": aliases, "alias_targets": set(aliases.values()) | set(aliases),
                  "literal_schemes": lit_schemes, "admitted": admitted}
    _REG_CACHE_KEY = key
    return _REG_CACHE


def _stdlib(index: dict | None = None) -> set[str]:
    """The standard library as the scheme index names it (``_meta.standard``); nothing ambient."""
    meta = (index or {}).get("_meta") if isinstance(index, dict) else None
    std = (meta or {}).get("standard") or ()
    return {str(x) for x in std}


def roster(tenant: Tenant | None = None) -> set[str]:
    if tenant is None:
        raise ValueError("mesh_federation_gate.roster: tenant is required — graphy resolves identity "
                         "only through a declared Tenant; absent tenant = refuse")
    r = json.loads(_join_keys_path(tenant).read_text())["substrate_roster"]
    g = {x for x in r.get("grandfathered", []) if not str(x).startswith("_")}
    a = {x for x in r.get("admitted", {}) if not str(x).startswith("_")}
    return g | a


def _validate_roster_membership(tenant: Tenant) -> None:
    rost = roster(tenant)
    unknown = sorted(CORE_NAMES - rost)
    if unknown:
        raise RuntimeError(
            f"mesh_federation_gate: roster validation FAILED — kept membership names absent from the "
            f"roster: {unknown}. Every membership set the gate keeps must name only rostered slugs.")


def _scan_schemes(edges_path: Path) -> tuple[set[str], set[str]]:
    src: set[str] = set()
    dst: set[str] = set()
    with open(edges_path, "rb") as f:
        tail = b""
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            buf = tail + chunk
            for m in _SRC_RE.finditer(buf):
                src.add(m.group(1).decode())
            for m in _DST_RE.finditer(buf):
                dst.add(m.group(1).decode())
            tail = buf[-_OVERLAP:]
    return src, dst


def _resolve_member(slug: str, tenant: Tenant) -> Path | None:
    d = Path(tenant.data_home) / f"{slug}_graph"
    if not d.is_dir():
        return None
    try:
        return Path(resolve_graph(str(d)))
    except Exception:
        return d


def _row_cursor(rd: Path) -> dict:
    cur: dict = {}
    sp = rd / "stats.json"
    if sp.exists():
        st = json.loads(sp.read_text())
        cur = {k: st[k] for k in ("freshness_token", "published_head", "worktree", "built_at_sha")
               if st.get(k) is not None}
    ep = rd / "edges.json"
    if ep.exists():
        s = ep.stat()
        cur["edges_size"] = s.st_size
        cur["edges_mtime_ns"] = s.st_mtime_ns
    return cur


def _build_row(slug: str, tenant: Tenant) -> dict:
    rd = _resolve_member(slug, tenant)
    if rd is None:
        return {"own": [], "out": [], "missing": True}
    ep = rd / "edges.json"
    if not ep.exists():
        return {"own": [], "out": [], "missing": True}
    src, dst = _scan_schemes(ep)
    for sidecar in ("wormhole_edges.json", "design_slips.json"):
        wp = rd / sidecar
        if wp.exists():
            wsrc, wdst = _scan_schemes(wp)
            src |= wsrc
            dst |= wdst
    own = src
    out = dst - own
    return {"own": sorted(own), "out": sorted(out), "cursor": _row_cursor(rd)}


def _registry_digest(tenant: Tenant) -> str:
    return hashlib.sha256(_join_keys_path(tenant).read_bytes()).hexdigest()[:16]


def build_index(tenant: Tenant) -> dict:
    idx: dict = {slug: _build_row(slug, tenant) for slug in sorted(roster(tenant))}
    idx["_meta"] = {"registry_digest": _registry_digest(tenant)}
    return idx


@contextlib.contextmanager
def _index_lock(tenant: Tenant):
    lock_path = _index_lock_path(tenant)
    lock_path.touch(exist_ok=True)
    with open(lock_path, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def _write_index(idx: dict, tenant: Tenant) -> None:
    index_path = _index_path(tenant)
    tmp = index_path.with_name(index_path.name + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(idx, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, index_path)


def _atomic_write_index(idx: dict, tenant: Tenant) -> None:
    with _index_lock(tenant):
        _write_index(idx, tenant)


def _index_drifted_rows(idx: dict, tenant: Tenant) -> list:
    out = []
    for slug in roster(tenant):
        rd = _resolve_member(slug, tenant)
        if rd is None:
            continue
        if idx.get(slug, {}).get("cursor") != _row_cursor(rd):
            out.append(slug)
    return out


def _index_drift(idx: dict, tenant: Tenant) -> bool:
    return (idx.get("_meta", {}).get("registry_digest") != _registry_digest(tenant)
            or bool(_index_drifted_rows(idx, tenant))
            or any(s not in idx for s in roster(tenant)))


def _heal_index(idx: dict, tenant: Tenant) -> dict:
    for slug in _index_drifted_rows(idx, tenant):
        idx[slug] = _build_row(slug, tenant)
    for slug in roster(tenant):
        if slug not in idx:
            idx[slug] = _build_row(slug, tenant)
    idx["_meta"] = {"registry_digest": _registry_digest(tenant)}
    return idx


def _load_index(tenant: Tenant, build_if_absent: bool = True) -> dict:
    index_path = _index_path(tenant)
    if not index_path.exists():
        if not build_if_absent:
            raise SystemExit(f"mesh_federation_gate: no scheme index at {index_path} — run --build-index first")
        with _index_lock(tenant):
            if index_path.exists():
                return json.loads(index_path.read_text())
            idx = build_index(tenant)
            _write_index(idx, tenant)
            return idx
    idx = json.loads(index_path.read_text())
    if not _index_drift(idx, tenant):
        return idx
    with _index_lock(tenant):
        idx = json.loads(index_path.read_text())
        if _index_drift(idx, tenant):
            idx = _heal_index(idx, tenant)
            _write_index(idx, tenant)
    return idx


def observe(member_slug: str, tenant: Tenant | None = None) -> dict:
    if tenant is None:
        raise ValueError("mesh_federation_gate.observe: tenant is required — graphy resolves identity "
                         "only through a declared Tenant; absent tenant = refuse")
    result: dict = {"member": member_slug}
    try:
        with _index_lock(tenant):
            index_path = _index_path(tenant)
            idx = json.loads(index_path.read_text()) if index_path.exists() else build_index(tenant)
            if member_slug in roster(tenant):
                idx[member_slug] = _build_row(member_slug, tenant)
            idx["_meta"] = {"registry_digest": _registry_digest(tenant)}
            _write_index(idx, tenant)
        result["index"] = "refreshed"
    except Exception as exc:
        print(f"[federation-observer] WARN: index refresh failed for {member_slug!r}: {exc!r} — the read-time "
              f"self-heal recovers; publish NOT rolled back", file=sys.stderr)
        result["index"] = f"warn:{type(exc).__name__}"
    try:
        from graphy.inventory import main as inventory_main
        inventory_main(tenant=tenant)
        result["inventory"] = "regenerated"
    except Exception as exc:
        print(f"[federation-observer] WARN: inventory regen failed after {member_slug!r}: {exc!r} — publish "
              f"NOT rolled back", file=sys.stderr)
        result["inventory"] = f"warn:{type(exc).__name__}"
    return result


def _owners(index: dict) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for slug, v in index.items():
        if slug.startswith("_") or not isinstance(v, dict):
            continue
        for sch in v.get("own", []):
            owners.setdefault(sch, set()).add(slug)
    return owners


def _edge_join(a: str, b: str, index: dict) -> bool:
    ao, ax = set(index[a]["own"]), set(index[a]["out"])
    bo, bx = set(index[b]["own"]), set(index[b]["out"])
    return bool((bo & ax) or (ao & bx))


def classify(slug: str, index: dict, parked: set[str] | None = None,
             stdlib: set[str] | None = None, reg: dict | None = None,
             *, tenant: Tenant | None = None, core: set[str] | None = None) -> dict:
    if slug not in index:
        raise SystemExit(f"mesh_federation_gate: {slug} not in the scheme index")
    if reg is None:
        if tenant is None:
            raise ValueError("mesh_federation_gate.classify: tenant is required when reg is None — graphy "
                             "resolves identity only through a declared Tenant; absent tenant = refuse")
        reg = _registry(tenant)
    parked = _parked() if parked is None else parked
    stdlib = _stdlib(index) if stdlib is None else stdlib
    core_names = frozenset(core) if core is not None else CORE_NAMES

    if index[slug].get("missing"):
        stamp = reg["admitted"].get(slug) or {}
        if stamp.get("deferred") is True:
            return {
                "name": slug, "axis": ["deferred"], "join_key": [], "state": "parked",
                "evidence": {"no_standalone_graph": True, "deferred": True,
                             "reason": stamp.get("join_key", "admitted, build-pending — off-union until built")},
            }
        if stamp.get("augment") is not True:
            return {
                "name": slug, "axis": ["unknown"], "join_key": [], "state": "missing-error",
                "evidence": {"no_standalone_graph": True,
                             "reason": "dirless roster member with no augment:true stamp — admitted-but-unbuilt, not an augment"},
            }
        from graphy.augment_registry import declared_from_stamp, observed_from_index
        join_keys = sorted(stamp.get("join_keys", []))
        axis = ["code"]
        declared = declared_from_stamp(stamp)
        observed = observed_from_index(stamp, index)
        state = "augment" if observed["scheme_complete"] else "augment_incomplete"
        return {
            "name": slug, "axis": axis, "join_key": join_keys, "state": state,
            "evidence": {"no_standalone_graph": True, "declared": declared, "observed": observed},
        }

    own = set(index[slug]["own"])
    out = set(index[slug]["out"])
    owners = _owners(index)
    rost = {k for k in index if not k.startswith("_")}

    axes = ["code"] if own else ["unknown"]
    join_keys = sorted(own) or []

    joined = sorted(t for t in rost if t != slug and _edge_join(slug, t, index))
    core_partners = [t for t in joined if t in core_names]
    noncore_partners = [t for t in joined if t not in core_names]

    stamp = reg["admitted"].get(slug, {})
    reg_edge_types = sorted(stamp.get("edge_types", []) or [])
    reg_join_key = stamp.get("join_key")
    declared_code_join = sorted(set(reg_edge_types) & REGISTRY_CODE_JOIN_EDGES)

    known = set(owners) | reg["literal_schemes"] | reg["alias_targets"]
    gap_refs = sorted(s for s in out if s not in known and s not in stdlib)

    shared_unwired = sorted(
        t for t in rost if t != slug and t not in joined
        and ((own | out) & (set(index[t]["own"]) | set(index[t]["out"])))
        and t not in parked
    )

    if slug in core_names:
        state = "core"
    elif slug in parked:
        state = "parked"
    elif core_partners or declared_code_join:
        state = "joined-to-core"
    elif noncore_partners:
        state = "joined-within-axis"
    elif shared_unwired or gap_refs:
        state = "cross-axis-gap"
    else:
        state = "solo"

    evidence = {
        "own": sorted(own), "out": sorted(out),
        "core_partners": core_partners, "noncore_partners": noncore_partners,
        "gap_refs": gap_refs, "shared_unwired": shared_unwired,
        "registry_join_key": reg_join_key, "registry_edge_types": reg_edge_types,
        "declared_code_join": declared_code_join,
    }
    return {"name": slug, "axis": axes, "join_key": join_keys, "state": state, "evidence": evidence}


def _canon(card: dict) -> str:
    keep = {k: card[k] for k in ("name", "axis", "join_key", "state", "evidence") if k in card}
    return json.dumps(keep, sort_keys=True)


def verify_card(card: dict, index: dict, reg: dict | None = None,
                parked: set[str] | None = None, stdlib: set[str] | None = None,
                *, tenant: Tenant | None = None) -> tuple[bool, str]:
    slug = card.get("name")
    if slug not in index:
        return False, f"{slug}: not in roster/index (invented or missing)"
    truth = classify(slug, index, reg=reg, parked=parked, stdlib=stdlib, tenant=tenant)
    if _canon(card) != _canon(truth):
        return False, f"{slug}: card != recompute\n  card : {_canon(card)}\n  truth: {_canon(truth)}"
    return True, f"{slug}: ok ({truth['state']})"


def cmd_all(index: dict, tenant: Tenant) -> int:
    rost = sorted(roster(tenant))
    not_in_index = [s for s in rost if s not in index]
    cards = [classify(s, index, tenant=tenant) for s in rost if s in index]
    tally: dict[str, int] = {}
    for c in cards:
        tally[c["state"]] = tally.get(c["state"], 0) + 1
    for st in ("core", "joined-to-core", "joined-within-axis", "cross-axis-gap", "solo", "parked",
               "augment", "augment_incomplete", "missing-error"):
        if tally.get(st):
            print(f"  {st:20} {tally[st]}")
    errors = [c["name"] for c in cards if c["state"] in ("missing-error", "augment_incomplete")] + not_in_index
    covered = {c["name"] for c in cards}
    if covered != set(rost) or errors:
        print(f"EXACT-COVER FAILED: not_in_index={not_in_index} · "
              f"missing_errors={[c['name'] for c in cards if c['state'] == 'missing-error']} · "
              f"augment_incomplete={[c['name'] for c in cards if c['state'] == 'augment_incomplete']} · "
              f"sym_diff={set(rost) ^ covered}", file=sys.stderr)
        return 1
    return 0


def cmd_verify_map(map_path: str, index: dict, tenant: Tenant) -> int:
    m = json.loads(Path(map_path).read_text())
    subs = m.get("substrates", [])
    bad = []
    for card in subs:
        ok, msg = verify_card(card, index, tenant=tenant)
        if not ok:
            bad.append(msg)
    if bad:
        print("VERIFY-MAP FAILED:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    full_roster = roster(tenant)
    not_in_index = sorted(s for s in full_roster if s not in index)
    if not_in_index:
        print(f"VERIFY-MAP: index STALE — roster members absent from the index: {not_in_index} "
              f"(rebuild --build-index)", file=sys.stderr)
        return 1
    map_slugs = {c["name"] for c in subs}
    if map_slugs != full_roster:
        print(f"VERIFY-MAP cover mismatch vs roster: {full_roster ^ map_slugs}", file=sys.stderr)
        return 1
    print(f"  ✓ verify-map: {len(subs)} cards recompute-equal, cover exact (full roster {len(full_roster)})")
    return 0


def emit_map(index: dict, tenant: Tenant) -> dict:
    full_roster = sorted(s for s in roster(tenant) if s in index)
    cards = [classify(s, index, tenant=tenant) for s in full_roster]
    cross_axis_gap = sorted(c["name"] for c in cards if c["state"] == "cross-axis-gap")
    dangling = {c["name"]: c["evidence"]["gap_refs"]
                for c in cards if c.get("evidence", {}).get("gap_refs")}
    tally: dict[str, int] = {}
    for c in cards:
        tally[c["state"]] = tally.get(c["state"], 0) + 1
    backlog_empty = not (cross_axis_gap or dangling)
    return {
        "substrates": cards,
        "tally": tally,
        "smash_backlog": {"cross_axis_gap": cross_axis_gap, "dangling_refs": dangling},
        "gaps_empty_reason": ("no cross-axis-gap substrate and no dangling refs" if backlog_empty else None),
    }


def cmd_emit_map(out_path: str, index: dict, tenant: Tenant) -> int:
    m = emit_map(index, tenant)
    Path(out_path).write_text(json.dumps(m, indent=2, sort_keys=True))
    rc = cmd_verify_map(out_path, index, tenant)
    if rc == 0:
        gaps = len(m["smash_backlog"]["cross_axis_gap"])
        dang = len(m["smash_backlog"]["dangling_refs"])
        print(f"  ✓ emitted {len(m['substrates'])} cards → {out_path} · {m['tally']} · "
              f"smash-backlog: {gaps} gap-substrates + {dang} substrates with dangling refs")
    return rc


def _node_schemes(rd: Path) -> set[str]:
    np_ = rd / "nodes.json"
    if not np_.exists():
        return set()
    nodes = json.loads(np_.read_text())
    ids = nodes.keys() if isinstance(nodes, dict) else (n.get("id", "") for n in nodes)
    return {nid.split("://", 1)[0] for nid in ids if isinstance(nid, str) and "://" in nid}


def census(index: dict | None = None, reg: dict | None = None, node_schemes: dict | None = None,
           *, tenant: Tenant | None = None, base_members: set[str] | None = None) -> list[str]:
    if tenant is None:
        raise ValueError("mesh_federation_gate.census: tenant is required — graphy resolves identity only "
                         "through a declared Tenant; absent tenant = refuse")
    index = _load_index(tenant) if index is None else index
    reg = _registry(tenant) if reg is None else reg
    base = frozenset(base_members) if base_members is not None else frozenset(CORE_NAMES)
    augment_schemes = {jk.split("://", 1)[0]
                       for stamp in reg["admitted"].values() if isinstance(stamp, dict) and stamp.get("augment") is True
                       for jk in stamp.get("join_keys", [])}
    real_owner_schemes = {sch for sch, slugs in _owners(index).items() if slugs - base}
    accounted = (CORE_NAMES | base | set(reg["literal_schemes"]) | augment_schemes | real_owner_schemes
                 | set(reg["alias_targets"]) | _stdlib(index))
    flagged: set[str] = set()
    for member in base:
        if node_schemes is not None:
            member_schemes = set(node_schemes.get(member, ()))
        else:
            rd = _resolve_member(member, tenant)
            member_schemes = _node_schemes(rd) if rd is not None else set()
        for sch in member_schemes:
            if sch not in accounted:
                flagged.add(sch)
    return sorted(flagged)


def cmd_census(index: dict, tenant: Tenant) -> int:
    _validate_roster_membership(tenant)
    flagged = census(index, tenant=tenant)
    if flagged:
        print(f"UNREGISTERED-WALKABLE: {flagged} — a walkable overlay axis with no augment:true stamp is "
              f"invisible to a cold instance. Register it via the augment registry.", file=sys.stderr)
        return 1
    print("census CLEAN — every walkable overlay axis in the base members is a registered augment / owned / literal-join.")
    return 0


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
    ap = argparse.ArgumentParser(prog="mesh_federation_gate")
    ap.add_argument("slug", nargs="?", help="classify one substrate")
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name for every minted card — graphy resolves identity only "
                         "through a declared Tenant, and the receipt name is part of that declaration.")
    ap.add_argument("--data-home", required=True,
                    help="the tenant data_home holding the `<slug>_graph` directories and the federation scheme index.")
    ap.add_argument("--join-keys", required=True,
                    help="path to the tenant's substrate_override_registry.json.")
    ap.add_argument("--build-index", action="store_true", help="(re)build the scheme index + graph-dir baseline (one lock)")
    ap.add_argument("--all", action="store_true", help="classify the whole roster (exact-cover tally)")
    ap.add_argument("--verify-map", metavar="MAP", help="recompute-equality check a federation map")
    ap.add_argument("--emit-map", nargs="?", const="", metavar="PATH",
                    help="assemble the federation map (default: <data_home>/mesh_federation_map.json)")
    ap.add_argument("--observe", metavar="MEMBER",
                    help="post-publish observer: refresh MEMBER's index row + regen the inventory (locked/atomic)")
    ap.add_argument("--census", action="store_true",
                    help="self-audit census: fail loud on an UNREGISTERED-WALKABLE overlay axis")
    a = ap.parse_args(argv)

    tenant = _cli_tenant(a.data_home, a.join_keys)

    if a.observe:
        print(json.dumps(observe(a.observe, tenant), indent=1))
        return 0
    if a.census:
        return cmd_census(_load_index(tenant), tenant)

    if a.build_index:
        _validate_roster_membership(tenant)
        data_home = Path(tenant.data_home)
        with _index_lock(tenant):
            idx = build_index(tenant)
            _write_index(idx, tenant)
            dirs = sorted(p.name for p in data_home.glob("*_graph") if p.is_dir())
            baseline = _write_baseline(tenant, dirs)
        print(f"  ✓ scheme index: {len(idx)} substrates → {_index_path(tenant)}")
        print(f"  ✓ graph-dir baseline: {len(dirs)} dirs → {baseline}")
        return 0

    index = _load_index(tenant)
    if a.emit_map is not None:
        out = Path(a.emit_map) if a.emit_map else Path(tenant.data_home) / "mesh_federation_map.json"
        return cmd_emit_map(out, index, tenant)
    if a.verify_map:
        return cmd_verify_map(a.verify_map, index, tenant)
    if a.all:
        return cmd_all(index, tenant)
    if a.slug:
        print(json.dumps(classify(a.slug, index, tenant=tenant), indent=2, sort_keys=True))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
