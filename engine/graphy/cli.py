
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

from graphy.tenant import Tenant, TenantError

# Every verb's module is imported inside its handler, never here: `graphy --help` and every
# `python -m graphy` a rebuild spawns pay for the verb they run, not for all of them. The
# parser lists the producers by name so it never loads the minting lane; the floor pins this
# tuple to smash.PRODUCERS.
_PRODUCER_NAMES = ("python_ast", "typescript_ast")

__all__ = ["main", "_load_tenant"]




def _flatten(text: str) -> str:
    return re.sub(r"[ \t]*\r?\n[ \t]*", " ", text)




def _load_tenant(descriptor: str) -> Tenant:
    p = Path(descriptor)
    if not p.is_file():
        raise TenantError(f"tenant descriptor not found at {descriptor}")
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise TenantError(
            f"tenant descriptor at {descriptor} is unreadable "
            f"({type(exc).__name__}: {exc})") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise TenantError(
            f"tenant descriptor at {descriptor} is not valid JSON "
            f"({type(exc).__name__}: {exc})") from exc
    if not isinstance(data, dict):
        raise TenantError(
            f"tenant descriptor at {descriptor} must be a JSON object, "
            f"got {type(data).__name__}")
    lanes = data.get("build_lanes")
    if isinstance(lanes, dict):
        data["build_lanes"] = {
            key: tuple(entry) if isinstance(entry, list) else entry
            for key, entry in lanes.items()
        }
    adapters = data.get("adapters")
    if isinstance(adapters, list):
        data["adapters"] = tuple(adapters)
    try:
        return Tenant(**data)
    except TenantError:
        raise
    except TypeError as exc:
        raise TenantError(
            f"tenant descriptor at {descriptor} has an invalid shape "
            f"({type(exc).__name__}: {exc})") from exc


def _roster(tenant: Tenant) -> list[str]:
    from graphy import journal
    slugs = {journal._names(key)[1] for key in tenant.build_lanes}
    return sorted(slugs)


def _parse_lanes(lanes: list[str] | None) -> dict:
    build_lanes: dict = {}
    for pair in lanes or ():
        key, sep, rest = str(pair).partition(":")
        kind, has_cmd, command = rest.partition("=")
        if not sep or not key or not kind:
            raise ValueError(
                f"--lane {pair!r} does not match KEY:KIND[=COMMAND] — the lane declares both halves")
        build_lanes[key] = (command if has_cmd else None, kind)
    return build_lanes


def _descriptor_dict(tenant: Tenant) -> dict:
    from graphy import journal
    return {
        "root": str(tenant.root),
        "data_home": str(tenant.data_home),
        "adapters": list(tenant.adapters),
        "build_lanes": {k: [cmd, kind] for k, (cmd, kind) in tenant.build_lanes.items()},
        "join_keys": str(tenant.join_keys),
        "cursor": tenant.cursor,
        "policy": tenant.policy,
        "journal": str(tenant.journal),
    }




def _cmd_init(args: argparse.Namespace) -> int:
    from graphy import journal
    if not args.tenant:
        print("INIT REFUSED: --tenant is required — graphy never guesses the path to create",
              file=sys.stderr)
        return 2
    target = Path(args.tenant)

    try:
        target.lstat()
    except FileNotFoundError:
        pass
    else:
        print(f"INIT REFUSED: {args.tenant} already exists — init refuses to "
              "overwrite a live path (the target is byte-untouched)",
              file=sys.stderr)
        return 2

    try:
        build_lanes = _parse_lanes(args.lane)
        tenant = Tenant(
            root=Path(args.root),
            data_home=Path(args.data_home),
            adapters=tuple(args.adapter) if args.adapter else (),
            build_lanes=build_lanes,
            join_keys=Path(args.join_keys),
            cursor=args.cursor,
            policy=args.policy,
            journal=Path(args.journal),
        )
    except (TenantError, ValueError, OSError, TypeError) as exc:
        print(f"INIT REFUSED: {exc}", file=sys.stderr)
        return 2

    try:
        Path(tenant.data_home).mkdir(parents=True, exist_ok=True)
        Path(tenant.journal).mkdir(parents=True, exist_ok=True)
        jk = Path(tenant.join_keys)
        if not jk.exists():
            jk.parent.mkdir(parents=True, exist_ok=True)
            jk.write_text(
                json.dumps({
                    "_meta": {"description": "graphy init registry"},
                    "registered_joins": {"literal_joins": {}},
                }, indent=2, sort_keys=True),
                encoding="utf-8")
        target.write_text(
            json.dumps(_descriptor_dict(tenant), indent=2, sort_keys=True),
            encoding="utf-8")
    except OSError as exc:
        print(f"INIT REFUSED: {exc}", file=sys.stderr)
        return 2

    print(f"INIT OK: {target}")
    return 0




