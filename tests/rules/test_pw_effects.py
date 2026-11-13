"""Phase 4 unit 4: planned-work effects Trade, Craftwork, Sawing, Food Supply, Heating Supply
(R-090..R-094; R-089 executing/losing; R-054 milling, R-105 selling, R-053 raft log driving as the
base behaviour each effect is measured against).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py and tests/support/{rounds,travel,woodwork}.py. There is no scenario loader, so
every state is reached by scripted play. `reach()` plays a 2-player base-side game with chosen
PW_DRAW cards (the laid-out cards), a lazily resolved travel script per (round, seat) (`Tr`:
locations are read from that round's path, so seeds do not matter) and per-phase `W.Steps`; it
searches seeds until the check passes (the path tokens are random). Test bodies then play the
interesting part by hand and read results from snapshots.

Conventions
  * PW card index c = order in data/components/planned_work.yaml; PLAN_WORK(c, pair) = 67 + 3c +
    pair - 1; PW_DRAW(c) = 47 + c. A plan made in round 1 with pair 1 targets round 2 (R-088).
  * SELL_EQUIP(e) = 130 + e with e 0 raft, 1 sledge, 2 wagon (ACTIONS 1.5, 5). SELL_SET and SAW ids
    as in ACTIONS 5.3 and 5.6. RIVER_MOVE(k) = 201 + k.
  * Base side only (Market is location 19, Planned work 8, Bearers 4, Woodcutters 10, Sawyers 16).
  * The planning round is always round 1, so "the round it is planned" is round 1 and the target
    round is round 2 (pair 1); the round after the target is round 3.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import woodwork as W

PW_LOC = 8
MARKET = 19
PW_DRAW0 = 47
PLAN0 = 67
SELL_EQUIP0 = 130
SELL_SET0 = 97
SELL_JOKERS = 129
RIVER0 = 201
SAW0 = 214
SAW_IDS = range(214, 227)
TYPES = ("board", "shingle", "stake", "reed")

_DATA = R._yaml("planned_work.yaml")["planned_work"]  # pyright: ignore[reportPrivateUsage]
IDS: list[str] = [c["id"] for c in _DATA]
TRADE, CRAFT, SAW, FOODS, HEAT = (
    IDS.index(i)
    for i in ("pw_trade", "pw_craftwork", "pw_sawing", "pw_food_supply", "pw_heating_supply")
)
SEASONS = {c["id"]: c["seasons"] for c in _DATA}
assert all("summer" in SEASONS[IDS[c]] for c in (TRADE, CRAFT, SAW, FOODS, HEAT))

LAYOUT_A = [TRADE, CRAFT, SAW, HEAT]  # 2 players: players + 2 = 4 cards
LAYOUT_F = [FOODS, TRADE, CRAFT, SAW]


def PLAN(c: int, pair: int) -> int:
    return PLAN0 + 3 * c + (pair - 1)


def SELL_EQUIP(e: int) -> int:
    return SELL_EQUIP0 + e


_SET_IDX = {(2, 0): 0, (2, 1): 1, (3, 0): 2, (3, 1): 3, (3, 2): 4, (4, 0): 5, (4, 1): 6, (4, 2): 7}


def sell_set(x: int, s: int, j: int = 0) -> int:
    return SELL_SET0 + 8 * x + _SET_IDX[(s, j)]


def saw_id(k: int, n: int) -> int:
    off = n if k == 0 else (7 + n if k == 1 else 11 + n)
    return SAW0 + off


class NoSeed(Exception):
    """This seed's path cannot give the scripted holdings; try the next one."""


# --------------------------------------------------------------------------- scripted play


def build(cards: list[int], seed: int, n: int = 2) -> Any:
    """Setup with the PW_DRAW outcomes `cards` in order; stops at the first travel node."""
    game: Any = H.as_game({"players": n, "joinery": False})  # pyright: ignore[reportUnknownMemberType]
    s: Any = game.new_initial_state()
    rng = random.Random(seed)
    want = [PW_DRAW0 + c for c in cards]
    while not s.is_terminal():
        if s.is_chance_node():
            outs = [a for a, p in s.chance_outcomes() if p > 0]
            if want and all(PW_DRAW0 <= a < PW_DRAW0 + 10 for a in outs):
                a = want.pop(0)
                assert a in outs
                s.apply_action(a)
            else:
                s.apply_action(H.sample_chance(s, rng))  # pyright: ignore[reportUnknownMemberType]
            continue
        sn = R.try_snapshot(s)
        if sn is None or sn["phase"] not in ("SP", "PK"):
            break
        s.apply_action(s.legal_actions()[0])
    assert not want and H.phase_of(s) == "TR"  # pyright: ignore[reportUnknownMemberType]
    return s


Want = tuple[Any, ...]
_HIRE = {"bearers": R.HIRE_BEARER, "woodcutters": R.HIRE_WOODCUTTER, "sawyers": R.HIRE_SAWYER}


