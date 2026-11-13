"""tools.collect_games: schema, determinism, reserved seeds, agreement with the tournament path."""

import json
from pathlib import Path

import pytest

from tools.collect_games import (
    COMPONENTS,
    FEATURE_NAMES,
    PART_NAMES,
    collect,
    main,
    parse_matchup,
    read_game,
    schedule,
)
from tools.tournament import play_game_record

MATCHUP = "heuristic-v4,heuristic-v2:2"


@pytest.fixture(scope="module")
def data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("bot_games")
    collect([MATCHUP], out, seed_start=200, workers=2)
    return out


def test_parse_matchup_and_rotation(tmp_path: Path) -> None:
    assert parse_matchup("heuristic-v4:max_sawyers=2,heuristic-v2:7") == (
        ["heuristic-v4:max_sawyers=2", "heuristic-v2"],
        7,
    )
    with pytest.raises(ValueError):
        parse_matchup("heuristic-v4,heuristic-v2")  # no count
    jobs = schedule([MATCHUP, "heuristic-v2,random:1"], 200, tmp_path)
    assert [j.seed for j in jobs] == [200, 201, 202]
    assert jobs[0].seats == ("heuristic-v4", "heuristic-v2")
    assert jobs[1].seats == ("heuristic-v2", "heuristic-v4")  # odd seed swaps


def test_reserved_seeds_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reserved"):
        schedule([MATCHUP], 100, tmp_path)
    assert main(["--matchups", MATCHUP, "--seed-start", "150", "--out", str(tmp_path)]) == 2
    assert not list(tmp_path.glob("*.jsonl.gz"))


def test_schema_and_footer(data: Path) -> None:
    manifest = json.loads((data / "manifest.json").read_text())
    assert manifest["schema"] == 1 and manifest["games_new"] == 2
    assert set(manifest["bot_yaml_sha256"]) == {"heuristic-v4", "heuristic-v2"}
    header, rows, footer = read_game(data / "200.jsonl.gz")
    assert header["feature_names"] == list(FEATURE_NAMES)
    assert header["part_names"] == list(PART_NAMES)
    assert header["components"] == list(COMPONENTS)
    assert len(rows) == footer["rows"] == footer["decisions"] > 100
    assert [r["d"] for r in rows] == list(range(len(rows)))
    for row in rows:
        assert row["p"] in (0, 1)
        assert len(row["f"]) == len(row["v"]) == len(row["acc"]) == 2
        assert all(len(f) == len(FEATURE_NAMES) for f in row["f"])
        assert all(len(v) == len(PART_NAMES) for v in row["v"])
        assert all(len(a) == len(COMPONENTS) for a in row["acc"])
    for seat in range(2):
        assert sum(footer["breakdown"][seat]) == footer["final"][seat]
        # the money accrued so far never exceeds what the final breakdown ends with by construction
        # of the ledger: the last row's accrued start money is the footer's
        assert rows[-1]["acc"][seat][0] == footer["breakdown"][seat][0]
    top = max(footer["final"])
    assert footer["winner"] == [i for i, f in enumerate(footer["final"]) if f == top]


def test_matches_tournament_path(data: Path) -> None:
    from tools.tournament import Replay, load_game

    game = load_game(
        Replay(
            game="lignum",
            params={"players": 2, "joinery": True, "returns": "win_loss", "easy_winter": False},
        )
    )
    for seed, seats in (
        (200, ["heuristic-v4", "heuristic-v2"]),
        (201, ["heuristic-v2", "heuristic-v4"]),
    ):
        rec = play_game_record(game, seats, str(seed))
        _, _, footer = read_game(data / f"{seed}.jsonl.gz")
        assert footer["final"] == rec.final
        assert footer["actions"] == len(rec.history)


def test_deterministic_resumable_and_sampled(data: Path, tmp_path: Path) -> None:
    collect([MATCHUP], tmp_path, seed_start=200, workers=1, games_cap=1)
    a = read_game(data / "200.jsonl.gz")
    b = read_game(tmp_path / "200.jsonl.gz")
    assert a == b
    again = collect([MATCHUP], data, seed_start=200, workers=1)
    assert again["games_new"] == 0 and again["games_skipped"] == 2  # resumable
    sampled = tmp_path / "every"
    collect([MATCHUP], sampled, seed_start=200, every=10, workers=1, games_cap=1)
    _, rows, footer = read_game(sampled / "200.jsonl.gz")
    assert [r["d"] for r in rows] == list(range(0, footer["decisions"], 10))
    assert footer["final"] == a[2]["final"]  # sampling does not change the game
