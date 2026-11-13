"""Phase 4 unit 12: Buildings C, Small Storage Area, Field, Office (R-114, R-115, R-116;
with R-041, R-055, R-056, R-058, R-069, R-073, R-081, R-082, R-083 and the notes O-U4-9, O-U4-12).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (5.4, 5.11 and the STORE_PIECE rows) and
tests/harness.py only, in the style of test_buildings_a.py / test_buildings_b.py: a seat gets a
building by `bldscen.give` (white-box assignment of `held_buildings`) on a state reached by scripted
play with joinery=true. Boards are made by assigning the same per-seat tuples the existing tests
assign (`sale_logs`, `sale`, `dry`, `store`, `held_tasks`). The building and its
actions are implemented, so no test here is pending.

Ids: STORE_PIECE(k, z) = 384 + 4k + z (k: 0 firewood, 1 softwood, 2 hardwood; z: 0 sale area,
1..3 drying areas 1..3), PLACE_TASK(s, r) = 231 + 3s + r with r = 2 the stored piece (ACTIONS 5.4),
BUY_FODDER 34, MOVE_TO(l) = 7 + l, RIVER_SALE(k) = 438 + k.

Fixture facts (task_10 = hardwood +0, firewood +0, firewood +1; task_13 = hardwood +0, firewood +0,
unmilled firewood; task_16 = hardwood +0, firewood +2; all from data/components/cards.yaml): the
chain of `sawmill.chain_steps` leaves P0 with task_10 held, 2 milled firewood in the sale area and 2
in drying 1 at round 2's Tasks phase, and 2 milled firewood in drying 3 at round 4's winter.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest
import yaml

from tests import harness as H
from tests.support import bldscen as B
from tests.support import rounds as R
from tests.support import sawmill as SM
from tests.support import travel as T
from tests.support import winter as V

STORAGE, FIELD, OFFICE = "small_storage_area", "field", "office"
FW, SW, HW = 0, 1, 2
BUY_FODDER = R.BUY_FODDER
STORE_IDS = range(384, 396)
SELL_0_3 = range(396, 396 + 24)  # SELL(zone 0..3, piece)
TASK10 = R.task_ids().index("task_10")
TASK13 = R.task_ids().index("task_13")
TASK16 = R.task_ids().index("task_16")
S10_HW, S10_FW0, S10_FW1 = SM.slot("task_10", 0), SM.slot("task_10", 1), SM.slot("task_10", 2)
S13_FW_MILLED, S13_FW_UNMILLED = SM.slot("task_13", 1), SM.slot("task_13", 2)
S16_FW2 = SM.slot("task_16", 1)
FW_LOG = "firewood_log"


def store(kind: int, zone: int) -> int:
    return 384 + 4 * kind + zone


def stored_place(slot: int) -> int:
    """PLACE_TASK(slot, 2): the Small Storage Area piece (ACTIONS 5.4)."""
    return SM.place_task(slot, 2)


def _tup(t: tuple[Any, ...], i: int, v: Any) -> tuple[Any, ...]:
    return tuple(v if j == i else x for j, x in enumerate(t))


def _buildings() -> list[dict[str, Any]]:
    with open(R.ROOT / "data" / "components" / "buildings.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["buildings"]


def _stores(s: Any) -> list[int]:
    return [a for a in s.legal_actions() if a in STORE_IDS]


def _stored_uses(s: Any) -> list[int]:
    """PLACE_TASK actions whose source is the stored piece (r = 2)."""
    return [a for a in s.legal_actions() if a in SM.PLACE_TASK_IDS and (a - 231) % 3 == 2]


def _set_sale_logs(s: Any, counts: tuple[int, int, int], seat: int = 0) -> None:
    s.sale_logs = _tup(s.sale_logs, seat, counts)


def _set_drying(s: Any, area: int, counts: tuple[int, ...], seat: int = 0) -> None:
    """counts: 3 disk counts then 3 log counts (firewood, softwood, hardwood)."""
    s.dry = _tup(s.dry, seat, _tup(s.dry[seat], area, counts))


def _clear_wood(s: Any, seat: int = 0) -> None:
    s.sale_logs = _tup(s.sale_logs, seat, (0, 0, 0))
    s.sale = _tup(s.sale, seat, (0, 0, 0))
    s.dry = _tup(s.dry, seat, tuple((0,) * 6 for _ in range(3)))


# The helpers below read internal state fields rather than a scenario dump: after a commit or a
# placement the turn is mid-turn (S-MIDTURN), so the dump raises, as in test_craftwork_selling.py.
_NAMES = ("firewood", "softwood", "hardwood")


def _pieces(disks: tuple[int, ...], logs: tuple[int, ...]) -> Counter[str]:
    c = Counter({f"{k}_disk": n for k, n in zip(_NAMES, disks, strict=True) if n})
    c.update({f"{k}_log": n for k, n in zip(_NAMES, logs, strict=True) if n})
    return c


def _sale(s: Any) -> Counter[str]:
    return _pieces(s.sale[0], s.sale_logs[0])


def _drying(s: Any) -> list[Counter[str]]:
    return [_pieces(a[:3], a[3:]) for a in s.dry[0]]


def _filled(s: Any, task: str) -> list[int]:
    idx = R.task_ids().index(task)
    if idx not in s.held_tasks[0]:
        raise AssertionError(f"{task} not held")
    n = s.filled[idx].bit_length()
    return [r for r in range(n) if s.filled[idx] >> r & 1]


# =========================================================================== R-114 fixtures


def _chain_state(stop: tuple[int, str, int], key: str, building: bool = True) -> Any:
    s = SM.reach(SM.chain_steps(True), stop, key, j=True)
    if building:
        B.give(s, 0, STORAGE)
    return s


def _r2_w5(building: bool = True) -> Any:
    """Round 2 Tasks phase, P0: task_10 held, 2 milled firewood in the sale area, 2 in drying 1."""
    return _chain_state((2, "W5", 0), "c_r2w5", building)


_CACHE: dict[Any, Any] = {}


def _winter_state(rnd: int, key: str, steps: Callable[[], Any] | None = None) -> Any:
    """P0's N4 turn of round `rnd` (4 or 8), holding task_10, joinery game; a fresh clone."""
    k = (rnd, key)
    if k not in _CACHE:
        st = steps() if steps else SM.chain_steps(True)
        _CACHE[k] = V.reach(st, (rnd, "N4", 0), j=True)
    return _CACHE[k].clone()


