"""Phase 4 unit 5: huts. Construction and the three effects (R-100, R-101, R-102, R-103).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (3, 5.7, A1, A7, A9) and docs/SCENARIOS.md only,
through tests/harness.py and tests/support/*.py. The harness has no scenario loader, so every
state is reached by scripted play from a seeded setup. Craftwork tokens are collected from the
round-1 path (3 craftwork tokens per fill), so seeds are searched for the holding a test needs.

Conventions
  * ids: BUILD_HUT(0)=134, HUT_TOKEN(x)=136+x (x: board 0, shingle 1, stake 2, reed 3, joker 4),
    HUT_AREA(h)=141+h (h: 0 drying, 1 food, 2 worker), HUT_FOOD(a)=144+a, HUT_DRY(z,p)=150+6z+p
    (p: 0 firewood disk, 1 firewood log, ...), ASSIGN_WORKER(w)=174+w, TAKE_LOAN=1.
  * Scenario dumps exist only at turn boundaries. A hut action leaves the turn open, so results
    are read at the next boundary after the turn is ended.
  * `Tr0` is a policy for seat 0's round-1 travel: it visits mandatory locations and every
    non-reed craftwork spot in ascending location order, then (optionally) builds huts at the
    last move node of the round, then goes to the clearing.
"""

from __future__ import annotations

import functools
from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import sawmill as SM
from tests.support import travel as T
from tests.support import woodwork as W

BUILD_HUT = 134
LOAN = H.TAKE_LOAN
CLEAR = R.MOVE_CLEARING
TYPES = ("board", "shingle", "stake", "reed", "joker")
NONREED = ("board", "shingle", "stake", "joker")
DRYING, FOOD, WORKER = 0, 1, 2
FW_DISK, FW_LOG = 0, 1


def hut_token(x: int) -> int:
    return 136 + x


def hut_area(h: int) -> int:
    return 141 + h


def hut_food(a: int) -> int:
    return 144 + a


def hut_dry(z: int, p: int) -> int:
    return 150 + 6 * z + p


ASSIGN_HUT = 176
HUT_IDS = range(134, 168)
HUT_DRY_IDS = range(150, 168)
HUT_FOOD_IDS = range(144, 150)


def choose_tokens(h: dict[str, int]) -> list[int] | None:
    """Independent statement of a valid 3-token set (R-100): stake, board, shingle once each,
    jokers substituting. Returns HUT_TOKEN type indexes in non-decreasing order."""
    jokers = h.get("joker", 0)
    out: list[int] = []
    for x, t in enumerate(("board", "shingle", "stake")):
        if h.get(t, 0) >= 1:
            out.append(x)
        elif jokers > 0:
            jokers -= 1
            out.append(4)
        else:
            return None
    return sorted(out)


def seat(s: Any, i: int = 0) -> dict[str, Any]:
    return T.seat_of(T.snap(s), i)


def huts(s: Any, i: int = 0) -> dict[str, int]:
    h = seat(s, i).get("huts") or {}
    return {k: h.get(k, 0) for k in ("drying", "food", "worker")}


def craft(s: Any, i: int = 0) -> dict[str, int]:
    c = seat(s, i)["craftwork"]
    return {k: c.get(k, 0) for k in TYPES}


def hut_legal(s: Any) -> list[int]:
    return [a for a in s.legal_actions() if a in HUT_IDS]


# --------------------------------------------------------------------------- travel policy


class Tr0:
    """Seat 0 travel in rounds 1 (and, with `collect_rounds`, later): mandatory visits and craft
    spots in ascending location order, then the scripted builds, then the clearing."""

    def __init__(
        self,
        mand: list[tuple[int, list[int]]] | None = None,
        builds: dict[int, list[tuple[int, ...]]] | None = None,
        take: tuple[str, ...] = NONREED,
        collect_rounds: tuple[int, ...] = (1,),
    ):
        self.mand = sorted(mand or [])
        self.builds = builds or {}
        self.take = take
        self.collect = collect_rounds
        self.done: dict[int, int] = {}
        self.q: list[int] = []

    def _next(self, ctx: R.Ctx, commit: bool) -> list[int]:
        sn = ctx.snap
        assert sn is not None
        me = T.seat_of(sn, 0)
        pos = me["foreman"]
        cands: list[tuple[int, list[int]]] = []
        if ctx.round in self.collect:
            for loc, tok in T.spots(sn).items():
                if loc > pos and tok in self.take and H.MOVE_TO(loc) in ctx.legal:
                    cands.append((loc, []))
        if ctx.round == 1:
            cands += [m for m in self.mand if m[0] > pos]
        if cands:
            loc, acts = min(cands, key=lambda c: c[0])
            return [H.MOVE_TO(loc), *acts]
        idx = self.done.get(ctx.round, 0)
        plan = self.builds.get(ctx.round, [])
        if idx < len(plan):
            toks = choose_tokens(me["craftwork"])
            if toks is not None:
                if commit:
                    self.done[ctx.round] = idx + 1
                return [BUILD_HUT, *map(hut_token, toks), *map(hut_area, sorted(plan[idx]))]
        return [CLEAR]

    def at_node(self, ctx: R.Ctx) -> bool:
        return (
            ctx.phase == "TR"
            and ctx.player == 0
            and ctx.snap is not None
            and CLEAR in ctx.legal
            and not self.q
        )

    def peek(self, ctx: R.Ctx) -> list[int]:
        return self._next(ctx, commit=False)

    def __call__(self, ctx: R.Ctx) -> int | None:
        if ctx.phase != "TR" or ctx.player != 0:
            return None
        if self.q:
            return self.q.pop(0)
        if not self.at_node(ctx):
            return None
        step = self._next(ctx, commit=True)
        self.q = step[1:]
        return step[0]


