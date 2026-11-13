"""Wood-work helpers for unit-7 tests (R-045..R-053), written from the spec only.

Everything goes through the public API (tests/harness.py, tests/support/rounds.py and travel.py).

Key ideas
  * `Steps` is a drive() policy keyed by (round, phase, seat) holding queues of scripted actions.
    An entry is an int, a callable(state) -> int | None (None skips the entry) or `Opt(a)`, which is
    played only if `a` is legal and silently skipped otherwise.  `Opt` exists because ACTIONS 5.2
    says `ASSIGN_WORKER` is auto-skipped when exactly one worker source is legal (AMBIGUITY A4):
    the tests must pass whichever way the engine presents that node.
  * `reach()` plays a game with a policy and stops at the first turn-boundary node that matches
    (round, phase, seat); the test then plays the turn by hand.
  * Snapshots exist only at turn boundaries (SCENARIOS 1.3), so tests read results at the next node.
"""

from __future__ import annotations

import functools
from collections import Counter
from collections.abc import Callable
from typing import Any, cast

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

FW, SW, HW = 0, 1, 2
TAKE_WOOD_IDS = range(177, 195)
MOVE_WOOD_IDS = range(195, 201)
RIVER_IDS = range(201, 204)
MOVE_CUT_IDS = range(168, 174)
ASSIGN_IDS = range(174, 177)
USE_WAGON = 210
END_TRIP = 213


def assign(w: int) -> int:
    return 174 + w


def take_wood(a: int, k: int) -> int:
    """a = 0-based cutting area, k = kind (0 firewood, 1 softwood, 2 hardwood)."""
    return 177 + 3 * a + k


def move_cut(a: int) -> int:
    return 168 + a


def move_wood(k: int, d: int) -> int:
    """d = 0 sawing area, 1 sale area."""
    return 195 + 2 * k + d


def river_move(k: int) -> int:
    return 201 + k


def ids(legal: list[int], rng: range) -> list[int]:
    return sorted(a for a in legal if a in rng)


def pm(x: Any) -> Counter[str]:
    """Piece map (dict or list shorthand) as a Counter without zero entries."""
    if not x:
        return Counter()
    if isinstance(x, dict):
        return Counter({k: v for k, v in cast("dict[str, int]", x).items() if v})
    return Counter(cast("list[str]", x))


def zone(sn: dict[str, Any], seat: int, name: str) -> Counter[str]:
    return pm(T.seat_of(sn, seat).get(name))


def area_wood(sn: dict[str, Any], a: int) -> dict[str, int]:
    """Wood of cutting area a (0-based) as {firewood, softwood, hardwood}."""
    return R.wood(cast("dict[str, Any]", H.areas(sn)[a]))  # pyright: ignore[reportUnknownMemberType]


def area_total(sn: dict[str, Any], a: int) -> int:
    return sum(area_wood(sn, a).values())


# --------------------------------------------------------------------------- scripted policy


class Opt:
    """Play `a` if it is legal, otherwise skip the entry."""

    def __init__(self, a: int):
        self.a = a


class Steps:
    def __init__(self) -> None:
        self.table: dict[tuple[int, str, int], list[Any]] = {}

    def add(self, rnd: int, phase: str, seat: int, *entries: Any) -> Steps:
        self.table.setdefault((rnd, phase, seat), []).extend(entries)
        return self

    def __call__(self, ctx: R.Ctx) -> int | None:
        q = self.table.get((ctx.round, ctx.phase, ctx.player))
        legal = ctx.legal
        while q:
            e = q.pop(0)
            if isinstance(e, Opt):
                if e.a in legal:
                    return e.a
                continue
            a: Any = e(ctx.state) if callable(e) else e
            if a is None:
                continue
            return cast("int", a)
        return None


def first_take(kind: int) -> Callable[[Any], int]:
    """The first legal TAKE_WOOD of this kind (any kind if kind < 0); fails loudly if none."""

    def pick(state: Any) -> int:
        got = [
            a
            for a in state.legal_actions()
            if a in TAKE_WOOD_IDS and (kind < 0 or (a - 177) % 3 == kind)
        ]
        assert got, f"no legal TAKE_WOOD of kind {kind}: {state.legal_actions()}"
        return got[0]

    return pick


def cut(count: int, kind: int = FW, src: int = 0) -> list[Any]:
    """Entries for `count` single-piece cuts by worker source `src` (0 hired, 1 mill)."""
    out: list[Any] = []
    for _ in range(count):
        out += [Opt(assign(src)), first_take(kind)]
    return out


def rank_pick(i: int) -> Callable[[Any], int]:
    """PK pick: the i-th cutting area ranked by wood count (ties by lower number)."""

    def pick(state: Any) -> int:
        sn = R.try_snapshot(state)
        if sn is None:
            return H.PICK_AREA(0)
        order = sorted(range(6), key=lambda a: (-area_total(sn, a), a))
        return H.PICK_AREA(order[i % 6])

    return pick


