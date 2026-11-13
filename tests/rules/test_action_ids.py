"""Phase 2 unit 1: decision and chance ID encode/decode (ACTIONS 1.2, 1.5, 2, 3, 5.3, 5.6, 7).

Planned API (lignum/actions.py), stated so the implementer can follow it:

    @dataclass(frozen=True) class Action: name: str; params: tuple[int, ...]
        name is the upper-case table name (e.g. "MOVE_TO"); params in table order.
        Same class is used for decisions and for chance outcomes (separate ID spaces).
    encode(name, *params) -> int          decision ID; ValueError for an unknown name, a wrong
                                          param count or a param outside its domain
    decode(action_id) -> Action           ValueError outside 0..439
    action_name(action_id) -> str         human readable, unique per ID, starts with the table name
                                          (used by action_to_string); e.g. "MOVE_TO(5)", "DONE"
    encode_chance(name, *params) -> int   chance outcome ID, same error rules
    decode_chance(outcome_id) -> Action   ValueError outside 0..102
    chance_name(outcome_id) -> str        unique per ID, starts with the table name

Name and param conventions are exactly the ACTIONS section 2 / 3 tables. Parameterless actions have
params == (). SELL_SET takes (x, s, j); ID 129 is the separate parameterless SELL_SET_JOKERS.
"""

import dataclasses
import itertools

import pytest


class _Lazy:
    """Import the module on first attribute use, so a missing module fails the (pending) test
    instead of breaking collection."""

    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        import importlib

        return getattr(importlib.import_module(self._name), attr)


A = _Lazy("lignum.actions")
R = range


def _decision_table() -> dict[str, dict[tuple[int, ...], int]]:
    """Independent reading of ACTIONS section 3: name -> {params: id}."""
    t: dict[str, dict[tuple[int, ...], int]] = {}

    def add(name, domains, fn):
        t[name] = {p: fn(*p) for p in itertools.product(*domains)}

    add("DONE", [], lambda: 0)
    add("TAKE_LOAN", [], lambda: 1)
    add("PICK_AREA", [R(6)], lambda a: 2 + a)
    add("MOVE_TO", [R(1, 24)], lambda loc: 7 + loc)
    add("HIRE_BEARER", [], lambda: 31)
    add("HIRE_WOODCUTTER", [], lambda: 32)
    add("HIRE_SAWYER", [], lambda: 33)
    add("BUY_FODDER", [], lambda: 34)
    add("BUY_SAW", [], lambda: 35)
    add("BUY_FOOD", [], lambda: 36)
    add("SELL_FOOD", [], lambda: 37)
    add("TAKE_TASK", [R(19)], lambda x: 38 + x)
    add("CHOOSE_BUILDING", [R(10)], lambda b: 57 + b)
    add("PLAN_WORK", [R(10), R(3)], lambda c, n: 67 + 3 * c + n)
    sets = [(2, 0), (2, 1), (3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2)]
    t["SELL_SET"] = {(x, s, j): 97 + 8 * x + i for x in R(4) for i, (s, j) in enumerate(sets)}
    t["SELL_SET_JOKERS"] = {(): 129}
    add("SELL_EQUIP", [R(3)], lambda e: 130 + e)
    add("TAKE_OVERTIME", [], lambda: 133)
    add("BUILD_HUT", [R(2)], lambda v: 134 + v)
    add("HUT_TOKEN", [R(5)], lambda x: 136 + x)
    add("HUT_AREA", [R(3)], lambda h: 141 + h)
    add("HUT_FOOD", [R(6)], lambda a: 144 + a)
    add("HUT_DRY", [R(3), R(6)], lambda z, p: 150 + 6 * z + p)
    add("MOVE_CUT_TOKEN", [R(6)], lambda a: 168 + a)
    add("ASSIGN_WORKER", [R(3)], lambda w: 174 + w)
    add("TAKE_WOOD", [R(6), R(3)], lambda a, k: 177 + 3 * a + k)
    add("MOVE_WOOD", [R(3), R(2)], lambda k, d: 195 + 2 * k + d)
    add("RIVER_MOVE", [R(3)], lambda k: 201 + k)
    add("WC_MOVE", [R(3), R(2)], lambda k, d: 204 + 2 * k + d)
    add("USE_WAGON", [], lambda: 210)
    add("USE_SLEDGE", [], lambda: 211)
    add("USE_PW_LOGDRIVING", [], lambda: 212)
    add("END_TRIP", [], lambda: 213)
    # ACTIONS 5.3: off = n (k=0, n 0..6), 7+n (k=1, n 0..3), 11+n (k=2, n 0..1)
    t["SAW"] = {
        **{(0, n): 214 + n for n in R(7)},
        **{(1, n): 214 + 7 + n for n in R(4)},
        **{(2, n): 214 + 11 + n for n in R(2)},
    }
    add("WINTER_CUT", [], lambda: 227)
    add("TAKE_BONUS", [R(3)], lambda k: 228 + k)
    add("PLACE_TASK", [R(48), R(3)], lambda s, r: 231 + 3 * s + r)
    add("PLACE_JOINERY", [R(3), R(3)], lambda k, q: 375 + 3 * k + q)
    add("STORE_PIECE", [R(3), R(4)], lambda k, z: 384 + 4 * k + z)
    add("SELL", [R(6), R(6)], lambda z, p: 396 + 6 * z + p)
    add("DRY_ENTER", [R(6)], lambda p: 432 + p)
    add("RIVER_SALE", [R(2)], lambda k: 438 + k)
    return t