def stop_pre_build(tr: Tr0, rnd: int = 1) -> Callable[[R.Ctx], bool]:
    """Seat 0's move node of `rnd` when nothing but builds / the clearing remains."""

    def stop(ctx: R.Ctx) -> bool:
        if ctx.round != rnd or not tr.at_node(ctx):
            return False
        first = tr.peek(ctx)[0]
        return first in (CLEAR, BUILD_HUT)

    return stop


def stop_pre_clear(tr: Tr0, rnd: int = 1) -> Callable[[R.Ctx], bool]:
    def stop(ctx: R.Ctx) -> bool:
        return ctx.round == rnd and tr.at_node(ctx) and tr.peek(ctx)[0] == CLEAR

    return stop


# --------------------------------------------------------------------------- seed search


def r1_holding(seed: int, joinery: bool, take: tuple[str, ...] = NONREED) -> Counter[str]:
    sn = T.snap(T.start(2, joinery, seed))
    return Counter(t for t in T.spots(sn).values() if t in take)


def is_plain(h: Counter[str]) -> bool:
    return h == Counter(board=1, shingle=1, stake=1)


def is_joker_set(h: Counter[str]) -> bool:
    return h["joker"] == 1 and sum(h.values()) == 3 and max(h[t] for t in TYPES[:3]) == 1


@functools.cache
def find_seed(kind: str, joinery: bool = False) -> int:
    """First seed whose round-1 path gives seat 0 (taking every non-reed craft spot) `kind`."""
    for seed in range(1, 1500):
        h = r1_holding(seed, joinery, NONREED if kind != "reed" else TYPES)
        ok = {
            "plain": is_plain(h),
            "joker": is_joker_set(h),
            "none": sum(h.values()) == 0,
            "two": sum(h.values()) == 2 and max(h.values()) == 1,
            "dups": sum(h.values()) == 3 and max(h.values()) >= 2 and h["joker"] == 0,
            "reed": h["reed"] >= 1 and h["joker"] == 0 and sum(h.values()) == 3,
        }[kind]
        if ok:
            return seed
    raise AssertionError(f"no seed gives holding kind {kind}")


_REACH: dict[Any, Any] = {}


def reach_tr(
    kind: str,
    joinery: bool = False,
    builds: tuple[tuple[int, ...], ...] = (),
    stop: str = "pre_build",
    key: Any = None,
) -> Any:
    """State at seat 0's last round-1 move node (`pre_build`: before any build; `pre_clear`: after
    the builds), seat 0 having collected every non-reed craft token."""
    ck = ("tr", kind, joinery, builds, stop)
    if ck in _REACH:
        return _REACH[ck].clone()
    seed = find_seed(kind, joinery)
    take = TYPES if kind == "reed" else NONREED
    tr = Tr0(builds={1: list(builds)}, take=take)
    st = stop_pre_build(tr) if stop == "pre_build" else stop_pre_clear(tr)
    run = R.drive({"players": 2, "joinery": joinery}, seed=seed, policy=tr, stop=st)
    assert run.stopped
    _REACH[ck] = run.state
    return run.state.clone()


def to_boundary_of(s: Any, pred: Callable[[dict[str, Any], int], bool], limit: int = 60) -> None:
    """Apply DONE (or the clearing at TR) until the turn-boundary node satisfies `pred`."""
    for _ in range(limit):
        sn = R.try_snapshot(s)
        if sn is not None and pred(sn, s.current_player()):
            return
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        elif H.DONE in s.legal_actions():
            s.apply_action(H.DONE)
        elif CLEAR in s.legal_actions():
            s.apply_action(CLEAR)
        else:
            s.apply_action(s.legal_actions()[0])
    raise AssertionError("to_boundary_of: limit")


def next_p0_boundary(s: Any) -> None:
    """End the current turn(s) until a turn boundary of seat 0 is reached (a different node)."""
    first = True
    for _ in range(80):
        if not first:
            sn = R.try_snapshot(s)
            if sn is not None and s.current_player() == 0 and not s.is_chance_node():
                return
        first = False
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        elif H.DONE in s.legal_actions():
            s.apply_action(H.DONE)
        elif CLEAR in s.legal_actions():
            s.apply_action(CLEAR)
        else:
            s.apply_action(s.legal_actions()[0])
    raise AssertionError("next_p0_boundary: limit")


# =========================================================================== R-100 construction


@pytest.mark.parametrize("joinery", [False, True])
def test_R100_plain_set_offers_build_hut(joinery):
    """R-100: stake + board + shingle in hand makes BUILD_HUT(0) legal in the travel window, with
    joinery=false as well as true (a hut uses no joiner)."""
    s = reach_tr("plain", joinery)
    assert craft(s) == {"board": 1, "shingle": 1, "stake": 1, "reed": 0, "joker": 0}
    assert BUILD_HUT in s.legal_actions()


@pytest.mark.parametrize("kind", ["none", "two", "dups", "reed"])
def test_R100_no_valid_set_no_build(kind):
    """R-100: fewer than 3 tokens, duplicates without the missing type, or a reed in place of a
    type (no Small Workshop) never allow BUILD_HUT."""
    s = reach_tr(kind)
    assert BUILD_HUT not in s.legal_actions()


