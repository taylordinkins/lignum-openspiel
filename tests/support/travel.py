"""Supply-path helpers for unit-6 tests (written from the spec only; public API only).

Everything here is derived from docs/RULES_SPEC.md R-021..R-025, R-040..R-044 and docs/ACTIONS.md.
The `oracle_moves` function is an independent statement of R-040's activation test; it knows
nothing of the engine.

Planned work, Buildings and the Market are Phase-4 content (ACTIONS section 7), so their
locations are never asserted either way: `PHASE4_KINDS`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

from tests import harness as H
from tests.support import rounds as R

CLEARING = 23
PHASE4_KINDS = frozenset({"pw", "buildings", "market"})

_BASE_KINDS = {
    4: "bearers",
    6: "fodder",
    8: "pw",
    10: "woodcutters",
    13: "tasks",
    16: "sawyers",
    19: "market",
}
_JOIN_KINDS = {
    4: "bearers",
    6: "fodder",
    8: "pw",
    10: "woodcutters",
    12: "buildings",
    14: "tasks",
    16: "joiner",
    18: "sawyers",
    21: "market",
}
CAPACITY = {
    "bearers": 4,
    "fodder": 2,
    "pw": 4,
    "woodcutters": 4,
    "buildings": 2,
    "tasks": 4,
    "joiner": 1,
    "sawyers": 4,
    "market": 4,
    "spot": 1,
}


def last_loc(joinery: bool) -> int:
    return 22 if joinery else 20


def kind_of(joinery: bool, loc: int) -> str:
    """Acquisition kind of printed location `loc` on the side (R-021, R-022); 'none' if absent."""
    if loc < 1 or loc > last_loc(joinery):
        return "none"
    return (_JOIN_KINDS if joinery else _BASE_KINDS).get(loc, "spot")


def params(n: int, joinery: bool = False) -> dict[str, Any]:
    return {"players": n, "joinery": joinery}


def start(n: int, joinery: bool = False, seed: int = 1) -> Any:
    """Round 1, P0 to move at TR."""
    s: Any = H.play_setup(params(n, joinery), seed=seed)  # pyright: ignore[reportUnknownMemberType]
    assert H.phase_of(s) == "TR"  # pyright: ignore[reportUnknownMemberType]
    return s


def snap(state: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", H.snapshot(state))  # pyright: ignore[reportUnknownMemberType]


def seat_of(sn: dict[str, Any], i: int) -> dict[str, Any]:
    return cast("dict[str, Any]", H.seats(sn)[i])  # pyright: ignore[reportUnknownMemberType]


def spots(sn: dict[str, Any]) -> dict[int, str | None]:
    return cast("dict[int, str | None]", H.tokens(sn))  # pyright: ignore[reportUnknownMemberType]


def spot_with(sn: dict[str, Any], *kinds: str) -> list[int]:
    return sorted(loc for loc, t in spots(sn).items() if t in kinds)


def move_locs(state: Any) -> list[int]:
    """Printed location numbers (23 = clearing) of the legal MOVE_TO actions."""
    return sorted(a - 7 for a in state.legal_actions() if 8 <= a <= 30)


def play(state: Any, *actions: int) -> Any:
    return H.apply_actions(state, list(actions))  # pyright: ignore[reportUnknownMemberType]


def at_move_node(state: Any) -> bool:
    """True when the acting seat is about to choose a destination (the clearing is always
    enterable at such a node and is never legal in the middle of a visit, R-040/R-044)."""
    return R.MOVE_CLEARING in state.legal_actions()


def end_visit(state: Any) -> None:
    """Close a visit with DONE if it is still open (a visit may also close automatically,
    ACTIONS 1.4; whether it does so after the last possible multi-unit acquisition is not fixed)."""
    if not state.is_terminal() and not at_move_node(state) and H.DONE in state.legal_actions():
        state.apply_action(H.DONE)


def visit(state: Any, loc: int, *acts: int) -> Any:
    """MOVE_TO(loc), the acquisitions `acts`, then close the visit."""
    play(state, H.MOVE_TO(loc), *acts)
    end_visit(state)
    return state


def hire(state: Any, loc: int, action: int, count: int) -> Any:
    return visit(state, loc, *([action] * count))


def goto_clearing(state: Any) -> Any:
    return play(state, R.MOVE_CLEARING)


def total_wood(area: dict[str, Any]) -> int:
    return sum(R.wood(area).values())


def own_wood(sn: dict[str, Any], i: int) -> int:
    """Wood pieces in seat i's selected cutting area (R-041 Woodcutters cap)."""
    area = seat_of(sn, i)["cutting_area"]
    return total_wood(cast("dict[str, Any]", H.areas(sn)[area - 1]))  # pyright: ignore[reportUnknownMemberType]


