
from __future__ import annotations

import json

import pytest

from graphy import Golden, Harness, ParityError, load_golden

MINT = "python -m graphy.parity mint --surface nodes"


def _golden(surface="nodes", payload=None, **over):
    body = {
        "surface": surface,
        "oracle_commit": "a0c1224",
        "mint_command": MINT,
        "payload": [1, 2, 3] if payload is None else payload,
    }
    body.update(over)
    return body


def _write(tmp_path, body, name="golden.json"):
    p = tmp_path / name
    p.write_text(json.dumps(body), encoding="utf-8")
    return p



@pytest.mark.parametrize("field", ["surface", "oracle_commit", "mint_command"])
def test_RED_golden_missing_provenance_is_refused(tmp_path, field):
    p = _write(tmp_path, _golden(**{field: ""}))
    with pytest.raises(ParityError, match="provenance"):
        load_golden(p)


def test_RED_golden_without_payload_is_refused(tmp_path):
    body = _golden()
    del body["payload"]
    with pytest.raises(ParityError, match="no payload"):
        load_golden(_write(tmp_path, body))


def test_RED_missing_file_is_refused(tmp_path):
    with pytest.raises(ParityError, match="not found"):
        load_golden(tmp_path / "nope.json")


def test_RED_malformed_json_is_refused(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ParityError, match="not valid JSON"):
        load_golden(p)


def test_GREEN_a_complete_golden_loads(tmp_path):
    g = load_golden(_write(tmp_path, _golden()))
    assert g.surface == "nodes"
    assert g.oracle_commit == "a0c1224"
    assert g.mint_command == MINT
    assert g.payload == [1, 2, 3]
    assert g.provenance == "nodes@a0c1224"



def test_RED_unwired_harness_fails_red():
    with pytest.raises(ParityError, match="no tool wired"):
        Harness().check(Golden("nodes", "a0c1224", MINT, [1, 2, 3]))


def test_RED_undeclared_surface_is_refused():
    h = Harness()
    h.register("nodes", lambda: [1, 2, 3])
    with pytest.raises(ParityError, match="unfalsifiable"):
        h.check(Golden("edges", "a0c1224", MINT, [1, 2, 3]))


def test_RED_empty_surface_name_is_refused():
    with pytest.raises(ParityError, match="non-empty parity surface"):
        Harness().register("   ", lambda: [])


def test_RED_two_producers_for_one_surface_are_refused():
    h = Harness()
    h.register("nodes", lambda: [1])
    with pytest.raises(ParityError, match="two authorities"):
        h.register("nodes", lambda: [2])


def test_RED_empty_golden_set_is_not_success():
    h = Harness()
    h.register("nodes", lambda: [1, 2, 3])
    with pytest.raises(ParityError, match="empty parity run"):
        h.check_all([])



def test_RED_divergence_fails_and_names_the_remint():
    h = Harness()
    h.register("nodes", lambda: [1, 2, 99])
    with pytest.raises(ParityError) as exc:
        h.check(Golden("nodes", "a0c1224", MINT, [1, 2, 3]))
    msg = str(exc.value)
    assert "parity FAILED" in msg
    assert "a0c1224" in msg
    assert MINT in msg


def test_GREEN_a_wired_matching_surface_passes():
    h = Harness()
    h.register("nodes", lambda: [1, 2, 3])
    h.check(Golden("nodes", "a0c1224", MINT, [1, 2, 3]))
    assert h.surfaces == ("nodes",)


def test_GREEN_check_all_counts_what_it_proved():
    h = Harness()
    h.register("nodes", lambda: [1, 2, 3])
    h.register("edges", lambda: {"a": "b"})
    proven = h.check_all([
        Golden("nodes", "a0c1224", MINT, [1, 2, 3]),
        Golden("edges", "a0c1224", MINT, {"a": "b"}),
    ])
    assert proven == 2



def test_RED_a_bool_is_not_its_integer_twin():
    h = Harness()
    h.register("flag", lambda: 1)
    with pytest.raises(ParityError, match="parity FAILED"):
        h.check(Golden("flag", "a0c1224", MINT, True))

    h2 = Harness()
    h2.register("flag", lambda: True)
    with pytest.raises(ParityError, match="parity FAILED"):
        h2.check(Golden("flag", "a0c1224", MINT, 1))


