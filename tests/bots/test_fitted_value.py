"""Phase 7 unit 3b: the fitted value (lignum.bots.fitted), shared features, heuristic-v5 seat."""

from __future__ import annotations

import gzip
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyspiel
import pytest
import yaml

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots import bot_candidates
from lignum.bots.features import FEATURE_NAMES, features
from lignum.bots.fitted import COMPONENTS
from lignum.bots.value import value, value_parts
from lignum.bots.weights import BOTS_DIR, load_profile, value_weights
from lignum.game import LignumState
from lignum.rules import CRAFT_ORDER
from tools.collect_games import collect
from tools.tournament import Replay, load_game, play_game_record

ROOT = BOTS_DIR.parent.parent
PART_OF = {
    "wood_sales": ("wood",),
    "joinery": ("joinery",),
    "tasks": ("tasks",),
    "office": ("office",),
    "craftwork": ("craft",),
    "winter": ("winter",),
    "loan_repayment": ("loan",),
    "rest": ("plans", "buildings", "income"),
}


def _states(seed: int, every: int = 25) -> list[LignumState]:
    rng = np.random.RandomState(seed)
    s: Any = pyspiel.load_game("python_lignum(players=2)").new_initial_state()
    out: list[LignumState] = []
    n = 0
    while not s.is_terminal():
        if n % every == 0 and not s.is_chance_node():
            out.append(s.clone())
        n += 1
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(int(rng.choice(acts, p=probs)))
        else:
            s.apply_action(int(rng.choice(bot_candidates(s))))
    return out


def _reference(state: LignumState, seat: int, w: Any) -> float:
    """Pure-Python value from the YAML by feature name, hand-set parts from value_parts."""
    fit = yaml.safe_load((ROOT / w["value_fit"]).read_text())
    feats = dict(zip(FEATURE_NAMES, features(state, seat, w), strict=True))
    opp = 1 - seat
    feats["opp_money"] = state.money[opp]
    feats["opp_loan_repay"] = state._tables().loan_repay[state.loans[opp]]  # pyright: ignore
    feats["round"] = state.round
    parts = value_parts(state, seat, w)
    total = float(state.money[seat])
    for c in COMPONENTS:
        if c in w["fitted_components"]:
            spec = fit["components"][c]
            total += spec["intercept"] + sum(v * feats[n] for n, v in spec["coef"].items())
        else:
            total += sum(parts[p] for p in PART_OF[c])
    return total


def test_fitted_value_matches_yaml_reference() -> None:
    w = value_weights("heuristic-v5")
    assert "value_fit" in w
    checked = 0
    for seed in (3, 4):
        for s in _states(seed):
            for seat in (0, 1):
                assert value(s, seat, w) == pytest.approx(_reference(s, seat, w), abs=1e-6)
                checked += 1
    assert checked > 20


def test_empty_fitted_components_equals_hand_set() -> None:
    w = {**value_weights("heuristic-v4"), "value_fit": "data/bots/value_fit.yaml"}
    w["fitted_components"] = ()
    hand = value_weights("heuristic-v4")
    for s in _states(5, 40):
        assert value(s, 0, w) == pytest.approx(value(s, 0, hand), abs=1e-6)


def test_v5_keeps_hand_set_tasks_office_loan() -> None:
    w = load_profile("heuristic-v5")
    assert set(w["value"]["fitted_components"]) == {
        "wood_sales",
        "joinery",
        "craftwork",
        "winter",
        "rest",
    }
    v4 = dict(load_profile("heuristic-v4"))
    v5 = {k: v for k, v in w.items() if k not in ("value",)}
    assert v5 == {k: v for k, v in v4.items() if k != "value"}


def test_features_parity_with_collector() -> None:
    from tools import collect_games

    assert collect_games.FEATURE_NAMES is FEATURE_NAMES
    assert collect_games.features is features
    assert len(CRAFT_ORDER) > 1
    s = _states(6, 20)[3]
    assert len(features(s, 0, value_weights("heuristic-v4"))) == len(FEATURE_NAMES)


