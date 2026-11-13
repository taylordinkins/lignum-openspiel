"""Scripted-play rig for the joinery side (Phase 4 unit 10, buildings), written from the spec only.

A copy of the planned-work rigs (pwscen / test_pw_hut_drying) for a 2-player game with
joinery=true, since buildings exist only there (R-002). There is no scenario loader in the harness,
so a board is reached by scripted play and then a building is handed to a seat by assigning the
state's per-seat `held_buildings` tuple (indices into data/components/buildings.yaml), as the
winter-payment tests assign `food`, `money`, `store`. `give(state, seat, building_id)` does that.

Wants (per (round, seat)): ("plan", card, pair) | ("hire", name, n) | ("spots", kinds, n)
| ("pick", [types]) | ("loan", n). Stops: ("node", rnd, phase, seat) | ("tr", rnd, seat).
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

import pytest
import yaml

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import woodwork as W

PW_LOC = 8
MARKET = 21
PW_DRAW0 = 47
PLAN0 = 67
CLEAR = R.MOVE_CLEARING

with open(R.ROOT / "data" / "components" / "buildings.yaml", encoding="utf-8") as _fh:
    BUILDINGS: list[str] = [b["id"] for b in yaml.safe_load(_fh)["buildings"]]

_PW = R._yaml("planned_work.yaml")["planned_work"]  # pyright: ignore[reportPrivateUsage]
PW_IDS: list[str] = [c["id"] for c in _PW]
LOG, FOODS, HUT, TRADE, CRAFT, OT = (
    PW_IDS.index(i)
    for i in (
        "pw_log_driving",
        "pw_food_supply",
        "pw_hut_construction",
        "pw_trade",
        "pw_craftwork",
        "pw_overtime",
    )
)


def PLAN(c: int, pair: int) -> int:
    return PLAN0 + 3 * c + (pair - 1)


def give(state: Any, seat: int, *building_ids: str) -> None:
    """Hand `building_ids` to `seat` (white-box: assigns the state's `held_buildings`)."""
    held: list[tuple[int, ...]] = [tuple(h) for h in state.held_buildings]
    held[seat] = tuple(BUILDINGS.index(b) for b in building_ids)
    state.held_buildings = tuple(held)


class NoSeed(Exception):
    """This seed's path cannot give the scripted holdings; try the next one."""


Want = tuple[Any, ...]
_HIRE = {"bearers": R.HIRE_BEARER, "woodcutters": R.HIRE_WOODCUTTER, "sawyers": R.HIRE_SAWYER}


def build(cards: list[int], seed: int, n: int = 2) -> Any:
    game: Any = H.as_game({"players": n, "joinery": True})  # pyright: ignore[reportUnknownMemberType]
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


def _resolve(sn: dict[str, Any], seat: int, wants: list[Want], clear: bool) -> list[int]:
    me = T.seat_of(sn, seat)
    toks = T.spots(sn)
    taken: set[int] = set()
    visits: list[tuple[int, list[int]]] = []
    loans: list[int] = []

    def free(kind: tuple[str, ...]) -> list[int]:
        return sorted(
            loc
            for loc, t in toks.items()
            if t in kind and me["foreman"] < loc < MARKET and loc not in taken
        )

    for w in wants:
        kind = w[0]
        if kind == "loan":
            loans += [H.TAKE_LOAN] * w[1]
        elif kind == "plan":
            visits.append((PW_LOC, [PLAN(w[1], w[2])]))
        elif kind == "hire":
            name, count = w[1], w[2]
            if name == "woodcutters" and T.own_wood(sn, seat) - me["hired"]["woodcutters"] < count:
                raise NoSeed("not enough wood in the cutting area")
            visits.append((R.loc(True, name), [_HIRE[name]] * count + [H.DONE]))
        elif kind == "fodder":
            visits.append((R.loc(True, "fodder"), [R.BUY_FODDER]))
        elif kind == "spots":
            locs = free(w[1])[: w[2]]
            if len(locs) < w[2]:
                raise NoSeed("not enough token spots of that kind ahead")
            taken.update(locs)
            visits += [(loc, []) for loc in locs]
        elif kind == "pick":
            for t in w[1]:
                got = free((t,))
                if not got:
                    raise NoSeed(f"no {t} spot")
                taken.add(got[0])
                visits.append((got[0], []))
        elif kind == "tryp":  # collect those of the listed craft types not yet held, if offered
            need: Counter[str] = Counter(w[1])
            need.subtract(Counter(me["craftwork"]))
            for typ, cnt in need.items():
                for _ in range(max(cnt, 0)):
                    got = free((typ,))
                    if got:
                        taken.add(got[0])
                        visits.append((got[0], []))
        else:  # pragma: no cover
            raise AssertionError(kind)
    visits.sort(key=lambda v: v[0])
    out: list[int] = list(loans)
    for loc, acts in visits:
        out += [H.MOVE_TO(loc), *acts]
    if clear:
        out.append(CLEAR)
    return out


class Tr:
    """Travel scripts per (round, seat), resolved at the seat's first travel node of the round.
    A seat with no entry goes to the clearing; with clear=False the queue ends without it."""

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
        return self.q[key].pop(0) if self.q[key] else None

    def exhausted(self, key: tuple[int, int]) -> bool:
        if key not in self.q:
            return self.wants.get(key) == []
        return not self.q[key]


def best_area(ctx: R.Ctx) -> int | None:
    if ctx.phase != "PK" or ctx.snap is None:
        return None
    legal = [a for a in ctx.legal if 2 <= a <= 7]
    if not legal:
        return None
    snap = ctx.snap
    return max(legal, key=lambda a: (W.area_total(snap, a - 2), -a))


_CACHE: dict[Any, Any] = {}


def reach(
    key: Any,
    wants: dict[tuple[int, int], list[Want]],
    steps: Any,
    stop: tuple[Any, ...],
    check: Any,
    cards: list[int],
    max_seeds: int = 150,
) -> Any:
    """State at `stop` for the first seed whose state satisfies `check`; a fresh clone each call."""
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
            for _ in range(30000):
                if s.is_terminal():
                    break
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
