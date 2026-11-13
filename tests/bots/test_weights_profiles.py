"""Phase 7 unit 1a: bot weights live in YAML profiles; heuristic-v1 is the frozen Phase 6 bot."""

from __future__ import annotations

import ast
import json
import pathlib
import random
from typing import Any

import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots import HeuristicBot
from lignum.bots import value as value_module
from lignum.bots.value import value
from lignum.bots.weights import BOTS_DIR, load_profile, profile_path, value_weights

GOLDEN: dict[str, Any] = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "heuristic_golden.json").read_text()
)


def _replay(bot: HeuristicBot, seed: int) -> tuple[list[int], list[list[Any]], list[float]]:
    """Replay the 2p game the way the fixture was recorded (heuristic at both seats)."""
    game = pyspiel.load_game("python_lignum(players=2,returns=margin)")
    state = game.new_initial_state()
    chance = random.Random(seed)
    rngs = [random.Random(f"{seed}:{i}") for i in range(2)]
    acts: list[int] = []
    vals: list[list[Any]] = []
    while not state.is_terminal():
        if state.is_chance_node():
            a, p = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(a, p)[0])
            continue
        if len(acts) % 40 == 0:
            vals.append([len(acts), [value(state, 0, bot.vw), value(state, 1, bot.vw)]])
        a = bot.choose(state, rngs[state.current_player()])
        acts.append(a)
        state.apply_action(a)
    return acts, vals, list(state.returns())


# The "heuristic" case is expected to change once tuning starts (the golden then no longer applies
# to it); the "heuristic-v1" case is the real guard that the frozen bot never changes.
@pytest.mark.parametrize("profile", ["heuristic", "heuristic-v1"])
@pytest.mark.parametrize("seed", [3, 11, 29])
def test_profile_matches_pre_refactor_games(profile: str, seed: int) -> None:
    rec = GOLDEN[str(seed)]
    acts, vals, returns = _replay(HeuristicBot(profile=profile), seed)
    assert acts == rec["actions"]
    assert returns == rec["returns"]
    assert [v[0] for v in vals] == [v[0] for v in rec["values"]]
    for got, want in zip(vals, rec["values"], strict=True):
        assert got[1] == pytest.approx(want[1], abs=1e-9)


def test_value_takes_explicit_weights() -> None:
    game = pyspiel.load_game("python_lignum(players=2)")
    state = game.new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    bot = HeuristicBot()
    for _ in range(120):
        if state.is_terminal():
            break
        state.apply_action(bot.choose(state, random.Random(1)))
    # The two profiles are identical today; "heuristic" is expected to diverge once tuning starts
    # (then drop this line), "heuristic-v1" is frozen.
    assert value_weights("heuristic-v1") == value_weights("heuristic")
    assert value(state, 0, value_weights("heuristic-v1")) == value(state, 0)
    w = dict(value_weights())
    w["joiner_income_discount"] = 0.0
    w["sale_discount"] = 0.0
    w["upstream_discount"] = 0.0
    w["dry_discount"] = 0.0
    w["river_discount"] = 0.0
    assert value(state, 0, w) != value(state, 0)


def test_value_module_has_no_numeric_tunables() -> None:
    tree = ast.parse(pathlib.Path(value_module.__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            val = node.value
            assert not (isinstance(val, ast.Constant) and isinstance(val.value, int | float)), (
                f"module-level numeric constant at line {node.lineno}"
            )


def test_v1_has_same_keys_as_working_copy() -> None:
    assert (BOTS_DIR / "heuristic_v1.yaml").exists()
    work, v1 = load_profile("heuristic"), load_profile("heuristic-v1")

    def keys(d: Any, prefix: str = "") -> set[str]:
        out: set[str] = set()
        if isinstance(d, dict):
            for k, v in d.items():
                out.add(prefix + str(k))
                out |= keys(v, prefix + str(k) + ".")
        return out

    assert keys(work) == keys(v1)
    assert "value" in work


def test_two_profiles_do_not_interfere() -> None:
    a, b = HeuristicBot(profile="heuristic"), HeuristicBot(profile="heuristic-v1")
    assert a.vw is not b.vw


def test_profiles_are_read_only() -> None:
    w = load_profile("heuristic-v1")
    with pytest.raises(TypeError):
        w["value"]["x"] = 1  # type: ignore[index]
    with pytest.raises(TypeError):
        w["new"] = 1  # type: ignore[index]


def test_profile_path_maps_dash_and_dot() -> None:
    assert profile_path("heuristic-v1").name == "heuristic_v1.yaml"
    assert profile_path("a.b-c").name == "a_b_c.yaml"


def test_mcts_profile_selects_value_weights() -> None:
    from unittest.mock import patch

    from lignum.bots import mcts as mcts_module
    from lignum.bots.mcts import ISMCTSBot

    default = ISMCTSBot(simulations=2)
    assert default.vw is value_weights("heuristic")
    assert default._fallback.vw is default.vw  # pyright: ignore[reportPrivateUsage]
    bot = ISMCTSBot(simulations=2, profile="heuristic-v1")
    assert bot.vw is value_weights("heuristic-v1")
    assert bot._fallback.vw is bot.vw  # pyright: ignore[reportPrivateUsage]
    game = pyspiel.load_game("python_lignum(players=2)")
    state = game.new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    seen: list[Any] = []
    real = mcts_module.value

    def spy(st: Any, seat: int, w: Any = None) -> float:
        seen.append(w)
        return real(st, seat, w)

    with patch.object(mcts_module, "value", spy):
        bot.choose(state, random.Random(0))
    assert seen
    assert all(w is bot.vw for w in seen)


def _keys(d: Any, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for k, v in d.items():
        out.add(prefix + k)
        if hasattr(v, "items"):
            out |= _keys(v, prefix + k + ".")
    return out


def test_heuristic_v2_profile_extends_v1() -> None:
    v1, v2 = load_profile("heuristic-v1"), load_profile("heuristic-v2")
    assert _keys(v1) <= _keys(v2)
    assert v2["provision"] == 1 and "provision" not in v1
    assert "heat_full_weight" in v2["value"] and "heat_full_weight" not in v1["value"]
    bot = HeuristicBot(profile="heuristic-v2")
    assert bot.w is v2


def test_heuristic_v2_registered_and_plays() -> None:
    from server.bots import BOTS, is_valid_seat_type

    assert is_valid_seat_type("heuristic-v2") and "heuristic-v2" in BOTS
    game = pyspiel.load_game("python_lignum(players=2,returns=margin)")
    state = game.new_initial_state()
    chance, rng = random.Random(5), random.Random("5:b")
    while not state.is_terminal():
        if state.is_chance_node():
            a, p = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(a, p)[0])
        else:
            a = BOTS["heuristic-v2"].choose(state, rng)
            assert a in state.legal_actions()
            state.apply_action(a)