def test_RED_a_bool_nested_in_a_container_is_not_its_integer_twin():
    h = Harness()
    h.register("nodes", lambda: {"ok": 1, "counts": [0]})
    with pytest.raises(ParityError, match="parity FAILED"):
        h.check(Golden("nodes", "a0c1224", MINT, {"ok": True, "counts": [False]}))


def test_GREEN_matching_bools_and_numbers_still_pass():
    h = Harness()
    h.register("flag", lambda: True)
    h.check(Golden("flag", "a0c1224", MINT, True))
    h.register("count", lambda: 1.0)
    h.check(Golden("count", "a0c1224", MINT, 1))


def test_RED_container_provenance_is_refused_not_stringified(tmp_path):
    for field, bad in (
        ("surface", {"a": "b"}),
        ("oracle_commit", ["a0c1224"]),
        ("mint_command", {"cmd": "x"}),
    ):
        body = {"surface": "nodes", "oracle_commit": "a0c1224",
                "mint_command": MINT, "payload": [1]}
        body[field] = bad
        p = tmp_path / f"golden_{field}.json"
        p.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(ParityError, match="must be a string"):
            load_golden(p)


def test_RED_non_string_scalar_provenance_is_also_refused(tmp_path):
    body = {"surface": "nodes", "oracle_commit": 1224,
            "mint_command": MINT, "payload": [1]}
    p = tmp_path / "golden_int.json"
    p.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ParityError, match="must be a string"):
        load_golden(p)



class _AlwaysEqual:

    def __eq__(self, other):  # noqa: D105
        return True

    def __repr__(self):  # noqa: D105
        return "<AlwaysEqual>"


def test_RED_a_non_json_value_cannot_self_certify_as_parity():
    h = Harness()
    h.register("nodes", _AlwaysEqual)
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nodes", "a0c1224", MINT, 1))


def test_RED_a_non_json_value_nested_in_a_container_is_refused():
    h = Harness()
    h.register("nodes", lambda: {"ok": [_AlwaysEqual()]})
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nodes", "a0c1224", MINT, {"ok": [1]}))


def test_RED_Golden_itself_refuses_non_string_provenance():
    with pytest.raises(ParityError, match="must be a string"):
        Golden("surface", ["not", "a", "commit"], MINT, [])
    with pytest.raises(ParityError, match="must be a string"):
        Golden("surface", "a0c1224", {"not": "a command"}, [])
    with pytest.raises(ParityError, match="must be a string"):
        Golden({"s": 1}, "a0c1224", MINT, [])


def test_RED_Golden_refuses_empty_provenance():
    for bad in ("", "   "):
        with pytest.raises(ParityError, match="must not be empty"):
            Golden(bad, "a0c1224", MINT, [])


def test_GREEN_valid_Golden_still_constructs_and_proves():
    g = Golden("nodes", "a0c1224", MINT, [1, 2, 3])
    assert g.provenance == "nodes@a0c1224"
    h = Harness()
    h.register("nodes", lambda: [1, 2, 3])
    h.check(g)


def test_RED_non_finite_floats_are_not_json():
    for bad in (float("nan"), float("inf"), float("-inf")):
        h = Harness()
        h.register("nodes", lambda bad=bad: bad)
        with pytest.raises(ParityError, match="outside the JSON data model"):
            h.check(Golden("nodes", "a0c1224", MINT, 1))

    h2 = Harness()
    h2.register("nested", lambda: {"counts": [1, float("nan")]})
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h2.check(Golden("nested", "a0c1224", MINT, {"counts": [1, 2]}))


def test_GREEN_ordinary_finite_floats_still_pass():
    h = Harness()
    h.register("nodes", lambda: [1.5, -2.0, 0.0, 1e308])
    h.check(Golden("nodes", "a0c1224", MINT, [1.5, -2.0, 0.0, 1e308]))


class _SneakyInt(int):

    def __eq__(self, other):  # noqa: D105
        return True

    def __hash__(self):  # noqa: D105
        return int.__hash__(self)


def test_RED_a_json_scalar_SUBCLASS_cannot_self_certify():
    assert json.dumps(_SneakyInt(2)) == "2"
    h = Harness()
    h.register("nodes", lambda: _SneakyInt(2))
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nodes", "a0c1224", MINT, 1))