def _store_cb(
    kind: int = FW, zone: int = 0, mutate: Callable[[Any], None] | None = None
) -> Callable[[Any], int]:
    """A scripted-play entry for round 2's Tasks phase: hand P0 the building (and optionally
    change the board first), then commit the piece (kind, zone)."""

    def go(state: Any) -> int:
        B.give(state, 0, STORAGE)
        if mutate:
            mutate(state)
        return store(kind, zone)

    return go


def _with_stored(kind: int = FW, zone: int = 0, mutate: Callable[[Any], None] | None = None) -> Any:
    """P0's round-8 N4 turn, the building holding a piece committed in round 2's Tasks phase."""
    key = ("stored", kind, zone, mutate.__name__ if mutate else None)

    def steps() -> Any:
        st = SM.chain_steps(True)
        st.add(2, "W5", 0, _store_cb(kind, zone, mutate))
        return st

    s = _winter_state(8, repr(key), steps)
    return s


def _hw_in_sale(s: Any) -> None:
    _set_sale_logs(s, (1, 0, 1))


# =========================================================================== R-114 commit


def test_R114_commit_a_milled_piece_from_the_sale_area():
    """R-114: in a Tasks phase a seat with the building commits one milled piece from the sale
    area; the piece leaves the sale area."""
    s = _r2_w5()
    assert store(FW, 0) in s.legal_actions()
    before = _sale(s)[FW_LOG]
    s.apply_action(store(FW, 0))
    assert _sale(s)[FW_LOG] == before - 1


def test_R114_commit_is_legal_in_round_1_tasks_phase_too():
    """R-114/R-055: any Tasks phase where wood may go on task cards counts, round 1 included."""
    s = _chain_state((1, "W5", 0), "c_r1w5")
    assert store(FW, 0) in s.legal_actions()


def test_R114_commit_from_drying_area_one_keeps_other_pieces():
    """R-114: the drying areas count as sale areas: a piece from drying 1 can be committed and
    the other piece there stays."""
    s = _r2_w5()
    assert _drying(s)[0][FW_LOG] == 2
    assert store(FW, 1) in s.legal_actions()
    s.apply_action(store(FW, 1))
    assert _drying(s)[0][FW_LOG] == 1
    assert _sale(s)[FW_LOG] == 2


