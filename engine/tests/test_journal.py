from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

import graphy.journal as gj
from graphy.tenant import Tenant



def _tenant(tmp_path: Path, *, build_lanes=None, admitted=None, grandfathered=None) -> Tenant:
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True, exist_ok=True)
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({
        "substrate_roster": {"grandfathered": grandfathered or [],
                             "admitted": admitted or {}},
        "registered_joins": {"literal_joins": []},
    }), encoding="utf-8")
    return Tenant(
        root=tmp_path, data_home=data_home, adapters=(),
        build_lanes=build_lanes or {}, join_keys=join_keys,
        cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal",
    )


def _graph_dir(tenant: Tenant, name: str, nodes: dict, sha: str = "cafe1234",
               edges: list | None = None) -> Path:
    gd = Path(tenant.data_home) / name
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    if edges is not None:
        (gd / "edges.json").write_text(json.dumps(edges), encoding="utf-8")
    (gd / "stats.json").write_text(json.dumps({"built_at_sha": sha}), encoding="utf-8")
    return gd


def _read_records(tenant: Tenant, base: str) -> list[dict]:
    jpath = Path(tenant.journal) / f"{base}.journal.jsonl"
    return [json.loads(l) for l in jpath.read_text(encoding="utf-8").splitlines() if l.strip()]



@pytest.mark.parametrize("call", [
    lambda: gj.journal_path("widgets"),
    lambda: gj.append_page("widgets", set(), {"a"}),
    lambda: gj.read_journal("widgets"),
    lambda: gj.shelf_journals(),
    lambda: gj.find_events("born", "x"),
    lambda: gj.find_graph_deaths("widgets"),
    lambda: gj.load_manifest(),
    lambda: gj.steward(),
    lambda: gj.eligible_dir(Path("widgets_graph")),
])
def test_absent_tenant_refuses_naming_tenant(call):
    with pytest.raises(ValueError, match="tenant"):
        call()


def test_observers_refuse_absent_tenant_loud_not_raising(tmp_path, capsys):
    assert gj.observe_publish("widgets", {"nodes": set(), "edges": set(), "absent": True,
                                          "cursor": None}, tmp_path) is None
    assert gj.inplace_observer(tmp_path / "widgets_graph") is None
    err = capsys.readouterr().err
    assert err.count("tenant is required") == 2



def test_journal_path_contained_and_escape_refuses(tmp_path):
    tenant = _tenant(tmp_path)
    jp = gj.journal_path("widgets", tenant)
    assert jp.parent == Path(tenant.journal)
    with pytest.raises(ValueError, match="grammar"):
        gj.journal_path("../evil", tenant)
    with pytest.raises(ValueError, match="grammar"):
        gj.journal_path("UPPER", tenant)


def test_manifest_symlink_escape_refuses_before_write(tmp_path):
    tenant = _tenant(tmp_path)
    Path(tenant.journal).mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside_manifest.json"
    outside.write_text("{}", encoding="utf-8")
    (Path(tenant.journal) / "manifest.json").symlink_to(outside)
    gj.append_page("widgets", set(), {"a"}, bootstrap=True, tenant=tenant)
    with pytest.raises(ValueError, match="escap"):
        gj.steward(tenant, adopt=True)
    assert outside.read_text(encoding="utf-8") == "{}"


