"""Ledger sub-components, funnels and tools.breakdown_history."""

import io
import json

import pytest

from tests import harness as H
from tools import breakdown_history as BH
from tools.ledger import FUNNEL_KEYS, SPENDING_KEYS, WINTER_KEYS, Ledger
from tools.replay import Replay, load_game
from tools.tournament import main, play_game_record, run_tournament


def _record(players: int, seed: str):
    game = load_game(Replay(game="lignum", params={"players": players, "joinery": True}))
    seats = ["heuristic" if s % 2 == 0 else "random" for s in range(players)]
    return game, play_game_record(game, seats, seed)


@pytest.mark.parametrize("players", [2, 3])
def test_sub_components_sum_to_parents(players) -> None:
    for seed in ("a", "b"):
        _, rec = _record(players, f"sub:{players}:{seed}")
        for s in range(players):
            d = rec.detail[s]
            assert sum(d["winter"].values()) == rec.breakdown[s]["winter"]
            assert sum(d["spending"].values()) == rec.breakdown[s]["spending"]
            assert set(d["winter"]) == set(WINTER_KEYS)
            assert set(d["spending"]) == set(SPENDING_KEYS)
            assert set(rec.funnels[s]) == set(FUNNEL_KEYS)
            f = rec.funnels[s]
            assert f["tasks_taken"] >= f["tasks_completed"] + f["tasks_incomplete"]
            assert f["joinery_sold"] <= f["joinery_placed"]
            info = d["winter_info"]
            assert info["feed_from_stock"] + info["feed_missing_units"] == info["feed_required"]
            assert info["heat_from_stock"] + info["heat_missing_units"] == info["heat_required"]


def test_winter_shortfall_split_and_forced_loan_on_a_constructed_state() -> None:
    state = H.play_setup({"players": 2, "joinery": True}, seed=1)
    t = state._tables()
    ledger = Ledger(state)
    state.round = t.winter_rounds[0]
    state.wint = (0, 1)
    state.food = (0, 0)
    state.money = (50, 50)
    state.store = ((0, 0, 0),) * 2
    ledger.run(_start_settle(state))
    # P0 has no food and no heat stock: the shortfall dollars are what P0 pays, split by kind
    p = ledger.detail()
    for s in range(2):
        assert p[s]["winter"]["feed_shortfall"] <= 0
        assert sum(p[s]["winter"].values()) == ledger.parts[s]["winter"]
        assert p[s]["winter_info"]["shortfall_price"] == t.shortfall_unit


def _start_settle(state):
    def step() -> None:
        state.pay, state.w_turn = 0, 0
        state._settle()

    return step


def test_funnels_count_on_synthetic_actions() -> None:
    state = H.play_setup({"players": 2, "joinery": True}, seed=1)
    ledger = Ledger(state)
    assert all(v == 0 for v in ledger.funnels()[0].values())
    ledger._count[0]["joinery_placed"] = 2
    ledger._count[0]["joinery_sold"] = 1
    assert ledger.funnels()[0]["joinery_unsold"] == 1


def test_tournament_reports_detail_and_funnels() -> None:
    r = run_tournament(["random", "random"], 2, 2, seed=3)
    b = r["bots"]["random"]
    assert sum(b["mean_detail"]["spending"].values()) == pytest.approx(
        b["mean_breakdown"]["spending"]
    )
    assert sum(b["mean_detail"]["winter"].values()) == pytest.approx(b["mean_breakdown"]["winter"])
    assert set(b["mean_funnel"]) == set(FUNNEL_KEYS)
    out = io.StringIO()
    assert main(["--bots", "random,random", "--games", "1"], out) == 0
    assert "funnels" in out.getvalue() and "sub-components" in out.getvalue()


def test_breakdown_history_on_synthetic_complete_and_partial(tmp_path) -> None:
    game, rec = _record(2, "hist:1")
    params = {"num_players": 2, "joinery": True}
    full = tmp_path / "full.json"
    full.write_text(json.dumps({"game": "lignum", "params": params, "history": rec.history,
                                "seats": ["human", "random"], "seed": 1, "salt": "x"}))  # fmt: skip
    part = tmp_path / "part.json"
    part.write_text(json.dumps({"game": "lignum", "params": params,
                                "history": rec.history[:60], "seed": 2, "salt": "y"}))  # fmt: skip
    out = io.StringIO()
    assert BH.main([str(tmp_path)], out) == 0
    text = out.getvalue()
    assert "2 distinct game(s), 1 complete" in text
    assert "part.json: 60 actions, PARTIAL" in text
    assert "mean over 2 seat(s) of 1 complete" in text
    a = BH.analyse_file(full)
    assert a.complete and a.final == [int(x) for x in rec.final]
    assert [sum(b.values()) for b in a.breakdown] == a.final
    # only partial games: say so, still succeed
    out = io.StringIO()
    assert BH.main([str(part), "--partial"], out) == 0
    assert "No complete game" in out.getvalue() and "PARTIAL, 60 actions" in out.getvalue()
    assert BH.main([str(tmp_path / "missing.json")], io.StringIO()) == 2


def test_unattributed_money_from_unknown_caller_raises() -> None:
    import lignum.game as engine

    state = H.play_setup({"players": 2}, seed=1)
    ledger = Ledger(state)

    def mystery() -> None:
        state.money = engine._bump(state.money, 0, 3)  # pyright: ignore[reportPrivateUsage]

    ledger.run(mystery)
    assert ledger.parts[0]["unattributed"] == 3
    with pytest.raises(AssertionError, match="unattributed"):
        ledger.breakdown()
    with pytest.raises(AssertionError, match="unattributed"):
        ledger.detail()


def test_overlapping_ledger_runs_raise() -> None:
    state = H.play_setup({"players": 2}, seed=1)
    ledger = Ledger(state)
    with pytest.raises(RuntimeError, match="overlaps"):
        ledger.run(lambda: ledger.run(lambda: None))


def test_payment_after_loan_is_not_loan_proceeds() -> None:
    state = H.play_setup({"players": 2}, seed=1)
    ledger = Ledger(state)
    assert ledger._classify("_acquire", "TAKE_LOAN", 0, -4) == [  # pyright: ignore[reportPrivateUsage]
        ("spending", -4)
    ]
    assert ledger._classify("_apply_travel", "TAKE_LOAN", 0, 10)[0][0] == "loan_proceeds"  # pyright: ignore[reportPrivateUsage]