@pytest.mark.parametrize("area", [1, 2])
def test_R114_commit_from_the_second_and_third_drying_areas_at_any_stage(area):
    """R-114: a milled piece from drying 2 or drying 3 (any dryness stage) can be committed."""
    s = _r2_w5()
    _clear_wood(s)
    _set_drying(s, area, (0, 0, 0, 1, 0, 0))
    assert store(FW, area + 1) in s.legal_actions()
    s.apply_action(store(FW, area + 1))
    assert _drying(s)[area] == Counter()


@pytest.mark.parametrize("kind", [FW, SW, HW])
def test_R114_any_milled_kind_is_valid_firewood_included(kind):
    """R-114: any milled kind may be committed, milled firewood included."""
    s = _r2_w5()
    _clear_wood(s)
    counts = [0, 0, 0]
    counts[kind] = 1
    _set_sale_logs(s, (counts[0], counts[1], counts[2]))
    assert _stores(s) == [store(kind, 0)]


def test_R114_only_kinds_actually_held_are_offered():
    """R-114: with only milled firewood in the sale area, no softwood/hardwood commit is offered."""
    s = _r2_w5()
    _clear_wood(s)
    _set_sale_logs(s, (1, 0, 0))
    assert _stores(s) == [store(FW, 0)]


def test_R114_not_legal_without_the_building():
    """R-114: a seat without the building has no commit action."""
    s = _r2_w5(building=False)
    assert _stores(s) == []


def test_R114_other_seats_building_gives_this_seat_nothing():
    """R-114: P1 holds the building; P0 (to move, with milled wood) cannot commit."""
    s = _r2_w5(building=False)
    B.give(s, 1, STORAGE)
    assert _stores(s) == []


def test_R114_not_legal_in_the_selling_phase():
    """R-114: the commit follows the task-card rules: not in Selling (W6)."""
    s = _chain_state((2, "W6", 0), "c_r2w6")
    assert _stores(s) == []


def test_R114_not_legal_in_the_drying_phase():
    """R-114: not in the Drying phase (W7) either."""
    s = _chain_state((2, "W7", 0), "c_r2w7")
    assert _stores(s) == []


def test_R114_not_legal_in_winter_year_one():
    """R-114/R-069: in the winter of year 1 no wood goes on tasks, so none can be committed."""
    s = _winter_state(4, "plain")
    B.give(s, 0, STORAGE)
    _set_sale_logs(s, (2, 0, 0))
    assert _stores(s) == []


# --------------------------------------------------------------------------- sources that are out


def _only(s: Any, **fields: tuple[Any, ...]) -> None:
    """Clear P0's sale and drying wood, then assign per-seat 3-count fields for seat 0."""
    _clear_wood(s)
    for name, counts in fields.items():
        setattr(s, name, _tup(getattr(s, name), 0, counts))


def test_R114_cannot_commit_unmilled_wood():
    """R-114: only milled pieces: an unmilled disk in the sale area gives no commit."""
    s = _r2_w5()
    _only(s, sale=(1, 1, 0))
    assert _stores(s) == []


def test_R114_cannot_commit_an_unmilled_disk_from_a_drying_area():
    """R-114: a lone disk in drying 1 (unmilled) gives no commit."""
    s = _r2_w5()
    _clear_wood(s)
    _set_drying(s, 0, (1, 0, 0, 0, 0, 0))
    assert _stores(s) == []


def test_R114_cannot_commit_from_the_firewood_storage():
    """R-114: milled wood in the firewood storage cannot be committed."""
    s = _r2_w5()
    _only(s, store=(2, 1, 1))
    assert _stores(s) == []


def test_R114_cannot_commit_from_woodpile_sawing_area_or_river():
    """R-114: wood in the woodpile, the sawing area and the river cannot be committed."""
    s = _r2_w5()
    _only(s, woodpile=(1, 1, 1), sawing=(1, 1, 1), river=(1, 1, 1))
    assert _stores(s) == []


# =========================================================================== R-114 one piece only


