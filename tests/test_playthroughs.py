"""Golden playthroughs (PLAN.md section 6 item 5): replay, compare the trace, check invariants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum.invariants import check_invariants
from tools.make_playthroughs import OUT_DIR, digest

FILES = sorted(OUT_DIR.glob("*.json"))


def test_there_are_four_goldens() -> None:
    assert len(FILES) == 4


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_playthrough_replays_exactly(path: Path) -> None:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    game = pyspiel.load_game("python_" + data["game"], data["params"])
    state = game.new_initial_state()
    assert check_invariants(state) == []
    history, trace = data["history"], data["trace"]
    assert len(history) == len(trace)
    for i, (action, row) in enumerate(zip(history, trace, strict=True)):
        player = state.current_player()
        got = [player, action, state.action_to_string(player, action)]
        assert got == row[:3], f"{path.name} step {i}: expected {row[:3]}, got {got}"
        assert action in state.legal_actions(), f"{path.name} step {i}: {action} is illegal"
        state.apply_action(action)
        assert check_invariants(state) == [], f"{path.name} step {i}"
        assert digest(state) == row[3], f"{path.name} step {i}: state digest differs"
    assert state.is_terminal()
    assert [float(r) for r in state.returns()] == data["returns"]
    assert list(state.final) == data["final_dollars"]  # type: ignore[attr-defined]
