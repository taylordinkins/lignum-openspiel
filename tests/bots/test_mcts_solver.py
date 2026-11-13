"""Phase 7 unit 5c: own-turn solver in MCTS rollouts and tree prior (knobs, seats, legality)."""

from __future__ import annotations

import random

import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots.mcts import ISMCTSBot
from lignum.bots.weights import load_profile
from server.bots import BOTS, SOLVER_ROLLOUT, mcts_fast, parse_bot_spec


def _trace(bot: ISMCTSBot, seed: int, plies: int, players: int = 2) -> list[int]:
    game = pyspiel.load_game(f"python_lignum(players={players})")
    state = game.new_initial_state()
    chance = random.Random(seed)
    rng = random.Random(seed)
    out: list[int] = []
    while len(out) < plies and not state.is_terminal():
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(acts, probs)[0])
            continue
        a = bot.choose(state, rng)
        assert a in state.legal_actions()
        state.apply_action(a)
        out.append(a)
    return out


def _small(**kw: object) -> ISMCTSBot:
    return ISMCTSBot(simulations=4, rollout="heuristic", rollout_depth=8, **kw)  # type: ignore[arg-type]


def test_knobs_default_off_and_existing_seats_unchanged() -> None:
    for name in ("mcts", "mcts-fast"):
        bot = BOTS[name]
        assert isinstance(bot, ISMCTSBot)
        assert not bot.solver_rollout and not bot.solver_tree and bot.policy_profile is None
        s = bot._search  # pyright: ignore[reportPrivateUsage]
        assert s.heuristic is s.prior is bot._fallback  # pyright: ignore[reportPrivateUsage]
    assert "mcts-solver" not in BOTS  # tournament/CLI only until unit 6


def test_spec_parsing_and_sim_cap() -> None:
    b = parse_bot_spec("mcts-solver", time_cap=False)
    assert isinstance(b, ISMCTSBot) and b.simulations == 60 and b.time_budget is None
    assert b.solver_rollout and b.solver_tree and b.policy_profile == "heuristic-v6"
    assert parse_bot_spec("mcts-solver:7").simulations == 7  # type: ignore[attr-defined]
    assert parse_bot_spec("mcts-solver:7").time_budget == 2.0  # type: ignore[attr-defined]
    f = parse_bot_spec("mcts-fast:7", time_cap=False)
    assert isinstance(f, ISMCTSBot) and f.simulations == 7 and not f.solver_rollout
    with pytest.raises(ValueError):
        parse_bot_spec("mcts-solver:x")


def test_knobs_respected() -> None:
    full = load_profile("heuristic-v6")["solver"]
    on = _small(
        policy_profile="heuristic-v6",
        solver_rollout=True,
        rollout_solver={"beam": 2, "node_cap": 9},
    )
    roll = on._search.heuristic  # pyright: ignore[reportPrivateUsage]
    assert roll is not None and roll is not on._fallback  # pyright: ignore[reportPrivateUsage]
    assert roll.w["solver"]["beam"] == 2 and roll.w["solver"]["node_cap"] == 9
    assert roll.w["solver"]["max_depth"] == full["max_depth"]
    assert on._search.prior is on._fallback  # pyright: ignore[reportPrivateUsage]  # tree off
    tree = _small(policy_profile="heuristic-v6", solver_tree=True)
    assert tree._search.heuristic is tree._fallback  # pyright: ignore[reportPrivateUsage]
    p = tree._search.prior  # pyright: ignore[reportPrivateUsage]
    assert p is not None and p.w["solver"]["beam"] == full["beam"]
    assert SOLVER_ROLLOUT["node_cap"] < full["node_cap"]


@pytest.mark.parametrize("rollout,tree", [(True, False), (False, True), (True, True)])
def test_legal_and_deterministic(rollout: bool, tree: bool) -> None:
    def bot() -> ISMCTSBot:
        return _small(
            policy_profile="heuristic-v6",
            solver_rollout=rollout,
            solver_tree=tree,
            rollout_solver=SOLVER_ROLLOUT,
        )

    assert _trace(bot(), 3, 30) == _trace(bot(), 3, 30)


def test_full_2p_game_plays_legally_with_small_sim_cap() -> None:
    bot = mcts_fast(2, time_cap=False, solver=True)
    game = pyspiel.load_game("python_lignum(players=2)")
    state = game.new_initial_state()
    chance = random.Random(5)
    rng = random.Random(5)
    while not state.is_terminal():
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(acts, probs)[0])
            continue
        a = bot.choose(state, rng)
        assert a in state.legal_actions()
        state.apply_action(a)


def test_solver_knob_needs_enabled_solver_profile() -> None:
    for kw in ({"solver_rollout": True}, {"solver_tree": True}):
        with pytest.raises(ValueError, match="solver"):
            ISMCTSBot(policy_profile="heuristic-v4", **kw)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="solver"):
            ISMCTSBot(**kw)  # type: ignore[arg-type]


@pytest.mark.parametrize("spec", ["mcts-fast:0", "mcts-solver:0"])
def test_zero_sims_rejected(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_bot_spec(spec)


def test_heuristic_planner_follows_game_tables() -> None:
    from lignum.bots import HeuristicBot
    from tests.harness import load_game

    bot = HeuristicBot(profile="heuristic-v4")
    s2 = load_game(players=2, joinery=True).new_initial_state()
    s3 = load_game(players=3, joinery=True).new_initial_state()
    p2 = bot._plan(s2)  # pyright: ignore[reportPrivateUsage]
    assert bot._plan(s2) is p2  # pyright: ignore[reportPrivateUsage]
    assert bot._plan(s3) is not p2  # pyright: ignore[reportPrivateUsage]