def test_R114_fill_only_while_empty_second_commit_is_illegal():
    """R-114: after a piece is committed, with more milled wood available, no second commit."""
    s = _r2_w5()
    s.apply_action(store(FW, 0))
    assert _sale(s)[FW_LOG] == 1 and _drying(s)[0][FW_LOG] == 2
    assert _stores(s) == []


def test_R114_stays_full_in_later_rounds_until_moved():
    """R-114: a never-moved piece keeps the building full: in round 4's winter (and in round 3's
    Tasks phase) no further commit is offered."""
    st = SM.chain_steps(True)
    st.add(2, "W5", 0, _store_cb())
    s = V.reach(st, (3, "W5", 0), j=True)
    _set_sale_logs(s, (3, 0, 0))
    assert _stores(s) == []


def test_R114_piece_cannot_be_used_on_a_task_before_the_final_assignment():
    """R-114: before round 8's Tasks phase the only use of the piece is the move: it cannot be
    placed on task_10's free firewood spaces in the phase it was committed."""
    s = _r2_w5()
    s.apply_action(store(FW, 0))
    assert _stored_uses(s) == []


def test_R114_piece_cannot_be_used_in_a_later_round_before_round_eight():
    """R-114: in round 3's Tasks phase the stored piece still cannot go on a task."""
    st = SM.chain_steps(True)
    st.add(2, "W5", 0, _store_cb())
    s = V.reach(st, (3, "W5", 0), j=True)
    assert _stored_uses(s) == []


# =========================================================================== R-114 final assignment


def test_R114_stored_piece_moves_to_a_free_milled_space_in_round_eight():
    """R-114: in round 8's Tasks phase the stored firewood fills a free milled firewood space of
    task_10 and is locked there."""
    s = _with_stored()
    assert stored_place(S10_FW0) in s.legal_actions()
    s.apply_action(stored_place(S10_FW0))
    assert _filled(s, "task_10") == [S10_FW0 - S10_HW]


def test_R114_stored_firewood_fills_a_plus_one_space_regardless_of_stage():
    """R-114 (O-U4-9): the printed stage is ignored: task_10's firewood +1 space accepts it."""
    s = _with_stored()
    assert stored_place(S10_FW1) in s.legal_actions()
    s.apply_action(stored_place(S10_FW1))
    assert _filled(s, "task_10") == [S10_FW1 - S10_HW]


def test_R114_stored_firewood_fills_a_plus_two_space_regardless_of_stage():
    """R-114: a +2 requirement (task_16's firewood +2) accepts the stored piece too."""

    s = _with_stored()
    s.held_tasks = _tup(s.held_tasks, 0, (TASK10, TASK16))
    assert stored_place(S16_FW2) in s.legal_actions()


@pytest.mark.parametrize("zone", [0, 1, 2, 3])
def test_R114_piece_from_any_source_area_fills_any_stage(zone):
    """R-114: a piece committed from the sale or any drying area counts as any dryness stage."""

    def put(s: Any) -> None:
        _clear_wood(s)
        if zone == 0:
            _set_sale_logs(s, (1, 0, 0))
        else:
            _set_drying(s, zone - 1, (0, 0, 0, 1, 0, 0))

    put.__name__ = f"put{zone}"
    s = _with_stored(FW, zone, put)
    assert {stored_place(S10_FW0), stored_place(S10_FW1)} <= set(s.legal_actions())


def test_R114_stored_hardwood_fills_the_hardwood_space_only():
    """R-114: a stored milled hardwood fills task_10's hardwood space and no firewood space."""
    s = _with_stored(HW, 0, _hw_in_sale)
    assert stored_place(S10_HW) in s.legal_actions()
    assert stored_place(S10_FW0) not in s.legal_actions()
    assert stored_place(S10_FW1) not in s.legal_actions()


def test_R114_kind_must_match_firewood_never_fills_hardwood():
    """R-114: the stored firewood cannot fill the hardwood space."""
    s = _with_stored()
    assert stored_place(S10_HW) not in s.legal_actions()


def test_R114_stored_softwood_has_no_space_on_task_ten():
    """R-114: a stored softwood finds no softwood space on task_10: no move is offered."""

    def sw(s: Any) -> None:
        _set_sale_logs(s, (1, 1, 0))

    s = _with_stored(SW, 0, sw)
    assert _stored_uses(s) == []