def _chance_table() -> dict[str, dict[tuple[int, ...], int]]:
    """Independent reading of ACTIONS section 2: name -> {params: id}."""
    t: dict[str, dict[tuple[int, ...], int]] = {}
    t["AREAS3"] = {(r,): r for r in R(20)}
    t["WINTER"] = {(c, h): 20 + 2 * c + h for c in R(4) for h in R(2)}
    t["TASK_DRAW"] = {(x,): 28 + x for x in R(19)}
    t["PW_DRAW"] = {(c,): 47 + c for c in R(10)}
    t["PLACEMENT_DRAW"] = {(q,): 57 + q for q in R(19)}
    t["BUILDING_DRAW"] = {(b,): 76 + b for b in R(10)}
    t["CRAFT_DRAW"] = {(x,): 86 + x for x in R(5)}
    t["SPOT_TOKEN"] = {(y,): 91 + y for y in R(12)}
    return t


DEC = _decision_table()
CH = _chance_table()
DEC_ITEMS = [(n, p, i) for n, d in DEC.items() for p, i in d.items()]
CH_ITEMS = [(n, p, i) for n, d in CH.items() for p, i in d.items()]


def test_R075_decision_table_partitions_0_to_439():
    """ACTIONS 3/7: the independent table covers 0..439 exactly once (440 IDs, no gaps)."""
    ids = sorted(i for _, _, i in DEC_ITEMS)
    assert ids == list(range(440))


def test_R075_chance_table_partitions_0_to_102():
    """ACTIONS 2/7: the independent table covers 0..102 exactly once (103 outcomes)."""
    assert sorted(i for _, _, i in CH_ITEMS) == list(range(103))


def test_R075_encode_matches_spec_formula_for_every_decision_id():
    """ACTIONS 3: encode(name, *params) gives the documented ID for all 440 decision IDs."""
    for name, params, expected in DEC_ITEMS:
        assert A.encode(name, *params) == expected, (name, params)


def test_R075_decode_matches_spec_for_every_decision_id():
    """ACTIONS 3: decode(id) returns the documented (name, params) for all 440 IDs."""
    for name, params, i in DEC_ITEMS:
        a = A.decode(i)
        assert (a.name, tuple(a.params)) == (name, params), i


def test_R075_decision_round_trip_all_440():
    """ACTIONS 1.2: encode(decode(i)) == i and decode(encode(a)) == a over the whole space."""
    for i in range(440):
        a = A.decode(i)
        assert A.encode(a.name, *a.params) == i
        assert A.decode(A.encode(a.name, *a.params)) == a


def test_R075_chance_matches_spec_and_round_trips_all_103():
    """ACTIONS 2: chance encode/decode match the table and round-trip for all 103 outcomes."""
    for name, params, i in CH_ITEMS:
        assert A.encode_chance(name, *params) == i, (name, params)
        a = A.decode_chance(i)
        assert (a.name, tuple(a.params)) == (name, params), i
        assert A.encode_chance(a.name, *a.params) == i