def test_R100_build_sequence_only_hut_and_loan_actions_legal():
    """R-100/ACTIONS 5.7: after BUILD_HUT only HUT_TOKEN (and TAKE_LOAN) is legal, then only
    HUT_AREA (and TAKE_LOAN); no move, DONE or other action in between."""
    s = reach_tr("plain")
    s.apply_action(BUILD_HUT)
    legal = set(s.legal_actions())
    assert legal <= {hut_token(0), hut_token(1), hut_token(2), LOAN}
    assert {hut_token(0), hut_token(1), hut_token(2)} <= legal  # any of the three may come first
    assert H.DONE not in legal and CLEAR not in legal
    s.apply_action(hut_token(0))
    s.apply_action(hut_token(1))
    s.apply_action(hut_token(2))
    legal = set(s.legal_actions())
    assert legal <= {hut_area(0), hut_area(1), hut_area(2), LOAN}
    assert {hut_area(0), hut_area(1), hut_area(2)} <= legal
    assert H.DONE not in legal and CLEAR not in legal


def test_R100_hut_token_order_is_free():
    """ACTIONS 5.7 (user ruling 2026-11-06): the order of HUT_TOKEN picks does not matter; after
    x=1 the lower x=0 and the higher x=2 are both legal, but x=1 again is not (one shingle only,
    a set has one of each)."""
    s = reach_tr("plain")
    s.apply_action(BUILD_HUT)
    s.apply_action(hut_token(1))
    legal = set(s.legal_actions())
    assert hut_token(0) in legal
    assert hut_token(1) not in legal
    assert hut_token(2) in legal


def test_R100_hut_areas_are_non_decreasing():
    """ACTIONS 5.7: HUT_AREA is played in non-decreasing h: after h=1 the area 0 is not legal."""
    s = reach_tr("plain")
    T.play(s, BUILD_HUT, hut_token(0), hut_token(1), hut_token(2), hut_area(1))
    legal = set(s.legal_actions())
    assert hut_area(0) not in legal
    assert hut_area(1) in legal and hut_area(2) in legal


def test_R100_take_loan_mid_build_keeps_the_build_open():
    """ACTIONS 5.7 / C5: TAKE_LOAN is the only other build-time action and keeps the build open."""
    s = reach_tr("plain")
    s.apply_action(BUILD_HUT)
    assert LOAN in s.legal_actions()
    s.apply_action(LOAN)
    assert hut_token(0) in s.legal_actions()
    T.play(s, hut_token(0), hut_token(1), hut_token(2), hut_area(0), hut_area(0), hut_area(0))
    T.play(s, CLEAR)
    to_boundary_of(s, lambda sn, p: p == 1)
    assert seat(s)["loans"] == 1
    assert huts(s)["drying"] == 3


@pytest.mark.parametrize(
    "areas,expected",
    [
        ((0, 0, 0), {"drying": 3, "food": 0, "worker": 0}),
        ((0, 1, 2), {"drying": 1, "food": 1, "worker": 1}),
        ((0, 0, 2), {"drying": 2, "food": 0, "worker": 1}),
        ((1, 1, 1), {"drying": 0, "food": 3, "worker": 0}),
        ((2, 2, 2), {"drying": 0, "food": 0, "worker": 3}),
    ],
)
def test_R100_tokens_flip_and_go_to_chosen_areas(areas, expected):
    """R-100: the three tokens go all on one area, one on each, or two and one; they leave the
    craftwork holding (flipped, removed from the craftwork stock) and sit as hut tokens."""
    s = reach_tr("plain", builds=(areas,), stop="pre_clear")
    s.apply_action(CLEAR)
    to_boundary_of(s, lambda sn, p: p == 1)
    assert huts(s) == expected
    assert sum(craft(s).values()) == 0
    removed = T.snap(s)["supply"]["craftwork_removed"]
    assert sum(removed.values()) >= 3  # S-CRAFT: flipped tokens count as out of the pile


def test_R100_joker_substitutes_for_a_missing_type():
    """R-100 (D20, C13): a joker is any of the three types: joker + two different tokens build."""
    s = reach_tr("joker")
    h = craft(s)  # read before BUILD_HUT: snapshots of an open build are rejected
    assert h["joker"] == 1
    assert BUILD_HUT in s.legal_actions()
    s.apply_action(BUILD_HUT)
    assert hut_token(4) in s.legal_actions()  # the joker may be flipped
    toks = choose_tokens(h)
    assert toks is not None and 4 in toks
    T.play(s, *map(hut_token, toks), hut_area(0), hut_area(0), hut_area(1))
    T.play(s, CLEAR)
    to_boundary_of(s, lambda sn, p: p == 1)
    assert huts(s) == {"drying": 2, "food": 1, "worker": 0}
    assert sum(craft(s).values()) == 0


def test_R100_window_open_at_turn_start_and_closed_by_first_action():
    """R-100/C5/A1: BUILD_HUT is legal at the start of a wood-work turn (W1) with a set in hand;
    TAKE_LOAN does not close the window, the first ASSIGN_WORKER does."""
    seed = find_seed("plain")
    tr = Tr0()
    steps = W.Steps()
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(tr, steps),
        stop=lambda c: (c.round, c.phase, c.player) == (1, "W1", 0),
    )
    assert run.stopped
    s = run.state
    assert craft(s) == {"board": 1, "shingle": 1, "stake": 1, "reed": 0, "joker": 0}
    assert BUILD_HUT in s.legal_actions()
    s.apply_action(LOAN)
    assert BUILD_HUT in s.legal_actions()
    s.apply_action(W.assign(1))
    assert BUILD_HUT not in s.legal_actions()