def _resolve(sn: dict[str, Any], seat: int, wants: list[Want], clear: bool) -> list[int]:
    me = T.seat_of(sn, seat)
    toks = T.spots(sn)
    visits: list[tuple[int, list[int]]] = []
    for w in wants:
        kind = w[0]
        if kind == "plan":
            visits.append((PW_LOC, [PLAN(w[1], w[2])]))
        elif kind == "hire":
            name, count = w[1], w[2]
            if name == "woodcutters" and T.own_wood(sn, seat) - me["hired"]["woodcutters"] < count:
                raise NoSeed("not enough wood in the cutting area")
            visits.append((R.loc(False, name), [_HIRE[name]] * count + [H.DONE]))
        elif kind == "spots":
            locs = sorted(
                loc for loc, t in toks.items() if t in w[1] and me["foreman"] < loc < MARKET
            )[: w[2]]
            visits += [(loc, []) for loc in locs]
        elif kind == "craft_to":  # (total tokens of one real type, jokers among them)
            total, jokers = w[1], w[2]
            have = me["craftwork"]
            avail: dict[str, list[int]] = {t: [] for t in (*TYPES, "joker")}
            for loc, t in sorted(toks.items()):
                if t in avail and me["foreman"] < loc < MARKET:
                    avail[str(t)].append(loc)
            order = sorted(TYPES, key=lambda t: -(have[t] + len(avail[t])))
            t = order[0]
            need_real = max(0, total - jokers - have[t])
            need_j = max(0, jokers - have["joker"])
            visits += [(loc, []) for loc in avail[t][:need_real]]
            visits += [(loc, []) for loc in avail["joker"][:need_j]]
        else:  # pragma: no cover
            raise AssertionError(kind)
    visits.sort(key=lambda v: v[0])
    out: list[int] = []
    for loc, acts in visits:
        out += [H.MOVE_TO(loc), *acts]
    if clear:
        out.append(R.MOVE_CLEARING)
    return out


class Tr:
    """Travel scripts per (round, seat), resolved at the seat's first travel node of the round.
    A seat with no entry goes to the clearing; with clear=False the queue ends without it, and
    `exhausted` is true at the next travel boundary (where tests stop)."""

    def __init__(self, wants: dict[tuple[int, int], list[Want]], clear: bool = True):
        self.wants = wants
        self.clear = clear
        self.q: dict[tuple[int, int], list[int]] = {}

    def __call__(self, ctx: R.Ctx) -> int | None:
        key = (ctx.round, ctx.player)
        if ctx.phase != "TR" or key not in self.wants:
            return None
        if key not in self.q:
            assert ctx.snap is not None
            self.q[key] = _resolve(ctx.snap, ctx.player, self.wants[key], self.clear)
            if not self.q[key] and not self.clear and self.wants[key]:
                raise NoSeed("script needs no moves in this round")  # stop would be missed
        return self.q[key].pop(0) if self.q[key] else None

    def exhausted(self, key: tuple[int, int]) -> bool:
        if key not in self.q:
            return self.wants.get(key) == []
        return not self.q[key]


def best_area(ctx: R.Ctx) -> int | None:
    """PK: the legal cutting area holding the most wood."""
    if ctx.phase != "PK" or ctx.snap is None:
        return None
    sn = ctx.snap
    legal = [a for a in ctx.legal if 2 <= a <= 7]
    if not legal:
        return None
    return max(legal, key=lambda a: (W.area_total(sn, a - 2), -a))


def best_area_p0_r2(steps: W.Steps) -> W.Steps:
    return steps


_CACHE: dict[Any, Any] = {}


def reach(
    key: Any,
    cards: list[int],
    wants: dict[tuple[int, int], list[Want]],
    steps: Any,
    stop: tuple[Any, ...],
    check: Any,
    max_seeds: int = 60,
) -> Any:
    """State at `stop` = ("node", round, phase, seat) or ("tr", round, seat) (the seat has played
    its whole travel script, clearing excluded), for the first seed whose path satisfies `check`.
    A fresh clone each call."""
    if key in _CACHE:
        return _CACHE[key].clone()
    for seed in range(1, max_seeds + 1):
        s = build(cards, seed)
        tr = Tr(wants, clear=stop[0] != "tr")
        st: W.Steps = steps()
        pol = R.chain(tr, st, best_area)
        rng = random.Random(seed + 1000)
        rnd, ph = 1, "TR"
        found = None
        try:
            for _ in range(20000):
                assert not s.is_terminal()
                if s.is_chance_node():
                    s.apply_action(H.sample_chance(s, rng))  # pyright: ignore[reportUnknownMemberType]
                    continue
                sn = R.try_snapshot(s)
                if sn is not None:
                    rnd, ph = sn["round"], sn["phase"]
                ctx = R.Ctx(s, rnd, ph, sn, rng)
                if sn is not None:
                    if stop[0] == "node" and (rnd, ph, s.current_player()) == stop[1:]:
                        found = s
                        break
                    if (
                        stop[0] == "tr"
                        and ph == "TR"
                        and rnd == stop[1]
                        and tr.exhausted((rnd, s.current_player()))
                        and s.current_player() == stop[2]
                    ):
                        found = s
                        break
                a = pol(ctx)
                if a is None:
                    a = R.default_action(ctx)
                assert a in s.legal_actions(), f"scripted action {a} illegal in r{rnd} {ph}"
                s.apply_action(a)
        except NoSeed:
            continue
        if found is not None and check(found):
            _CACHE[key] = found
            return found.clone()
    pytest.fail(f"no seed up to {max_seeds} gives the scripted holdings for {key!r}")


def snap(s: Any) -> dict[str, Any]:
    return T.snap(s)


def me(s: Any, i: int = 0) -> dict[str, Any]:
    return T.seat_of(T.snap(s), i)


