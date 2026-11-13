"""Tests for tools/replay.py (kingisdead backlog: the replayer /triage-report needs)."""

import io
import json
from pathlib import Path

import pytest

from tools import replay


def write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "r.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_replays_report_to_terminal(tmp_path: Path) -> None:
    report = {"game": "tic_tac_toe", "params": {}, "history": [0, 3, 1, 4, 2], "note": "x"}
    out = io.StringIO()
    assert replay.main([str(write(tmp_path, report)), "--steps"], out=out) == 0
    text = out.getvalue()
    assert "returns: [1.0, -1.0]" in text
    assert "   0       P0: 0" in text  # seats are labelled from 0


def test_reads_nested_export_and_bare_list(tmp_path: Path) -> None:
    nested = {"report_id": "a", "export": {"game": "tic_tac_toe", "history": [4]}}
    assert replay.main([str(write(tmp_path, nested))], out=io.StringIO()) == 0
    bare = write(tmp_path, [4, 0])
    assert replay.main([str(bare), "--game", "tic_tac_toe"], out=io.StringIO()) == 0


def test_illegal_action_reports_step(tmp_path: Path) -> None:
    out = io.StringIO()
    path = write(tmp_path, {"game": "tic_tac_toe", "history": [4, 4]})
    assert replay.main([str(path)], out=out) == 1
    assert "step 1: action 4 is illegal for P1" in out.getvalue()


def test_chance_steps_and_param_alias(tmp_path: Path) -> None:
    path = write(tmp_path, {"game": "kuhn_poker", "params": {"num_players": 2}, "history": [0, 1]})
    out = io.StringIO()
    assert replay.main([str(path), "--steps"], out=out) == 0
    assert "chance" in out.getvalue()


@pytest.mark.parametrize(
    "data",
    [{"history": [1]}, {"game": "no_such_game", "history": []}, {"game": "x", "history": ["a"]}],
)
def test_bad_input_exits_2(tmp_path: Path, data: object) -> None:
    assert replay.main([str(write(tmp_path, data))], out=io.StringIO()) == 2
