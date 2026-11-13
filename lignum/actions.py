"""Decision and chance action IDs (R-075; ACTIONS 1.2, 2, 3, 5.3, 5.6).

IDs are frozen once Phase 2 closes. Decisions occupy 0..439, chance outcomes 0..102 (separate
spaces). Each family is a name plus the ordered list of valid parameter tuples; its IDs run
contiguously from a fixed start, which is asserted against the ACTIONS tables at import.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from lignum.constants import MAX_CHANCE_OUTCOMES, NUM_DISTINCT_ACTIONS

Params = tuple[int, ...]


@dataclass(frozen=True)
class Action:
    """A decoded decision or chance outcome: table name plus parameters in table order."""

    name: str
    params: Params


def _p(*domains: range | list[int]) -> list[Params]:
    return list(itertools.product(*domains))


_R = range

_SELL_SET_SHAPES = [(2, 0), (2, 1), (3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2)]

# (name, first id, ordered valid params) -- ACTIONS section 3.
_DECISIONS: list[tuple[str, int, list[Params]]] = [
    ("DONE", 0, _p()),
    ("TAKE_LOAN", 1, _p()),
    ("PICK_AREA", 2, _p(_R(6))),
    ("MOVE_TO", 8, _p(_R(1, 24))),
    ("HIRE_BEARER", 31, _p()),
    ("HIRE_WOODCUTTER", 32, _p()),
    ("HIRE_SAWYER", 33, _p()),
    ("BUY_FODDER", 34, _p()),
    ("BUY_SAW", 35, _p()),
    ("BUY_FOOD", 36, _p()),
    ("SELL_FOOD", 37, _p()),
    ("TAKE_TASK", 38, _p(_R(19))),
    ("CHOOSE_BUILDING", 57, _p(_R(10))),
    ("PLAN_WORK", 67, _p(_R(10), _R(3))),
    ("SELL_SET", 97, [(x, s, j) for x in _R(4) for s, j in _SELL_SET_SHAPES]),
    ("SELL_SET_JOKERS", 129, _p()),
    ("SELL_EQUIP", 130, _p(_R(3))),
    ("TAKE_OVERTIME", 133, _p()),
    ("BUILD_HUT", 134, _p(_R(2))),
    ("HUT_TOKEN", 136, _p(_R(5))),
    ("HUT_AREA", 141, _p(_R(3))),
    ("HUT_FOOD", 144, _p(_R(6))),
    ("HUT_DRY", 150, _p(_R(3), _R(6))),
    ("MOVE_CUT_TOKEN", 168, _p(_R(6))),
    ("ASSIGN_WORKER", 174, _p(_R(3))),
    ("TAKE_WOOD", 177, _p(_R(6), _R(3))),
    ("MOVE_WOOD", 195, _p(_R(3), _R(2))),
    ("RIVER_MOVE", 201, _p(_R(3))),
    ("WC_MOVE", 204, _p(_R(3), _R(2))),
    ("USE_WAGON", 210, _p()),
    ("USE_SLEDGE", 211, _p()),
    ("USE_PW_LOGDRIVING", 212, _p()),
    ("END_TRIP", 213, _p()),
    # ACTIONS 5.3: sawing count n by kind k: firewood 0..6, softwood 0..3, hardwood 0..1.
    ("SAW", 214, [(k, n) for k, top in ((0, 7), (1, 4), (2, 2)) for n in _R(top)]),
    ("WINTER_CUT", 227, _p()),
    ("TAKE_BONUS", 228, _p(_R(3))),
    ("PLACE_TASK", 231, _p(_R(48), _R(3))),
    ("PLACE_JOINERY", 375, _p(_R(3), _R(3))),
    ("STORE_PIECE", 384, _p(_R(3), _R(4))),
    ("SELL", 396, _p(_R(6), _R(6))),
    ("DRY_ENTER", 432, _p(_R(6))),
    ("RIVER_SALE", 438, _p(_R(2))),
]

# (name, first id, ordered valid params) -- ACTIONS section 2.
_CHANCES: list[tuple[str, int, list[Params]]] = [
    ("AREAS3", 0, _p(_R(20))),
    ("WINTER", 20, _p(_R(4), _R(2))),
    ("TASK_DRAW", 28, _p(_R(19))),
    ("PW_DRAW", 47, _p(_R(10))),
    ("PLACEMENT_DRAW", 57, _p(_R(19))),
    ("BUILDING_DRAW", 76, _p(_R(10))),
    ("CRAFT_DRAW", 86, _p(_R(5))),
    ("SPOT_TOKEN", 91, _p(_R(12))),
]


def _label(name: str, params: Params) -> str:
    return f"{name}({','.join(map(str, params))})" if params else name


def _build(
    table: list[tuple[str, int, list[Params]]], size: int
) -> tuple[dict[tuple[str, Params], int], list[Action | None]]:
    ids: dict[tuple[str, Params], int] = {}
    by_id: list[Action | None] = [None] * size
    for name, start, plist in table:
        for offset, params in enumerate(plist):
            i = start + offset
            assert 0 <= i < size and by_id[i] is None, (name, params, i)
            by_id[i] = Action(name, params)
            ids[(name, params)] = i
    return ids, by_id


_DEC_IDS, _DEC_BY_ID = _build(_DECISIONS, NUM_DISTINCT_ACTIONS)
_CH_IDS, _CH_BY_ID = _build(_CHANCES, MAX_CHANCE_OUTCOMES)
# Both spaces must be fully covered (no gaps).
assert all(a is not None for a in _DEC_BY_ID)
assert all(a is not None for a in _CH_BY_ID)


def _encode(ids: dict[tuple[str, Params], int], kind: str, name: str, params: Params) -> int:
    try:
        return ids[(name, params)]
    except KeyError:
        known = any(n == name for n, _ in ids)
        reason = "parameters out of domain or wrong arity" if known else "unknown name"
        raise ValueError(f"invalid {kind} {_label(name, params)}: {reason}") from None


def _decode(by_id: list[Action | None], kind: str, action_id: int) -> Action:
    if not 0 <= action_id < len(by_id) or by_id[action_id] is None:
        raise ValueError(f"{kind} id {action_id} outside 0..{len(by_id) - 1}")
    action = by_id[action_id]
    assert action is not None
    return action


def encode(name: str, *params: int) -> int:
    """Return the decision ID for a table name and parameters (R-075)."""
    return _encode(_DEC_IDS, "decision", name, tuple(params))


def decode(action_id: int) -> Action:
    """Return the decision named by an ID (R-075)."""
    return _decode(_DEC_BY_ID, "decision", action_id)


def action_name(action_id: int) -> str:
    """Human-readable unique name of a decision ID, e.g. "MOVE_TO(5)" (R-075)."""
    a = decode(action_id)
    return _label(a.name, a.params)


def encode_chance(name: str, *params: int) -> int:
    """Return the chance outcome ID for a table name and parameters (R-075)."""
    return _encode(_CH_IDS, "chance outcome", name, tuple(params))


def decode_chance(outcome_id: int) -> Action:
    """Return the chance outcome named by an ID (R-075)."""
    return _decode(_CH_BY_ID, "chance outcome", outcome_id)


def chance_name(outcome_id: int) -> str:
    """Human-readable unique name of a chance outcome ID (R-075)."""
    a = decode_chance(outcome_id)
    return _label(a.name, a.params)


# Named IDs for parameterless decisions (engine code uses these, never literals).
DONE = encode("DONE")
TAKE_LOAN = encode("TAKE_LOAN")
HIRE_BEARER = encode("HIRE_BEARER")
HIRE_WOODCUTTER = encode("HIRE_WOODCUTTER")
HIRE_SAWYER = encode("HIRE_SAWYER")
BUY_FODDER = encode("BUY_FODDER")
BUY_SAW = encode("BUY_SAW")
BUY_FOOD = encode("BUY_FOOD")
SELL_FOOD = encode("SELL_FOOD")
SELL_SET_JOKERS = encode("SELL_SET_JOKERS")
TAKE_OVERTIME = encode("TAKE_OVERTIME")
USE_WAGON = encode("USE_WAGON")
USE_SLEDGE = encode("USE_SLEDGE")
USE_PW_LOGDRIVING = encode("USE_PW_LOGDRIVING")
END_TRIP = encode("END_TRIP")
WINTER_CUT = encode("WINTER_CUT")
