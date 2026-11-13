"""Plan-level search (lignum.bots.plan_search) and the strategist's RoundPlan hook."""

from __future__ import annotations

import random

import pyspiel

import lignum.game  # noqa: F401
from lignum import actions as A
from lignum.bots.plan_search import PlanConfig, PlanSearchBot
from lignum.bots.strategist import Ctx, RoundPlan, StrategistBot
from lignum.game import PHASE_PK, PHASE_TR, LignumState


def _to(st: pyspiel.State, rng: random.Random, pred) -> LignumState:  # type: ignore[no-untyped-def]
    bot = StrategistBot()
    while not (isinstance(st, LignumState) and not st.is_chance_node() and pred(st)):
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
        else:
            st.apply_action(bot.choose(st, rng))
    assert isinstance(st, LignumState)
    return st


def test_plan_forces_area_pick() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    rng = random.Random(3)
    st = _to(game.new_initial_state(), rng, lambda s: s.phase == PHASE_PK)
    bot = StrategistBot()
    own = bot.choose(st, random.Random(0))
    other = next(a for a in range(6) if A.encode("PICK_AREA", a) != own)
    bot.plans[st.current_player()] = RoundPlan(st.round, area=other)
    assert bot.choose(st, random.Random(0)) == A.encode("PICK_AREA", other)
    bot.plans[st.current_player()] = RoundPlan(st.round + 1, area=other)  # other round: ignored
    assert bot.choose(st, random.Random(0)) == own


def test_plan_task_choice() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    rng = random.Random(4)
    st = _to(game.new_initial_state(), rng, lambda s: s.phase == PHASE_TR and bool(s.task_row))
    bot = StrategistBot()
    seat = st.current_player()
    c = Ctx(st, seat, bot.w)
    target = st.task_row[-1]
    bot.plans[seat] = RoundPlan(st.round, task=target)
    assert bot._best_task(c)[0] == target  # pyright: ignore[reportPrivateUsage]
    bot.plans[seat] = RoundPlan(st.round, task=-1)
    assert bot._best_task(c)[0] == -1  # pyright: ignore[reportPrivateUsage]


def test_plan_search_plays_legal_game() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    pb = PlanSearchBot(cfg=PlanConfig(playouts=2, areas=1, tasks=1, keep=1))
    bots = [pb, StrategistBot()]
    rng = random.Random(5)
    st = game.new_initial_state()
    planned = 0
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
            continue
        a = bots[st.current_player()].choose(st, rng)
        assert a in st.legal_actions()
        planned += bool(pb.last_scores)
        pb.last_scores = {}
        st.apply_action(a)
    assert planned >= 3
    assert isinstance(st, LignumState) and len(st.final) == 2


def test_candidates_include_own_choice_first() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    st = _to(game.new_initial_state(), random.Random(6), lambda s: s.phase == PHASE_PK)
    plans = PlanSearchBot().candidates(st)
    assert plans[0] == RoundPlan(st.round)
    assert len(set(plans)) == len(plans) > 1