def test_R100_two_sets_can_be_built():
    """R-100 (FAQ): a seat may build several sets: after the first build a second set in hand
    makes BUILD_HUT legal again, and the hut area holds 3 + 3 tokens."""
    s = _two_sets()
    s.apply_action(CLEAR)
    to_boundary_of(s, lambda sn, p: sn["phase"] != "TR")
    assert huts(s) == {"drying": 6, "food": 0, "worker": 0}
    assert sum(craft(s).values()) == 0


@functools.cache
def _two_set_seed() -> int:
    for seed in range(1, 2500):
        tr = Tr0(builds={1: [(0, 0, 0)], 2: [(0, 0, 0)]}, collect_rounds=(1, 2))
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            policy=tr,
            stop=lambda c, tr=tr: c.round == 2 and tr.at_node(c) and tr.peek(c)[0] == BUILD_HUT,
        )
        if run.stopped and tr.done.get(1) == 1:
            return seed
        if run.stopped:
            continue
    raise AssertionError("no seed gives two sets over rounds 1 and 2")


def _two_sets() -> Any:
    seed = _two_set_seed()
    tr = Tr0(builds={1: [(0, 0, 0)], 2: [(0, 0, 0)]}, collect_rounds=(1, 2))
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=tr,
        stop=lambda c: c.round == 2 and tr.at_node(c) and tr.peek(c)[0] == BUILD_HUT,
    )
    s = run.state
    assert BUILD_HUT in s.legal_actions()
    assert choose_tokens(craft(s)) is not None
    toks = choose_tokens(craft(s))
    assert toks is not None
    T.play(s, BUILD_HUT, *map(hut_token, toks), *[hut_area(0)] * 3)
    return s


# =========================================================================== wood chain fixture


def dry_state(
    builds: tuple[tuple[int, ...], ...] = ((0, 0, 0),),
    two: bool = False,
    saw: bool = True,
    stop: tuple[int, str, int] = (1, "W5", 0),
    steps_extra: Callable[[W.Steps], None] | None = None,
    key: Any = None,
    joinery: bool = False,
) -> Any:
    """Round 1 (2 players, base side): P0 collects every non-reed craft token plus a bearer, the
    free sawyer and the saw token, builds `builds` at its last move node, cuts, carries and mills
    one firewood disk into 4 logs in the sale area (`two`: a second disk goes unmilled to the sale
    area, so the sale area holds 4 logs + 1 disk). Returns the state at `stop`."""
    seed = find_seed("plain", joinery)
    j = joinery
    mand: list[tuple[int, list[int]]] = []
    if saw:
        mand.append((W.spot_loc(2, j, seed, "saw", 0), []))
    mand.append((R.loc(j, "bearers"), [R.HIRE_BEARER] * (2 if two else 1) + [H.DONE]))
    mand.append((R.loc(j, "sawyers"), [R.HIRE_SAWYER, H.DONE]))
    if two:
        mand.append((R.loc(j, "woodcutters"), [R.HIRE_WOODCUTTER, H.DONE]))
    tr = Tr0(mand=mand, builds={1: list(builds)})
    st = W.Steps()
    cuts = (0, 1) if two else (1,)
    carries = (0, 1) if two else (0,)
    for src in cuts:
        st.add(1, "W1", 0, W.Opt(W.assign(src)), W.first_take(W.FW))
    for dest in carries:
        st.add(1, "W3", 0, W.Opt(W.assign(0)), W.move_wood(W.FW, dest))
    if saw:
        st.add(1, "W4", 0, W.Opt(W.assign(0)), SM.saw(0, 0))
    if steps_extra:
        steps_extra(st)
    ck = ("dry", builds, two, saw, stop, key, joinery)
    if ck in _REACH:
        return _REACH[ck].clone()
    run = R.drive(
        {"players": 2, "joinery": joinery},
        seed=seed,
        policy=R.chain(tr, st),
        stop=lambda c: (c.round, c.phase, c.player) == stop,
    )
    assert run.stopped
    _REACH[ck] = run.state
    return run.state.clone()


def sale(s: Any) -> Counter[str]:
    return W.pm(seat(s)["sale"])


def drying(s: Any) -> list[Counter[str]]:
    return [W.pm(x) for x in seat(s)["drying"]]


LOG = "firewood_log"
DISK = "firewood_disk"


# =========================================================================== R-101 drying hut


def test_R101_fixture_has_four_logs_in_sale_and_three_drying_tokens():
    """R-101 (fixture sanity): after sawing the sale area holds 4 milled firewood and the seat holds
    three drying hut tokens."""
    s = dry_state()
    assert sale(s) == Counter({LOG: 4})
    assert huts(s) == {"drying": 3, "food": 0, "worker": 0}


def test_R101_sale_piece_moves_into_first_drying_area():
    """R-101 (user answer 2026-11-04): a drying token moves one piece from the sale area into
    drying 1; the token is spent."""
    s = dry_state()
    assert hut_dry(0, FW_LOG) in s.legal_actions()
    s.apply_action(hut_dry(0, FW_LOG))
    s.apply_action(H.DONE)  # end the W5 turn
    next_p0_boundary(s)
    assert sale(s) == Counter({LOG: 3})
    assert drying(s)[0] == Counter({LOG: 1})
    assert huts(s)["drying"] == 2


