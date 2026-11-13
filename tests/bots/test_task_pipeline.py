"""Task pipeline of heuristic-v2 (Phase 7 unit 1d): gated by profile keys, legal, planner bounds."""

from __future__ import annotations

import random

import pyspiel

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots.heuristic import HeuristicBot
from lignum.bots.tasks import TaskPlanner, held_assessments, seq_index
from lignum.bots.weights import load_profile
from lignum.components import load_components
from lignum.game import PHASE_TR


def test_pipeline_keys_only_in_v2() -> None:
    assert load_profile("heuristic-v2")["task_pipeline"] == 1
    for name in ("heuristic", "heuristic-v1"):
        w = load_profile(name)
        assert "task_pipeline" not in w
        assert "task_plan_weight" not in w["value"]


def test_seq_index_skips_first_winter() -> None:
    game = pyspiel.load_game("python_lignum(players=2)")
    t = game.new_initial_state()._tables()  # pyright: ignore[reportPrivateUsage]
    assert [seq_index(t, r) for r in (1, 2, 3, 5, 6, 7, 8)] == [1, 2, 3, 4, 5, 6, 7]


def test_planner_probabilities_in_range_and_games_play() -> None:
    game = pyspiel.load_game("python_lignum(players=2)")
    bot = HeuristicBot(profile="heuristic-v2")
    tasks = load_components().tasks
    rng = random.Random(3)
    state = game.new_initial_state()
    seen = 0
    while not state.is_terminal():
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(acts, weights=probs)[0])
            continue
        if state.phase == PHASE_TR and state.task_row:  # offered cards get a chance in [0, 1]
            planner = TaskPlanner(state._tables(), bot.vw)  # pyright: ignore[reportPrivateUsage]
            seat = state.current_player()
            for ti in state.task_row:
                a = planner.assess(state, seat, [], ti)[ti]
                assert 0.0 <= a.prob <= 1.0
                seen += 1
        seat = state.current_player()
        for a in held_assessments(
            TaskPlanner(state._tables(), bot.vw),
            state,
            seat,
            tasks,  # pyright: ignore[reportPrivateUsage]
        ).values():
            assert 0.0 <= a.prob <= 1.0
        state.apply_action(bot.choose(state.clone(), rng))
    assert seen > 0