def legal_in(s: Any, rng: range | tuple[int, ...]) -> list[int]:
    return [a for a in s.legal_actions() if a in rng]


def zone(s: Any, name: str, i: int = 0) -> Counter[str]:
    return W.zone(snap(s), i, name)


def plans_of(s: Any) -> list[dict[str, Any]]:
    return list(snap(s)["planned_work"]["plans"])


# --------------------------------------------------------------------------- shared scenarios

# Sawing / Heating: round 1 gets P0 a saw (path spot), 2 bearers, 1 woodcutter and 2 firewood disks
# (hired woodcutter + mill worker cut, bearers carry them to the sawing area, nothing is milled
# yet); in the target round (2) P0 hires a sawyer (free) and mills in W4.


def _cuts(*srcs: int) -> list[Any]:
    out: list[Any] = []
    for src in srcs:
        out += [W.Opt(W.assign(src)), W.first_take(-1)]
    return out


def _carries(count: int, dest: int = 0) -> list[Any]:
    out: list[Any] = []
    for _ in range(count):
        out += [W.Opt(W.assign(0)), W.move_wood(W.FW, dest)]
    return out


def _plan_wants(plans_by_seat: dict[int, int]) -> dict[tuple[int, int], list[Want]]:
    return {(1, seat): [("plan", c, 1)] for seat, c in plans_by_seat.items()}


def sawing_scenario(
    key: str,
    *,
    p0_plan: int | None = None,
    p1_plan: int | None = None,
    disks: int = 2,
    r2_sawyer: bool = True,
    in_r1: bool = False,
) -> Any:
    """P0 with `disks` (1 or 2) firewood disks in the sawing area, 1 saw, and a sawyer hired in
    the stop round (round 1 if in_r1, else round 2) or only the mill worker (r2_sawyer False).
    Stops at W4 of that round, seat 0. A plan is always for pair 1 (target round 2)."""
    plans = {s: c for s, c in ((0, p0_plan), (1, p1_plan)) if c is not None}
    wants = _plan_wants(plans)
    r1: list[Want] = [("hire", "bearers", disks)]
    if disks == 2:
        r1.append(("hire", "woodcutters", 1))
    r1.append(("spots", ("saw",), 1))
    if in_r1:
        r1.append(("hire", "sawyers", 1))
    wants[(1, 0)] = r1 + ([("plan", p0_plan, 1)] if p0_plan is not None else [])
    if not in_r1 and r2_sawyer:
        wants[(2, 0)] = [("hire", "sawyers", 1)]

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(1, "W1", 0, *_cuts(1) if disks == 1 else _cuts(0, 1))
        st.add(1, "W3", 0, *_carries(disks))
        return st

    def check(s: Any) -> bool:
        return (
            zone(s, "sawing") == Counter({"firewood_disk": disks})
            and me(s)["equipment"]["saw"] == 1
        )

    stop = 1 if in_r1 else 2
    return reach(key, LAYOUT_A, wants, steps, ("node", stop, "W4", 0), check)


def _first_assign(s: Any, w: int) -> None:
    W.assign_if_needed(s, w)


# --------------------------------------------------------------------------- R-092 Sawing


def test_R092_one_sawyer_one_saw_mills_two_disks_in_target_round():
    """R-092 + example: P0 holds PW Sawing in its target round with 1 sawyer, 1 saw and 2 firewood
    disks in the sawing area: it mills both with that one worker and saw; the saw is spent once;
    8 firewood logs end up in the firewood storage / sale area (R-054 output per disk)."""
    s = sawing_scenario("saw_plan", p0_plan=SAW)
    assert plans_of(s) and plans_of(s)[0]["target"] == 2
    _first_assign(s, 0)
    s.apply_action(saw_id(0, 3))
    assert legal_in(s, SAW_IDS), "second disk with the same sawyer and saw must be offered"
    s.apply_action(saw_id(0, 1))
    assert not zone(s, "sawing")
    assert me(s)["equipment"]["saw"] == 0
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert zone(s, "firewood_storage") == Counter({"firewood_log": 4})
    assert zone(s, "sale") == Counter({"firewood_log": 4})


def test_R092_no_plan_one_sawyer_one_saw_mills_one_disk():
    """R-092 baseline / R-054: without PW Sawing the same holdings mill one disk only; after one
    SAW no further SAW or worker assignment is legal and the other disk stays."""
    s = sawing_scenario("saw_noplan")
    _first_assign(s, 0)
    s.apply_action(saw_id(0, 2))
    assert not legal_in(s, SAW_IDS)
    assert not legal_in(s, W.ASSIGN_IDS)
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert zone(s, "sawing") == Counter({"firewood_disk": 1})


def test_R092_other_seats_plan_does_not_double_my_sawing():
    """R-089/R-092: P1 planned PW Sawing for round 2; P0 (no plan) still mills one disk per
    sawyer+saw in round 2."""
    s = sawing_scenario("saw_other", p1_plan=SAW)
    assert [p["seat"] for p in plans_of(s)] == [1]
    _first_assign(s, 0)
    s.apply_action(saw_id(0, 2))
    assert not legal_in(s, SAW_IDS)