def test_R114_cannot_fill_a_requirement_for_unmilled_wood():
    """R-114 (O-U4-12): task_13's third space asks for an unmilled firewood disk; the stored
    milled firewood does not fit it, but fits the milled firewood space next to it."""
    s = _with_stored()
    s.held_tasks = _tup(s.held_tasks, 0, (TASK10, TASK13))
    legal = s.legal_actions()
    assert stored_place(S13_FW_UNMILLED) not in legal
    assert stored_place(S13_FW_MILLED) in legal


def test_R114_only_free_requirement_spaces_accept_the_piece():
    """R-114: a space already filled by a locked piece is not available: with task_10's firewood +1
    space filled from drying 2, the stored piece goes only to the +0 space."""
    s = _with_stored()
    _clear_wood(s)
    _set_drying(s, 1, (0, 0, 0, 1, 0, 0))
    s.apply_action(SM.place_task(S10_FW1, 0))
    legal = s.legal_actions()
    assert stored_place(S10_FW1) not in legal
    assert stored_place(S10_FW0) in legal


def test_R114_no_free_space_means_the_piece_is_not_placeable():
    """R-114: if no card has a free space of the kind, no move is offered (the piece scores $0)."""
    s = _with_stored(HW, 0, _hw_in_sale)
    s.held_tasks = _tup(s.held_tasks, 0, ())
    assert _stored_uses(s) == []


def test_R114_move_is_only_for_the_seats_own_task_cards():
    """R-114/R-055: P1's task cards are not targets; with P0 holding no card nothing is offered."""
    s = _with_stored()
    s.held_tasks = (tuple(), (TASK10,))
    assert _stored_uses(s) == []


def test_R114_stored_piece_cannot_be_placed_in_winter_year_one():
    """R-114/R-069: in round 4's Tasks phase the stored piece cannot move (and nothing else may be
    placed on tasks in the first winter)."""
    st = SM.chain_steps(True)
    st.add(2, "W5", 0, _store_cb())
    s = V.reach(st, (4, "N4", 0), j=True)
    assert _stored_uses(s) == []
    assert not [a for a in s.legal_actions() if a in SM.PLACE_TASK_IDS]


def test_R114_building_empties_after_the_move_and_never_refills():
    """R-114: after the stored piece is moved the building cannot be refilled, even in the same
    phase with milled wood in the sale area; a second move is not offered either."""
    s = _with_stored()
    _set_sale_logs(s, (2, 0, 0))
    s.apply_action(stored_place(S10_FW0))
    assert _stores(s) == []
    assert _stored_uses(s) == []


def test_R114_stored_piece_counts_for_task_completion():
    """R-114/R-056: the locked piece counts as a filled space of the card (task_16: two spaces,
    hardwood +0 and firewood +2; the stored piece takes the firewood one)."""
    s = _with_stored()
    s.held_tasks = _tup(s.held_tasks, 0, (TASK16,))
    s.apply_action(stored_place(S16_FW2))
    assert _filled(s, "task_16") == [1]


# --------------------------------------------------------------------------- round 8 same phase


def test_R114_round_eight_commit_and_move_in_the_same_phase():
    """R-114 (user answer 2026-11-04): in round 8's Tasks phase a piece may be committed from the
    sale area and moved to a task in that same phase."""
    s = _winter_state(8, "plain")
    B.give(s, 0, STORAGE)
    _set_sale_logs(s, (1, 0, 0))
    assert store(FW, 0) in s.legal_actions()
    s.apply_action(store(FW, 0))
    assert stored_place(S10_FW0) in s.legal_actions()
    s.apply_action(stored_place(S10_FW0))
    assert _filled(s, "task_10") == [S10_FW0 - S10_HW]


def test_R114_round_eight_commit_from_a_drying_area_then_move():
    """R-114: in round 8 a piece from a drying area (any stage) is committed and moved at once."""
    s = _winter_state(8, "plain")
    B.give(s, 0, STORAGE)
    _clear_wood(s)
    _set_drying(s, 0, (0, 0, 0, 1, 0, 0))
    s.apply_action(store(FW, 1))
    assert stored_place(S10_FW1) in s.legal_actions()


def test_R114_round_eight_commit_is_once_only_even_if_not_moved():
    """R-114: committing in round 8 fills the building; a second commit is not offered."""
    s = _winter_state(8, "plain")
    B.give(s, 0, STORAGE)
    _set_sale_logs(s, (2, 0, 0))
    s.apply_action(store(FW, 0))
    assert _stores(s) == []


