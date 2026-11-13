"""tools.tournament: determinism, seat rotation, Wilson CI."""

import io

import pytest

from tools.tournament import main, run_tournament, wilson, winner_shares


def test_wilson_bounds() -> None:
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi
    assert wilson(0, 0) == (0.0, 1.0)
    assert 0.0 <= wilson(10, 10)[0] < 1.0
    assert wilson(10, 10)[1] == pytest.approx(1.0)


def test_winner_shares_split_ties() -> None:
    assert winner_shares([1.0, 0.0]) == [1.0, 0.0]
    assert winner_shares([1.0, 1.0, 0.0]) == [0.5, 0.5, 0.0]


def test_random_vs_random_deterministic_and_rotated() -> None:
    a = run_tournament(["random", "random"], 2, 2, seed=3)
    b = run_tournament(["random", "random"], 2, 2, seed=3)
    assert a == b
    assert a["bots"]["random"]["games"] == 4  # both seats counted
    assert main(["--bots", "random"], io.StringIO()) == 2  # wrong bot count


@pytest.mark.slow
def test_heuristic_vs_random_runs(tmp_path) -> None:
    path = tmp_path / "out.json"
    out = io.StringIO()
    code = main(
        ["--players", "2", "--games", "4", "--seed", "1", "--bots", "heuristic,random",
         "--json", str(path)],
        out,
    )  # fmt: skip
    assert code == 0
    assert path.exists()
    assert "heuristic" in out.getvalue()
    rr = run_tournament(["heuristic", "random", "mcts-fast"][:2], 2, 2, 1, "round-robin")
    assert rr["bots"]["heuristic"]["games"] == 2


def test_final_dollar_stats_reported() -> None:
    r = run_tournament(["random", "random"], 2, 2, seed=3)
    b = r["bots"]["random"]
    assert {"mean_dollars", "median_dollars", "mean_margin"} <= set(b)
    assert b["mean_margin"] == pytest.approx(0.0)  # both seats are the same bot: margins cancel


@pytest.mark.parametrize("players", [2, 3, 4])
def test_breakdown_sums_to_engine_final_dollars(players) -> None:
    from tools.ledger import COMPONENTS
    from tools.replay import Replay, load_game
    from tools.tournament import play_game_record

    game = load_game(Replay(game="lignum", params={"players": players, "joinery": True}))
    for seed in ("a", "b", "c"):
        seats = ["heuristic" if s % 2 == 0 else "random" for s in range(players)]
        rec = play_game_record(game, seats, f"ledger:{players}:{seed}")
        for s in range(players):
            assert set(rec.breakdown[s]) == set(COMPONENTS)
            assert sum(rec.breakdown[s].values()) == rec.final[s]
            assert rec.breakdown[s]["unattributed"] == 0
            assert rec.breakdown[s]["loan_repayment"] <= 0
            assert rec.breakdown[s]["winter"] <= 0


def test_report_has_breakdown_and_timings() -> None:
    r = run_tournament(["random", "random"], 2, 1, seed=3, timings=True)
    b = r["bots"]["random"]
    assert sum(b["mean_breakdown"].values()) == pytest.approx(b["mean_dollars"])
    assert b["ms_per_move"]["moves"] > 0
    assert b["ms_per_move"]["mean"] >= 0 and b["ms_per_move"]["p90"] >= 0
    out = io.StringIO()
    assert main(["--bots", "random,random", "--games", "1"], out) == 0
    assert "by component" in out.getvalue()
    assert "ms per move" in out.getvalue()