def test_R092_not_doubled_in_the_planning_round():
    """R-089/R-092: P0 plans Sawing in round 1 (target round 2); in round 1's sawing phase, with a
    sawyer, saw and 2 disks, it can still mill only one disk."""
    s = sawing_scenario("saw_planning_round", p0_plan=SAW, in_r1=True)
    assert me(s)["hired"]["sawyers"] == 1
    _first_assign(s, 0)
    s.apply_action(saw_id(0, 2))
    assert not legal_in(s, SAW_IDS)


def test_R092_mill_worker_mills_two_disks():
    """R-092 ('or mill worker, hut worker'): in the target round the mill worker (no sawyer
    hired) with 1 saw mills both disks."""
    s = sawing_scenario("saw_mill_worker", p0_plan=SAW, r2_sawyer=False)
    assert me(s)["hired"]["sawyers"] == 0 and not me(s)["mill_worker_used"]
    _first_assign(s, 1)
    s.apply_action(saw_id(0, 0))
    assert legal_in(s, SAW_IDS)
    s.apply_action(saw_id(0, 4))
    assert not zone(s, "sawing")
    assert me(s)["mill_worker_used"] is True


def test_R092_doubling_is_limited_to_disks_present():
    """R-092 ('The disks must be in the sawing area'): with one disk in the sawing area, one
    sawyer and one saw under PW Sawing, nothing more can be milled after that disk."""
    s = sawing_scenario("saw_one_disk", p0_plan=SAW, disks=1)
    assert zone(s, "sawing") == Counter({"firewood_disk": 1})
    _first_assign(s, 0)
    s.apply_action(saw_id(0, 4))
    assert not legal_in(s, SAW_IDS)


def test_R089_sawing_plan_without_sawyer_or_saw_is_lost_but_harmless():
    """R-089: a plan whose components are missing is lost: nothing is forced and nothing is
    refunded. P0 plans Sawing but has no saw (no saw spot taken) and 1 disk: no SAW is legal in the
    target round, DONE is, and the plan stays recorded."""
    wants = {(1, 0): [("hire", "bearers", 1), ("plan", SAW, 1)], (2, 0): [("hire", "sawyers", 1)]}

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(1, "W1", 0, *_cuts(1))
        st.add(1, "W3", 0, *_carries(1))
        return st

    s = reach(
        "saw_lost",
        LAYOUT_A,
        wants,
        steps,
        ("node", 2, "W4", 0),
        lambda s: (
            me(s)["equipment"]["saw"] == 0 and zone(s, "sawing") == Counter({"firewood_disk": 1})
        ),
    )
    assert not legal_in(s, SAW_IDS)
    assert H.DONE in s.legal_actions()
    assert [p["seat"] for p in plans_of(s)] == [0]


# --------------------------------------------------------------------------- R-094 Heating Supply


def heating_scenario(
    key: str, *, p0_plan: int | None = None, p1_plan: int | None = None, in_r1: bool = False
) -> Any:
    """P0: 1 saw, 1 firewood disk in the sawing area. Target round 2: the mill worker is free
    (round 1's cut is done by the mill worker). in_r1: a hired woodcutter cuts and the mill worker
    is free to mill in round 1's W4 (stop there)."""
    plans = {s: c for s, c in ((0, p0_plan), (1, p1_plan)) if c is not None}
    wants = _plan_wants(plans)
    r1: list[Want] = [("hire", "bearers", 1), ("spots", ("saw",), 1)]
    if in_r1:
        r1.append(("hire", "woodcutters", 1))
    wants[(1, 0)] = r1 + ([("plan", p0_plan, 1)] if p0_plan is not None else [])

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(1, "W1", 0, *_cuts(0 if in_r1 else 1))
        st.add(1, "W3", 0, *_carries(1))
        return st

    def check(s: Any) -> bool:
        return zone(s, "sawing") == Counter({"firewood_disk": 1}) and me(s)["equipment"]["saw"] == 1

    return reach(key, LAYOUT_A, wants, steps, ("node", 1 if in_r1 else 2, "W4", 0), check)


def test_R094_firewood_disk_yields_six_logs_in_target_round():
    """R-094: with PW Heating Supply in its target round, milling a firewood disk yields 6 logs,
    placed individually in the firewood storage / sale area (any split, here 2 + 4)."""
    s = heating_scenario("heat_plan", p0_plan=HEAT)
    _first_assign(s, 1)
    assert saw_id(0, 5) in s.legal_actions() and saw_id(0, 6) in s.legal_actions()
    s.apply_action(saw_id(0, 2))
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert not zone(s, "sawing")
    assert zone(s, "firewood_storage") == Counter({"firewood_log": 2})
    assert zone(s, "sale") == Counter({"firewood_log": 4})
    assert me(s)["equipment"]["saw"] == 0


