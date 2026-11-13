"""Hut rules, legality side (R-100..R-103). Pure: no pyspiel, no I/O.

Hut tokens sit per seat on the three hut-effect areas of the sawmill board. A build is a short
sequence (ACTIONS 5.7): ``BUILD_HUT``, three ``HUT_TOKEN`` in any order (user ruling 2026-11-06),
three ``HUT_AREA`` in non-decreasing area; the tokens flip when the last ``HUT_AREA`` is played.
"""

from __future__ import annotations

from typing import Protocol

from lignum.rules import (
    CRAFT_ORDER,
    SetupTables,
    building_param,
    has_building,
    plan_active,
    plan_param,
)
from lignum.woodwork import ZONE_D2, zone_count

HUT_DRYING, HUT_FOOD, HUT_WORKER = 0, 1, 2
HUT_AREA_NAMES = ("drying", "food", "worker")
HUT_NAMES = ("BUILD_HUT", "HUT_TOKEN", "HUT_AREA", "HUT_FOOD", "HUT_DRY")
SET_SIZE = 3  # tokens of a normal build (R-100)
JOKER = CRAFT_ORDER.index("joker")
# Types a build may flip: board, shingle, stake and the joker; a reed bundle only as the shingle
# and only with the Small Workshop (R-100, R-110).
BUILD_TYPES = tuple(CRAFT_ORDER.index(x) for x in ("board", "shingle", "stake", "joker"))
REED = CRAFT_ORDER.index("reed")
SHINGLE = CRAFT_ORDER.index("shingle")

HB_PW = 2  # ``hb_open`` value of an open PW build (1 = normal)

Move = tuple[str, tuple[int, ...]]


class HutState(Protocol):
    """The slice of the game state the hut rules read (structural; see ``LignumState``)."""

    n: int
    picks: tuple[int, ...]
    held_craft: tuple[tuple[int, ...], ...]
    huts: tuple[tuple[int, int, int], ...]
    area_food: tuple[int, ...]
    hb_open: int
    hb_tok: tuple[int, ...]
    hb_area: tuple[int, ...]
    sale: tuple[tuple[int, int, int], ...]
    sale_logs: tuple[tuple[int, int, int], ...]
    dry: tuple[tuple[tuple[int, ...], ...], ...]
    round: int
    plans: tuple[tuple[int, int, int, int], ...]
    held_buildings: tuple[tuple[int, ...], ...]


def _valid_set(chosen: tuple[int, ...], pw: bool, reed_max: int) -> bool:
    """A full choice is a set when its real types are all different (jokers fill the rest;
    a reed stands as the shingle, R-110, at most ``reed_max`` per hut); PW Hut Construction (R-095)
    accepts any types, equal ones included."""
    if chosen.count(REED) > reed_max:
        return False
    if pw:
        return True
    real = [SHINGLE if x == REED else x for x in chosen if x != JOKER]
    return len(set(real)) == len(real)


def _completes(
    held: tuple[int, ...],
    chosen: tuple[int, ...],
    pw: int,
    types: tuple[int, ...],
    reed_max: int,
) -> bool:
    """Whether ``chosen`` (any order) can be extended to a valid set from the holding."""
    if len(chosen) == (pw or SET_SIZE):
        return _valid_set(chosen, bool(pw), reed_max)
    if not _valid_set(chosen, bool(pw), reed_max):
        return False
    return any(
        held[x] > chosen.count(x) and _completes(held, (*chosen, x), pw, types, reed_max)
        for x in types
    )


def build_types(t: SetupTables, s: HutState, seat: int) -> tuple[int, ...]:
    """Implements R-100, R-110: the token types a build may use; reed only with Small Workshop."""
    if has_building(t, s.held_buildings, seat, "small_workshop"):
        return (*BUILD_TYPES, REED)
    return BUILD_TYPES


def build_size(t: SetupTables, s: HutState) -> int:
    """Tokens of the open build: the PW Hut Construction count (R-095) or a normal set (R-100)."""
    return plan_param(t, "pw_hut_construction", "tokens_needed") if s.hb_open == HB_PW else SET_SIZE


def build_actions(t: SetupTables, s: HutState, seat: int) -> list[Move]:
    """Implements R-100 / ACTIONS 5.7: the decisions of an open build (loans are added by the
    caller)."""
    pw = build_size(t, s) if s.hb_open == HB_PW else 0
    size = pw or SET_SIZE
    if len(s.hb_tok) < size:
        held = s.held_craft[seat]
        types = build_types(t, s, seat)
        reed_max = building_param(t, "small_workshop", "reed_as_shingle_max")
        return [
            ("HUT_TOKEN", (x,))
            for x in types
            if held[x] > s.hb_tok.count(x) and _completes(held, (*s.hb_tok, x), pw, types, reed_max)
        ]
    last = s.hb_area[-1] if s.hb_area else 0
    return [("HUT_AREA", (h,)) for h in range(HUT_WORKER + 1) if h >= last]


def window_actions(t: SetupTables, s: HutState, seat: int, winter: bool) -> list[Move]:
    """Implements R-100..R-102: hut actions legal while the seat's window is open."""
    out: list[Move] = []
    types = build_types(t, s, seat)
    reed_max = building_param(t, "small_workshop", "reed_as_shingle_max")
    if _completes(s.held_craft[seat], (), 0, types, reed_max):
        out.append(("BUILD_HUT", (0,)))
    n_pw = plan_param(t, "pw_hut_construction", "tokens_needed")
    if plan_active(t, s, seat, "pw_hut_construction") and _completes(
        s.held_craft[seat], (), n_pw, types, reed_max
    ):
        out.append(("BUILD_HUT", (1,)))  # R-095
    tokens = s.huts[seat]
    if tokens[HUT_FOOD]:
        for a, food in enumerate(s.area_food):
            # user decision 2026-11-06: only free areas that hold food (R-102 is silent on empty)
            if food and (winter or all(s.picks[e] != a for e in range(s.n) if e != seat)):
                out.append(("HUT_FOOD", (a,)))
    if tokens[HUT_DRYING]:
        for z in range(ZONE_D2 + 1):  # sale area, drying 1, drying 2 (drying 3 has no right)
            out += [("HUT_DRY", (z, p)) for p in range(6) if zone_count(s, seat, z, p)]  # type: ignore[arg-type]
    return out