def test_no_time_cap_sim_capped_mcts_is_reproducible() -> None:
    from server.bots import parse_bot_spec
    from tools.replay import Replay, load_game
    from tools.tournament import play_game_record

    assert parse_bot_spec("mcts:3", time_cap=False).time_budget is None  # type: ignore[attr-defined]
    assert parse_bot_spec("mcts:3").time_budget == 10.0  # type: ignore[attr-defined]
    assert parse_bot_spec("mcts-fast", time_cap=False).time_budget is None  # type: ignore[attr-defined]
    assert parse_bot_spec("mcts-fast").time_budget == 2.0  # type: ignore[attr-defined]
    game = load_game(Replay(game="lignum", params={"players": 2, "joinery": True}))
    seats = ["mcts:2", "random"]
    a = play_game_record(game, seats, "repro:1", time_cap=False)
    b = play_game_record(game, seats, "repro:1", time_cap=False)
    assert a.history == b.history
    assert a.final == b.final


def test_ledger_splits_final_sale_components_on_a_constructed_state() -> None:
    """Joinery/wood, Office/tasks split of the final-sale payouts (random and heuristic play
    never reach them), checked against hand-computed prices from the tables."""
    from lignum.components import load_components
    from tests import harness as H
    from tools.ledger import Ledger

    state = H.play_setup({"players": 2, "joinery": True}, seed=1)
    t = state._tables()
    state.round = t.winter_rounds[1]
    state.wint = (0, 1)
    state.joiners = (2, 0)
    state.joinery_wood = ((0, 1, 2), (-1, -1, -1))  # P0: slot 2 uncovered by joiners (R-082)
    state.sale = ((1, 0, 0), (0, 0, 0))  # P0: one unmilled firewood disk in the sale area
    office = t.building_ids.index("office")
    state.held_buildings = ((office,), ())
    tid = 0
    task = load_components().tasks[tid]
    state.held_tasks = ((tid,), ())
    full = (1 << len(task.requirements)) - 1
    state.filled = tuple(full if i == tid else 0 for i in range(len(state.filled)))
    ledger = Ledger(state)
    ledger.run(state._end_winter)
    assert state.is_terminal()
    p0 = ledger.breakdown()[0]
    bonus = t.joinery_bonus
    assert p0["joinery"] == sum(t.wood_price[k][1] + bonus for k in (0, 1))
    assert p0["wood_sales"] == t.wood_price[0][0] + t.dry_bonus[0]
    assert p0["office"] == 1  # one held task card
    assert p0["tasks"] == task.reward
    assert p0["unattributed"] == 0
    assert sum(p0.values()) == state.final[0]


def test_override_specs_parse_and_apply() -> None:
    from lignum.bots.heuristic import HeuristicBot
    from tools.tournament import make_bot, parse_overrides, split_bots

    assert parse_overrides("heuristic-v4") == ("heuristic-v4", {})
    assert parse_overrides("heuristic-v4:max_sawyers=2;value.x=0.5,saw_target=3") == (
        "heuristic-v4",
        {"max_sawyers": 2, "value.x": 0.5, "saw_target": 3},
    )
    assert split_bots("heuristic-v4:max_sawyers=2,saw_target=3,heuristic-v2,random") == [
        "heuristic-v4:max_sawyers=2;saw_target=3",
        "heuristic-v2",
        "random",
    ]
    bot = make_bot("heuristic-v4:max_sawyers=2,saw_target=3,woodcutter_cap.hw=1")
    assert isinstance(bot, HeuristicBot)
    assert bot.w["max_sawyers"] == 2 and bot.w["saw_target"] == 3
    assert bot.w["woodcutter_cap"]["hw"] == 1
    base = make_bot("heuristic-v4")
    assert base.w["saw_target"] != 3 or base.w["max_sawyers"] != 2  # profile itself untouched
    for bad in (
        "heuristic-v4:nope=1",
        "heuristic-v4:max_sawyers",
        "random:a=1",
        "heuristic-v4:value.nope=1",
    ):
        with pytest.raises(ValueError):
            make_bot(bad)
    assert make_bot("random") is not None


def test_override_seats_play(tmp_path) -> None:
    out = io.StringIO()
    code = main(
        ["--players", "2", "--games", "1", "--seed", "1", "--bots",
         "heuristic-v4:max_sawyers=2,saw_target=3,mill_saws=1,heuristic-v2"],
        out,
    )  # fmt: skip
    assert code == 0
