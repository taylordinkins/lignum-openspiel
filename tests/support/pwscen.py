"""Scripted-play scenario builder for planned-work tests (units 4-7), written from the spec only.

There is no scenario loader in the harness, so every board is reached by playing a 2-player,
base-side game from setup with chosen PW_DRAW outcomes (the laid-out cards), a lazily resolved
travel script per (round, seat) and per-phase `woodwork.Steps`. `reach()` searches seeds until the
caller's check accepts the state (the path tokens and area contents are random).

Wants (per (round, seat)): ("plan", card, pair) | ("hire", "bearers"|"woodcutters"|"sawyers", n)
| ("spots", kinds, count). Stops: ("node", rnd, phase, seat) | ("tr", rnd, seat) |
("round", rnd) = first decision node whose snapshot is in round rnd | ("first", rnd, phase).
"""

from __future__ import annotations

import random
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

_DATA = R._yaml("planned_work.yaml")["planned_work"]  # pyright: ignore[reportPrivateUsage]
IDS: list[str] = [c["id"] for c in _DATA]
SEASONS: dict[str, list[str]] = {c["id"]: list(c["seasons"]) for c in _DATA}
TRADE, CRAFT, SAW, FOODS, HEAT, HUT, DRY, OT, LOG, CUT = (
    IDS.index(i)
    for i in (
        "pw_trade",
        "pw_craftwork",
        "pw_sawing",
        "pw_food_supply",
        "pw_heating_supply",
        "pw_hut_construction",
        "pw_drying",
        "pw_overtime",
        "pw_log_driving",
        "pw_cutting",
    )
)


def PLAN(c: int, pair: int) -> int:
    return PLAN0 + 3 * c + (pair - 1)


class NoSeed(Exception):
    """This seed's path cannot give the scripted holdings; try the next one."""


Want = tuple[Any, ...]
_HIRE = {"bearers": R.HIRE_BEARER, "woodcutters": R.HIRE_WOODCUTTER, "sawyers": R.HIRE_SAWYER}


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


def _resolve(sn: dict[str, Any], seat: int, wants: list[Want], clear: bool) -> list[int]:
    me = T.seat_of(sn, seat)
    toks = T.spots(sn)
    visits: list[tuple[int, list[int]]] = []
    loans: list[int] = []
    for w in wants:
        kind = w[0]
        if kind == "loan":
            loans += [H.TAKE_LOAN] * w[1]
        elif kind == "fodder":
            visits.append((R.loc(False, "fodder"), [R.BUY_FODDER]))
        elif kind == "plan":
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
            if len(locs) < w[2]:
                raise NoSeed("not enough token spots of that kind ahead")
            visits += [(loc, []) for loc in locs]
        else:  # pragma: no cover
            raise AssertionError(kind)
    visits.sort(key=lambda v: v[0])
    out: list[int] = list(loans)
    for loc, acts in visits:
        out += [H.MOVE_TO(loc), *acts]
    if clear:
        out.append(R.MOVE_CLEARING)
    return out


class Tr:
    """Travel scripts per (round, seat), resolved at the seat's first travel node of the round.
    A seat with no entry goes to the clearing. With clear=False the queue ends without it and
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
        return self.q[key].pop(0) if self.q[key] else None

    def exhausted(self, key: tuple[int, int]) -> bool:
        if key not in self.q:
            return self.wants.get(key) == []
        return not self.q[key]


def best_area(ctx: R.Ctx) -> int | None:
    """PK: the legal cutting area holding the most wood (lowest number on ties)."""
    sn = ctx.snap
    if ctx.phase != "PK" or sn is None:
        return None
    legal = [a for a in ctx.legal if 2 <= a <= 7]
    if not legal:
        return None
    return max(legal, key=lambda a: (W.area_total(sn, a - 2), -a))


_CACHE: dict[Any, Any] = {}


def reach(
    key: Any,
    cards: list[int],
    wants: dict[tuple[int, int], list[Want]],
    steps: Any,
    stop: tuple[Any, ...],
    check: Any = None,
    max_seeds: int = 80,
) -> Any:
    """State at `stop` for the first seed whose state satisfies `check`; a fresh clone per call."""
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
                assert not s.is_terminal(), "game ended before the stop"
                if s.is_chance_node():
                    s.apply_action(H.sample_chance(s, rng))  # pyright: ignore[reportUnknownMemberType]
                    continue
                sn = R.try_snapshot(s)
                if sn is not None:
                    rnd, ph = sn["round"], sn["phase"]
                ctx = R.Ctx(s, rnd, ph, sn, rng)
                if sn is not None:
                    kind = stop[0]
                    if (
                        kind == "node"
                        and (rnd, ph, s.current_player()) == stop[1:]
                        or kind == "round"
                        and rnd == stop[1]
                        or kind == "first"
                        and (rnd, ph) == stop[1:]
                        or (
                            kind == "tr"
                            and ph == "TR"
                            and rnd == stop[1]
                            and tr.exhausted((rnd, s.current_player()))
                            and s.current_player() == stop[2]
                        )
                    ):
                        found = s
                    if found is not None:
                        break
                a = pol(ctx)
                if a is None:
                    a = R.default_action(ctx)
                assert a in s.legal_actions(), f"scripted action {a} illegal in r{rnd} {ph}"
                s.apply_action(a)
        except NoSeed:
            continue
        if found is not None and (check is None or check(found)):
            _CACHE[key] = found
            return found.clone()
    pytest.fail(f"no seed up to {max_seeds} gives the scripted holdings for {key!r}")


def advance(s: Any, stop: Any, rng_seed: int = 5, limit: int = 30000) -> Any:
    """Keep playing with default actions (clearing, DONE, first legal) until `stop(snap, state)`
    holds at a turn-boundary node. Returns the state."""
    rng = random.Random(rng_seed)
    for _ in range(limit):
        assert not s.is_terminal(), "game ended before the stop"
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))  # pyright: ignore[reportUnknownMemberType]
            continue
        sn = R.try_snapshot(s)
        if sn is not None and stop(sn, s):
            return s
        ctx = R.Ctx(s, sn["round"] if sn else 0, sn["phase"] if sn else "", sn, rng)
        s.apply_action(R.default_action(ctx))
    raise AssertionError("advance: step limit")


def snap(s: Any) -> dict[str, Any]:
    return T.snap(s)


def me(s: Any, i: int = 0) -> dict[str, Any]:
    return T.seat_of(T.snap(s), i)


def legal_in(s: Any, rng: range | tuple[int, ...]) -> list[int]:
    return [a for a in s.legal_actions() if a in rng]