def test_R114_round_eight_cannot_commit_from_the_firewood_storage():
    """R-114: in round 8 milled wood in the firewood storage still cannot be committed."""
    s = _winter_state(8, "plain")
    B.give(s, 0, STORAGE)
    _only(s, store=(3, 3, 3))
    assert _stores(s) == []


def test_R114_round_eight_no_commit_without_the_building():
    """R-114: without the building round 8's Tasks phase offers no commit."""
    s = _winter_state(8, "plain")
    _set_sale_logs(s, (1, 0, 0))
    assert _stores(s) == []


# =========================================================================== R-114 never sold


def _sells_in_shortfall(stored: bool) -> int:
    """Play P0's round-4 shortfall (loans first, then sell zones 0..3 until none is legal) and
    count the pieces sold from the sale and drying areas."""
    st = SM.chain_steps(True)
    if stored:
        st.add(2, "W5", 0, _store_cb())
    s = V.to_shortfall(st, 0, j=True)
    sold = 0
    for _ in range(60):
        legal = s.legal_actions()
        sells = [a for a in legal if a in SELL_0_3]
        if sells:
            s.apply_action(min(sells))
            sold += 1
        elif legal == [H.TAKE_LOAN]:
            s.apply_action(H.TAKE_LOAN)
        else:
            break
    return sold


def test_R114_stored_piece_is_not_sold_in_the_winter_shortfall():
    """R-114/R-073: the baseline seat can sell 4 pieces from the sale and drying areas in the
    first winter's shortfall; with one of them stored it can sell only 3."""
    base = _sells_in_shortfall(False)
    assert base == 4
    assert _sells_in_shortfall(True) == base - 1


def _round8_shortfall_sells(stored: bool) -> int:
    """P0 with $0, no food and both loans taken reaches round 8's shortfall holding one milled
    firewood in the sale area (and, if `stored`, a committed piece); sell until none is legal."""
    if stored:
        s = _with_stored()
    else:
        s = _winter_state(8, "plain")
        B.give(s, 0, STORAGE)
    _clear_wood(s)
    _set_sale_logs(s, (1, 0, 0))
    s.food = _tup(s.food, 0, 0)
    s.money = _tup(s.money, 0, 0)
    s.loans = _tup(s.loans, 0, 2)
    s.apply_action(H.DONE)
    for _ in range(100):
        if V.in_sf(s) and s.current_player() == 0:
            break
        assert not s.is_terminal(), "left winter without a shortfall"
        legal = s.legal_actions()
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    sold = 0
    while [a for a in s.legal_actions() if a in SELL_0_3]:
        s.apply_action(min(a for a in s.legal_actions() if a in SELL_0_3))
        sold += 1
    return sold


def test_R114_stored_piece_is_not_sold_in_round_eight_shortfall():
    """R-114/R-073: in round 8's winter shortfall only the sale-area piece is sold; the piece
    still in the Small Storage Area is not offered, so both runs sell exactly one piece."""
    assert _round8_shortfall_sells(False) == 1
    assert _round8_shortfall_sells(True) == 1


def _finish(s: Any) -> Any:
    for _ in range(600):
        if s.is_terminal():
            return s
        legal = s.legal_actions()
        sn = R.try_snapshot(s)
        if sn is not None and sn["phase"] == "FS":
            s.apply_action([a for a in legal if V.RIVER_SALE0 <= a < V.RIVER_SALE0 + 2][0])
            continue
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("too many steps")


def test_R114_never_moved_piece_is_not_sold_in_the_final_sale():
    """R-114/R-081/R-082: a stored piece that is never moved is worth $0: the final dollars equal
    the reference model computed from the board at round 8's last Tasks turn (which counts no
    stored wood), so the margin returns match the model."""
    st = SM.chain_steps(True)
    st.add(2, "W5", 0, _store_cb())
    run = R.drive(
        {**V.params(2, True), "returns": "margin"},
        seed=V.SEED,
        policy=V.policy(st),
        stop=V._last_n4_of_round_8,  # pyright: ignore[reportPrivateUsage]
    )
    assert run.stopped
    s = run.state
    sn = V.snap(s)
    d = [float(V.final_dollars(x, V.requirement(sn, 2))["dollars"]) for x in H.seats(sn)]
    s = _finish(s)
    assert list(s.returns()) == pytest.approx(V.margin_returns(d))