def _kind_mill_scenario(kind: str) -> Any:
    """P0 plans Heating Supply in round 1 (saw from a path spot). In round 2 (target) P0 picks the
    cutting area with the most `kind` wood, the mill worker cuts one piece of it, a bearer carries
    the disk to the sawing area and a hired sawyer mills it. Stops at W4 of round 2, seat 0."""
    k = W.SW if kind == "softwood" else W.HW
    chosen: list[int] = []

    def pick_kind(state: Any) -> int:
        sn = R.try_snapshot(state)
        assert sn is not None
        best = max(range(6), key=lambda a: (W.area_wood(sn, a)[kind], -a))
        if W.area_wood(sn, best)[kind] == 0:
            raise NoSeed(f"no {kind} in any area in round 2")
        chosen[:] = [best]
        return H.PICK_AREA(best)

    def pick_other(state: Any) -> int:
        return W.pick_not(chosen[0])(state)

    wants: dict[tuple[int, int], list[Want]] = {
        (1, 0): [("spots", ("saw",), 1), ("plan", HEAT, 1)],
        (2, 0): [("hire", "bearers", 1), ("hire", "sawyers", 1)],
    }

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(2, "PK", 0, pick_kind)
        st.add(2, "PK", 1, pick_other)
        st.add(2, "W1", 0, W.Opt(W.assign(1)), W.first_take(k))
        st.add(2, "W3", 0, W.Opt(W.assign(0)), W.move_wood(k, 0))
        return st

    def check(s: Any) -> bool:
        return (
            zone(s, "sawing") == Counter({f"{kind}_disk": 1})
            and me(s)["equipment"]["saw"] == 1
            and bool(plans_of(s))
        )

    return reach(("heat_kind", kind), LAYOUT_A, wants, steps, ("node", 2, "W4", 0), check, 150)


def test_R094_softwood_disk_still_gives_three_logs_under_the_plan():
    """R-094: 'Softwood and hardwood are unchanged': with PW Heating Supply active in its target
    round a softwood disk still yields 3 logs (SAW with 4 or more logs is not legal)."""
    s = _kind_mill_scenario("softwood")
    _first_assign(s, 0)
    legal = s.legal_actions()
    assert saw_id(1, 1) in legal
    assert saw_id(1, 3) in legal
    s.apply_action(saw_id(1, 1))
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert zone(s, "firewood_storage") == Counter({"softwood_log": 1})
    assert zone(s, "sale") == Counter({"softwood_log": 2})
    assert not zone(s, "sawing")


def test_R094_hardwood_disk_still_gives_one_log_under_the_plan():
    """R-094: with PW Heating Supply active, a hardwood disk still yields exactly 1 log."""
    s = _kind_mill_scenario("hardwood")
    _first_assign(s, 0)
    s.apply_action(saw_id(2, 0))
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert zone(s, "sale") == Counter({"hardwood_log": 1})
    assert not zone(s, "firewood_storage")
    assert not zone(s, "sawing")


def test_R094_all_six_logs_may_go_to_the_firewood_storage():
    """R-094 ('placement into the firewood storage or sale area' unchanged): SAW with 6 logs to
    the storage and 0 to the sale area is legal and does that."""
    s = heating_scenario("heat_plan", p0_plan=HEAT)
    _first_assign(s, 1)
    s.apply_action(saw_id(0, 6))
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert zone(s, "firewood_storage") == Counter({"firewood_log": 6})
    assert not zone(s, "sale")


def test_R094_the_plan_does_not_force_six_the_base_split_still_totals_six():
    """R-089/R-094: the effect is not an option to refuse: any SAW of a firewood disk under the
    plan yields 6 logs in total (4 in storage + 2 to sale is a valid split of the six)."""
    s = heating_scenario("heat_plan", p0_plan=HEAT)
    _first_assign(s, 1)
    s.apply_action(saw_id(0, 4))
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    assert zone(s, "firewood_storage") == Counter({"firewood_log": 4})
    assert zone(s, "sale") == Counter({"firewood_log": 2})


def test_R094_no_plan_firewood_disk_yields_four_only():
    """R-094 baseline / R-054: without the plan SAW(firewood, 5 or 6) is illegal and 4 is legal."""
    s = heating_scenario("heat_noplan")
    _first_assign(s, 1)
    legal = s.legal_actions()
    assert saw_id(0, 4) in legal
    assert saw_id(0, 5) not in legal and saw_id(0, 6) not in legal


def test_R094_other_seats_plan_does_not_apply():
    """R-089/R-094: P1's Heating Supply plan for round 2 does not help P0."""
    s = heating_scenario("heat_other", p1_plan=HEAT)
    _first_assign(s, 1)
    assert saw_id(0, 5) not in s.legal_actions()


def test_R094_not_in_the_planning_round():
    """R-089/R-094: P0 plans Heating in round 1 (target 2); milling in round 1 still gives 4."""
    s = heating_scenario("heat_planning_round", p0_plan=HEAT, in_r1=True)
    _first_assign(s, 1)
    legal = s.legal_actions()
    assert saw_id(0, 4) in legal and saw_id(0, 5) not in legal


# --------------------------------------------------------------------------- R-090 Trade


def trade_scenario(
    key: str,
    *,
    p0_plan: int | None = None,
    p1_plan: int | None = None,
    planning_round: bool = False,
) -> Any:
    """P0 collects every raft, sledge, wagon and saw spot before the Market in round 1 (so it
    holds at least 2 sellable tokens and a saw). Stops at P0's travel node after that (round 1,
    with the Market still ahead) or at its first travel node of round 2."""
    plans = {s: c for s, c in ((0, p0_plan), (1, p1_plan)) if c is not None}
    wants = _plan_wants(plans)
    wants[(1, 0)] = [("spots", ("raft", "sledge", "wagon", "saw"), 6)] + (
        [("plan", p0_plan, 1)] if p0_plan is not None else []
    )
    if not planning_round:
        wants[(2, 0)] = []

    def check(s: Any) -> bool:
        eq = me(s)["equipment"]
        return (
            eq["raft"] + eq["sledge"] + eq["wagon"] >= 2
            and eq["saw"] >= 1
            and (MARKET in [a - 7 for a in s.legal_actions() if 8 <= a <= 30])
        )

    stop = ("tr", 1, 0) if planning_round else ("tr", 2, 0)
    return reach(key, LAYOUT_A, wants, W.Steps, stop, check)