def test_R075_id_spaces_are_separate():
    """ACTIONS 1.2: ID 5 is PICK_AREA as a decision but AREAS3 as a chance outcome."""
    assert A.decode(5).name == "PICK_AREA"
    assert A.decode_chance(5).name == "AREAS3"
    assert A.decode(30).name == "MOVE_TO"  # decision-only range beyond some chance ranges
    assert A.decode_chance(30).name == "TASK_DRAW"


def test_R075_boundary_ids():
    """ACTIONS 3: boundary IDs (DONE=0, MOVE_TO(23)=30, SELL_SET_JOKERS=129, RIVER_SALE(1)=439)."""
    assert A.decode(0).name == "DONE"
    assert A.decode(439).name == "RIVER_SALE" and tuple(A.decode(439).params) == (1,)
    assert A.encode("MOVE_TO", 23) == 30
    assert A.encode("SELL_SET_JOKERS") == 129
    assert A.encode("SAW", 2, 1) == 226
    assert A.encode("PLACE_TASK", 47, 2) == 374


def test_R075_out_of_range_ids_rejected():
    """ACTIONS 1.2: IDs outside the two spaces raise ValueError (no wraparound, no negatives)."""
    for bad in (-1, 440, 1000):
        with pytest.raises(ValueError):
            A.decode(bad)
    for bad in (-1, 103, 440):
        with pytest.raises(ValueError):
            A.decode_chance(bad)


def test_R075_invalid_params_rejected():
    """ACTIONS 3/5.3/5.6: out-of-domain params and wrong arity are not encodable."""
    bad_calls = [
        ("MOVE_TO", 0),  # locations are 1..23
        ("MOVE_TO", 24),
        ("PICK_AREA", 6),
        ("SAW", 1, 4),  # softwood: n 0..3
        ("SAW", 2, 2),  # hardwood: n 0..1
        ("SAW", 0, 7),
        ("SELL_SET", 0, 1, 0),  # size 1 is not a set
        ("SELL_SET", 0, 5, 0),
        ("SELL_SET", 0, 2, 2),  # needs s - j >= 1 real token
        ("SELL_SET", 4, 2, 0),  # real type x is 0..3
        ("STORE_PIECE", 0, 4),  # zone 0..3 only
        ("PLAN_WORK", 0, 3),
        ("DONE", 0),  # wrong arity
        ("TAKE_TASK",),
        ("NO_SUCH_ACTION",),
    ]
    for call in bad_calls:
        with pytest.raises(ValueError):
            A.encode(*call)
    for call in (("AREAS3", 20), ("WINTER", 4, 0), ("WINTER", 0, 2), ("SPOT_TOKEN", 12), ("X",)):
        with pytest.raises(ValueError):
            A.encode_chance(*call)


def test_R075_sell_set_order_within_type():
    """ACTIONS 5.6: per type x the order is (2,0),(2,1),(3,0),(3,1),(3,2),(4,0),(4,1),(4,2)."""
    order = [(2, 0), (2, 1), (3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2)]
    for x in range(4):
        ids = [A.encode("SELL_SET", x, s, j) for s, j in order]
        assert ids == list(range(97 + 8 * x, 105 + 8 * x))


def test_R075_action_names_unique_readable_and_prefixed():
    """ACTIONS 1.5/3: action_name is a unique non-empty str per ID starting with the table name."""
    names = [A.action_name(i) for i in range(440)]
    assert all(isinstance(n, str) and n for n in names)
    assert len(set(names)) == 440
    for name, _params, i in DEC_ITEMS:
        assert A.action_name(i).startswith(name), i
    assert A.action_name(0) == "DONE" or "DONE" in A.action_name(0)
    # parameters are visible so logs distinguish actions of one family
    assert "5" in A.action_name(A.encode("MOVE_TO", 5))


def test_R075_chance_names_unique_and_prefixed():
    """ACTIONS 2: chance_name is unique per outcome and begins with the table name."""
    names = [A.chance_name(i) for i in range(103)]
    assert len(set(names)) == 103
    for name, _params, i in CH_ITEMS:
        assert A.chance_name(i).startswith(name), i


def test_R075_action_is_frozen_and_hashable():
    """ACTIONS 1.2: typed actions are immutable value objects usable as dict keys."""
    a = A.decode(8)
    assert a == A.decode(8) and hash(a) == hash(A.decode(8))
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.name = "X"  # type: ignore[misc]