# =========================================================================== R-114 data


def test_R114_capacity_comes_from_data_not_code():
    """R-114 / CLAUDE.md: the capacity is a data parameter of the building in buildings.yaml."""
    b = {x["id"]: x for x in _buildings()}
    assert b[STORAGE]["params"]["capacity"] == 1


# =========================================================================== R-115 Field


def _fodder_loc() -> int:
    return R.loc(True, "fodder")


def _field_start(building: bool) -> Any:
    s = T.start(2, True)
    if building:
        B.give(s, 0, FIELD)
    return s


def test_R115_baseline_fodder_costs_one_dollar_without_the_field():
    """R-041 baseline for R-115: no building, fodder costs $1 (P0 starts with $5)."""
    s = _field_start(False)
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    assert T.seat_of(T.snap(s), 0)["money"] == 4


def test_R115_fodder_costs_nothing_with_the_field():
    """R-115: with the Field the fodder costs $0: money stays $5, the fodder sits on the value-3
    slot and the visit ends."""
    s = _field_start(True)
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 5
    assert me["fodder"] == {"slot3": True, "slot2": False}
    assert me["fodder_bought"] is True
    assert s.current_player() == 1


def test_R115_a_seat_without_money_can_enter_fodder_with_the_field():
    """R-115/R-040: with $0 and no loan taken, the Fodder location is enterable and the fodder is
    free; without the Field it is not enterable."""
    s = _field_start(True)
    s.money = _tup(s.money, 0, 0)
    assert H.MOVE_TO(_fodder_loc()) in s.legal_actions()
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    assert T.seat_of(T.snap(s), 0)["money"] == 0


def test_R115_penniless_seat_with_both_loans_taken_can_enter_fodder_with_the_field():
    """R-115/R-040: $0 and both loans taken, with the Field: Fodder is enterable and the fodder
    costs $0 (money stays $0)."""
    s = _field_start(True)
    s.money = _tup(s.money, 0, 0)
    s.loans = _tup(s.loans, 0, 2)
    assert H.MOVE_TO(_fodder_loc()) in s.legal_actions()
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 0 and me["fodder"]["slot3"] is True


def test_R115_without_the_field_a_penniless_seat_cannot_enter_fodder():
    """R-115 baseline: $0 and two loans taken, no Field: Fodder cannot be entered (R-040)."""
    s = _field_start(False)
    s.money = _tup(s.money, 0, 0)
    s.loans = _tup(s.loans, 0, 2)
    assert H.MOVE_TO(_fodder_loc()) not in s.legal_actions()


def test_R115_other_seats_still_pay_one_dollar():
    """R-115: only the Field's holder is exempt: P1 (no Field) pays $1 while P0 holds it."""
    s = _field_start(True)
    T.play(s, R.MOVE_CLEARING)
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    assert T.seat_of(T.snap(s), 1)["money"] == 4


def test_R115_field_holder_in_second_seat_pays_nothing():
    """R-115: P1 holds the Field and buys the fodder for $0."""
    s = T.start(2, True)
    B.give(s, 1, FIELD)
    T.play(s, R.MOVE_CLEARING)
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    assert T.seat_of(T.snap(s), 1)["money"] == 5


def test_R115_free_fodder_still_uses_up_the_path_supply():
    """R-115/R-041: the fodder still comes off the path; with the only fodder (2 players) taken,
    the other seat cannot enter Fodder."""
    s = _field_start(True)
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    assert T.snap(s)["path"]["fodder"] == 0
    assert _fodder_loc() not in T.move_locs(s)


def test_R115_value_three_slot_limit_is_unchanged_in_the_next_round():
    """R-115/R-043: with the value-3 slot occupied the Field holder cannot enter Fodder in round 2
    (free or not), although the location is refilled."""
    given = {"done": False}

    def give_field(ctx: R.Ctx) -> int | None:
        if not given["done"]:
            B.give(ctx.state, 0, FIELD)
            given["done"] = True
        return None

    pol = R.chain(
        give_field, R.Script({(1, 0): [H.MOVE_TO(_fodder_loc()), BUY_FODDER, R.MOVE_CLEARING]})
    )
    run = R.drive(
        T.params(3, True),
        seed=4,
        policy=pol,
        stop=lambda c: c.round == 2 and c.phase == "TR" and c.player == 0,
    )
    assert run.stopped
    sn = T.snap(run.state)
    assert T.seat_of(sn, 0)["fodder"]["slot3"] is True
    assert sn["path"]["fodder"] == R.quantities(3)["fodder_on_path"]
    assert _fodder_loc() not in T.move_locs(run.state)