def _sellable(eq: dict[str, int]) -> dict[int, int]:
    return {0: eq["raft"], 1: eq["sledge"], 2: eq["wagon"]}


def test_R090_trade_sells_raft_sledge_wagon_at_two_dollars_each():
    """R-090: in the target round at the Market a seat with PW Trade may sell any number of its
    raft, sledge and wagon tokens at $2 each; SELL_EQUIP is offered for exactly the types held."""
    s = trade_scenario("trade_plan", p0_plan=TRADE)
    held = _sellable(me(s)["equipment"])
    money0 = me(s)["money"]
    s.apply_action(H.MOVE_TO(MARKET))
    offered = {a - SELL_EQUIP0 for a in legal_in(s, range(130, 133))}
    assert offered == {e for e, c in held.items() if c > 0}
    total = sum(held.values())
    assert total >= 2
    for _ in range(total):
        s.apply_action(min(legal_in(s, range(130, 133))))
    assert not legal_in(s, range(130, 133))
    T.end_visit(s)
    seat = me(s)
    assert seat["money"] == money0 + 2 * total
    eq = seat["equipment"]
    assert (eq["raft"], eq["sledge"], eq["wagon"]) == (0, 0, 0)


def _broke(s: Any) -> Any:
    """White-box: P0 has $0 and both loans taken (as the winter-payment tests set state)."""
    s.money = (0, *s.money[1:])
    s.loans = (2, *s.loans[1:])
    seat = me(s)
    assert seat["money"] == 0 and seat["loans"] == 2
    assert all(seat["craftwork"][k] == 0 for k in (*TYPES, "joker"))
    assert seat["equipment"]["raft"] + seat["equipment"]["sledge"] + seat["equipment"]["wagon"] >= 2
    return s


def test_R090_market_enterable_with_nothing_but_tradeable_equipment_in_target_round():
    """R-090/R-104/R-040: a seat with $0, no loan left, no craftwork, but a raft/sledge/wagon, may
    enter the Market in its PW Trade target round (it can sell equipment); there it may sell the
    tokens and cannot buy anything before the sale."""
    s = _broke(trade_scenario("trade_plan", p0_plan=TRADE))
    assert H.MOVE_TO(MARKET) in s.legal_actions()
    s.apply_action(H.MOVE_TO(MARKET))
    assert legal_in(s, range(130, 133))


def test_R090_market_not_enterable_without_the_plan_when_broke():
    """R-104/R-040: the same $0, loans-maxed holder of equipment without a Trade plan has nothing
    to buy or sell, so the Market is not enterable."""
    s = _broke(trade_scenario("trade_noplan"))
    assert H.MOVE_TO(MARKET) not in s.legal_actions()


def test_R090_market_not_enterable_in_the_planning_round_when_broke():
    """R-089/R-090/R-040: in the round the Trade plan is made (target is later) the broke seat
    cannot enter the Market."""
    s = _broke(trade_scenario("trade_planning_round", p0_plan=TRADE, planning_round=True))
    assert H.MOVE_TO(MARKET) not in s.legal_actions()


def test_R090_saws_are_not_sellable():
    """R-090: saws and other equipment cannot be sold: only raft/sledge/wagon appear in
    SELL_EQUIP, and after selling every sellable token the saws are still held."""
    s = trade_scenario("trade_plan", p0_plan=TRADE)
    saws0 = me(s)["equipment"]["saw"]
    assert saws0 >= 1
    s.apply_action(H.MOVE_TO(MARKET))
    while legal_in(s, range(130, 133)):
        s.apply_action(legal_in(s, range(130, 133))[0])
    T.end_visit(s)
    assert me(s)["equipment"]["saw"] == saws0


def test_R090_no_plan_no_equipment_sale():
    """R-090 baseline: without a Trade plan SELL_EQUIP is never legal at the Market."""
    s = trade_scenario("trade_noplan")
    s.apply_action(H.MOVE_TO(MARKET))
    assert not legal_in(s, range(130, 133))


def test_R090_other_seats_plan_does_not_let_me_sell():
    """R-089/R-090: P1's Trade plan for round 2 gives P0 nothing."""
    s = trade_scenario("trade_other", p1_plan=TRADE)
    s.apply_action(H.MOVE_TO(MARKET))
    assert not legal_in(s, range(130, 133))


def test_R090_not_in_the_planning_round():
    """R-089/R-090: P0 plans Trade in round 1 and visits the Market the same round (target is
    round 2): equipment cannot be sold yet."""
    s = trade_scenario("trade_planning_round", p0_plan=TRADE, planning_round=True)
    assert plans_of(s)[0]["target"] == 2
    s.apply_action(H.MOVE_TO(MARKET))
    assert not legal_in(s, range(130, 133))