def test_collected_game_unchanged(tmp_path: Path) -> None:
    """Byte-level golden of the v4 vs v2 game at seed 200 (every 3rd decision): features and parts
    must not drift when the feature code is shared with the runtime."""
    collect(["heuristic-v4,heuristic-v2:1"], tmp_path, seed_start=200, workers=1, every=3)
    with gzip.open(tmp_path / "200.jsonl.gz") as f:
        raw = f.read()
    assert hashlib.sha256(raw).hexdigest() == (
        "de880ba42fb8259e87649bc548349bcce2a7ab51fde167a9ba6d4a5aa23ad6f4"
    )


def test_runtime_modules_do_not_import_numpy() -> None:
    code = (
        "import sys, lignum.bots.fitted, lignum.bots.features, server.bots;"
        "bad=[m for m in ('numpy','sklearn','scipy') if m in sys.modules];"
        "sys.exit(1 if bad else 0)"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True)
    assert r.returncode == 0, r.stderr.decode()


def test_v5_seat_plays_a_legal_game() -> None:
    game = load_game(
        Replay(
            game="lignum",
            params={"players": 2, "joinery": True, "returns": "win_loss", "easy_winter": False},
        )
    )
    rec = play_game_record(game, ["heuristic-v5", "heuristic-v4"], "7")
    assert len(rec.final) == 2 and rec.history
    from tools.tournament import make_bot

    make_bot("heuristic-v5:max_sawyers=2")  # overrides work as for v4


def test_v5_value_section_equals_v4_apart_from_fit_keys() -> None:
    v4 = dict(value_weights("heuristic-v4"))
    v5 = {
        k: v
        for k, v in value_weights("heuristic-v5").items()
        if k not in ("value_fit", "fitted_components")
    }
    assert v5 == v4


def test_features_use_training_weights() -> None:
    """Overriding heat credits in the playing profile must not change the fitted value."""
    from tools.tournament import make_bot

    w = dict(value_weights("heuristic-v5"))
    over = {**w, "heat_credit_sawing": 0.0, "heat_credit_woodpile": 0.9, "heat_full_weight": 0}
    for s in _states(8, 30):
        # winter, tasks, office, loan and the hand-set parts use their own weights; fit only
        # the components that read features, with everything else empty of the overridden keys
        a = {**w, "fitted_components": tuple(COMPONENTS)}
        b = {**over, "fitted_components": tuple(COMPONENTS)}
        assert value(s, 0, a) == pytest.approx(value(s, 0, b), abs=1e-9)
    assert make_bot("heuristic-v5") is not None


def test_fit_game_params_fall_back_to_hand_set_value() -> None:
    fit = yaml.safe_load((ROOT / "data/bots/value_fit.yaml").read_text())
    assert fit["game_params"] == {"players": 2, "joinery": True, "easy_winter": False}
    w = value_weights("heuristic-v5")
    hand = value_weights("heuristic-v4")
    s: Any = pyspiel.load_game("python_lignum(players=3)").new_initial_state()
    rng = np.random.RandomState(1)
    for _ in range(60):
        if s.is_terminal():
            break
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(int(rng.choice(acts, p=probs)))
        else:
            s.apply_action(int(rng.choice(bot_candidates(s))))
    assert value(s, 0, w) == pytest.approx(value(s, 0, hand), abs=1e-9)


def test_missing_fit_fails_at_construction() -> None:
    from lignum.bots.heuristic import HeuristicBot

    prof = {k: v for k, v in load_profile("heuristic-v5").items() if k != "value"}
    bad = {**prof, "value": {**value_weights("heuristic-v5"), "value_fit": "data/bots/nope.yaml"}}
    with pytest.raises(FileNotFoundError):
        HeuristicBot(weights=bad)


def test_collect_manifest_records_fit_hash(tmp_path: Path) -> None:
    from tools.collect_games import bot_hashes, sha256

    h = bot_hashes(["heuristic-v5", "heuristic-v4"])
    assert h["heuristic-v5:value_fit"] == sha256(ROOT / "data/bots/value_fit.yaml")
    assert "heuristic-v4:value_fit" not in h