def test_loss_log_symlink_escape_refuses_outside_untouched(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    Path(tenant.journal).mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside_losses.jsonl"
    outside.write_text("", encoding="utf-8")
    (Path(tenant.journal) / "losses.jsonl").symlink_to(outside)
    gd = _graph_dir(tenant, "widgets_graph", {"a": {}})
    assert gj.observe_publish("widgets_graph", None, gd, tenant=tenant) is None
    err = capsys.readouterr().err
    assert "PAGE LOST" in err and "loss-log write failed" in err
    assert outside.read_text(encoding="utf-8") == ""


def test_manifest_and_losses_land_inside_journal_home(tmp_path):
    tenant = _tenant(tmp_path)
    gd = _graph_dir(tenant, "widgets_graph", {"n1": {}})
    gj.observe_publish("widgets_graph", None, gd, tenant=tenant)
    losses = Path(tenant.journal) / "losses.jsonl"
    assert losses.exists() and losses.parent == Path(tenant.journal)
    gj.append_page("widgets_graph", set(), {"n1"}, bootstrap=True, tenant=tenant)
    gj.steward(tenant, adopt=True)
    assert (Path(tenant.journal) / "manifest.json").exists()



def test_bootstrap_then_diff_then_heartbeat(tmp_path):
    tenant = _tenant(tmp_path)
    p1 = gj.append_page("widgets", set(), {"a", "b"}, cursor="cafe1234",
                        bootstrap=True, tenant=tenant)
    assert p1["bootstrap"] and p1["seq"] == 1 and p1["n_born"] == 2
    assert "born" not in p1
    p2 = gj.append_page("widgets", {"a", "b"}, {"a", "b", "c"}, cursor="beef5678",
                        prev_cursor="cafe1234", tenant=tenant)
    assert p2["seq"] == 2 and p2["born"] == ["c"] and "gap_after_seq" not in p2
    p3 = gj.append_page("widgets", {"a", "b", "c"}, {"a", "b", "c"}, cursor="beef5678",
                        prev_cursor="beef5678", tenant=tenant)
    assert p3["seq"] == 3 and p3["n_born"] == 0 and "gap_after_seq" not in p3
    records = _read_records(tenant, "widgets_graph")
    assert records[0]["kind"] == "journal"
    assert [r["seq"] for r in records if r["kind"] == "page"] == [1, 2, 3]


def test_gap_is_identity_checked_never_seq_contiguity(tmp_path):
    tenant = _tenant(tmp_path)
    gj.append_page("widgets", set(), {"a"}, cursor="cafe1234", bootstrap=True, tenant=tenant)
    gapped = gj.append_page("widgets", {"a", "x"}, {"a", "x", "y"}, cursor="beef5678",
                            prev_cursor="dead0000", tenant=tenant)
    assert gapped["seq"] == 2
    assert gapped["gap_after_seq"] == 1
    clean = gj.append_page("widgets", {"a", "x", "y"}, {"a", "x", "y"}, cursor="beef5678",
                           prev_cursor="beef5678", tenant=tenant)
    assert "gap_after_seq" not in clean


def test_truncation_caps_keep_true_counts(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    monkeypatch.setattr(gj, "NODE_CAP", 3)
    page = gj.append_page("widgets", set(), {f"n{i}" for i in range(10)},
                          prev_cursor=None, tenant=tenant)
    assert page["n_born"] == 10 and len(page["born"]) == 3 and page["truncated"]


def test_edge_identity_dst_repr_discriminates_line_never(tmp_path):
    e1 = {"src": "a", "edge_type": "calls", "dst_repr": "conn.execute", "line": 5}
    e2 = {"src": "a", "edge_type": "calls", "dst_repr": "conn.execute", "line": 99}
    e3 = {"src": "a", "edge_type": "calls", "dst_repr": "other.fn", "line": 5}
    assert gj._edge_key(e1) == gj._edge_key(e2)
    assert gj._edge_key(e1) != gj._edge_key(e3)


def test_cursor_normalization():
    assert gj._norm_cursor("a" * 40) == "a" * 8
    assert gj._norm_cursor("cafe1234") == "cafe1234"
    assert gj._norm_cursor("declared-cli") == "declared-cli"
    assert gj._norm_cursor(None) is None



def test_concurrent_appends_never_mint_duplicate_seq(tmp_path, monkeypatch):
    tenant = _tenant(tmp_path)
    gj.append_page("widgets", set(), {"a"}, cursor="cafe1234", bootstrap=True, tenant=tenant)

    in_section = threading.Event()
    release = threading.Event()
    real_tail = gj._tail_state
    first = threading.Lock()
    trapped = {"done": False}

    b_in_section = threading.Event()

    def trapping_tail(content):
        with first:
            if not trapped["done"]:
                trapped["done"] = True
                in_section.set()
                assert release.wait(timeout=10), "release never came"
            else:
                b_in_section.set()
        return real_tail(content)

    monkeypatch.setattr(gj, "_tail_state", trapping_tail)
    results: dict = {}

    def worker(name, prev):
        results[name] = gj.append_page("widgets", {"a"}, {"a", name}, cursor=f"{name}cursor",
                                       prev_cursor=prev, tenant=tenant)

    ta = threading.Thread(target=worker, args=("aa", "cafe1234"))
    ta.start()
    assert in_section.wait(timeout=10)
    tb = threading.Thread(target=worker, args=("bb", "aacursor"))
    tb.start()
    # B reaches the tail only past the journal lock; 0.2 s is the ceiling on "still blocked"
    assert not b_in_section.wait(timeout=0.2), "worker B must BLOCK at the journal lock while A holds it"
    release.set()
    ta.join(timeout=10)
    tb.join(timeout=10)
    assert not ta.is_alive() and not tb.is_alive()
    assert results["aa"]["seq"] == 2
    assert results["bb"]["seq"] == 3
    assert "gap_after_seq" not in results["bb"]



def _tear(tenant: Tenant, base: str) -> None:
    jpath = Path(tenant.journal) / f"{base}.journal.jsonl"
    with open(jpath, "a", encoding="utf-8") as fh:
        fh.write('{"kind": "page", "torn...')


def test_torn_journal_refuses_by_default_names_count(tmp_path):
    tenant = _tenant(tmp_path)
    gj.append_page("widgets", set(), {"a"}, bootstrap=True, tenant=tenant)
    _tear(tenant, "widgets_graph")
    with pytest.raises(gj.TornJournalError, match="1 unparseable"):
        gj.find_events("born", "a", graph="widgets", tenant=tenant)
    with pytest.raises(gj.TornJournalError, match="1 unparseable"):
        gj.find_graph_deaths("widgets", tenant)


def test_torn_journal_allow_torn_answers_with_warning(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    gj.append_page("widgets", {"z"}, {"z", "a"}, prev_cursor=None, tenant=tenant)
    _tear(tenant, "widgets_graph")
    hits = gj.find_events("born", "a", graph="widgets", tenant=tenant, allow_torn=True)
    assert hits and hits[0]["matched"] == ["a"]
    assert "torn journal" in capsys.readouterr().err


def test_intact_journal_answers_clean(tmp_path):
    tenant = _tenant(tmp_path)
    gj.append_page("widgets", {"z"}, {"z", "a"}, prev_cursor=None, tenant=tenant)
    hits = gj.find_events("born", "a", graph="widgets", tenant=tenant)
    assert hits and hits[0]["graph"] == "widgets"



def test_eligibility_refuses_temp_versioned_and_offshelf(tmp_path):
    tenant = _tenant(tmp_path)
    dh = Path(tenant.data_home)
    for bad in (".widgets_graph.build.42", ".widgets_graph.tmp.9",
                "widgets_graph.v8f3a11.clean.1.2"):
        d = dh / bad
        d.mkdir(parents=True, exist_ok=True)
        assert not gj.eligible_dir(d, tenant), bad
    onshelf = dh / "widgets_graph"
    onshelf.mkdir(parents=True, exist_ok=True)
    assert gj.eligible_dir(onshelf, tenant)
    offshelf = tmp_path / "elsewhere" / "widgets_graph"
    offshelf.mkdir(parents=True)
    assert not gj.eligible_dir(offshelf, tenant)



def test_observe_publish_diff_and_prev_cursor_thread(tmp_path):
    tenant = _tenant(tmp_path)
    gd = _graph_dir(tenant, "widgets_graph", {"a": {}, "b": {}}, sha="beef5678")
    old_snap = {"nodes": {"a"}, "edges": set(), "absent": False, "cursor": "cafe1234"}
    page = gj.observe_publish("widgets_graph", old_snap, gd, tenant=tenant)
    assert page and page["n_born"] == 1 and page["cursor"] == "beef5678"
    assert page["prev_cursor"] == "cafe1234"


def test_observe_publish_offshelf_skips_no_page(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    off = tmp_path / "elsewhere" / "widgets_graph"
    off.mkdir(parents=True)
    (off / "nodes.json").write_text("{}", encoding="utf-8")
    assert gj.observe_publish("widgets_graph",
                              {"nodes": set(), "edges": set(), "absent": True, "cursor": None},
                              off, tenant=tenant) is None
    assert "skip" in capsys.readouterr().err
    assert not (Path(tenant.journal) / "widgets_graph.journal.jsonl").exists()


def test_observe_publish_unreadable_old_counts_loss(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    gd = _graph_dir(tenant, "widgets_graph", {"a": {}})
    assert gj.observe_publish("widgets_graph", None, gd, tenant=tenant) is None
    assert "PAGE LOST" in capsys.readouterr().err
    loss_rows = (Path(tenant.journal) / "losses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(loss_rows) == 1 and "unreadable" in loss_rows[0]


def test_snapshot_ids_three_outcomes(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    gd = _graph_dir(tenant, "widgets_graph", {"a": {}}, sha="cafe1234")
    snap = gj.snapshot_ids(gd)
    assert snap == {"nodes": {"a"}, "edges": set(), "absent": False, "cursor": "cafe1234"}
    empty = Path(tenant.data_home) / "fresh_graph"
    empty.mkdir()
    assert gj.snapshot_ids(empty)["absent"] is True
    corrupt = Path(tenant.data_home) / "corrupt_graph"
    corrupt.mkdir()
    (corrupt / "nodes.json").write_text("{not json", encoding="utf-8")
    assert gj.snapshot_ids(corrupt) is None
    assert "snapshot unreadable" in capsys.readouterr().err


def test_inplace_observer_closure_and_temp_none(tmp_path):
    tenant = _tenant(tmp_path)
    gd = _graph_dir(tenant, "widgets_graph", {"a": {}}, sha="cafe1234")
    closure = gj.inplace_observer(gd, tenant)
    assert closure is not None
    page = closure({"nodes": {"a": {}, "b": {}}, "edges": []}, {"built_at_sha": "beef5678"})
    assert page and page["n_born"] == 1 and page["prev_cursor"] == "cafe1234"
    temp = Path(tenant.data_home) / ".widgets_graph.build.42"
    temp.mkdir()
    (temp / "nodes.json").write_text("{}", encoding="utf-8")
    assert gj.inplace_observer(temp, tenant) is None
    birth = Path(tenant.data_home) / "newborn_graph"
    birth.mkdir()
    assert gj.inplace_observer(birth, tenant) is None


def test_forced_failure_observer_law(tmp_path, monkeypatch, capsys):
    tenant = _tenant(tmp_path)
    gd = _graph_dir(tenant, "widgets_graph", {"a": {}})

    def _boom(*a, **k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(gj, "append_page", _boom)
    assert gj.observe_publish("widgets_graph",
                              {"nodes": set(), "edges": set(), "absent": True, "cursor": None},
                              gd, tenant=tenant) is None
    assert "PAGE LOST" in capsys.readouterr().err



def test_find_graph_deaths_requires_bootstrap_proof(tmp_path):
    tenant = _tenant(tmp_path)
    gj.append_page("widgets", set(), {"a", "b"}, bootstrap=True, tenant=tenant)
    gj.append_page("widgets", {"a", "b"}, set(), prev_cursor=None, tenant=tenant)
    deaths = gj.find_graph_deaths("widgets", tenant, allow_torn=True)
    assert len(deaths) == 1 and deaths[0]["graph_death"] and deaths[0]["n_died"] == 2
    gj.append_page("orphan", {"x"}, set(), prev_cursor=None, tenant=tenant)
    assert gj.find_graph_deaths("orphan", tenant) == []



def test_steward_five_states_and_union_regression(tmp_path):
    tenant = _tenant(tmp_path, admitted={"alpha": {}}, grandfathered=["ghost"])
    gj.append_page("alpha", set(), {"a"}, bootstrap=True, tenant=tenant)
    gj.append_page("beta", set(), {"b"}, bootstrap=True, tenant=tenant)
    gj.append_page("ghost", set(), {"g"}, bootstrap=True, tenant=tenant)
    (Path(tenant.journal) / "headless_graph.journal.jsonl").write_text(
        '{"kind": "page", "graph": "headless", "seq": 1}\n', encoding="utf-8")

    first = gj.steward(tenant, adopt=True)
    assert {r["graph"] for r in first["adopted"]} == {"alpha", "beta", "ghost"}
    assert [r["file"] for r in first["headerless"]] == ["headless_graph.journal.jsonl"]

    manifest = gj.load_manifest(tenant)
    manifest["journals"].append({"uuid": "u-x", "graph": "alpha",
                                 "file": "elsewhere_alpha_graph.journal.jsonl"})
    manifest["journals"].append({"uuid": "u-y", "graph": "gone",
                                 "file": "gone_graph.journal.jsonl"})
    (Path(tenant.journal) / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = gj.steward(tenant)
    healthy = {r["graph"] for r in report["healthy"]}
    assert "alpha" in healthy
    assert "ghost" in healthy
    assert "beta" not in healthy
    assert {r["graph"] for r in report["departed"]} == {"beta", "gone"}
    assert [r["graph"] for r in report["absent_here"]] == ["alpha"]


def test_steward_grain_parity_lane_key_normalizes(tmp_path):
    tenant = _tenant(tmp_path, build_lanes={"widgets_graph": (None, "on-demand")})
    gj.append_page("widgets", set(), {"a"}, bootstrap=True, tenant=tenant)
    gj.steward(tenant, adopt=True)
    report = gj.steward(tenant)
    assert [r["graph"] for r in report["healthy"]] == ["widgets"]
    assert report["departed"] == []



def _identity(tenant: Tenant) -> list[str]:
    return ["--tenant-id", "test", "--data-home", str(tenant.data_home),
            "--join-keys", str(tenant.join_keys)]


def test_cli_identity_round_trip_executes(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    cli_tenant = gj._cli_tenant(str(tenant.data_home), str(tenant.join_keys), "test")
    gj.append_page("widgets", set(), {"a"}, cursor="cafe1234", bootstrap=True, tenant=cli_tenant)
    rc = gj.main(_identity(tenant) + ["log", "widgets"])
    assert rc == 0
    assert "seq=1" in capsys.readouterr().out


def test_RED_a_blank_tenant_id_refuses_by_name(tmp_path, capsys):
    """`--tenant-id " "` passes argparse's required= and used to be dropped on the floor — five module
    mains declared the flag and never read it (review.py: argparse-dest-never-read). The declared
    receipt name is read, and a blank one refuses the way open_for refuses it."""
    tenant = _tenant(tmp_path)
    rc = gj.main(["--tenant-id", " ", "--data-home", str(tenant.data_home), "--join-keys", str(tenant.join_keys), "log", "widgets"])
    assert rc == 2 and "JOURNAL REFUSED: --tenant-id must not be empty" in capsys.readouterr().err
    assert gj._cli_tenant(str(tenant.data_home), str(tenant.join_keys), "test").cursor == "cli:test"


def test_cli_absent_identity_refuses_naming_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        gj.main(["log", "widgets"])
    assert exc.value.code == 2
    assert "--tenant-id" in capsys.readouterr().err


def test_cli_steward_lane_constructs_through_real_tenant(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    cli_tenant = gj._cli_tenant(str(tenant.data_home), str(tenant.join_keys), "test")
    gj.append_page("widgets", set(), {"a"}, bootstrap=True, tenant=cli_tenant)
    rc = gj.main(_identity(tenant) + ["steward", "--adopt",
                                      "--lane", "widgets_graph:on-demand"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 healthy" in out or "adopted" in out.lower()
    rc2 = gj.main(_identity(tenant) + ["steward", "--lane", "widgets_graph:on-demand"])
    assert rc2 == 0


def test_cli_bogus_lane_kind_refuses_via_real_constructor(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    rc = gj.main(_identity(tenant) + ["steward", "--lane", "widgets_graph:bogus"])
    err = capsys.readouterr().err
    assert rc == 2 and "JOURNAL REFUSED" in err and "bogus" in err
    with pytest.raises(ValueError, match="KEY:KIND"):
        gj.main(_identity(tenant) + ["steward", "--lane", "keyonly"])


def test_cli_diff_append_named_vs_empty_old(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    cli_tenant = gj._cli_tenant(str(tenant.data_home), str(tenant.join_keys), "test")
    new = _graph_dir(cli_tenant, "widgets_graph", {"a": {}}, sha="beef5678")
    empty_old = tmp_path / "empty_old"
    empty_old.mkdir()
    rc = gj.main(_identity(tenant) + ["diff-append", "--graph", "widgets_graph",
                                      "--old", str(empty_old), "--new", str(new)])
    assert rc == 1
    assert "refusing to fabricate" in capsys.readouterr().err
    rc = gj.main(_identity(tenant) + ["diff-append", "--graph", "widgets_graph",
                                      "--old", "", "--new", str(new)])
    assert rc == 0
    assert "(bootstrap)" in capsys.readouterr().out


def test_cli_torn_refusal_and_allow_torn(tmp_path, capsys):
    tenant = _tenant(tmp_path)
    cli_tenant = gj._cli_tenant(str(tenant.data_home), str(tenant.join_keys), "test")
    gj.append_page("widgets", {"z"}, {"z", "a"}, prev_cursor=None, tenant=cli_tenant)
    jpath = Path(cli_tenant.journal) / "widgets_graph.journal.jsonl"
    with open(jpath, "a", encoding="utf-8") as fh:
        fh.write('{"torn...')
    rc = gj.main(_identity(tenant) + ["born", "a", "--graph", "widgets"])
    assert rc == 3
    assert "REFUSED" in capsys.readouterr().err
    rc = gj.main(_identity(tenant) + ["born", "a", "--graph", "widgets", "--allow-torn"])
    assert rc == 0