def oracle_moves(sn: dict[str, Any], joinery: bool) -> set[int]:
    """Locations (23 = clearing) the acting seat may enter at a TR move node, per R-040 items
    1-5, R-041, R-042 and R-043, for the non-Phase-4 kinds only. Loans count for payment
    (R-040 item 4) but are not part of the seat's money."""
    me = sn["current_player"]
    s = seat_of(sn, me)
    pos = s["foreman"]
    assert isinstance(pos, int)
    can_pay = s["money"] >= 1 or s["loans"] < 2
    n_seats = len(cast("list[Any]", H.seats(sn)))  # pyright: ignore[reportUnknownMemberType]
    occ: Counter[int] = Counter(
        f for f in (seat_of(sn, i)["foreman"] for i in range(n_seats)) if isinstance(f, int)
    )
    path = sn["path"]
    tok = spots(sn)
    out = {CLEARING}
    for loc in range(pos + 1, last_loc(joinery) + 1):
        kind = kind_of(joinery, loc)
        if kind in PHASE4_KINDS or occ[loc] >= CAPACITY[kind]:
            continue
        if kind == "spot":
            t = tok.get(loc)
            ok = t is not None and t != "x" and not (t == "saw" and s["equipment"]["saw"] >= 4)
        elif kind == "bearers":
            ok = path["bearers"] > 0 and can_pay
        elif kind == "woodcutters":
            ok = (
                path["woodcutters"] > 0
                and own_wood(sn, me) - s["hired"]["woodcutters"] > 0
                and can_pay
            )
        elif kind == "fodder":
            ok = (
                path["fodder"] > 0
                and not s["fodder"]["slot3"]
                and not s["fodder_bought"]
                and can_pay
            )
        elif kind == "tasks":
            ok = len(sn["supply"]["tasks_laid_out"]) > 0 and not s["task_taken"] and can_pay
        elif kind == "sawyers":
            ok = path["sawyers_free"] > 0 and s["hired"]["sawyers"] == 0
        elif kind == "joiner":
            ok = path["joiner"] > 0 and s["joiners"] < 3
        else:  # pragma: no cover
            raise AssertionError(kind)
        if ok:
            out.add(loc)
    return out


def legal_non_phase4_moves(state: Any, joinery: bool) -> set[int]:
    return {loc for loc in move_locs(state) if kind_of(joinery, loc) not in PHASE4_KINDS}


def broke_p0(joinery: bool = False, seed: int = 1) -> Any:
    """4 players, round 1. P0 takes both loans ($13), hires all 10 bearers (location 4) and then
    all 3 woodcutters its 3-firewood area allows ($3 -> $0), the others going straight to the
    clearing. Returns the state at P0's third travel node: P0 on location 10, $0, 2 loans."""
    j = joinery
    s = start(4, j, seed)
    play(s, H.TAKE_LOAN, H.TAKE_LOAN)
    hire(s, R.loc(j, "bearers"), R.HIRE_BEARER, 10)
    for _ in (1, 2, 3):
        goto_clearing(s)
    assert s.current_player() == 0
    hire(s, R.loc(j, "woodcutters"), R.HIRE_WOODCUTTER, 3)
    assert s.current_player() == 0
    return s
