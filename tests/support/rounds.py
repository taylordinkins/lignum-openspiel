"""Round driver for unit-4 tests (written from the spec only; no engine internals).

`drive()` plays a whole game through the public OpenSpiel API with a seeded chance sampler and a
pluggable policy, and records, for every round, the chance outcomes that were resolved between
the last decision node of the previous round and the first decision node of the new one
(the "trail"), plus the scenario dumps (SCENARIOS.md section 8) on both sides of that gap.

Scenario dumps only exist at turn boundaries (SCENARIOS 1.3), so mid-turn nodes get `snap=None`.

Default policy (when the supplied policy returns None):
  * TR  : MOVE_TO(23), the forest clearing, which is always enterable (R-044);
  * W/N : DONE when legal, else the first legal action;
  * SP, PK and anything else: the first legal action.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from tests import harness as H

ROOT = Path(__file__).resolve().parents[2]
CLEARING = 23
MOVE_CLEARING = H.MOVE_TO(CLEARING)
TAKE_TASK0 = 38
TAKE_TASK_END = 56
CHOOSE_BUILDING0 = 57
CHOOSE_BUILDING_END = 66
TAKE_WOOD0, TAKE_WOOD_END = 177, 194
ASSIGN0, ASSIGN_END = 174, 176
HIRE_BEARER, HIRE_WOODCUTTER, HIRE_SAWYER, BUY_FODDER = 31, 32, 33, 34

# Printed location numbers (R-021, R-022).
LOC_BASE = {"bearers": 4, "fodder": 6, "woodcutters": 10, "tasks": 13, "sawyers": 16}
LOC_JOIN = {
    "bearers": 4,
    "fodder": 6,
    "woodcutters": 10,
    "buildings": 12,
    "tasks": 14,
    "joiner": 16,
    "sawyers": 18,
}


def loc(joinery: bool, name: str) -> int:
    return (LOC_JOIN if joinery else LOC_BASE)[name]


def move(joinery: bool, name: str) -> int:
    return H.MOVE_TO(loc(joinery, name))


CRAFT = ("board", "shingle", "stake", "reed", "joker")
SPOT_NAMES = ("wagon", "raft", "saw", "sledge", "dollar", "food", "x", *CRAFT)  # SPOT_TOKEN(y)
SEASONAL = (1, 2, 3, 5, 6, 7)
WINTER = (4, 8)
SEASON_PHASES = ("RS", "PK", "TR", "W1", "W2", "W3", "W4", "W5", "W6", "W7")
WINTER_PHASES = ("WS", "NB", "N1", "N2", "N3", "N4", "N5", "N6", "SF", "FS")


def _yaml(name: str) -> dict[str, Any]:
    with open(ROOT / "data" / "components" / name, encoding="utf-8") as fh:
        return cast("dict[str, Any]", yaml.safe_load(fh))


def setup_data() -> dict[str, Any]:
    return _yaml("setup.yaml")


def quantities(n: int) -> dict[str, Any]:
    return cast("dict[str, Any]", setup_data()["by_players"][n])


def token_mix(n: int) -> dict[str, int]:
    """The 10 equipment tokens of R-017 by SPOT_NAMES name (x-marker is 'x')."""
    q: dict[str, int] = dict(quantities(n)["path_equipment_tokens"])
    if "x_marker" in q:
        q["x"] = q.pop("x_marker")
    return q


def placement_cards() -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", _yaml("cards.yaml")["placement"])


def task_ids() -> list[str]:
    tasks = cast("list[dict[str, Any]]", _yaml("cards.yaml")["tasks"])
    return [t["id"] for t in tasks]


def craft_totals() -> dict[str, int]:
    return dict(setup_data()["supply"]["craftwork_by_type"])


def total(x: Any) -> int:
    """Sum of an int / dict-of-ints / list field."""
    if x is None:
        return 0
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    if isinstance(x, dict):
        return sum(total(v) for v in cast("dict[Any, Any]", x).values())
    return sum(total(v) for v in x)


def wood(area: dict[str, Any]) -> dict[str, int]:
    w: dict[str, int] = area.get("wood", {}) or {}
    return {k: w.get(k, 0) for k in ("firewood", "softwood", "hardwood")}


def food(area: dict[str, Any]) -> int:
    return area.get("food", 0) or 0


def try_snapshot(state: Any) -> dict[str, Any] | None:
    try:
        return cast("dict[str, Any]", H.snapshot(state))  # pyright: ignore[reportUnknownMemberType]
    except Exception:  # mid-turn (S-MIDTURN) or not a decision node
        return None


@dataclass
class Ctx:
    state: Any
    round: int
    phase: str
    snap: dict[str, Any] | None
    rng: random.Random

    @property
    def player(self) -> int:
        return self.state.current_player()

    @property
    def legal(self) -> list[int]:
        return self.state.legal_actions()


@dataclass
class Event:
    """First turn-boundary decision node of a round."""

    round: int
    phase: str
    trail: list[int]  # chance outcomes resolved just before this node
    outcomes: list[dict[int, float]]  # chance_outcomes() (id -> probability) at each trail step
    before: dict[str, Any] | None  # last turn-boundary dump before the trail
    after: dict[str, Any]


@dataclass
class Run:
    events: list[Event] = field(default_factory=list[Event])
    log: list[tuple[int, str, int]] = field(
        default_factory=list[tuple[int, str, int]]
    )  # (round, phase, player)
    state: Any = None
    stopped: bool = False

    def event(self, rnd: int) -> Event:
        for e in self.events:
            if e.round == rnd:
                return e
        raise AssertionError(f"round {rnd} never started")

    def families(self, ev: Event) -> list[str]:
        return [H.chance_family(a)[0] for a in ev.trail]


class Script:
    """Per-(round, seat) list of travel actions played in order at TR.

    An entry may be an int or a callable(state) -> int (e.g. 'first legal TAKE_TASK').
    When a seat's list is exhausted the default (clearing) applies.
    """

    def __init__(self, scripts: dict[tuple[int, int], list[Any]]):
        self.q: dict[tuple[int, int], list[Any]] = {k: list(v) for k, v in scripts.items()}

    def __call__(self, ctx: Ctx) -> int | None:
        if ctx.phase != "TR":
            return None
        q = self.q.get((ctx.round, ctx.player))
        if not q:
            return None
        a: Any = q.pop(0)
        return cast("int", a(ctx.state) if callable(a) else a)


def first_legal(lo: int, hi: int) -> Callable[[Any], int]:
    def pick(state: Any) -> int:
        got: list[int] = [a for a in state.legal_actions() if lo <= a <= hi]
        assert got, f"no legal action in {lo}..{hi}"
        return got[0]

    return pick


def cut_all_wood(ctx: Ctx) -> int | None:
    """W1: keep assigning workers and taking wood while that is legal."""
    if ctx.phase != "W1":
        return None
    legal = ctx.legal
    for lo, hi in ((TAKE_WOOD0, TAKE_WOOD_END), (ASSIGN0, ASSIGN_END)):
        got = [a for a in legal if lo <= a <= hi]
        if got:
            return got[0]
    return None


def chain(*policies: Callable[[Ctx], int | None]) -> Callable[[Ctx], int | None]:
    def run(ctx: Ctx) -> int | None:
        for p in policies:
            a = p(ctx)
            if a is not None:
                return a
        return None

    return run


def default_action(ctx: Ctx) -> int:
    legal = ctx.legal
    if ctx.phase == "TR":
        assert MOVE_CLEARING in legal, f"clearing not enterable in TR: {legal}"
        return MOVE_CLEARING
    if ctx.phase in ("SP", "PK"):
        return legal[0]
    return H.DONE if H.DONE in legal else legal[0]


def drive(
    params: Any,
    seed: int = 0,
    policy: Callable[[Ctx], int | None] | None = None,
    stop: Callable[[Ctx], bool] | None = None,
    max_steps: int = 20000,
) -> Run:
    """Play from the initial state. `stop(ctx)` is checked at turn-boundary nodes only; when it
    returns True the run ends there (before the node's action) with `run.stopped = True`."""
    game: Any = H.as_game(params)  # pyright: ignore[reportUnknownMemberType]
    state: Any = game.new_initial_state()
    rng = random.Random(seed)
    run = Run(state=state)
    trail: list[int] = []
    outs: list[dict[int, float]] = []
    last_snap: dict[str, Any] | None = None
    rnd: int = 0
    phase: str = ""
    for _ in range(max_steps):
        if state.is_terminal():
            return run
        if state.is_chance_node():
            outs.append(dict(state.chance_outcomes()))
            c: int = H.sample_chance(state, rng)  # pyright: ignore[reportUnknownMemberType]
            trail.append(c)
            state.apply_action(c)
            continue
        snap = try_snapshot(state)
        if snap is not None:
            phase = snap["phase"]
            if snap["round"] != rnd:
                rnd = snap["round"]
                run.events.append(Event(rnd, phase, trail, outs, last_snap, snap))
            trail, outs = [], []
            last_snap = snap
            run.log.append((rnd, phase, state.current_player()))
        ctx = Ctx(state, rnd, phase, snap, rng)
        if snap is not None and stop is not None and stop(ctx):
            run.stopped = True
            return run
        a: int | None = policy(ctx) if policy else None
        if a is None:
            a = default_action(ctx)
        assert a in state.legal_actions(), f"policy chose illegal {a} in {phase} r{rnd}"
        state.apply_action(a)
    raise AssertionError("drive: step limit")


def seasonal_events(run: Run) -> list[Event]:
    return [e for e in run.events if e.round in SEASONAL]