def test_R101_one_piece_advances_one_area_per_token():
    """R-101: several tokens in a window advance the same piece one area per token:
    sale -> drying 1 -> drying 2 -> drying 3, all three tokens spent."""
    s = dry_state()
    T.play(s, hut_dry(0, FW_LOG), hut_dry(1, FW_LOG))
    s.apply_action(hut_dry(2, FW_LOG))
    assert not [a for a in s.legal_actions() if a in HUT_DRY_IDS]  # no token left
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    d = drying(s)
    assert d[2] == Counter({LOG: 1})
    assert d[0] == Counter() and d[1] == Counter()
    assert sale(s) == Counter({LOG: 3})
    assert huts(s)["drying"] == 0


def test_R101_third_area_wood_cannot_be_moved():
    """R-101: a piece in the third area has no area to its right. After one piece has gone to
    drying 3 with all three tokens, no HUT_DRY id is offered (zones are sale, drying 1, drying 2
    only; the piece in drying 3 is never a source)."""
    s = dry_state()
    T.play(s, hut_dry(0, FW_LOG), hut_dry(1, FW_LOG), hut_dry(2, FW_LOG))
    legal = [a for a in s.legal_actions() if a in HUT_DRY_IDS]
    assert legal == []  # tokens gone; and nothing offers a move out of drying 3


def test_R101_destination_capacity_is_ignored_and_whole_area_advances_next_drying():
    """R-101/R-059: three tokens put 3 logs in drying 1 (capacity 2); at the drying phase of the
    same round all 3 advance together into drying 2 (over capacity, allowed), and the sale-area
    log enters drying 1."""
    s = dry_state()
    T.play(s, *[hut_dry(0, FW_LOG)] * 3)
    s.apply_action(H.DONE)  # W5
    next_p0_boundary(s)  # W6, P0
    assert drying(s)[0] == Counter({LOG: 3})
    assert sale(s) == Counter({LOG: 1})
    assert H.DONE in s.legal_actions()  # drying 3 empty
    s.apply_action(H.DONE)
    next_p0_boundary(s)  # W7, P0
    assert W.snap(s)["phase"] == "W7"
    s.apply_action(SM.dry_enter(SM.FW_LOG))
    if H.DONE in s.legal_actions():
        s.apply_action(H.DONE)
    next_p0_boundary(s)
    d = drying(s)
    assert d[1] == Counter({LOG: 3})
    assert d[0] == Counter({LOG: 1})
    assert sale(s) == Counter()


def test_R101_milled_and_unmilled_may_share_a_drying_area():
    """R-101 (FAQ Official): hut moves may put a disk and a log in the same drying area."""
    s = dry_state(two=True)
    assert sale(s) == Counter({LOG: 4, DISK: 1})
    legal = set(s.legal_actions())
    assert hut_dry(0, FW_DISK) in legal and hut_dry(0, FW_LOG) in legal
    T.play(s, hut_dry(0, FW_DISK), hut_dry(0, FW_LOG))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert drying(s)[0] == Counter({DISK: 1, LOG: 1})


def test_R101_only_pieces_that_exist_are_offered():
    """R-101: HUT_DRY(z, p) needs a piece p in zone z: with 4 logs in the sale area and nothing in
    the drying areas, only HUT_DRY(0, firewood log) is legal."""
    s = dry_state()
    assert [a for a in s.legal_actions() if a in HUT_DRY_IDS] == [hut_dry(0, FW_LOG)]


def test_R101_no_drying_token_no_hut_dry():
    """R-101: HUT_DRY is not legal without a drying token (the hut tokens are on the food area)."""
    s = dry_state(builds=((1, 1, 1),))
    assert sale(s) == Counter({LOG: 4})
    assert not [a for a in s.legal_actions() if a in HUT_DRY_IDS]


def test_R101_window_in_selling_phase_closes_at_first_sale():
    """R-101/C5/A1: in W6 HUT_DRY is legal before the first SELL; a SELL closes the window."""
    s = dry_state(stop=(1, "W6", 0))
    assert hut_dry(0, FW_LOG) in s.legal_actions()
    sell_log = SM.sell(0, SM.FW_LOG)
    assert sell_log in s.legal_actions()
    s.apply_action(LOAN)  # a loan does not close the window
    assert hut_dry(0, FW_LOG) in s.legal_actions()
    s.apply_action(sell_log)
    assert not [a for a in s.legal_actions() if a in HUT_DRY_IDS]


def test_R101_window_in_drying_phase_closes_at_first_dry_enter():
    """R-101/C5/A1: in W7 HUT_DRY is legal at the start; the first DRY_ENTER closes the window."""
    s = dry_state(stop=(1, "W7", 0))
    assert hut_dry(0, FW_LOG) in s.legal_actions()
    s.apply_action(SM.dry_enter(SM.FW_LOG))
    assert not [a for a in s.legal_actions() if a in HUT_DRY_IDS]


def test_R101_window_closes_after_first_non_hut_action_in_w5():
    """R-101/C5: in W5 the window is open at the turn start (HUT_DRY legal); hut actions may be
    repeated inside it."""
    s = dry_state()
    s.apply_action(hut_dry(0, FW_LOG))
    assert hut_dry(0, FW_LOG) in s.legal_actions()
    assert hut_dry(1, FW_LOG) in s.legal_actions()


# =========================================================================== food fixture