def test_R089_trade_plan_without_equipment_is_lost():
    """R-089: P0 plans Trade but holds no raft/sledge/wagon in the target round: nothing is
    offered at the Market, nothing is refunded and the plan stays recorded."""
    wants: dict[tuple[int, int], list[Want]] = {(1, 0): [("plan", TRADE, 1)], (2, 0): []}
    s = reach(
        "trade_lost",
        LAYOUT_A,
        wants,
        W.Steps,
        ("tr", 2, 0),
        lambda s: sum(me(s)["equipment"][k] for k in ("raft", "sledge", "wagon")) == 0,
    )
    assert [p["seat"] for p in plans_of(s)] == [0]
    s.apply_action(H.MOVE_TO(MARKET))
    assert not legal_in(s, range(130, 133))


# --------------------------------------------------------------------------- R-091 Craftwork


def craft_scenario(
    key: str,
    total: int,
    jokers: int,
    *,
    p0_plan: int | None = None,
    p1_plan: int | None = None,
    planning_round: bool = False,
    second_round: bool = False,
    max_seeds: int = 150,
) -> Any:
    """P0 holds (before the Market) `total - jokers` real tokens of one type plus `jokers`
    jokers, collected from the path spots in round 1 (and round 2 when second_round). Stops at its
    travel node with the Market ahead (round 1 if planning_round, else round 2)."""
    plans = {s: c for s, c in ((0, p0_plan), (1, p1_plan)) if c is not None}
    wants = _plan_wants(plans)
    wants[(1, 0)] = [("craft_to", total, jokers)] + (
        [("plan", p0_plan, 1)] if p0_plan is not None else []
    )
    if not planning_round:
        wants[(2, 0)] = [("craft_to", total, jokers)] if second_round else []

    def check(s: Any) -> bool:
        h = me(s)["craftwork"]
        real = [t for t in TYPES if h[t] == total - jokers]
        others = sum(h[t] for t in TYPES) - (total - jokers)
        return (
            len(real) == 1
            and others == 0
            and h["joker"] == jokers
            and MARKET in [a - 7 for a in s.legal_actions() if 8 <= a <= 30]
        )

    stop = ("tr", 1, 0) if planning_round else ("tr", 2, 0)
    return reach(key, LAYOUT_A, wants, W.Steps, stop, check, max_seeds=max_seeds)


def _sell_one(s: Any, size: int, jokers: int) -> tuple[int, int]:
    """MOVE_TO(Market), sell the held set, close the visit; returns (money gained, type index)."""
    h = me(s)["craftwork"]
    x = next(i for i, t in enumerate(TYPES) if h[t] > 0)
    m0 = me(s)["money"]
    s.apply_action(H.MOVE_TO(MARKET))
    a = sell_set(x, size, jokers)
    assert a in s.legal_actions()
    s.apply_action(a)
    T.end_visit(s)
    return me(s)["money"] - m0, x


def test_R091_pair_sells_for_five_in_target_round():
    """R-091: with PW Craftwork in its target round, a set of 2 identical tokens pays $5 (base $2);
    the tokens leave the game."""
    s = craft_scenario("craft_pair_plan", 2, 0, p0_plan=CRAFT)
    gained, x = _sell_one(s, 2, 0)
    assert gained == 5
    assert me(s)["craftwork"][TYPES[x]] == 0
    assert snap(s)["supply"]["craftwork_removed"][TYPES[x]] >= 2


def test_R091_triple_sells_for_eight_in_target_round():
    """R-091: 3 identical tokens pay $8 (base $4)."""
    s = craft_scenario("craft_triple_plan", 3, 0, p0_plan=CRAFT, second_round=True)
    gained, _ = _sell_one(s, 3, 0)
    assert gained == 8


def test_R091_set_with_a_joker_pays_the_plan_price():
    """R-091/R-105: a set of 1 real token + 1 joker is a 2-set: $5 under PW Craftwork."""
    s = craft_scenario("craft_joker_plan", 2, 1, p0_plan=CRAFT)
    gained, _ = _sell_one(s, 2, 1)
    assert gained == 5
    assert me(s)["craftwork"]["joker"] == 0


def test_R091_four_identical_tokens_sell_for_eleven_in_target_round():
    """R-091: with PW Craftwork in its target round, a set of 4 identical tokens pays $11."""
    s = craft_scenario("craft_four_plan", 4, 0, p0_plan=CRAFT, second_round=True, max_seeds=1500)
    gained, x = _sell_one(s, 4, 0)
    assert gained == 11
    assert me(s)["craftwork"][TYPES[x]] == 0


def test_R091_three_tokens_plus_a_joker_sell_for_eleven_in_target_round():
    """R-091/R-105: three identical tokens plus a joker form a 4-set: $11 under the plan."""
    s = craft_scenario("craft_four_joker_plan", 4, 1, p0_plan=CRAFT, second_round=True)
    gained, _ = _sell_one(s, 4, 1)
    assert gained == 11
    assert me(s)["craftwork"]["joker"] == 0


def test_R091_four_set_without_plan_pays_six():
    """R-091 baseline / R-105: without the plan a 4-set pays $6."""
    s = craft_scenario("craft_four_noplan", 4, 0, second_round=True, max_seeds=1500)
    gained, _ = _sell_one(s, 4, 0)
    assert gained == 6


def test_R091_no_plan_pair_pays_two():
    """R-091 baseline / R-105: without the plan the same pair pays $2."""
    s = craft_scenario("craft_pair_noplan", 2, 0)
    gained, _ = _sell_one(s, 2, 0)
    assert gained == 2