def test_R115_no_second_fodder_in_the_same_round():
    """R-115/R-041: one fodder per seat per round: after the free purchase the seat has bought
    its fodder (`fodder_bought`) and the visit is over."""
    s = _field_start(True)
    T.play(s, H.MOVE_TO(_fodder_loc()), BUY_FODDER)
    assert T.seat_of(T.snap(s), 0)["fodder_bought"] is True
    assert BUY_FODDER not in s.legal_actions()


def test_R115_cost_value_comes_from_data_not_code():
    """R-115 / CLAUDE.md: the fodder cost is a data parameter of the Field in buildings.yaml."""
    b = {x["id"]: x for x in _buildings()}
    assert b[FIELD]["params"]["fodder_cost"] == 0


# =========================================================================== R-116 Office


def _take_any_task(state: Any) -> int:
    ids = [a for a in state.legal_actions() if R.TAKE_TASK0 <= a <= R.TAKE_TASK_END]
    assert ids, "no task card to take"
    return ids[0]


def _office_run(cards: int, office_seat: int | None) -> tuple[Any, list[float]]:
    """Play to the end with P0 holding `cards` task cards (1 = task_10; 2 adds a card taken in
    round 2) and the Office handed to `office_seat` at round 8's last Tasks turn. Returns the
    terminal state and the reference final dollars (which count no Office and no task reward)."""
    st = SM.chain_steps(True)
    if cards == 2:
        st.add(2, "TR", 0, H.MOVE_TO(R.loc(True, "tasks")), _take_any_task, R.MOVE_CLEARING)
    run = R.drive(
        {**V.params(2, True), "returns": "margin"},
        seed=V.SEED,
        policy=V.policy(st),
        stop=V._last_n4_of_round_8,  # pyright: ignore[reportPrivateUsage]
    )
    assert run.stopped
    s = run.state
    sn = V.snap(s)
    assert len(H.seats(sn)[0]["tasks"]) == cards and not H.seats(sn)[1]["tasks"]
    d = [float(V.final_dollars(x, V.requirement(sn, 2))["dollars"]) for x in H.seats(sn)]
    if office_seat is not None:
        B.give(s, office_seat, OFFICE)
    return _finish(s), d


def test_R116_baseline_unfinished_task_pays_nothing_without_the_office():
    """R-056/R-116 baseline: P0 holds one unfinished task and no Office: its final dollars equal
    the reference model."""
    s, d = _office_run(1, None)
    assert list(s.returns()) == pytest.approx(V.margin_returns(d))


def test_R116_one_dollar_for_one_unfinished_task_card():
    """R-116: the Office pays $1 for the one (uncompleted) task card P0 holds."""
    s, d = _office_run(1, 0)
    assert list(s.returns()) == pytest.approx(V.margin_returns([d[0] + 1, d[1]]))


def test_R116_one_dollar_per_card_with_two_cards():
    """R-116: two held cards, $2."""
    s, d = _office_run(2, 0)
    assert list(s.returns()) == pytest.approx(V.margin_returns([d[0] + 2, d[1]]))


def test_R116_seat_without_task_cards_gets_nothing():
    """R-116: P1 holds the Office but no task card: $0, the result equals the model."""
    s, d = _office_run(1, 1)
    assert list(s.returns()) == pytest.approx(V.margin_returns(d))


def test_R116_only_the_holders_cards_count():
    """R-116: P1 has the Office and P0 holds the card: P0's card gives P1 nothing and P0 nothing."""
    s, d = _office_run(2, 1)
    assert list(s.returns()) == pytest.approx(V.margin_returns(d))


def test_R116_amount_comes_from_data_not_code():
    """R-116 / CLAUDE.md: the per-card amount is a data parameter of the Office (buildings.yaml)."""
    b = {x["id"]: x for x in _buildings()}
    assert b[OFFICE]["params"]["money_per_task_card"] == 1
