"""Tests for tools/play_text.py: non-interactive play and a scripted human seat."""

import io

from tools import play_text


def run(argv: list[str], stdin: str = "") -> tuple[int, str]:
    out = io.StringIO()
    code = play_text.main(argv, out=out, inp=io.StringIO(stdin))
    return code, out.getvalue()


def test_auto_plays_a_full_seeded_game() -> None:
    code, text = run(["--players", "3", "--seed", "5", "--auto"])
    assert code == 0
    assert "returns: [" in text
    assert "P0" in text and "P2" in text
    assert "Player 1" not in text
    assert run(["--players", "3", "--seed", "5", "--auto"]) == (code, text)  # deterministic


def test_human_seat_gets_legal_actions_and_can_quit() -> None:
    code, text = run(["--players", "2", "--seed", "1", "--human", "0"], stdin="nope\n99999\nq\n")
    assert code == 1
    assert "P0 to act. Legal actions:" in text
    assert "not a legal action id" in text


def test_human_seat_accepts_an_action_id() -> None:
    # the first legal action offered is applied; then quit at the next prompt
    _, first = run(["--seed", "1", "--human", "0"], stdin="q\n")
    legal_id = int(first.split("Legal actions:\n")[1].split()[0])
    code, text = run(["--seed", "1", "--human", "0"], stdin=f"{legal_id}\nq\n")
    assert code == 1
    assert f": {legal_id} (" in text


def test_bad_arguments_exit_2() -> None:
    assert run(["--players", "9", "--auto"])[0] == 2
    assert run(["--human", "5"])[0] == 2


def test_bot_hidden_picks_are_not_printed_before_reveal() -> None:
    _, text = run(["--players", "3", "--seed", "5", "--auto"])
    lines = text.splitlines()
    assert any(line.endswith(": picked") for line in lines)
    # only the three public setup picks (SP, R-015) name their area
    assert sum("PICK_AREA" in line for line in lines) == 3