def _cmd_build(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import container
    from graphy import release as release_lane
    if not args.tenant:
        print("BUILD REFUSED: --tenant is required — graphy resolves identity only "
              "through a declared Tenant", file=sys.stderr)
        return 2
    if not args.tenant_id:
        print("BUILD REFUSED: --tenant-id is required — the receipt name "
              "compile_store refuses to write without", file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"BUILD REFUSED: {exc}", file=sys.stderr)
        return 2
    substrates = _roster(tenant)
    if not substrates:
        print("BUILD REFUSED: the tenant declares no build_lanes — nothing to compile",
              file=sys.stderr)
        return 2
    try:
        release_lane.require_one_release(tenant.data_home, substrates)
    except release_lane.ReleaseError as exc:
        print(f"BUILD REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        store_path = fstore.store_path_for(substrates, tenant=tenant)
        info = fstore.compile_store(substrates, store_path, tenant=tenant,
                                    tenant_id=args.tenant_id)
    except (fstore.StoreError, OSError, ValueError) as exc:
        print(f"BUILD REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"BUILD OK: compiled {info['nodes']} nodes / {info['edges']} edges "
          f"-> {info['db']}")
    dirs = [Path(tenant.data_home) / f"{s}_graph" for s in substrates]
    now = getattr(args, "container", "all") or "all"
    if now == "none":
        # Every shard pending, no parquet, no duckdb imported: eat's choice — the estate writes them
        # all on the first ask, on one connection, and nobody pays for a file nobody asked for (§61).
        deferred = [container.defer(d) for d in dirs]
        print(f"CONTAINER PENDING: {len(deferred)} shard(s) — graphy estate emits them on the first ask, "
              f"graphy container --emit writes them now")
        return 0
    if now != "all" and now not in {d.name for d in dirs}:
        print(f"BUILD REFUSED: --container {now} names no shard in the roster "
              f"({', '.join(d.name for d in dirs)})", file=sys.stderr)
        return 2
    if container.have_duckdb():
        try:
            if now == "all":
                receipts = container.emit_all(dirs)
                print(f"CONTAINER OK: {container.summarize(receipts)} beside the shards")
            else:
                receipts = container.emit_all([d for d in dirs if d.name == now])
                deferred = [container.defer(d) for d in dirs if d.name != now]
                print(f"CONTAINER OK: {container.summarize(receipts)} beside {now}; {len(deferred)} pending — "
                      f"graphy estate emits them on the first ask, graphy container --emit writes them now")
        except container.ContainerError as exc:
            print(f"CONTAINER FAILED: {exc}", file=sys.stderr)
            return 1
    else:
        print(f"CONTAINER SKIPPED: {container.INSTALL_HINT}; the JSON path is the reader")
    return 0




def _cmd_walk(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import traversal
    if not args.tenant:
        print("WALK REFUSED: --tenant is required — graphy resolves identity only "
              "through a declared Tenant", file=sys.stderr)
        return 2
    if not args.tenant_id:
        print("WALK REFUSED: --tenant-id is required — the receipt name open_for "
              "refuses to open without", file=sys.stderr)
        return 2
    if not args.seed:
        print("WALK REFUSED: --seed is required — a walk needs somewhere to start",
              file=sys.stderr)
        return 2
    if not args.target:
        print("WALK REFUSED: --target is required — a walk needs somewhere to go",
              file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"WALK REFUSED: {exc}", file=sys.stderr)
        return 2
    substrates = _roster(tenant)
    try:
        store = fstore.open_for(substrates, tenant=tenant, tenant_id=args.tenant_id,
                                on_stale=args.on_stale)
    except fstore.StoreError as exc:
        print(_flatten(f"WALK REFUSED: {exc} — rebuild the store with `graphy build`"),
              file=sys.stderr)
        return 2
    except (AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"WALK REFUSED: {exc} — rebuild the store with `graphy build`"),
              file=sys.stderr)
        return 2
    try:
        outcome = traversal.walk(store, traversal.home_for(tenant), args.seed, args.target,
                                 max_depth=args.max_depth, max_nodes=args.max_nodes,
                                 save=not args.no_store)
    except traversal.TraversalError as exc:
        print(f"WALK REFUSED: {exc}", file=sys.stderr)
        return 2
    rc = _render_walk(args, outcome.result)
    if outcome.note:
        print(f"TRAVERSAL SKIPPED: {outcome.note} — the walk ran live and nothing was stored")
    else:
        print(f"TRAVERSAL: source={outcome.source} reads={outcome.reads}"
              + (f" stored={outcome.stored}" if outcome.stored else " stored=no"))
    return rc


def _cmd_bridge(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import traversal
    from graphy import bridge as bridge_lane
    descs, ids = list(args.tenant or ()), list(args.tenant_id or ())
    if len(descs) != 2 or len(ids) != 2:
        print("BRIDGE REFUSED: exactly two --tenant and two --tenant-id, in order — a bridge walks "
              "from one declared tenant into another", file=sys.stderr)
        return 2
    if not args.seed or not args.target:
        print("BRIDGE REFUSED: --seed and --target are required — a walk needs somewhere to start "
              "and somewhere to go", file=sys.stderr)
        return 2
    pairs = []
    for desc, tid in zip(descs, ids):
        try:
            pairs.append((_load_tenant(desc), tid))
        except TenantError as exc:
            print(f"BRIDGE REFUSED: {exc}", file=sys.stderr)
            return 2
    try:
        sides = bridge_lane.open_sides(pairs, on_stale=args.on_stale, roster_of=_roster)
        receipt = bridge_lane.verify_joins(sides, list(args.join or ()), roster_of=_roster,
                                           allow_skew=args.allow_release_skew)
    except bridge_lane.BridgeError as exc:
        print(f"BRIDGE REFUSED: {exc}", file=sys.stderr)
        return 2
    except (fstore.StoreError, AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"BRIDGE REFUSED: {exc} — rebuild the store with `graphy build`"), file=sys.stderr)
        return 2
    counted = [bridge_lane.Side(s.tenant_id, s.tenant, traversal.Counting(s.store)) for s in sides]
    res = bridge_lane.cross(counted, list(args.join), args.seed, args.target,
                            max_depth=args.max_depth, max_nodes=args.max_nodes)
    text, rc = bridge_lane.render(res, receipt, max_depth=args.max_depth, max_nodes=args.max_nodes)
    print(text)
    print("BRIDGE: " + " · ".join(f"{s.tenant_id} reads={s.store.reads} generation={s.store.generation()}"
                                  for s in counted))
    return rc


def _cmd_arms(args: argparse.Namespace) -> int:
    from graphy import fanout
    from graphy import federated_store as fstore
    from graphy import arms as arms_lane
    for flag in ("tenant", "tenant_id", "partition", "dir"):
        if not getattr(args, flag):
            print(f"ARMS REFUSED: --{flag.replace('_', '-')} is required — the arms are cut by a declared "
                  "partition into a declared directory over a declared tenant", file=sys.stderr)
            return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"ARMS REFUSED: {exc}", file=sys.stderr)
        return 2
    roster = _roster(tenant)
    corpus = args.corpus
    if corpus is None:
        if len(roster) != 1:
            print(f"ARMS REFUSED: the tenant holds {len(roster)} corpora ({', '.join(roster)}) — "
                  f"name one with --corpus; a door never guesses", file=sys.stderr)
            return 2
        corpus = roster[0]
    elif corpus not in roster:
        print(f"ARMS REFUSED: {corpus!r} is not a corpus of this tenant ({', '.join(roster)})", file=sys.stderr)
        return 2
    try:
        cut = fanout.load_partition(args.partition)
    except fanout.FanoutError as exc:
        print(f"ARMS REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        store = fstore.open_for(roster, tenant=tenant, tenant_id=args.tenant_id, on_stale=args.on_stale)
    except (fstore.StoreError, AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"ARMS REFUSED: {exc} — rebuild the store with `graphy build`"), file=sys.stderr)
        return 2
    tenant_dir = args.tenant_dir or f"tenants/{Path(tenant.root).name}"
    try:
        regions = arms_lane.render_all(store, corpus, cut, tenant_dir=tenant_dir, tenant_id=args.tenant_id)
        if args.verify:
            text, rc = arms_lane.render_verdicts(arms_lane.verify(regions, args.dir))
            print(text)
            return rc
        done = arms_lane.generate(regions, args.dir)
    except arms_lane.ArmsError as exc:
        print(f"ARMS REFUSED: {exc}", file=sys.stderr)
        return 2
    print("ARMS OK: " + " · ".join(f"{n} {w}" for n, w in done)
          + f" -> {args.dir} (store {store.generation()}, cut sha256:{(cut.sha256 or '')[:12]}…)")
    return 0


def _cmd_farm(args: argparse.Namespace) -> int:
    from graphy import index as shard_index
    from graphy import farm as farm_lane
    if not args.index or not args.work:
        print("FARM REFUSED: --index and --work are required — the farm lands shards in a declared index from a "
              "declared work directory", file=sys.stderr)
        return 2
    if bool(args.top) == bool(args.packages):
        print("FARM REFUSED: exactly one of --top N or --packages <file> names what to mint", file=sys.stderr)
        return 2
    try:
        if args.top:
            specs = farm_lane.top_packages(args.top, producer=args.producer)
        else:
            specs = [ln.split("#", 1)[0].strip() for ln in Path(args.packages).read_text(encoding="utf-8").splitlines()]
            specs = [s for s in specs if s]
    except (farm_lane.FarmError, OSError) as exc:
        print(f"FARM REFUSED: {exc}", file=sys.stderr)
        return 2
    if args.skip:
        skip = {farm_lane.normalize(x) for x in args.skip}
        specs = [s for s in specs if farm_lane.normalize(farm_lane.Spec.parse(s).distribution) not in skip]
    print(f"FARM: {len(specs)} package(s) -> {args.index} with {args.jobs} job(s), producer {args.producer}, "
          f"wheel cap {args.max_wheel_mb} MB")
    try:
        receipt = farm_lane.farm(specs, index=args.index, work=args.work, jobs=args.jobs, python=args.python,
                                 producer=args.producer, max_wheel_mb=args.max_wheel_mb, keep_venv=args.keep_venv,
                                 log=print, force=args.force, timeout=args.timeout)
    except farm_lane.FarmError as exc:
        print(f"FARM REFUSED: {exc}", file=sys.stderr)
        return 2
    t = receipt["totals"]
    print(f"FARM {'OK' if t['minted'] or not t['refused'] else 'RED'}: minted {t['minted']} · skipped {t['skipped']} · "
          f"refused {t['refused']} · shards new {t['shards_new']} / already there {t['shards_exist']} in {t['seconds']}s "
          f"-> {args.index} ({len(shard_index.catalog(args.index))} name(s)); receipt {Path(args.work) / farm_lane.RECEIPT_NAME}")
    return 0 if t["minted"] or not t["refused"] else 1


def _cmd_draw(args: argparse.Namespace) -> int:
    from graphy import fanout
    from graphy import federated_store as fstore
    from graphy import doors
    from graphy import traversal
    from graphy import draw as draw_lane
    from graphy import sugiyama as sugi
    if args.check:
        red = sugi.check_artifact(args.check)
        for r in red:
            print(f"CHECK RED {r}")
        print("CHECK GREEN" if not red else f"CHECK RED: {len(red)} reason(s) over {args.check}")
        return 0 if not red else 1
    if not args.tenant or not args.tenant_id:
        print("DRAW REFUSED: --tenant and --tenant-id are required — graphy resolves identity only through a declared Tenant",
              file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"DRAW REFUSED: {exc}", file=sys.stderr)
        return 2
    roster = _roster(tenant)
    corpus = args.corpus
    if corpus is None and not args.symbol:
        if len(roster) != 1:
            print(f"DRAW REFUSED: the tenant holds {len(roster)} corpora ({', '.join(roster)}) — name one with --corpus; "
                  "a door never guesses", file=sys.stderr)
            return 2
        corpus = roster[0]
    try:
        store = fstore.open_for(roster, tenant=tenant, tenant_id=args.tenant_id, on_stale=args.on_stale)
    except (fstore.StoreError, AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"DRAW REFUSED: {exc} — rebuild the store with `graphy build`"), file=sys.stderr)
        return 2
    counted = traversal.Counting(store)
    counted.find = store.find
    counted.owned, counted.edges = store.owned, store.edges
    try:
        if args.atlas:
            if not args.partition:
                print("DRAW REFUSED: --atlas needs --partition — the arms are the partition's groups", file=sys.stderr)
                return 2
            cut = fanout.load_partition(args.partition)
            r = draw_lane.atlas(counted, corpus, cut, args.atlas, lr=args.lr, min_weight=args.min_weight)
            print(f"ATLAS OK: {len(r['pictures'])} picture(s) × ascii+html -> {args.atlas} (generation {r['generation']})")
            return 0
        if args.symbol:
            seed = doors.resolve(counted, args.symbol)
            pic = draw_lane.neighbourhood(counted, seed, radius=args.radius, max_nodes=args.max_nodes)
        elif args.arm:
            if not args.partition:
                print("DRAW REFUSED: --arm needs --partition", file=sys.stderr)
                return 2
            pic = draw_lane.arm(counted, corpus, fanout.load_partition(args.partition), args.arm, min_weight=args.min_weight)
        elif args.pillars:
            if not args.partition:
                print("DRAW REFUSED: --pillars needs --partition", file=sys.stderr)
                return 2
            pic = draw_lane.pillars(counted, corpus, fanout.load_partition(args.partition), min_weight=args.min_weight)
        else:
            pic = draw_lane.units(counted, corpus, depth=args.depth, min_weight=args.min_weight)
        text = draw_lane.render(pic, emit=args.emit, lr=args.lr, color=(args.emit == "ascii" and not args.out and args.color),
                                interactive=args.interactive, title=args.title)
    except (draw_lane.DrawError, doors.DoorError, fanout.FanoutError) as exc:
        print(f"DRAW UNANSWERABLE: {exc}", file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        line = f"DRAW OK: {pic.summary()} -> {args.out}"
        if args.emit == "html":
            red = sugi.check_artifact(args.out)
            line += " · CHECK " + ("GREEN" if not red else "RED " + "; ".join(red))
        print(line)
        return 0 if not (args.emit == "html" and red) else 1
    print(text)
    print(f"DRAW: {pic.summary()} reads={counted.reads} generation={store.generation()}")
    return 0


def _cmd_showcase(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import showcase as showcase_lane
    if not args.target:
        print("SHOWCASE REFUSED: name a git url or a repo path (`.` for the one you stand in)", file=sys.stderr)
        return 2
    try:
        r = showcase_lane.showcase(args.target, out=args.out, work=args.work, log=print, no_provision=args.no_provision)
    except (showcase_lane.ShowcaseError, TenantError, fstore.StoreError, OSError) as exc:
        print(f"SHOWCASE REFUSED: {exc}", file=sys.stderr)
        return 2
    if r["check"]:
        print(f"SHOWCASE RED: the page failed its check — {'; '.join(r['check'])} ({r['page']})", file=sys.stderr)
        return 1
    print(f"SHOWCASE OK: {r['package']} · {len(r['arms'])} arm(s) ({', '.join(r['arms'])}) · {r['ring']} ring shard(s) · "
          f"CHECK GREEN · {r['seconds']}s\n  the page:  {r['page']}\n  the text:  {r['text']}")
    return 0


def _cmd_door(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import doors
    from graphy import traversal
    verb = args.door.upper()
    if not args.tenant or not args.tenant_id:
        print(f"{verb} REFUSED: --tenant and --tenant-id are required — graphy resolves identity "
              "only through a declared Tenant", file=sys.stderr)
        return 2
    if not args.symbol:
        print(f"{verb} REFUSED: a symbol is required — an exact node id or its dotted tail", file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"{verb} REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        store = fstore.open_for(_roster(tenant), tenant=tenant, tenant_id=args.tenant_id,
                                on_stale=args.on_stale)
    except (fstore.StoreError, AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"{verb} REFUSED: {exc} — rebuild the store with `graphy build`"), file=sys.stderr)
        return 2
    counted = traversal.Counting(store)
    counted.find = store.find
    try:
        seed = doors.resolve(counted, args.symbol)
    except doors.DoorError as exc:
        print(f"{verb} UNANSWERABLE: {exc}", file=sys.stderr)
        return 1
    if args.door == "descend":
        out = doors.render_descend(doors.descend(counted, seed, args.depth), args.limit)
    elif args.door == "blast":
        out = doors.render_blast(doors.blast(counted, seed, args.depth), args.limit)
    else:
        out = doors.render_explain(doors.explain(counted, seed, args.depth, tenant=tenant), args.limit)
    print(out)
    print(f"DOOR: {args.door} reads={counted.reads} generation={store.generation()}")
    return 0


def _cmd_pillars(args: argparse.Namespace) -> int:
    from graphy import fanout
    from graphy import federated_store as fstore
    from graphy import pillars as pillars_lane
    if not args.tenant or not args.tenant_id:
        print("PILLARS REFUSED: --tenant and --tenant-id are required — graphy resolves identity "
              "only through a declared Tenant", file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"PILLARS REFUSED: {exc}", file=sys.stderr)
        return 2
    roster = _roster(tenant)
    if not roster:
        print("PILLARS REFUSED: the tenant declares no build_lanes", file=sys.stderr)
        return 2
    corpus = args.corpus
    if corpus is None:
        if len(roster) != 1:
            print(f"PILLARS REFUSED: the tenant holds {len(roster)} corpora ({', '.join(roster)}) — "
                  f"name one with --corpus; a door never guesses", file=sys.stderr)
            return 2
        corpus = roster[0]
    elif corpus not in roster:
        print(f"PILLARS REFUSED: {corpus!r} is not a corpus of this tenant ({', '.join(roster)})",
              file=sys.stderr)
        return 2
    try:
        store = fstore.open_for(roster, tenant=tenant, tenant_id=args.tenant_id, on_stale=args.on_stale)
    except (fstore.StoreError, AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"PILLARS REFUSED: {exc} — rebuild the store with `graphy build`"), file=sys.stderr)
        return 2
    try:
        graph = pillars_lane.module_graph(store, corpus, depth=args.depth)
        proposal = pillars_lane.propose(graph, arms=args.arms, floor=args.floor, owned=args.owned,
                                       client=args.client, rest=args.rest)
    except pillars_lane.PillarsError as exc:
        print(f"PILLARS UNANSWERABLE: {exc}", file=sys.stderr)
        return 1
    print(pillars_lane.render(proposal, graph))
    if args.write:
        doc = pillars_lane.to_partition(proposal)
        pillars_lane.write_partition(args.write, doc)
        print(f"PILLARS WROTE: {args.write} — {len(doc['groups'])} group(s), rest={doc['rest']}; "
              f"cut the shard by it with `graphy fanout --partition`")
    print(f"DOOR: pillars generation={store.generation()}")
    if args.against:
        try:
            cut = fanout.load_partition(args.against)
        except fanout.FanoutError as exc:
            print(f"PILLARS REFUSED: {exc}", file=sys.stderr)
            return 2
        moved = pillars_lane.diff(proposal, cut)
        print(pillars_lane.render_diff(moved, args.against))
        return 1 if moved else 0
    return 0


def _cmd_refresh(args: argparse.Namespace) -> int:
    from graphy import refresh as refresh_lane
    from graphy import smash as smash_lane
    if not args.tenant or not args.tenant_id or not args.package:
        print("REFRESH REFUSED: --tenant, --tenant-id and --package are required — graphy never guesses "
              "which tenant, which receipt, or which shard is the root", file=sys.stderr)
        return 2
    try:
        receipt = refresh_lane.refresh(args.tenant, args.tenant_id, package=args.package, release=args.release,
                                       site_packages=args.site_packages, python=args.python, fixture=args.fixture,
                                       force=args.force, check_only=args.check, log=print)
    except refresh_lane.CheckFailed as exc:
        print(f"REFRESH CHECK FAILED: {exc}\n  the sibling stays on disk; the current substrate is untouched",
              file=sys.stderr)
        return 1
    except (refresh_lane.RefreshError, smash_lane.SmashError, TenantError, OSError, ValueError) as exc:
        print(f"REFRESH REFUSED: {exc}", file=sys.stderr)
        return 2
    if receipt["verdict"] == "NEWER":
        print(f"REFRESH NEWER: {receipt['distribution']} {receipt['current']} -> {receipt['release']}; run without --check to mint")
    return 0


def _cmd_mcp(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import mcp as mcp_server
    if not args.tenant or not args.tenant_id:
        print("MCP REFUSED: --tenant and --tenant-id are required — graphy resolves identity only "
              "through a declared Tenant", file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"MCP REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        tools = mcp_server.open_tools(tenant, args.tenant_id, _roster(tenant), on_stale=args.on_stale)
    except (fstore.StoreError, AttributeError, TypeError, KeyError, OSError) as exc:
        print(_flatten(f"MCP REFUSED: {exc} — rebuild the store with `graphy build`"), file=sys.stderr)
        return 2
    print(f"graphy mcp: serving tenant {args.tenant_id!r} generation {tools.generation} on stdio "
          f"({', '.join(t['name'] for t in mcp_server.TOOLS)})", file=sys.stderr)
    return mcp_server.serve(tools)


def _cmd_traversals(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import traversal
    dirs, rc = _tenant_dirs(args, "TRAVERSALS")
    if dirs is None:
        return rc
    tenant = _load_tenant(args.tenant)
    home = traversal.home_for(tenant)
    if not traversal.have_duckdb():
        print(f"TRAVERSALS REFUSED: {traversal.INSTALL_HINT}", file=sys.stderr)
        return 2
    try:
        store = fstore.open_for(_roster(tenant), tenant=tenant, tenant_id=args.tenant_id,
                                on_stale=args.on_stale)
    except fstore.StoreError as exc:
        print(_flatten(f"TRAVERSALS REFUSED: {exc}"), file=sys.stderr)
        return 2
    live = store.generation()
    if not args.replay:
        n = 0
        for gen_dir in sorted(p for p in home.iterdir() if p.is_dir()) if home.is_dir() else []:
            for seed, rp in traversal.stored(home, gen_dir.name).items():
                r = json.loads(rp.read_text(encoding="utf-8"))
                tag = "live" if gen_dir.name == live else "past"
                print(f"  {tag} {gen_dir.name[:12]}  {seed} -> {r['target']}  hops={r['hops']} "
                      f"rows={r['rows']} exhausted={r['exhausted']} reads={r['reads']}")
                n += 1
        print(f"TRAVERSALS OK: {n} stored walk(s) under {home} (live generation {live[:12]})")
        return 0
    try:
        reports = traversal.replay(store, home)
    except traversal.TraversalError as exc:
        print(f"TRAVERSALS REFUSED: {exc}", file=sys.stderr)
        return 2
    broken_total = 0
    for rep in reports:
        broken_total += len(rep["broken"])
        state = "HOLDS" if not rep["broken"] else "BROKEN"
        print(f"  {state} {rep['generation'][:12]} -> {rep['live'][:12]}  {rep['seed']} -> {rep['target']}  "
              f"hops_checked={rep['hops_checked']} broken={len(rep['broken'])} on_path={len(rep['path_broken'])}")
        for b in rep["broken"][: args.limit]:
            print(f"      hop {b['hop']}: {b['via_src']} -[{b['relation']}]-> {b['node']}  ({b['why']})")
        if len(rep["broken"]) > args.limit:
            print(f"      … {len(rep['broken']) - args.limit} more (raise --limit)")
    if not reports:
        print(f"TRAVERSALS REPLAY OK: no stored walk from a past generation under {home}")
        return 0
    print(f"TRAVERSALS REPLAY {'OK' if not broken_total else 'BROKEN'}: {len(reports)} past walk(s), "
          f"{broken_total} broken hop(s) against live generation {live[:12]}")
    return 0 if not broken_total else 1


def _render_walk(args: argparse.Namespace, result) -> int:
    if result.found:
        nodes = [result.seed] + [s.dst for s in result.steps]
        print(f"WALK PATH: seed={result.seed} target={result.target} "
              f"hops={len(result.steps)} visited={result.visited} "
              f"steps={' -> '.join(nodes)}")
        return 0
    if result.stopped_by is None:
        print(f"WALK NO-PATH: search exhausted (visited={result.visited}) — "
              "the snapshot genuinely does not connect them")
        return 1
    if result.stopped_by == "max_depth":
        print(f"WALK BUDGET-EXHAUSTED: max_depth={args.max_depth} "
              f"(visited={result.visited}) — a path may still exist; raise --max-depth")
        return 1
    if result.stopped_by == "max_nodes":
        print(f"WALK BUDGET-EXHAUSTED: max_nodes={args.max_nodes} "
              f"(visited={result.visited}) — a path may still exist; raise --max-nodes")
        return 1
    if result.stopped_by == "seed-absent":
        print(f"WALK UNANSWERABLE: seed {result.seed} absent from this snapshot")
        return 1
    if result.stopped_by == "target-absent":
        print(f"WALK UNANSWERABLE: target {result.target} absent from this snapshot")
        return 1
    print(f"WALK REFUSED: unknown stopped_by {result.stopped_by!r}")
    return 2




def _torn_line(jfile: Path) -> tuple[str, str] | None:
    try:
        lines = jfile.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError, AttributeError, TypeError, KeyError) as exc:
        return ("COULD-NOT-TELL", f"unreadable ({type(exc).__name__}: {exc})")
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except ValueError:
            return ("RED", f"line {i} is not valid JSON")
    return None


def _cmd_check(args: argparse.Namespace) -> int:
    from graphy import federated_store as fstore
    from graphy import journal
    from graphy import container
    from graphy import release as release_lane
    if not args.tenant:
        print("CHECK REFUSED: --tenant is required — graphy resolves identity only "
              "through a declared Tenant", file=sys.stderr)
        return 2
    if not args.tenant_id:
        print("CHECK REFUSED: --tenant-id is required — the receipt name open_for "
              "refuses to audit without", file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"CHECK REFUSED: {exc}", file=sys.stderr)
        return 2
    substrates = _roster(tenant)
    findings: list[tuple[str, str, str]] = []

    data_home = Path(tenant.data_home)
    from graphy.cartograph import cursor_drift, tenant_exclude
    drift = cursor_drift(tenant.cursor, Path(tenant.root), exclude=tenant_exclude(Path(args.tenant), tenant))
    if drift is not None:                                # graphyos #39: the cursor covers the working tree
        findings.append((
            "COULD-NOT-TELL" if drift.startswith("the repo's HEAD is unreadable") else "RED",
            f"cursor lane: STALE — {drift}",
            "re-eat the repo (`graphy eat .`) or run the tenant's rebuild so the store answers from the tree you stand in"))
    for scheme, pins in release_lane.collisions(release_lane.roster_releases(data_home, substrates)):
        findings.append((
            "RED",
            f"release lane: scheme {scheme!r} is owned under two releases — "
            + ", ".join(f"{slug}_graph={pin}" for slug, pin in sorted(pins.items())),
            "a roster names one release per scheme; drop one shard or declare it in another tenant"))
    store_blocked: tuple[str, str, str] | None = None
    for s in sorted(substrates):
        if store_blocked is not None:
            break
        graph_dir = data_home / f"{s}_graph"
        try:
            from graphy.native_json_graph_ir import load_graph_ir as _load_ir
            _load_ir(graph_dir)                 # the audit parses — once per shard per process
            fstore._shard_input_digest(graph_dir)
        except (fstore.StoreError, AttributeError, TypeError, KeyError,
                ValueError, OSError) as exc:
            store_blocked = (
                "COULD-NOT-TELL",
                f"store lane: cannot measure the shard for graph {s!r} at "
                f"{graph_dir}: {exc}",
                "restore the unreadable input and re-run graphy check")
    if store_blocked is None:
        try:
            fstore._scheme_index_input_digest(
                data_home / fstore._INDEX_INPUT_KEY, sorted(substrates))
        except (fstore.StoreError, AttributeError, TypeError, KeyError,
                ValueError, OSError) as exc:
            store_blocked = (
                "COULD-NOT-TELL",
                f"store lane: cannot measure the scheme index at "
                f"{data_home / fstore._INDEX_INPUT_KEY}: {exc}",
                "restore the unreadable input and re-run graphy check")
    if store_blocked is None:
        try:
            fstore._registry_input_digest(Path(tenant.join_keys))
        except (fstore.StoreError, AttributeError, TypeError, KeyError,
                ValueError, OSError) as exc:
            store_blocked = (
                "COULD-NOT-TELL",
                f"store lane: cannot measure the registry at "
                f"{tenant.join_keys}: {exc}",
                "restore the unreadable input and re-run graphy check")
    if store_blocked is not None:
        findings.append(store_blocked)
    else:
        try:
            fstore.open_for(substrates, tenant=tenant, tenant_id=args.tenant_id,
                            on_stale="refuse")
        except fstore.StoreError as exc:
            findings.append((
                "RED",
                f"store lane: {exc}",
                "rebuild the store with `graphy build`"))
        except (AttributeError, TypeError, KeyError, ValueError, OSError) as exc:
            findings.append((
                "COULD-NOT-TELL",
                f"store lane: {exc}",
                "restore the unreadable input and re-run graphy check"))

    for graph_class in sorted(tenant.build_lanes):
        base, slug = journal._names(graph_class)
        graph_dir = Path(tenant.data_home) / f"{slug}_graph"
        snap = journal.snapshot_ids(graph_dir)
        if snap is None:
            findings.append((
                "COULD-NOT-TELL",
                f"journal lane {graph_class!r}: the surface at {graph_dir} exists "
                "but could not be read — a diff against it would lie",
                "restore a readable graph surface and re-run graphy check"))
        jfile = Path(tenant.journal) / f"{base}.journal.jsonl"
        if jfile.exists():
            torn = _torn_line(jfile)
            if torn is not None:
                state, detail = torn
                if state == "RED":
                    findings.append((
                        "RED",
                        f"journal lane {graph_class!r}: torn journal {jfile} ({detail})",
                        "acknowledge the torn history before the next publish"))
                else:
                    findings.append((
                        "COULD-NOT-TELL",
                        f"journal lane {graph_class!r}: journal {jfile} {detail}",
                        "restore a readable journal and re-run graphy check"))

    states = {}
    for graph_class in sorted(tenant.build_lanes):
        _base, slug = journal._names(graph_class)
        try:
            states[slug] = container.verify(Path(tenant.data_home) / f"{slug}_graph")
        except (OSError, ValueError) as exc:           # a shard the container cannot read is named, never a crash
            states[slug] = "unreadable"
            findings.append((
                "COULD-NOT-TELL",
                f"container lane: shard {slug}_graph unreadable ({type(exc).__name__}: {exc})",
                "restore the shard, then graphy build"))
    stale = sorted(s for s, st in states.items() if st == "stale")
    if stale:
        findings.append((
            "RED",
            f"container lane: parquet older than the shard for {stale}",
            "rebuild the store with `graphy build` (duckdb installed) or `graphy container --emit`"))

    if not findings:
        fresh = sum(1 for st in states.values() if st == "fresh")
        pending = sum(1 for st in states.values() if st == "pending")
        note = (f"; container fresh for {fresh}/{len(states)} shard(s)"
                + (f", {pending} pending until the estate asks" if pending else "")
                if fresh or pending
                else "; no container (duckdb not installed or never emitted) — the JSON path is the reader")
        print("CHECK OK: descriptor valid; store fresh; journal readable for all "
              f"declared graphs{note}")
        return 0
    for state, reason, repair in findings:
        prefix = "CHECK RED:" if state == "RED" else "CHECK COULD-NOT-TELL:"
        print(_flatten(f"{prefix} {reason} — {repair}"), file=sys.stderr)
    return 1




def _cmd_fanout(args: argparse.Namespace) -> int:
    from graphy import fanout
    if not args.out:
        print("FANOUT REFUSED: --out is required — the fan-out needs a place to "
              "land", file=sys.stderr)
        return 2
    if args.verify:
        verdict = fanout.verify_fanout(args.out)
        line = f"FANOUT VERIFY: {verdict['status']} — {verdict['detail']}"
        if verdict["mismatched"]:
            line += " · " + ", ".join(verdict["mismatched"][:5])
        if verdict["status"] == "COHERENT":
            print(line)
            return 0
        print(line, file=sys.stderr)
        return 1
    if not args.graph_dir:
        print("FANOUT REFUSED: --graph-dir is required — the shard is the only "
              "identity the fan-out resolves", file=sys.stderr)
        return 2
    if args.partition and args.depth is not None:
        print("FANOUT REFUSED: --depth and --partition are two cuts — name one",
              file=sys.stderr)
        return 2
    try:
        if args.partition:
            cut = fanout.load_partition(args.partition)
        else:
            cut = fanout.Cut(depth=args.depth if args.depth is not None else 1)
        receipt = fanout.compile_fanout(args.graph_dir, args.out, cut)
    except fanout.FanoutError as exc:
        print(f"FANOUT REFUSED: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"FANOUT REFUSED: {exc}", file=sys.stderr)
        return 2
    how = receipt["cut"]
    how_s = (f"depth {how['depth']}" if how["kind"] == "depth"
             else f"partition {how['sha256'][:12]}… ({how['groups']} named, rest={how['rest']})")
    print(f"FANOUT OK: {len(receipt['groups'])} group(s) by {how_s} -> {args.out}")
    return 0




def _cmd_smash(args: argparse.Namespace) -> int:
    from graphy import smash as smash_lane
    from graphy.parity import ParityError
    for flag in ("package", "site_packages", "out"):
        if not getattr(args, flag):
            print(f"SMASH REFUSED: --{flag.replace('_', '-')} is required — graphy never guesses "
                  "the package, where its ring lives, or where shards land", file=sys.stderr)
            return 2
    try:
        receipt = smash_lane.smash(args.package, site_packages=args.site_packages, out=args.out,
                                   corpus=args.corpus, ring=not args.no_ring, log=print,
                                   producer=args.producer)
    except (smash_lane.SmashError, smash_lane.typescript_ast.ProducerUnavailable, OSError, ValueError) as exc:
        print(f"SMASH REFUSED: {exc}", file=sys.stderr)
        return 2
    unresolved = receipt["unresolved"]
    print(f"RING: {len(receipt['minted'])} shard(s) · stdlib skipped {len(receipt['stdlib'])}"
          + (f" · unresolved {', '.join(unresolved)}" if unresolved else " · ring closed")
          + f" -> {Path(receipt['out']) / smash_lane.RING_NAME}")
    if args.parity:
        root_shard = receipt["minted"][args.package]["shard"]
        try:
            golden = smash_lane.parity(root_shard, args.parity)
        except ParityError as exc:
            print(f"PARITY FAILED: {exc}", file=sys.stderr)
            return 1
        counts = receipt["minted"][args.package]
        print(f"PARITY OK: {golden.surface}@{golden.oracle_commit} — {counts['nodes']} nodes / "
              f"{counts['edges']} edges identical to {args.parity}")
    print(f"SMASH OK: {args.package} + {len(receipt['minted']) - 1} ring shard(s) -> {receipt['out']}")
    return 0


def _cmd_converge(args: argparse.Namespace) -> int:
    from graphy import converge as converge_lane
    if not args.tenant or not args.tenant_id:
        print("CONVERGE REFUSED: --tenant and --tenant-id are required — graphy resolves identity "
              "only through a declared Tenant", file=sys.stderr)
        return 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"CONVERGE REFUSED: {exc}", file=sys.stderr)
        return 2
    slugs = _roster(tenant)
    if not slugs:
        print("CONVERGE REFUSED: the tenant declares no build_lanes — nothing to measure", file=sys.stderr)
        return 2
    try:
        ring = converge_lane.load_ring(tenant.data_home, slugs)
    except (OSError, ValueError) as exc:
        print(f"CONVERGE REFUSED: {exc}", file=sys.stderr)
        return 2
    if args.resolve:
        for slug in slugs:
            s = converge_lane.resolve(ring, slug, write=True)
            via = " · ".join(f"{k} {v}" for k, v in s["via"].items()) or "none"
            left = " · ".join(f"{k} {v}" for k, v in s["unresolved"].items()) or "none"
            print(f"RESOLVE OK: {slug} {s['labels']} label(s) -> {s['resolved']} edge(s) "
                  f"({via}; {s['cross_shard']} cross-shard) · left as text: {left} -> {s['sidecar']}")
        ring = converge_lane.load_ring(tenant.data_home, slugs)
    report = converge_lane.converge(ring)
    print(f"CONVERGE: {len(slugs)} shard(s) under {tenant.data_home} · "
          f"{report['wormholes']} wormhole edge(s) over {report['wormhole_nodes']} node(s)")
    for row in report["pairs"]:
        kinds = " ".join(f"{k}={v}" for k, v in row["by_type"].items())
        print(f"  {row['from']:>20} -> {row['to']:<20} {row['edges']:6} edge(s) over {row['nodes']:5} node(s)   {kinds}")
    for slug, st in report["shards"].items():
        print(f"  {slug:>20}    edges {st['edges']} · with a dst {st['with_dst']} · into other shards "
              f"{st['into_other_shards']} · labels left as text {st['labels']}")
    if args.resolve:
        print(f"RESOLVED: rebuild the store to walk the new edges — graphy build --tenant {args.tenant} --tenant-id {args.tenant_id}")
    return 0


def _tenant_dirs(args: argparse.Namespace, verb: str) -> tuple[list[Path] | None, int]:
    if not args.tenant or not args.tenant_id:
        print(f"{verb} REFUSED: --tenant and --tenant-id are required — graphy resolves identity "
              "only through a declared Tenant", file=sys.stderr)
        return None, 2
    try:
        tenant = _load_tenant(args.tenant)
    except TenantError as exc:
        print(f"{verb} REFUSED: {exc}", file=sys.stderr)
        return None, 2
    slugs = _roster(tenant)
    if not slugs:
        print(f"{verb} REFUSED: the tenant declares no build_lanes", file=sys.stderr)
        return None, 2
    return [Path(tenant.data_home) / f"{s}_graph" for s in slugs], 0


def _cmd_container(args: argparse.Namespace) -> int:
    from graphy import container
    dirs, rc = _tenant_dirs(args, "CONTAINER")
    if dirs is None:
        return rc
    if args.emit:
        try:
            receipts, kept = container.emit_missing(dirs)
        except container.ContainerError as exc:
            print(f"CONTAINER REFUSED: {exc}", file=sys.stderr)
            return 2
        print(f"CONTAINER OK: {container.summarize(receipts)}" + (f" · {kept} already fresh" if kept else ""))
        return 0
    states = {d.name: container.verify(d) for d in dirs}
    for name, st in states.items():
        print(f"  {name:28} {st}")
    stale = [n for n, st in states.items() if st not in ("fresh", "pending")]
    pending = [n for n, st in states.items() if st == "pending"]
    fresh = len(dirs) - len(stale) - len(pending)
    if stale:
        print(f"CONTAINER STALE: {fresh}/{len(dirs)} fresh — emit with --emit")
        return 1
    if pending:
        print(f"CONTAINER PENDING: {fresh}/{len(dirs)} fresh · {len(pending)} pending — "
              f"graphy estate emits them on the first ask; --emit writes them now")
        return 0
    print(f"CONTAINER OK: {fresh}/{len(dirs)} fresh")
    return 0


def _cmd_estate_index(args: argparse.Namespace) -> int:
    from graphy import container
    from graphy import index_estate
    index = Path(args.index)
    if not index.is_absolute():
        print(f"ESTATE REFUSED: --index must be absolute, got {args.index} — a relative index is an ambient fallback", file=sys.stderr)
        return 2
    if not (index / "catalog.json").is_file():
        print(f"ESTATE REFUSED: no catalog.json at {index} — not an index", file=sys.stderr)
        return 2
    if args.emit:
        try:
            r = index_estate.emit_index(index)
        except container.ContainerError as exc:
            print(f"ESTATE REFUSED: {exc}", file=sys.stderr)
            return 2
        print(f"ESTATE EMITTED: {r['shards']} shard(s) · {r['nodes']} nodes · {r['edges']} edges in {r['seconds']}s "
              f"-> {index / index_estate.ESTATE_DIR} (catalog {r['catalog_sha256'][:12]}…)")
        if not args.sql:
            return 0
    if not args.sql and not args.emit:
        state, receipt = index_estate.verify_index_estate(index)
        print(f"ESTATE {state.upper()}: {index / index_estate.ESTATE_DIR}"
              + (f" — {receipt['shards']} shard(s) · {receipt['nodes']} nodes · {receipt['edges']} edges" if receipt else "")
              + ("" if state == "fresh" else "; run with --emit"))
        return 0 if state == "fresh" else 1
    try:
        con, receipt = index_estate.estate_index(index)
    except container.ContainerError as exc:
        print(f"ESTATE REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        started = __import__("time").perf_counter()
        cur = con.execute(args.sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        took = __import__("time").perf_counter() - started
    except Exception as exc:  # duckdb's own error classes; the query is the user's
        print(f"ESTATE REFUSED: {exc}", file=sys.stderr)
        return 2
    finally:
        con.close()
    print("\t".join(cols))
    for row in rows[: args.limit]:
        print("\t".join("" if v is None else str(v) for v in row))
    print(f"ESTATE OK: {len(rows)} row(s) over {receipt['shards']} shard(s) in {took * 1000:.1f} ms"
          + (f" (showing {args.limit})" if len(rows) > args.limit else ""))
    return 0


def _cmd_estate(args: argparse.Namespace) -> int:
    from graphy import container
    from graphy import traversal
    if args.index:
        return _cmd_estate_index(args)
    dirs, rc = _tenant_dirs(args, "ESTATE")
    if dirs is None:
        return rc
    sql = args.sql or ("SELECT corpus, count(*) AS edges FROM adj GROUP BY corpus ORDER BY edges DESC")
    try:
        con = container.estate(dirs, traversals=traversal.home_for(_load_tenant(args.tenant)), log=print)
    except container.ContainerError as exc:
        print(f"ESTATE REFUSED: {exc}", file=sys.stderr)
        return 2
    try:
        started = __import__("time").perf_counter()
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        took = __import__("time").perf_counter() - started
    except Exception as exc:  # duckdb's own error classes; the query is the user's
        print(f"ESTATE REFUSED: {exc}", file=sys.stderr)
        return 2
    finally:
        con.close()
    print("\t".join(cols))
    for row in rows[: args.limit]:
        print("\t".join("" if v is None else str(v) for v in row))
    print(f"ESTATE OK: {len(rows)} row(s) over {len(dirs)} shard(s) in {took * 1000:.1f} ms"
          + (f" (showing {args.limit})" if len(rows) > args.limit else ""))
    return 0


_NOT_A_PACKAGE = frozenset({"tests", "test", "docs", "doc", "examples", "example", "scripts", "benchmarks",
                            "build", "dist", "node_modules", "venv"})


def _package_candidates(repo: Path) -> list[Path]:
    """The importable packages a repo carries: a top-level or src/ directory with __init__.py."""
    out: list[Path] = []
    for base in (repo, repo / "src"):
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if (d.is_dir() and (d / "__init__.py").is_file() and not d.name.startswith((".", "_"))
                    and d.name not in _NOT_A_PACKAGE):
                out.append(d)
    return out


def _scheme_index_from_ring(sub: Path, description: str) -> None:
    from graphy import smash as smash_lane
    ring = json.loads((sub / smash_lane.RING_NAME).read_text(encoding="utf-8"))
    index = {"_meta": {"description": description, "standard": ring.get("standard", [])}, **ring["scheme_index"]}
    (sub / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n",
                                                       encoding="utf-8")


def _eat_typescript(args: argparse.Namespace, repo: Path) -> int:
    """The bolt-on over a TypeScript repo: the corpus is ``src/`` (or the package.json ``source``
    dir, or the repo), the scheme is the package.json name as a slug, the ring is resolved from
    ``--site-packages`` (its node_modules)."""
    from graphy import smash as smash_lane
    try:
        meta = json.loads((repo / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"EAT REFUSED: {repo / 'package.json'} unreadable ({exc})", file=sys.stderr)
        return 2
    name = args.package or (meta.get("name") if isinstance(meta.get("name"), str) else None) or repo.name
    package = smash_lane.slug_for_specifier(name)
    if not package:
        print(f"EAT REFUSED: {name!r} cannot name a shard — the slug grammar is [a-z0-9_]+", file=sys.stderr)
        return 2
    corpus = None
    src_field = meta.get("source")
    if isinstance(src_field, str):
        cand = (repo / src_field)
        cand = cand.parent if cand.is_file() else cand
        if cand.is_dir():
            corpus = cand
    if corpus is None:
        for cand in (repo / "src", repo):
            if cand.is_dir() and smash_lane.typescript_ast.is_package_dir(cand):
                corpus = cand
                break
    if corpus is None:
        print(f"EAT REFUSED: no TypeScript source under {repo} (src/ or the package.json `source`)", file=sys.stderr)
        return 2
    return _eat_run(args, repo, package, corpus, "typescript_ast")


def _cmd_eat(args: argparse.Namespace) -> int:
    """The bolt-on in one verb: mint the repo's package and its import ring into <repo>/.graphy,
    declare the tenant, resolve the labels, compile the store, emit the container, audit."""
    from graphy import container
    target = args.repo or args.repo_pos
    if not target:
        print("EAT REFUSED: name the codebase to eat — `graphy eat .` for the one you stand in", file=sys.stderr)
        return 2
    repo = Path(target).expanduser().resolve()
    if not repo.is_dir():
        print(f"EAT REFUSED: not a directory: {repo}", file=sys.stderr)
        return 2
    args._t0 = time.perf_counter()
    print(f"EAT: repo {repo}")
    candidates = _package_candidates(repo)
    producer = args.producer
    if producer is None:
        producer = "typescript_ast" if not candidates and (repo / "package.json").is_file() else "python_ast"
    corpus = None
    if producer != "typescript_ast":
        # Which package to eat is settled before anything is installed: a repo with ten importable
        # packages used to pay a minute of pip install to be told to pass --package (RECON.md §70).
        if args.package:
            matches = [c for c in candidates if c.name == args.package]
            if not matches:
                print(f"EAT REFUSED: no package {args.package!r} under {repo} or {repo / 'src'} "
                      f"(found: {[c.name for c in candidates] or 'none'})", file=sys.stderr)
                return 2
            corpus = matches[0]
        elif len(candidates) == 1:
            corpus = candidates[0]
        else:
            print(f"EAT REFUSED: {'no' if not candidates else len(candidates)} importable package(s) under {repo}"
                  f"{' — ' + ', '.join(c.name for c in candidates) if candidates else ''}; name one with --package",
                  file=sys.stderr)
            return 2
    if getattr(args, "no_provision", False):
        # Eating a repo you do not trust runs its build (pip install <repo>, or npm install): this
        # flag runs nothing — the ring is read from an empty directory, so the package is minted
        # from its source alone and every import it makes is left unresolved by name (graphyos #35).
        if args.site_packages:
            print("EAT REFUSED: --no-provision and --site-packages contradict — the first reads an empty ring, "
                  "the second the install you name", file=sys.stderr)
            return 2
        empty = (Path(args.home).expanduser().resolve() if args.home else repo / ".graphy") / "no-ring"
        empty.mkdir(parents=True, exist_ok=True)
        print("PROVISION SKIPPED: --no-provision; the ring is empty, every import is unresolved")
        args.site_packages = str(empty)
    elif not args.site_packages:
        from graphy import provision as provision_lane
        try:
            pv = provision_lane.provision(repo, producer, log=print)
        except RuntimeError as exc:
            print(f"EAT REFUSED: {exc}", file=sys.stderr)
            return 2
        print(f"PROVISION {'OK' if pv.installed else 'PARTIAL'}: {pv.how}")
        args.site_packages = str(pv.site)
        if producer == "typescript_ast" and not pv.site.is_dir():
            pv.site.mkdir(parents=True, exist_ok=True)
    if producer == "typescript_ast":
        return _eat_typescript(args, repo)
    return _eat_run(args, repo, corpus.name, corpus, "python_ast")


def _clear_substrate(sub: Path) -> None:
    """A re-eat starts from the previous substrate's shards, never from nothing: each
    ``<slug>_graph/`` keeps exactly nodes.json · edges.json · PROVENANCE.json — the splice the
    re-mint reads (``smash.mint``), so only the files whose bytes moved are parsed — and the
    stored walks keep their directory, so they diff against the new generation. Everything
    else under the substrate (the registry, the journal, the resolver's sidecars, the store,
    the parquet, the atlas) is a build product and is rebuilt."""
    from graphy import journal
    from graphy import traversal
    from graphy import smash as smash_lane
    kept = sub.parent / f".{traversal.DIRNAME}.keep"
    shutil.rmtree(kept, ignore_errors=True)
    if (sub / traversal.DIRNAME).is_dir():
        shutil.move(str(sub / traversal.DIRNAME), str(kept))     # walks survive a re-eat: they diff against it
    if sub.is_dir():
        for entry in list(sub.iterdir()):
            if entry.is_dir() and entry.name.endswith("_graph") and (entry / smash_lane.PROVENANCE_NAME).is_file():
                for f in list(entry.iterdir()):
                    if f.name not in ("nodes.json", "edges.json", smash_lane.PROVENANCE_NAME):
                        shutil.rmtree(f, ignore_errors=True) if f.is_dir() else f.unlink(missing_ok=True)
            elif entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
    if kept.is_dir():
        sub.mkdir(parents=True, exist_ok=True)
        shutil.move(str(kept), str(sub / traversal.DIRNAME))


def _eat_run(args: argparse.Namespace, repo: Path, package: str, corpus: Path, producer: str) -> int:
    from graphy import journal
    from graphy import smash as smash_lane
    home = Path(args.home).expanduser().resolve() if args.home else repo / ".graphy"
    sub = home / "substrate"
    desc = home / "tenant.json"
    home.mkdir(parents=True, exist_ok=True)
    if not args.home:
        (home / ".gitignore").write_text("*\n", encoding="utf-8")   # rebuilt, never tracked by the eaten repo
    t0 = getattr(args, "_t0", None) or time.perf_counter()
    _clear_substrate(sub)
    if desc.exists():
        desc.unlink()

    print(f"EAT: {package} at {corpus} -> {home}")
    rc = main(["smash", "--package", package, "--site-packages", args.site_packages,
               "--out", str(sub), "--corpus", str(corpus), "--producer", producer])
    if rc != 0:
        print("EAT FAILED at smash", file=sys.stderr)
        return rc
    ring = json.loads((sub / smash_lane.RING_NAME).read_text(encoding="utf-8"))
    live = {f"{m['slug']}_graph" for m in ring["minted"].values()}
    for d in sub.glob("*_graph"):
        if d.is_dir() and d.name not in live:
            shutil.rmtree(d, ignore_errors=True)                 # a shard the ring no longer names
    lanes = [f"--lane={m['slug']}_graph:static-dep" for m in ring["minted"].values()]
    from graphy.cartograph import repo_cursor
    cursor, dirty = repo_cursor(repo, exclude=(home,))   # the working tree's dirt joins the cursor (graphyos #39)
    if cursor is None:
        cursor = "sha256:" + hashlib.sha256((sub / f"{package}_graph" / "edges.json").read_bytes()).hexdigest()
    elif dirty:
        print(f"EAT: the working tree is dirty ({dirty} file(s) past HEAD) — the cursor carries it; "
              f"`graphy check` reads STALE the moment they move")
    rc = main(["init", "--tenant", str(desc), "--root", str(repo), "--data-home", str(sub),
               "--join-keys", str(sub / "registry.json"), "--journal", str(sub / "journal"),
               "--cursor", cursor, "--policy", "refuse", "--adapter", producer, *lanes])
    if rc != 0:
        print("EAT FAILED at init", file=sys.stderr)
        return rc
    _scheme_index_from_ring(sub, f"{package} scheme index — derived from ring.json by graphy eat")
    for step in (["converge", "--tenant", str(desc), "--tenant-id", package, "--resolve"],
                 ["build", "--tenant", str(desc), "--tenant-id", package, "--container", "none"],
                 ["check", "--tenant", str(desc), "--tenant-id", package]):
        rc = main(step)
        if rc != 0:
            print(f"EAT FAILED at {step[0]}", file=sys.stderr)
            return rc
    deps = [s for s in ring["minted"] if s != package]
    seed = f"{package}://module/{package}"
    target = f"{deps[0]}://module/{deps[0]}" if deps else seed
    parsed = sum(m.get("parsed", 0) for m in ring["minted"].values())
    unreadable = {f"{s}:{rel}" if s != package else rel: why
                  for s, m in ring["minted"].items() for rel, why in (m.get("unreadable") or {}).items()}
    files = sum(m.get("parsed", 0) + m.get("reused", 0) for m in ring["minted"].values()) + len(unreadable)
    clause = smash_lane.unreadable_phrase(unreadable)
    print(f"EAT OK: {package} + {len(deps)} ring shard(s) -> {home}  "
          f"({parsed} of {files} files parsed{'; ' + clause if clause else ''}, {time.perf_counter() - t0:.1f}s)")
    print(_next_steps(desc, package, seed, target, home))
    return 0


def _graphy_command() -> list[str]:
    """How this box runs graphy: the console script when it is on PATH, else this interpreter."""
    exe = shutil.which("graphy")
    return [exe] if exe else [sys.executable, "-m", "graphy"]


def _next_steps(desc: Path, package: str, seed: str, target: str, home: Path) -> str:
    """What a stranger does next, printed once at the end of eat: the MCP block for the client
    they already use, the drawing, three questions. Any model; the walk is graphy's."""
    cmd = _graphy_command()
    mcp = json.dumps({"mcpServers": {"graphy": {"command": cmd[0], "args": cmd[1:] + ["mcp", "--tenant", str(desc), "--tenant-id", package]}}}, indent=2)
    g = " ".join(cmd)
    tenant = f"--tenant {desc} --tenant-id {package}"
    return "\n".join([
        "",
        "  ADD YOUR MODEL — paste this into .mcp.json (Claude Code) or your client's MCP settings; the model is yours, the walk is graphy's:",
        *("  " + ln for ln in mcp.splitlines()),
        "",
        "  SEE IT",
        f"    {g} pillars {tenant} --write {home / 'partition.json'}        # the arms the walk proposes",
        f"    {g} draw {tenant} --pillars --partition {home / 'partition.json'} --lr",
        f"    {g} draw {tenant} --corpus {package} --lr --min-weight 2 --emit html --interactive -o {home / 'map.html'}",
        "  ASK IT",
        f"    {g} blast <symbol> {tenant}          # if this changes, what breaks",
        f"    {g} descend <symbol> {tenant}        # what it reaches, across packages",
        f"    {g} walk {tenant} --seed {seed} --target {target}",
    ])


def _cmd_push(args: argparse.Namespace) -> int:
    from graphy import index as shard_index
    if not args.index or not args.shard:
        print("PUSH REFUSED: --index and at least one shard directory are required — graphy never "
              "guesses where an index lives", file=sys.stderr)
        return 2
    if args.name and len(args.shard) != 1:
        print("PUSH REFUSED: --name names exactly one shard", file=sys.stderr)
        return 2
    for shard in args.shard:
        try:
            m = shard_index.push(shard, args.index, name=args.name)
        except (shard_index.IndexError_, OSError) as exc:
            print(f"PUSH REFUSED: {shard}: {exc}", file=sys.stderr)
            return 2
        c = m.get("counts") or {}
        print(f"PUSH OK: {m['name']} -> {m['address']}  ({m['state']}; "
              f"{c.get('node_count', '?')} nodes / {c.get('edge_count', '?')} edges)")
    return 0


def _cmd_pull(args: argparse.Namespace) -> int:
    from graphy import index as shard_index
    if not args.index or not args.ref or not args.out:
        print("PULL REFUSED: <name|address>, --index and --out are required — graphy never guesses "
              "where a shard comes from or lands", file=sys.stderr)
        return 2
    try:
        m = shard_index.pull(args.ref, args.index, args.out)
    except (shard_index.IndexError_, OSError) as exc:
        print(f"PULL REFUSED: {exc}", file=sys.stderr)
        return 2
    c = m.get("counts") or {}
    print(f"PULL OK: {m.get('name') or m['address']} -> {m['out']}  (verified {m['address'][:12]}…; "
          f"{c.get('node_count', '?')} nodes / {c.get('edge_count', '?')} edges)")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    from graphy import index as shard_index
    if not args.index:
        print("INDEX REFUSED: --index is required", file=sys.stderr)
        return 2
    try:
        if args.verify:
            rows = shard_index.verify_index(args.index)
            bad = 0
            for name, address, problem in rows:
                print(f"  {name:<40} {address[:12]}…  {'OK' if problem is None else 'BROKEN — ' + problem}")
                bad += problem is not None
            print(f"INDEX {'OK' if not bad else 'BROKEN'}: {len(rows)} named shard(s), {bad} broken")
            return 1 if bad else 0
        cat = shard_index.catalog(args.index)
    except (shard_index.IndexError_, OSError) as exc:
        print(f"INDEX REFUSED: {exc}", file=sys.stderr)
        return 2
    for name, address in sorted(cat.items()):
        print(f"  {name:<40} {address}")
    print(f"INDEX: {len(cat)} named shard(s) at {args.index}")
    return 0


def _cmd_shell(args: argparse.Namespace) -> int:
    from graphy.shell import install as shell_install
    if args.shell_verb != "install":
        print("SHELL REFUSED: the verb is `install`", file=sys.stderr)
        return 2
    if not args.repo:
        print("SHELL REFUSED: --repo is required — the hooks are written into a declared repo, never the cwd",
              file=sys.stderr)
        return 2
    try:
        info = shell_install.install(args.repo, python=args.python)
    except shell_install.ShellError as exc:
        print(f"SHELL REFUSED: {exc}", file=sys.stderr)
        return 2
    for w in info["written"]:
        print(f"  wrote {w}")
    print(f"SHELL OK: hooks for tenant {info['tenant_id']} under {info['repo']} run on {info['python']}")
    print(f"  route the agent:  echo 'Read GRAPHY.md first.' >> {info['repo']}/CLAUDE.md")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    from graphy import pillars as pillars_lane
    parser = argparse.ArgumentParser(
        prog="graphy",
        description="graphy — compile any codebase into a walkable substrate. "
                    "The exit code is the contract: 0 healthy, 1 an audit verdict "
                    "that cannot prove health, 2 the command never ran.",
    )
    sub = parser.add_subparsers(dest="verb", metavar="{eat,init,smash,push,pull,index,converge,build,container,estate,walk,bridge,arms,farm,draw,showcase,descend,blast,explain,pillars,mcp,traversals,shell,check,fanout}")

    p_eat = sub.add_parser(
        "eat", help="the bolt-on: mint a repo's package and its import ring into <repo>/.graphy, "
                    "resolve, build, emit the container, audit — one verb")
    p_eat.add_argument("repo_pos", nargs="?", default=None, metavar="REPO", help="the codebase to eat (`.` for the one you stand in)")
    p_eat.add_argument("--repo", default=None, help="the codebase to eat (the same as the positional)")
    p_eat.add_argument("--site-packages", default=None,
                       help="where the repo's dependencies are installed (its venv's site-packages)")
    p_eat.add_argument("--package", default=None,
                       help="the importable package to mint when the repo carries more than one")
    p_eat.add_argument("--home", default=None, help="where the tenant lands (default: <repo>/.graphy)")
    p_eat.add_argument("--no-provision", action="store_true",
                       help="run nothing of the repo's: no venv, no pip, no npm — the package is minted from its source "
                            "with an empty ring, every import unresolved (eating a repo you do not trust runs its build otherwise)")
    p_eat.add_argument("--producer", default=None, choices=_PRODUCER_NAMES,
                       help="the ecosystem door (default: python_ast; typescript_ast when the repo carries a package.json and no importable Python package)")
    p_eat.set_defaults(handler=_cmd_eat)

    p_init = sub.add_parser("init", help="scaffold a tenant descriptor + data-home skeleton")
    p_init.add_argument("--tenant", default=None, help="descriptor path to CREATE")
    p_init.add_argument("--root", default=None, help="absolute tenant root")
    p_init.add_argument("--data-home", default=None, help="absolute data home")
    p_init.add_argument("--join-keys", default=None, help="path to the join-keys registry")
    p_init.add_argument("--journal", default=None, help="path to the journal home")
    p_init.add_argument("--cursor", default=None, help="the receipt cursor string")
    p_init.add_argument("--policy", default=None, help="refuse or warn")
    p_init.add_argument("--adapter", action="append", default=None,
                        help="adapter name (repeatable)")
    p_init.add_argument("--lane", action="append", default=None,
                        help="KEY:KIND[=COMMAND] lane (repeatable); a command runs with {out} as the shard dir, e.g. pulled=python3 -m graphy pull <name> --index <abs> --out {out}")
    p_init.set_defaults(handler=_cmd_init)

    p_smash = sub.add_parser(
        "smash", help="mint a package into a <slug>_graph shard and follow its import ring")
    p_smash.add_argument("--package", default=None, help="the import name to mint (the scheme)")
    p_smash.add_argument("--site-packages", default=None,
                         help="the directory the ring is resolved from; also the default corpus")
    p_smash.add_argument("--out", default=None,
                         help="the data home the <slug>_graph shards and ring.json land in")
    p_smash.add_argument("--corpus", default=None,
                         help="mint the root from this package directory or .py file (a checkout) "
                              "instead of site-packages")
    p_smash.add_argument("--no-ring", action="store_true", help="mint the root only")
    p_smash.add_argument("--parity", default=None, metavar="GOLDEN_DIR",
                         help="after minting, prove the root shard record-for-record against a "
                              "golden shard (nodes.json + edges.json + PROVENANCE.json); exit 1 on divergence")
    p_smash.add_argument("--producer", default="python_ast", choices=_PRODUCER_NAMES,
                         help="the ecosystem door: python_ast over site-packages (default) or typescript_ast over node_modules")
    p_smash.set_defaults(handler=_cmd_smash)

    p_converge = sub.add_parser(
        "converge", help="measure the seam between a tenant's shards; --resolve turns text labels into edges")
    p_converge.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_converge.add_argument("--tenant-id", default=None, help="the receipt name")
    p_converge.add_argument("--resolve", action="store_true",
                            help="write <shard>/wormhole_edges.json for every shard in the roster, "
                                 "resolving calls/inherits/decorates labels through each module's own scope")
    p_converge.set_defaults(handler=_cmd_converge)

    p_build = sub.add_parser("build", help="compile the declared roster into its store")
    p_build.add_argument("--tenant", default=None,
                         help="path to the tenant descriptor JSON")
    p_build.add_argument("--tenant-id", default=None,
                         help="the receipt name written into every OverrideRecord")
    p_build.add_argument("--container", default="all", metavar="all|none|<slug>_graph",
                         help="the parquet beside every shard now (all, the default), beside one shard now "
                              "with the rest pending until graphy estate asks, or none — every shard pending "
                              "and no duckdb imported (what eat does)")
    p_build.set_defaults(handler=_cmd_build)

    p_container = sub.add_parser(
        "container", help="the parquet beside every shard: verify freshness, or --emit (needs duckdb)")
    p_container.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_container.add_argument("--tenant-id", default=None, help="the receipt name")
    p_container.add_argument("--emit", action="store_true", help="write adjacency.parquet + nodes.parquet + container.json")
    p_container.set_defaults(handler=_cmd_container)

    p_estate = sub.add_parser(
        "estate", help="one SQL query over every shard's parquet: views adj(corpus, src, dst, edge_type, …) and nodes(corpus, id, …)")
    p_estate.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_estate.add_argument("--tenant-id", default=None, help="the receipt name")
    p_estate.add_argument("--index", default=None,
                          help="an index directory instead of a tenant: one view over every named shard it holds "
                               "(adj: name, corpus, src, dst, edge_type, dst_repr, line · nodes: name, corpus, id, kind, "
                               "node_type, dotted, module, role, file, line, version)")
    p_estate.add_argument("--emit", action="store_true",
                          help="with --index: materialize the estate beside the index (parquet + a receipt pinning the catalog)")
    p_estate.add_argument("--sql", default=None, help="the query (default: edges per corpus; with --index and no --sql: the estate's state)")
    p_estate.add_argument("--limit", type=int, default=50, help="rows to print (default 50)")
    p_estate.set_defaults(handler=_cmd_estate)

    p_walk = sub.add_parser("walk", help="walk a bounded path through the compiled store")
    p_walk.add_argument("--tenant", default=None,
                        help="path to the tenant descriptor JSON")
    p_walk.add_argument("--tenant-id", default=None,
                        help="the receipt name open_for refuses to open without")
    p_walk.add_argument("--seed", default=None, help="the node id to walk FROM")
    p_walk.add_argument("--target", default=None, help="the node id to walk TO")
    p_walk.add_argument("--max-depth", type=int, default=6,
                        help="BFS depth budget (default: 6)")
    p_walk.add_argument("--max-nodes", type=int, default=250000,
                        help="BFS node budget (default: 250000)")
    p_walk.add_argument("--on-stale", default="refuse",
                        help="refuse|warn (default: refuse; heal was removed in R1)")
    p_walk.add_argument("--no-store", action="store_true",
                        help="run live and land nothing in the traversal store")
    p_walk.set_defaults(handler=_cmd_walk)

    p_bridge = sub.add_parser(
        "bridge", help="walk from one tenant into another through a declared join: two --tenant/--tenant-id pairs, "
                       "--join <scheme> the package both rings minted")
    p_bridge.add_argument("--tenant", action="append", default=None,
                          help="a tenant descriptor; give it twice, one per side, in order")
    p_bridge.add_argument("--tenant-id", action="append", default=None,
                          help="the receipt name for the matching --tenant; give it twice")
    p_bridge.add_argument("--join", action="append", default=None,
                          help="a scheme both sides carry (e.g. typing_extensions); the only literals the walk crosses on")
    p_bridge.add_argument("--seed", default=None, help="the node id to walk FROM")
    p_bridge.add_argument("--target", default=None, help="the node id to walk TO")
    p_bridge.add_argument("--allow-release-skew", action="store_true",
                          help="cross a join whose two sides pin different releases; the skew is printed and carried by the operator, never silent")
    p_bridge.add_argument("--max-depth", type=int, default=8, help="hop budget (default 8)")
    p_bridge.add_argument("--max-nodes", type=int, default=250000, help="visited-node budget (default 250000)")
    p_bridge.add_argument("--on-stale", default="refuse", help="refuse (default) or warn when a side's store is stale")
    p_bridge.set_defaults(handler=_cmd_bridge)

    p_arms = sub.add_parser(
        "arms", help="the walk-derived half of each arm file as a marked generated region: the inventory by module, "
                     "the inherits joins out, the re-walk; --verify names drift")
    p_arms.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_arms.add_argument("--tenant-id", default=None, help="the receipt name open_for refuses to open without")
    p_arms.add_argument("--corpus", default=None, help="which corpus to cut (required when the tenant holds more than one)")
    p_arms.add_argument("--partition", default=None, help="the partition file the arms are cut by")
    p_arms.add_argument("--dir", default=None, help="the arms directory: <NAME>.md per group of the partition")
    p_arms.add_argument("--tenant-dir", default=None,
                        help="how the re-walk block names the tenant dir from engine/ (default tenants/<root name>)")
    p_arms.add_argument("--verify", action="store_true",
                        help="re-render from the live store and name every arm whose region differs; exit 1 on drift")
    p_arms.add_argument("--on-stale", default="refuse", help="refuse (default) or warn when the store is stale")
    p_arms.set_defaults(handler=_cmd_arms)

    p_farm = sub.add_parser("farm", help="mint many packages into one content-addressed index, in parallel, resumably: "
                                         "one venv per package (--no-deps; the ring is the index), every shard pushed by name")
    p_farm.add_argument("--index", default=None, help="the index directory the shards land in (created if absent)")
    p_farm.add_argument("--work", default=None, help="the work directory: one job dir per package, farm.json the receipt")
    p_farm.add_argument("--top", type=int, default=None, help="mint the top N PyPI packages by downloads")
    p_farm.add_argument("--packages", default=None, help="a file of package specs, one per line (name or name==version; # comments)")
    p_farm.add_argument("--skip", action="append", default=None, help="a distribution to leave out (repeatable)")
    p_farm.add_argument("--jobs", type=int, default=1, help="parallel jobs (default 1)")
    p_farm.add_argument("--python", default=None, help="the interpreter that provisions each venv (default: this one)")
    p_farm.add_argument("--producer", default="python_ast", choices=_PRODUCER_NAMES)
    p_farm.add_argument("--max-wheel-mb", type=float, default=200.0, help="refuse a release whose smallest file is over this (default 200)")
    p_farm.add_argument("--timeout", type=int, default=900, help="seconds a pip install may take (default 900)")
    p_farm.add_argument("--keep-venv", action="store_true", help="keep each job's venv (default: deleted after the mint)")
    p_farm.add_argument("--force", action="store_true", help="re-mint names the index already holds")
    p_farm.set_defaults(handler=_cmd_farm)

    p_draw = sub.add_parser("draw", help="draw the codebase from the store: the unit map (default), one arm of a partition, or a "
                                         "symbol's neighbourhood — ASCII for the terminal, a self-contained HTML+SVG page for a human")
    p_draw.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_draw.add_argument("--tenant-id", default=None, help="the receipt name open_for refuses to open without")
    p_draw.add_argument("--corpus", default=None, help="which corpus to draw (required when the tenant holds more than one)")
    p_draw.add_argument("--depth", type=int, default=2, help="dotted segments that make a unit (default 2)")
    p_draw.add_argument("--min-weight", type=int, default=1, help="drop unit edges lighter than this (default 1: every edge)")
    p_draw.add_argument("--arm", default=None, help="one arm of --partition, module to module")
    p_draw.add_argument("--pillars", action="store_true", help="the partition's groups as nodes with the cross-arm edge counts")
    p_draw.add_argument("--partition", default=None, help="the partition file (--arm, --atlas)")
    p_draw.add_argument("--symbol", default=None, help="a symbol's neighbourhood: an exact id or its dotted tail")
    p_draw.add_argument("--radius", type=int, default=2, help="hops either way around --symbol (default 2)")
    p_draw.add_argument("--max-nodes", type=int, default=60, help="the neighbourhood's node budget (default 60)")
    p_draw.add_argument("--atlas", default=None, metavar="DIR", help="one drawing per arm plus the unit map, ascii and html, with a receipt")
    p_draw.add_argument("--lr", action="store_true", help="left-to-right flow (trees and wide fans read better)")
    p_draw.add_argument("--emit", choices=("ascii", "html", "json"), default="ascii")
    p_draw.add_argument("--interactive", action="store_true", help="html: click-focus reachability, zoom and pan")
    p_draw.add_argument("--color", action="store_true", help="ascii to a terminal: ANSI color")
    p_draw.add_argument("--title", default=None)
    p_draw.add_argument("-o", "--out", default=None, help="write the drawing here (html is checked on the way out)")
    p_draw.add_argument("--check", default=None, metavar="FILE", help="verify a written html page and exit")
    p_draw.add_argument("--on-stale", default="refuse")
    p_draw.set_defaults(handler=_cmd_draw)

    p_show = sub.add_parser("showcase", help="one page that shows a stranger their own codebase: clone when a url, eat, propose the "
                                             "pillars, draw, and write index.html + showcase.txt (the MCP block, three questions, how to add a model)")
    p_show.add_argument("target", nargs="?", default=None, help="a git url, or a repo path (`.`)")
    p_show.add_argument("--out", default=None, help="where the page lands (default <repo>/.graphy/showcase/)")
    p_show.add_argument("--work", default=None, help="where a url is cloned (default ./showcase/<name>)")
    p_show.add_argument("--no-provision", action="store_true",
                       help="eat with --no-provision: nothing of the repo's runs, the ring is empty")
    p_show.set_defaults(handler=_cmd_showcase)

    p_trav = sub.add_parser(
        "traversals", help="the traversal store: list the stored walks, or --replay past generations against the live store")
    p_trav.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_trav.add_argument("--tenant-id", default=None, help="the receipt name")
    p_trav.add_argument("--replay", action="store_true",
                        help="re-check every walk stored under a past generation, hop by hop, and name the broken ones")
    p_trav.add_argument("--limit", type=int, default=20, help="broken hops to print per walk (default 20)")
    p_trav.add_argument("--on-stale", default="refuse", help="refuse|warn")
    p_trav.set_defaults(handler=_cmd_traversals)

    for door, blurb, depth in (
            ("descend", "the callees down through the ring to the primitives, and every package crossing", 4),
            ("blast", "the dependents against the edges — who calls, inherits, imports or decorates it, own and ring", 4),
            ("explain", "the record, the docs (DOC_EXPLAINS), the tests that reach it, the journal page that birthed its shard", 3)):
        p_door = sub.add_parser(door, help=blurb)
        p_door.add_argument("symbol", nargs="?", default=None, help="an exact node id, or its dotted tail (get_request_handler)")
        p_door.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
        p_door.add_argument("--tenant-id", default=None, help="the receipt name open_for refuses to open without")
        p_door.add_argument("--depth", type=int, default=depth, help=f"hops to walk (default {depth})")
        p_door.add_argument("--limit", type=int, default=12, help="rows to print per section (default 12)")
        p_door.add_argument("--on-stale", default="refuse", help="refuse|warn")
        p_door.set_defaults(handler=_cmd_door, door=door)

    p_pil = sub.add_parser("pillars", help="propose a corpus's arm partition from its module graph, with the evidence per unit")
    p_pil.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_pil.add_argument("--tenant-id", default=None, help="the receipt name open_for refuses to open without")
    p_pil.add_argument("--corpus", default=None, help="which corpus to cut (required when the tenant holds more than one)")
    p_pil.add_argument("--depth", type=int, default=pillars_lane.DEFAULT_DEPTH,
                       help=f"dotted segments that make a unit (default {pillars_lane.DEFAULT_DEPTH}: the package's first-level children)")
    p_pil.add_argument("--arms", type=int, default=None,
                       help="how many arms to propose (crowns + the floor); default: every orchestrator with at least half the leader's fan-out, plus the floor")
    p_pil.add_argument("--floor", type=int, default=pillars_lane.DEFAULT_FLOOR,
                       help=f"a unit with fewer cross-unit edges than this is the edge (default {pillars_lane.DEFAULT_FLOOR})")
    p_pil.add_argument("--owned", type=float, default=pillars_lane.DEFAULT_OWNED,
                       help="the share of a foundation's fan-in one arm must take to own it; below it the foundation is shared, the floor (default 2/3)")
    p_pil.add_argument("--client", type=float, default=pillars_lane.DEFAULT_CLIENT,
                       help="the share of an orchestrator's fan-out one arm must take for it to be that arm's client; under it the orchestrator crowns an arm of its own (default 1/3)")
    p_pil.add_argument("--rest", default=pillars_lane.DEFAULT_REST, help=f"the rest group's name (default {pillars_lane.DEFAULT_REST})")
    p_pil.add_argument("--write", default=None, help="write the proposal as a partition file graphy fanout --partition cuts by")
    p_pil.add_argument("--against", default=None,
                       help="a curated partition to diff the proposal against; exit 1 names every unit cut differently, with its evidence")
    p_pil.add_argument("--on-stale", default="refuse", help="refuse|warn")
    p_pil.set_defaults(handler=_cmd_pillars)

    p_ref = sub.add_parser("refresh", help="when a tenant's package moves upstream: re-mint the ring at the newest release into a sibling substrate, prove it, and report born/died per shard")
    p_ref.add_argument("--tenant", default=None, help="path to the CURRENT tenant descriptor JSON; the sibling is declared beside it")
    p_ref.add_argument("--tenant-id", default=None, help="the receipt name the sibling is built and audited under")
    p_ref.add_argument("--package", default=None, help="the root shard's import name (the scheme), e.g. fastapi")
    p_ref.add_argument("--release", default=None, help="the release to mint instead of asking PyPI for the newest")
    p_ref.add_argument("--site-packages", default=None,
                       help="an already-provisioned site-packages holding the release; skips the venv, reads the version off its dist-info")
    p_ref.add_argument("--python", default=None, help="the interpreter that makes the venv and runs the verbs (default: this one)")
    p_ref.add_argument("--fixture", default=None, metavar="SHARD_DIR",
                       help="after a green check, re-mint this golden shard (a <slug>_graph dir) from the new ring with --no-ring, so the next rebuild's parity holds")
    p_ref.add_argument("--check", action="store_true", help="only compare the release against the shard's provenance; mint nothing")
    p_ref.add_argument("--force", action="store_true", help="re-mint over a sibling a previous refresh left at the same release")
    p_ref.set_defaults(handler=_cmd_refresh)

    p_mcp = sub.add_parser("mcp", help="the MCP server on stdio: hunt · descend · blast · walk · explain over one tenant's store")
    p_mcp.add_argument("--tenant", default=None, help="path to the tenant descriptor JSON")
    p_mcp.add_argument("--tenant-id", default=None, help="the receipt name open_for refuses to open without")
    p_mcp.add_argument("--on-stale", default="refuse", help="refuse|warn")
    p_mcp.set_defaults(handler=_cmd_mcp)

    p_push = sub.add_parser("push", help="push shard(s) into a content-addressed index directory, verified by their PROVENANCE")
    p_push.add_argument("shard", nargs="*", help="shard directories (nodes.json + edges.json + PROVENANCE.json)")
    p_push.add_argument("--index", default=None, help="absolute path of the index directory (created on first push)")
    p_push.add_argument("--name", default=None, help="the name to point at it (default: <distribution>==<version> from the PROVENANCE)")
    p_push.set_defaults(handler=_cmd_push)

    p_pull = sub.add_parser("pull", help="pull one shard by name or address, every byte verified before it lands")
    p_pull.add_argument("ref", nargs="?", default=None, help="a name (pydantic==2.11.7) or a 64-hex address")
    p_pull.add_argument("--index", default=None, help="an absolute index directory or an http(s) base with the same layout")
    p_pull.add_argument("--out", default=None, help="absolute directory to create for the shard (must not exist)")
    p_pull.set_defaults(handler=_cmd_pull)

    p_index = sub.add_parser("index", help="what an index holds; --verify re-hashes every entry")
    p_index.add_argument("--index", default=None, help="an absolute index directory or an http(s) base")
    p_index.add_argument("--verify", action="store_true", help="re-hash every named shard against its manifest, PROVENANCE and address")
    p_index.set_defaults(handler=_cmd_index)

    p_shell = sub.add_parser("shell", help="the hooks and the gate: `shell install --repo <abs>` bolts them onto an eaten repo")
    p_shell.add_argument("shell_verb", nargs="?", default="install", help="install")
    p_shell.add_argument("--repo", default=None, help="the eaten repo (holds .graphy/tenant.json)")
    p_shell.add_argument("--python", default=None, help="the interpreter the hooks run on (default: this one)")
    p_shell.set_defaults(handler=_cmd_shell)

    p_check = sub.add_parser("check", help="read-only audit over the declared tenant")
    p_check.add_argument("--tenant", default=None,
                         help="path to the tenant descriptor JSON")
    p_check.add_argument("--tenant-id", default=None,
                         help="the receipt name open_for refuses to audit without")
    p_check.set_defaults(handler=_cmd_check)

    p_fanout = sub.add_parser(
        "fanout", help="compile a graph shard into its fan-out (TOC + sections + receipt)")
    p_fanout.add_argument("--verify", action="store_true",
                          help="reader protocol: pin receipt.json and prove every "
                               "receipted output on disk matches it (no compile)")
    p_fanout.add_argument("--graph-dir", default=None,
                          help="path to the graph shard directory (nodes.json + edges.json)")
    p_fanout.add_argument("--out", default=None,
                          help="output directory for TOC.md, the section files, and receipt.json")
    p_fanout.add_argument("--depth", type=int, default=None,
                          help="group by the first N dotted segments (default 1; a single "
                               "package cuts at 2)")
    p_fanout.add_argument("--partition", default=None,
                          help="a partition file {\"groups\": {NAME: [dotted prefix, …]}, "
                               "\"rest\": NAME}; longest prefix wins, the receipt pins its sha")
    p_fanout.set_defaults(handler=_cmd_fanout)

    return parser


def _main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_usage(sys.stderr)
        return 2
    return handler(args)


def _profiled(argv: list[str] | None, prof_dir: str) -> int:
    """GRAPHY_PROFILE_DIR names a directory: this verb runs under cProfile and leaves
    ``<verb>-<pid>.prof`` (the stats) and ``<verb>-<pid>.json`` (verb · argv · seconds · rss_kb,
    the process's own peak resident set) there. The receipt (measure.py) reads a lane's worth of
    them and names the hottest function; nothing else reads them. Unset, this function never runs.
    A process already under a profiler names itself in GRAPHY_PROFILE_PID, so a verb called
    in-process by another (eat → smash, or a test under the floor's profiler) is not profiled twice
    — cProfile does not nest — while a child process, with its own pid, still is."""
    import cProfile
    import os
    import resource
    import time
    if os.environ.get("GRAPHY_PROFILE_PID") == str(os.getpid()):
        return _main(argv)
    os.environ["GRAPHY_PROFILE_PID"] = str(os.getpid())
    args = list(sys.argv[1:] if argv is None else argv)
    verb = next((a for a in args if not a.startswith("-")), "graphy")
    os.makedirs(prof_dir, exist_ok=True)
    stem = os.path.join(prof_dir, f"{verb}-{os.getpid()}")
    prof, t0 = cProfile.Profile(), time.perf_counter()
    try:
        rc = prof.runcall(_main, argv)
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.environ.pop("GRAPHY_PROFILE_PID", None)
        prof.dump_stats(stem + ".prof")
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_kb = rss // 1024 if sys.platform == "darwin" else rss
        with open(stem + ".json", "w", encoding="utf-8") as fh:
            json.dump({"verb": verb, "argv": args, "seconds": round(time.perf_counter() - t0, 3),
                       "rss_kb": rss_kb}, fh)
    return rc


def main(argv: list[str] | None = None) -> int:
    import os
    prof_dir = os.environ.get("GRAPHY_PROFILE_DIR")
    return _profiled(argv, prof_dir) if prof_dir else _main(argv)