def test_R091_other_seats_plan_does_not_raise_my_prices():
    """R-089/R-091: P1's Craftwork plan for round 2 does not change P0's $2 pair."""
    s = craft_scenario("craft_pair_other", 2, 0, p1_plan=CRAFT)
    gained, _ = _sell_one(s, 2, 0)
    assert gained == 2


def test_R091_not_in_the_planning_round():
    """R-089/R-091: P0 plans Craftwork in round 1 and sells the same round: $2, not $5."""
    s = craft_scenario("craft_pair_planning", 2, 0, p0_plan=CRAFT, planning_round=True)
    gained, _ = _sell_one(s, 2, 0)
    assert gained == 2


def test_R091_a_single_token_is_still_not_sellable():
    """R-091/R-105: the plan only changes prices; a lone token (not a set) cannot be sold."""
    s = craft_scenario("craft_single_plan", 1, 0, p0_plan=CRAFT)
    s.apply_action(H.MOVE_TO(MARKET))
    assert not [a for a in s.legal_actions() if 97 <= a <= 129]


# ----------------------------------------------------------------- R-093 Food Supply, R-053


def food_scenario(
    key: str, *, p0_plan: int | None = None, p1_plan: int | None = None, act_round: int = 2
) -> Any:
    """P0 holds at least 1 raft (path spot, round 1), a free bearer and 2 pieces in the woodpile
    in `act_round` (cut by a hired woodcutter and the mill worker). Stops at W3 of that round."""
    plans = {s: c for s, c in ((0, p0_plan), (1, p1_plan)) if c is not None}
    wants = _plan_wants(plans)
    r1: list[Want] = [("spots", ("raft",), 3)] + (
        [("plan", p0_plan, 1)] if p0_plan is not None else []
    )
    act: list[Want] = [("hire", "bearers", 1), ("hire", "woodcutters", 1)]
    if act_round == 1:
        wants[(1, 0)] = r1 + act
    else:
        wants[(1, 0)] = r1
        wants[(act_round, 0)] = act

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(act_round, "W1", 0, *_cuts(0, 1))
        return st

    def check(s: Any) -> bool:
        return me(s)["equipment"]["raft"] >= 1 and sum(zone(s, "woodpile").values()) >= 1

    return reach(key, LAYOUT_F, wants, steps, ("node", act_round, "W3", 0), check)


def _drive_all(s: Any) -> int:
    """Bearer log driving with every raft: returns the pieces placed. Seat state is read only
    once the trip has closed (no snapshot exists mid-turn)."""
    _first_assign(s, 0)
    pieces = 0
    while legal_in(s, range(201, 204)):
        s.apply_action(legal_in(s, range(201, 204))[0])
        pieces += 1
    for _ in range(5):
        if R.try_snapshot(s) is not None:
            break
        s.apply_action(213 if 213 in s.legal_actions() else H.DONE)
    return pieces


def _drive_and_read(s: Any) -> tuple[int, int, int, int]:
    """(food gained, pieces placed, rafts spent, river pieces) for a bearer driving every raft."""
    food0, rafts0 = me(s)["food"], me(s)["equipment"]["raft"]
    river0 = sum(zone(s, "river").values())
    pieces = _drive_all(s)
    seat = me(s)
    return (
        seat["food"] - food0,
        pieces,
        rafts0 - seat["equipment"]["raft"],
        sum(zone(s, "river").values()) - river0,
    )


def test_R093_two_food_per_piece_placed_on_river_in_target_round():
    """R-093 + example: in the target round (2) each wood piece P0 places on its river by raft log
    driving gives 2 food into its food storage (2 per piece)."""
    s = food_scenario("food_plan", p0_plan=FOODS)
    assert plans_of(s)[0]["target"] == 2
    gained, pieces, rafts, river = _drive_and_read(s)
    assert pieces >= 1 and river == pieces and rafts == pieces
    assert gained == 2 * pieces


def test_R093_no_plan_log_driving_gives_no_food():
    """R-093 baseline / R-053: without the plan each raft is spent (returns to the supply), the
    piece lands on the river and no food is gained."""
    s = food_scenario("food_noplan")
    gained, pieces, rafts, river = _drive_and_read(s)
    assert pieces >= 1 and river == pieces and rafts == pieces
    assert gained == 0


def test_R093_other_seats_plan_gives_me_no_food():
    """R-089/R-093: P1's Food Supply plan for round 2 gives P0 no food for its placements."""
    s = food_scenario("food_other", p1_plan=FOODS)
    gained, pieces, _, _ = _drive_and_read(s)
    assert pieces >= 1 and gained == 0


def test_R093_nothing_in_the_planning_round():
    """R-093 ('not in the round it is planned') + example: P0 plans Food Supply in round 1 (target
    round 2) and places pieces on the river by raft in round 1: no food."""
    s = food_scenario("food_planning_round", p0_plan=FOODS, act_round=1)
    gained, pieces, _, _ = _drive_and_read(s)
    assert pieces >= 1 and gained == 0


def test_R093_nothing_in_the_round_after_the_target():
    """R-093 ('not in the rest of the year'): the plan targets round 2; river placements in round 3
    (same year) give no food."""
    s = food_scenario("food_after_target", p0_plan=FOODS, act_round=3)
    gained, pieces, _, _ = _drive_and_read(s)
    assert pieces >= 1 and gained == 0