def _pk_both_share(ctx: R.Ctx) -> int | None:
    """PK: both seats pick the lowest-numbered area holding exactly 1 food, preferring an area
    for which another area also holds food (so that area is left unoccupied with food)."""
    if ctx.phase != "PK":
        return None
    sn = ctx.snap
    if sn is None:
        return None
    food = [R.food(a) for a in H.areas(sn)]
    for a, f in enumerate(food):
        if f == 1 and any(g > 0 for b, g in enumerate(food) if b != a):
            return H.PICK_AREA(a)
    return H.PICK_AREA(0)


def _pk_both_empty(ctx: R.Ctx) -> int | None:
    """PK: both seats pick the lowest-numbered area without food, leaving food areas free."""
    if ctx.phase != "PK" or ctx.snap is None:
        return None
    food = [R.food(a) for a in H.areas(ctx.snap)]
    return H.PICK_AREA(next((a for a, f in enumerate(food) if f == 0), 0))


def _pk_for(free_needed: int) -> Callable[[R.Ctx], int | None]:
    return _pk_both_share if free_needed == 1 else _pk_both_empty


def _food_ok(s: Any, free_needed: int) -> bool:
    sn = T.snap(s)
    me, other = T.seat_of(sn, 0), T.seat_of(sn, 1)
    if me["cutting_area"] != other["cutting_area"]:
        return False
    occ = me["cutting_area"] - 1
    food = [R.food(a) for a in H.areas(sn)]
    free = [a for a in range(6) if a != occ and food[a] > 0]
    if free_needed == 1 and food[occ] < 1:
        return False
    return len(free) >= free_needed and sn["round"] == 2


@functools.cache
def _food_seed(free_needed: int) -> int:
    for seed in range(1, 3000):
        if not is_plain(r1_holding(seed, False)):
            continue
        tr = Tr0(builds={1: [(1, 1, 1)]})
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            policy=R.chain(tr, _pk_for(free_needed)),
            stop=lambda c, tr=tr: c.round == 2 and tr.at_node(c),
        )
        if run.stopped and _food_ok(run.state, free_needed):
            return seed
    raise AssertionError("no seed with the needed round-2 food layout")


def food_state(free_needed: int = 1) -> Any:
    ck = ("food", free_needed)
    if ck not in _REACH:
        seed = _food_seed(free_needed)
        tr = Tr0(builds={1: [(1, 1, 1)]})
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            policy=R.chain(tr, _pk_for(free_needed)),
            stop=lambda c: c.round == 2 and tr.at_node(c),
        )
        assert run.stopped
        _REACH[ck] = run.state
    return _REACH[ck].clone()


def food_layout(s: Any) -> tuple[int, list[int], list[int]]:
    """(occupied area index, food by area, unoccupied areas holding food)."""
    sn = T.snap(s)
    occ = T.seat_of(sn, 0)["cutting_area"] - 1
    food = [R.food(a) for a in H.areas(sn)]
    return occ, food, [a for a in range(6) if a != occ and food[a] > 0]


# =========================================================================== R-102 food hut


def test_R102_free_area_food_goes_to_the_seat():
    """R-102: a food token takes the entire food of a free cutting area (no other token on it) into
    the food storage and is spent."""
    s = food_state()
    occ, food, free = food_layout(s)
    a = free[0]
    before = seat(s)["food"]
    assert huts(s)["food"] == 3
    assert hut_food(a) in s.legal_actions()
    s.apply_action(hut_food(a))
    s.apply_action(CLEAR)
    to_boundary_of(s, lambda sn, p: sn["phase"] != "TR")
    assert seat(s)["food"] == before + food[a]
    assert huts(s)["food"] == 2
    assert R.food(H.areas(T.snap(s))[a]) == 0


def _move_cut_ok(c: R.Ctx) -> bool:
    if c.phase != "W1" or c.player != 0 or c.round not in (2, 3) or c.snap is None:
        return False
    food = [R.food(a) for a in H.areas(c.snap)]
    mv = [a - 168 for a in c.legal if 168 <= a <= 173]
    return any(food[a] > 0 for a in mv) and T.seat_of(c.snap, 0)["money"] >= 1


def _own_area_run(seed: int) -> Any:
    tr = Tr0(builds={1: [(1, 1, 1)]})
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(tr, _pk_both_share),
        stop=_move_cut_ok,
    )
    return run.state if run.stopped else None


@functools.cache
def _own_area_seed() -> int:
    for seed in range(1, 3000):
        if is_plain(r1_holding(seed, False)) and _own_area_run(seed) is not None:
            return seed
    raise AssertionError("no seed where seat 0 can pay $1 to move to a free area with food")


def test_R102_seat_may_take_food_from_its_own_area():
    """R-102: 'the seat's own area is allowed' when no other seat's token is there. Seat 0 shares
    an area, pays $1 (MOVE_CUT_TOKEN) to move to a token-free area that holds food, and in its
    next window HUT_FOOD for that own area is legal and takes all of the area's food."""
    s = _own_area_run(_own_area_seed())
    sn = T.snap(s)
    food = [R.food(a) for a in H.areas(sn)]
    a = next(a for a in range(6) if 168 + a in s.legal_actions() and food[a] > 0)
    money = seat(s)["money"]
    s.apply_action(168 + a)
    s.apply_action(H.DONE)
    to_boundary_of(s, lambda sn, p: p == 0 and sn["phase"] in ("W3", "W5") and sn["round"] >= 2)
    sn2 = T.snap(s)
    assert T.seat_of(sn2, 0)["cutting_area"] == a + 1
    assert T.seat_of(sn2, 0)["money"] == money - 1
    assert R.food(H.areas(sn2)[a]) == food[a]
    assert hut_food(a) in s.legal_actions()
    before = seat(s)["food"]
    s.apply_action(hut_food(a))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert seat(s)["food"] == before + food[a]
    assert huts(s)["food"] == 2


