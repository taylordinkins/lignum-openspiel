"""Canary for docs/OPENSPIEL_NOTES.md: C++ MCTS/IS-MCTS segfault on Python games in OpenSpiel 2.0.2.

The bots run in a subprocess. The test fails once they stop crashing, so an OpenSpiel upgrade
flags it: update the notes and reconsider the C++ bots (PLAN.md D22).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CPP_BOT_SCRIPT = """
import sys, pyspiel
import lignum.game
game = pyspiel.load_game("python_lignum")
state = game.new_initial_state()
steps = 0
while not state.is_terminal() and (steps < 4 or state.is_chance_node()):
    state.apply_action(state.legal_actions()[0])
    steps += 1
evaluator = pyspiel.RandomRolloutEvaluator(1, 0)
if sys.argv[1] == "ismcts":
    bot = pyspiel.ISMCTSBot(0, evaluator, 2.0, 10)
else:
    bot = pyspiel.MCTSBot(game, evaluator, 2.0, 10, 100, False, 0, False)
print(bot.step(state))
"""


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["ismcts", "mcts"])
def test_cpp_bots_crash_on_python_games(kind: str) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", CPP_BOT_SCRIPT, kind],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PYTHONPATH": str(root), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == -11, (result.returncode, result.stdout, result.stderr[-500:])