def kind_pick(kind: str) -> Callable[[Any], int]:
    """PK pick: the area holding the most wood of `kind` (needs at least one)."""

    def pick(state: Any) -> int:
        sn = R.try_snapshot(state)
        assert sn is not None
        best = max(range(6), key=lambda a: (area_wood(sn, a)[kind], -a))
        assert area_wood(sn, best)[kind] > 0
        return H.PICK_AREA(best)

    return pick


def pick_not(avoid: int) -> Callable[[Any], int]:
    """PK pick: the lowest-numbered area other than `avoid` (0-based)."""

    def pick(_state: Any) -> int:
        return H.PICK_AREA(0 if avoid != 0 else 1)

    return pick


# --------------------------------------------------------------------------- travel scripts


def spot_loc(n: int, j: bool, seed: int, kind: str, idx: int = 0) -> int:
    """Printed location of the idx-th round-1 token spot holding `kind` (setup is seeded)."""
    locs = T.spot_with(T.snap(T.start(n, j, seed)), kind)
    assert len(locs) > idx, f"seed {seed} has no {kind} spot #{idx}"
    return locs[idx]


def tr_plan(
    n: int,
    j: bool,
    seed: int,
    *,
    bearers: int = 0,
    woodcutters: int = 0,
    fodder: bool = False,
    tokens: tuple[tuple[str, int], ...] = (),
    loans: int = 0,
) -> list[int]:
    """Round-1 travel for one seat: loans, then visits in ascending location order, then the
    clearing.  Multi-unit locations close with an explicit DONE (ACTIONS 1.4)."""
    visits: list[tuple[int, list[int]]] = []
    for kind, idx in tokens:
        visits.append((spot_loc(n, j, seed, kind, idx), []))
    if bearers:
        visits.append((R.loc(j, "bearers"), [R.HIRE_BEARER] * bearers + [H.DONE]))
    if fodder:
        visits.append((R.loc(j, "fodder"), [R.BUY_FODDER]))
    if woodcutters:
        visits.append((R.loc(j, "woodcutters"), [R.HIRE_WOODCUTTER] * woodcutters + [H.DONE]))
    visits.sort(key=lambda v: v[0])
    out: list[int] = [H.TAKE_LOAN] * loans
    for loc, acts in visits:
        out += [H.MOVE_TO(loc), *acts]
    out.append(R.MOVE_CLEARING)
    return out


# --------------------------------------------------------------------------- reaching states

_CACHE: dict[Any, Any] = {}


def reach(
    n: int,
    j: bool,
    seed: int,
    steps: Steps,
    stop_at: tuple[int, str, int],
    extra: Callable[[R.Ctx], int | None] | None = None,
    key: Any = None,
) -> Any:
    """State at the first turn-boundary node (round, phase, seat); a fresh clone each call."""
    if key is not None and key in _CACHE:
        return _CACHE[key].clone()
    pol = R.chain(steps, extra) if extra else steps
    run = R.drive(
        {"players": n, "joinery": j},
        seed=seed,
        policy=pol,
        stop=lambda c: (c.round, c.phase, c.player) == stop_at,
    )
    assert run.stopped, f"never reached {stop_at}"
    if key is not None:
        _CACHE[key] = run.state
        return run.state.clone()
    return run.state


def snap(s: Any) -> dict[str, Any]:
    return T.snap(s)


def me(s: Any, seat: int) -> dict[str, Any]:
    return T.seat_of(T.snap(s), seat)


def assign_if_needed(s: Any, w: int) -> None:
    """Commit worker source w if the engine asks for it (it may have auto-inserted it)."""
    if assign(w) in s.legal_actions():
        s.apply_action(assign(w))


def play(s: Any, *actions: int) -> Any:
    return T.play(s, *actions)


def end_turn(s: Any) -> None:
    """DONE for the acting seat (W1/W3 turns end only with DONE)."""
    assert H.DONE in s.legal_actions(), s.legal_actions()
    s.apply_action(H.DONE)


def advance_phase_to_seat(s: Any, phase: str, seat: int) -> None:
    """DONE for the acting seats until `seat` is to act in `phase`."""
    for _ in range(40):
        sn = R.try_snapshot(s)
        if sn is not None and sn["phase"] == phase and s.current_player() == seat:
            return
        assert sn is not None and sn["phase"] == phase, f"left {phase}"
        end_turn(s)
    raise AssertionError("advance_phase_to_seat: too many steps")


@functools.cache
def hardwood_round2_seed() -> tuple[int, int]:
    """(seed, 0-based area) of a 2-player base-side game where, at round 2's picks, some area
    holds hardwood (a placement card gave it, R-037)."""
    for seed in range(150):
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            stop=lambda c: c.round == 2 and c.phase == "PK",
        )
        if not run.stopped:
            continue
        sn = snap(run.state)
        for a in range(6):
            if area_wood(sn, a)["hardwood"] > 0:
                return seed, a
    raise AssertionError("no seed with round-2 hardwood")