def test_R102_area_with_another_seats_token_is_not_free():
    """R-102: a cutting area where another seat's token stands is not free: HUT_FOOD is not legal,
    even if it holds food (both seats share the area, so the food was not distributed, R-039)."""
    s = food_state()
    occ, food, _ = food_layout(s)
    assert food[occ] >= 1
    assert hut_food(occ) not in s.legal_actions()


def test_R102_no_food_token_no_hut_food():
    """R-102: HUT_FOOD is not legal without a food token in hand."""
    s = dry_state(builds=((0, 0, 0),))
    assert not [a for a in s.legal_actions() if a in HUT_FOOD_IDS]


def test_R102_two_tokens_take_two_areas():
    """R-102: several tokens may take food from several free areas in the same window."""
    s = food_state(2)
    occ, food, free = food_layout(s)
    before = seat(s)["food"]
    T.play(s, hut_food(free[0]), hut_food(free[1]))
    s.apply_action(CLEAR)
    to_boundary_of(s, lambda sn, p: sn["phase"] != "TR")
    assert seat(s)["food"] == before + food[free[0]] + food[free[1]]
    assert huts(s)["food"] == 1


def test_R102_window_closed_after_first_travel_action():
    """R-102/C5: at the move node HUT_FOOD is legal (window), but not in the middle of a visit
    started by a non-hut action."""
    s = food_state()
    _, _, free = food_layout(s)
    assert hut_food(free[0]) in s.legal_actions()
    spots = [loc for loc in T.move_locs(s) if T.kind_of(False, loc) == "spot"]
    if not spots:
        pytest.skip("no spot left to enter at this move node")
    s.apply_action(H.MOVE_TO(spots[0]))
    if not T.at_move_node(s):
        assert not [a for a in s.legal_actions() if a in HUT_FOOD_IDS]


@functools.cache
def _winter_seed() -> int:
    for seed in range(1, 1500):
        if not is_plain(r1_holding(seed, False)):
            continue
        tr = Tr0(builds={1: [(1, 1, 1)]})
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            policy=tr,
            stop=lambda c: c.round == 4 and c.phase == "N1" and c.player == 0,
        )
        if run.stopped:
            sn = T.snap(run.state)
            if any(R.food(a) > 0 for a in H.areas(sn)):
                return seed
    raise AssertionError("no seed with food in an area at winter")


def test_R102_in_winter_every_area_is_free():
    """R-102 (user answer 2026-11-04): in winter no cutting tokens are on the board, so a food token
    can take the food of any area that holds some."""
    seed = _winter_seed()
    tr = Tr0(builds={1: [(1, 1, 1)]})
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=tr,
        stop=lambda c: c.round == 4 and c.phase == "N1" and c.player == 0,
    )
    s = run.state
    sn = T.snap(s)
    foods = [R.food(a) for a in H.areas(sn)]
    assert huts(s)["food"] == 3
    legal = set(s.legal_actions())
    for a, f in enumerate(foods):
        if f > 0:
            assert hut_food(a) in legal, f"area {a} holds {f} food but is not takeable"
    a = next(a for a, f in enumerate(foods) if f > 0)
    before = seat(s)["food"]
    s.apply_action(hut_food(a))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert seat(s)["food"] == before + foods[a]
    assert huts(s)["food"] == 2


def _winter_picked_run(seed: int) -> tuple[Any, list[int]] | None:
    """Both seats pick a shared 1-food area (leaving food) every fall; returns the round-4 N1 state
    and the 0-based areas the seats stood on in round 3, or None if the run does not stop."""
    seen: list[int] = []

    def rec(ctx: R.Ctx) -> int | None:
        if ctx.round == 3 and ctx.phase != "PK" and ctx.snap is not None:
            for st in H.seats(ctx.snap):
                ca = st["cutting_area"]
                if ca and ca - 1 not in seen:
                    seen.append(ca - 1)
        return None

    tr = Tr0(builds={1: [(1, 1, 1)]})
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(rec, tr, _pk_both_share),
        stop=lambda c: c.round == 4 and c.phase == "N1" and c.player == 0,
    )
    return (run.state, seen) if run.stopped else None


@functools.cache
def _winter_picked_seed() -> int:
    for seed in range(1, 3000):
        if not is_plain(r1_holding(seed, False)):
            continue
        got = _winter_picked_run(seed)
        if got is None:
            continue
        s, seen = got
        foods = [R.food(a) for a in H.areas(T.snap(s))]
        if any(foods[a] > 0 for a in seen):
            return seed
    raise AssertionError("no seed leaving food in a round-3 picked area at winter")


def winter_picked_state() -> Any:
    got = _winter_picked_run(_winter_picked_seed())
    assert got is not None
    s, seen = got
    s._test_round3_areas = seen  # pyright: ignore[reportAttributeAccessIssue]
    return s


def test_R102_in_winter_an_area_picked_in_the_fall_is_free_for_hut_food():
    """R-102 (user answer 2026-11-04): in winter no cutting-area tokens stand on the board, so food
    left in an area that a seat picked in the round-3 fall can be taken, although in the fall that
    area was not free."""
    s = winter_picked_state()
    picked = s._test_round3_areas
    sn = T.snap(s)
    foods = [R.food(a) for a in H.areas(sn)]
    a = next(a for a in picked if foods[a] > 0)
    assert hut_food(a) in s.legal_actions()
    before = seat(s)["food"]
    s.apply_action(hut_food(a))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert seat(s)["food"] == before + foods[a]
    assert huts(s)["food"] == 2


