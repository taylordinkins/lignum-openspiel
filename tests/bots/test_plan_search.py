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


def test_plan_follow_up_round() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    st = _to(game.new_initial_state(), random.Random(3), lambda s: s.phase == PHASE_PK)
    bot = StrategistBot()
    own = bot.choose(st, random.Random(0))
    other = next(a for a in range(6) if A.encode("PICK_AREA", a) != own)
    later = RoundPlan(st.round, then=(RoundPlan(st.round + 1, area=other),))
    bot.plans[st.current_player()] = later
    assert bot.choose(st, random.Random(0)) == own  # this round: own choice
    earlier = RoundPlan(st.round - 1, then=(RoundPlan(st.round, area=other),))
    bot.plans[st.current_player()] = earlier
    assert bot.choose(st, random.Random(0)) == A.encode("PICK_AREA", other)


def test_two_round_candidates() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    st = _to(game.new_initial_state(), random.Random(4), lambda s: s.phase == PHASE_TR)
    pb = PlanSearchBot(cfg=PlanConfig(tasks=2, ahead=2))
    plans = pb.candidates(st)
    assert plans[0] == RoundPlan(st.round)
    two = [p for p in plans if p.then]
    assert two and all(len(p.then) == 1 and p.then[0].round > st.round for p in two)
    assert all(p.then[0].task == -1 or p.then[0].task != p.task for p in two)
    assert len(set(plans)) == len(plans)
    assert not any(p.then for p in PlanSearchBot(cfg=PlanConfig(tasks=2)).candidates(st))


def test_commit_bonus_keeps_scheduled_task_a_candidate() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    st = _to(game.new_initial_state(), random.Random(4), lambda s: s.phase == PHASE_TR)
    seat = st.current_player()
    pb = PlanSearchBot(cfg=PlanConfig(tasks=0, ahead=1, commit_bonus=2.0))
    due = st.task_row[-1]
    pb._chosen[seat] = RoundPlan(st.round - 1, then=(RoundPlan(st.round, task=due),))  # pyright: ignore[reportPrivateUsage]
    assert any(p.task == due for p in pb.candidates(st))


def test_two_round_plan_search_plays_legal_game() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    pb = PlanSearchBot(
        cfg=PlanConfig(playouts=2, areas=1, tasks=1, keep=1, ahead=1, commit_bonus=1.0)
    )
    bots = [StrategistBot(), pb]
    rng = random.Random(8)
    st = game.new_initial_state()
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
            continue
        a = bots[st.current_player()].choose(st, rng)
        assert a in st.legal_actions()
        st.apply_action(a)
    assert isinstance(st, LignumState) and len(st.final) == 2


def _planned_ctx(seed: int) -> tuple[LignumState, StrategistBot, int, int]:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    st = _to(game.new_initial_state(), random.Random(seed), lambda s: s.phase == PHASE_PK)
    seat = st.current_player()
    bot = StrategistBot()
    task = st.task_row[0]
    bot.plans[seat] = RoundPlan(st.round, task=-1, then=(RoundPlan(st.round + 1, task=task),))
    return st, bot, seat, task


def test_reserve_planned_adds_needs_for_scheduled_task() -> None:
    st, bot, seat, task = _planned_ctx(3)
    c = Ctx(st, seat, bot.w)  # flag off: choose() leaves Ctx.planned empty
    assert c.planned == () and all(n[3] != task for n in c.slot_plan().needs)
    c = Ctx(st, seat, bot.w)
    c.planned = bot._planned_tasks(c)  # pyright: ignore[reportPrivateUsage]
    assert c.planned == (task,)
    plan = c.slot_plan()
    for sl in c.planned_slots():
        assert sl.task == task
        covered = sl.slot in plan.slot_src or plan.storage_slot == sl
        assert covered or any(n[3] == task and n[0] == sl.kind for n in plan.needs)


def test_held_slots_keep_their_wood_before_planned_ones() -> None:
    st, bot, seat, _task = _planned_ctx(4)
    base = Ctx(st, seat, bot.w).slot_plan()
    c = Ctx(st, seat, bot.w)
    bot.plans[seat] = RoundPlan(
        st.round, task=-1, then=tuple(RoundPlan(st.round + 1, task=t) for t in st.task_row)
    )
    bot.reserve_planned = True
    c.planned = bot._planned_tasks(c)  # pyright: ignore[reportPrivateUsage]
    plan = c.slot_plan()
    for sl in c.open_slots():
        assert plan.slot_src.get(sl.slot) == base.slot_src.get(sl.slot)


def test_planned_task_dropped_once_held_or_taken_elsewhere() -> None:
    st, bot, seat, task = _planned_ctx(3)
    bot.reserve_planned = True
    st.task_row = tuple(t for t in st.task_row if t != task)
    assert bot._planned_tasks(Ctx(st, seat, bot.w)) == ()  # pyright: ignore[reportPrivateUsage]


def test_reserving_plan_search_plays_legal_game() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    pb = PlanSearchBot(cfg=PlanConfig(playouts=2, areas=1, tasks=1, keep=1, ahead=1, reserve=True))
    assert pb.strat.reserve_planned and pb.sim.reserve_planned
    bots = [pb, StrategistBot()]
    rng = random.Random(11)
    st = game.new_initial_state()
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
            continue
        a = bots[st.current_player()].choose(st, rng)
        assert a in st.legal_actions()
        st.apply_action(a)
    assert isinstance(st, LignumState) and len(st.final) == 2


def test_planned_task_value_ignores_its_own_reserved_wood() -> None:
    from lignum.bots.strategist import task_value

    st, bot, seat, task = _planned_ctx(3)
    plain = task_value(Ctx(st, seat, bot.w), task)
    c = Ctx(st, seat, bot.w)
    c.planned = (task,)
    assert task_value(c, task) == plain