def test_RED_a_scalar_subclass_nested_in_a_container_is_refused():
    h = Harness()
    h.register("nested", lambda: {"counts": [_SneakyInt(2)]})
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nested", "a0c1224", MINT, {"counts": [1]}))


def test_GREEN_every_ordinary_json_scalar_still_passes():
    payload = {"s": "x", "i": 1, "f": 1.5, "t": True, "f2": False, "n": None,
               "list": [1, "a", None, False]}
    h = Harness()
    h.register("all", lambda: json.loads(json.dumps(payload)))
    h.check(Golden("all", "a0c1224", MINT, payload))



class _SneakyKey(str):

    def __eq__(self, other):  # noqa: D105
        return other == "golden"

    def __hash__(self):  # noqa: D105
        return hash("golden")


def test_RED_a_str_subclass_object_KEY_cannot_self_certify():
    key = _SneakyKey("actual")
    assert json.dumps({key: 1}) == '{"actual": 1}'
    h = Harness()
    h.register("nodes", lambda: {key: 1})
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nodes", "a0c1224", MINT, {"golden": 1}))


def test_RED_a_str_subclass_key_nested_in_a_container_is_refused():
    h = Harness()
    h.register("nested", lambda: [{"ok": {_SneakyKey("actual"): 1}}])
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nested", "a0c1224", MINT, [{"ok": {"golden": 1}}]))


class _LyingDict(dict):

    def __init__(self, real, fake):
        super().__init__(real)
        self._fake = dict(fake)

    def keys(self):  # noqa: D102
        return self._fake.keys()

    def items(self):  # noqa: D102
        return self._fake.items()

    def __iter__(self):  # noqa: D105
        return iter(self._fake)

    def __getitem__(self, k):  # noqa: D105
        return self._fake[k]


def test_container_subclass_parity_follows_its_serialized_view():
    red = _LyingDict(real={"golden": 1}, fake={"other": 2})
    assert json.dumps(red) == '{"other": 2}'
    h = Harness()
    h.register("nodes", lambda: red)
    with pytest.raises(ParityError, match="parity FAILED"):
        h.check(Golden("nodes", "a0c1224", MINT, {"golden": 1}))

    green = _LyingDict(real={"other": 2}, fake={"golden": 1})
    assert json.dumps(green) == '{"golden": 1}'
    h2 = Harness()
    h2.register("nodes", lambda: green)
    h2.check(Golden("nodes", "a0c1224", MINT, {"golden": 1}))


class _StrTwin(str):

    def __hash__(self):  # noqa: D105
        return hash("nodes")

    def __eq__(self, other):  # noqa: D105
        return other == "nodes"


def test_RED_Golden_refuses_str_subclass_provenance():
    with pytest.raises(ParityError, match="must be a string"):
        Golden(_StrTwin("edges"), "a0c1224", MINT, [1])



class _GhostDict(dict):

    def keys(self):  # noqa: D102
        return {"ghost": 1}.keys()

    def items(self):  # noqa: D102
        return {"ghost": 1}.items()

    def __iter__(self):  # noqa: D105
        return iter({"ghost": 1})

    def __getitem__(self, k):  # noqa: D105
        return {"ghost": 1}[k]


def test_RED_empty_storage_dict_subclass_with_nonempty_view_is_refused():
    ghost = _GhostDict()
    assert json.dumps(ghost) == "{}"
    h = Harness()
    h.register("nodes", lambda: ghost)
    with pytest.raises(ParityError, match="outside the JSON data model"):
        h.check(Golden("nodes", "a0c1224", MINT, {"ghost": 1}))


class _GhostList(list):

    def __iter__(self):  # noqa: D105
        return iter([99])


def test_GREEN_empty_storage_list_subclass_follows_its_serialized_view():
    ghost = _GhostList()
    assert json.dumps(ghost) == "[99]"
    h = Harness()
    h.register("nodes", lambda: ghost)
    h.check(Golden("nodes", "a0c1224", MINT, [99]))


class _PlainEmptySub(dict):
    pass


def test_GREEN_an_honest_empty_dict_subclass_still_passes():
    h = Harness()
    h.register("nodes", lambda: _PlainEmptySub())
    h.check(Golden("nodes", "a0c1224", MINT, {}))