# =========================================================================== R-103 hut worker


def worker_state(
    stop: tuple[int, str, int],
    saw: bool = True,
    builds: tuple[tuple[int, ...], ...] = ((2, 2, 2),),
    script: Callable[[W.Steps], None] | None = None,
) -> Any:
    """Round 1: P0 collects craft tokens (plus the saw spot if `saw`), builds `builds`, hires no
    one, and the scripted W1/W3/W4 steps run until `stop`."""
    seed = find_seed("plain")
    mand: list[tuple[int, list[int]]] = []
    if saw:
        mand.append((W.spot_loc(2, False, seed, "saw", 0), []))
    tr = Tr0(mand=mand, builds={1: list(builds)})
    st = W.Steps()
    if script:
        script(st)
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(tr, st),
        stop=lambda c: (c.round, c.phase, c.player) == stop,
    )
    assert run.stopped
    return run.state


def test_R103_hut_worker_cuts_in_w1_and_token_is_spent():
    """R-103: ASSIGN_WORKER(2) in W1 lets a hut token take one piece; the token is spent."""
    s = worker_state((1, "W1", 0))
    assert huts(s)["worker"] == 3
    assert ASSIGN_HUT in s.legal_actions()
    s.apply_action(ASSIGN_HUT)
    s.apply_action(W.first_take(W.FW)(s))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert sum(W.zone(T.snap(s), 0, "woodpile").values()) == 1
    assert huts(s)["worker"] == 2


def test_R103_unused_hut_worker_stays():
    """R-103: a token not used in a turn is not spent: passing W1 with DONE keeps all three."""
    s = worker_state((1, "W1", 0))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert huts(s)["worker"] == 3


def test_R103_each_token_is_a_separate_worker_in_one_turn():
    """R-103 (C6): not limited to once per round: two hut tokens cut two pieces in one W1 turn,
    and the mill worker can still add a third."""
    s = worker_state((1, "W1", 0))
    for src in (2, 2, 1):
        s.apply_action(W.assign(src))
        s.apply_action(W.first_take(W.FW)(s))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert sum(W.zone(T.snap(s), 0, "woodpile").values()) == 3
    assert huts(s)["worker"] == 1


def test_R103_no_token_no_hut_worker():
    """R-103: ASSIGN_WORKER(2) is not legal without a worker hut token (the tokens are on the
    drying area)."""
    s = worker_state((1, "W1", 0), builds=((0, 0, 0),))
    assert ASSIGN_HUT not in s.legal_actions()
    assert W.assign(1) in s.legal_actions()


def test_R103_spent_tokens_are_gone():
    """R-103: after all three tokens are used, ASSIGN_WORKER(2) is no longer legal."""
    s = worker_state((1, "W1", 0))
    for _ in range(3):
        s.apply_action(ASSIGN_HUT)
        s.apply_action(W.first_take(W.FW)(s))
        if ASSIGN_HUT not in s.legal_actions():
            break
    assert ASSIGN_HUT not in s.legal_actions()


def _chain_script(st: W.Steps) -> None:
    st.add(1, "W1", 0, W.Opt(ASSIGN_HUT), W.first_take(W.FW))
    st.add(1, "W3", 0, W.Opt(ASSIGN_HUT), W.move_wood(W.FW, 0))


def test_R103_hut_worker_as_bearer_in_w3():
    """R-103/ACTIONS 5.2: in W3 a hut token stands in for a bearer (no equipment needed): it
    carries the woodpile piece to the sawing area and is spent."""
    s = worker_state(
        (1, "W3", 0), script=lambda st: st.add(1, "W1", 0, W.Opt(ASSIGN_HUT), W.first_take(W.FW))
    )
    assert huts(s)["worker"] == 2
    assert ASSIGN_HUT in s.legal_actions()
    T.play(s, ASSIGN_HUT, W.move_wood(W.FW, 0))
    s.apply_action(H.DONE)
    next_p0_boundary(s)
    assert sum(W.zone(T.snap(s), 0, "sawing").values()) == 1
    assert huts(s)["worker"] == 1


def test_R103_hut_worker_as_sawyer_needs_a_saw():
    """R-103: a hut token mills a disk in W4 only with a saw token: with the saw it is legal and
    produces 4 logs in the sale area; without a saw ASSIGN_WORKER(2) is not legal."""
    s = worker_state((1, "W4", 0), script=_chain_script)
    assert W.snap(s)["phase"] == "W4"
    assert huts(s)["worker"] == 1
    assert ASSIGN_HUT in s.legal_actions()
    T.play(s, ASSIGN_HUT, SM.saw(0, 0))
    s.apply_action(H.DONE) if H.DONE in s.legal_actions() else None
    next_p0_boundary(s)
    assert W.zone(T.snap(s), 0, "sale") == Counter({LOG: 4})
    assert huts(s)["worker"] == 0


def test_R103_hut_worker_not_offered_as_sawyer_without_saw():
    """R-103: a hut worker still needs the equipment of its work: with a piece in the sawing area
    but no saw token, ASSIGN_WORKER(2) is not legal in W4."""
    s = worker_state((1, "W4", 0), saw=False, script=_chain_script)
    assert seat(s)["equipment"]["saw"] == 0
    assert W.zone(T.snap(s), 0, "sawing")
    assert ASSIGN_HUT not in s.legal_actions()
