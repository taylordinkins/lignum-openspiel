"""Phase 2 unit 2: game shell, state skeleton, observer, parameters.

Rules: R-001, R-002, R-003 (parameters, player counts), R-028..R-032 (information, observer,
determinism, terminology); ACTIONS 1.2 and 2 for the game info numbers.

Planned API, stated so the implementer can follow it:

    lignum.game      LignumGame(pyspiel.Game), LignumState(pyspiel.State); importing the module
                     registers "python_lignum" via pyspiel.register_game.
    lignum.observer  LignumObserver with .tensor (flat float32), .dict (views), set_from(state,
                     player), string_from(state, player); branches on the IIGObservationType
                     (public_info, private_info, perfect_recall).
    LignumGame.make_py_observer(iig_obs_type=None, params=None) -> LignumObserver.
    State.__str__ == observer(private_info=ALL_PLAYERS, perfect_recall=False, public_info=True)
                     .string_from(state, 0)
    action_to_string uses lignum.actions.action_name (decisions) / chance_name (chance).
"""

import itertools
import random
import re
from math import comb

import numpy as np
import pyspiel
import pytest

from tests.rules.test_action_ids import _Lazy

A = _Lazy("lignum.actions")

PLAYERS = (2, 3, 4)
BOOLS = (True, False)
RETURNS = ("win_loss", "margin")


def _load(**params):
    import lignum.game  # noqa: F401  (registers python_lignum)

    if not params:
        return pyspiel.load_game("python_lignum")
    body = ",".join(
        f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in params.items()
    )
    return pyspiel.load_game(f"python_lignum({body})")


def _obs_type(private, perfect_recall=False):
    return pyspiel.IIGObservationType(
        public_info=True, perfect_recall=perfect_recall, private_info=private
    )


def _full_observer(game):
    return game.make_py_observer(_obs_type(pyspiel.PrivateInfoType.ALL_PLAYERS))


def _private_observer(game, perfect_recall=False):
    return game.make_py_observer(_obs_type(pyspiel.PrivateInfoType.SINGLE_PLAYER, perfect_recall))


def _public_observer(game):
    return game.make_py_observer(_obs_type(pyspiel.PrivateInfoType.NONE))


def _play_chance(state, rng, max_steps):
    """Apply up to max_steps sampled chance outcomes; return the action list."""
    acts = []
    while state.is_chance_node() and len(acts) < max_steps:
        outs = state.chance_outcomes()
        a = rng.choices([o[0] for o in outs], [o[1] for o in outs])[0]
        state.apply_action(a)
        acts.append(a)
    return acts


# ---------------------------------------------------------------- R-001 registration, params


def test_R001_registered_and_default_params():
    """R-001: defaults are players=2, joinery=true, returns=win_loss, easy_winter=false."""
    game = _load()
    assert game.get_type().short_name == "python_lignum"
    assert game.num_players() == 2
    assert dict(game.get_parameters()) == {
        "players": 2,
        "joinery": True,
        "returns": "win_loss",
        "easy_winter": False,
    }


@pytest.mark.parametrize(
    "players,joinery,returns,easy",
    list(itertools.product(PLAYERS, BOOLS, RETURNS, BOOLS)),
)
def test_R001_every_parameter_combination_loads(players, joinery, returns, easy):
    """R-001/R-003: all 24 combinations load, report the params back and give num_players."""
    game = _load(players=players, joinery=joinery, returns=returns, easy_winter=easy)
    assert game.num_players() == players
    p = dict(game.get_parameters())
    assert p["players"] == players
    assert p["joinery"] is joinery
    assert p["returns"] == returns
    assert p["easy_winter"] is easy
    assert not game.new_initial_state().is_terminal()


def test_R001_partial_params_use_defaults_for_the_rest():
    """R-001: unspecified parameters fall back to the defaults."""
    p = dict(_load(players=3).get_parameters())
    assert p["players"] == 3
    assert p["joinery"] is True
    assert p["returns"] == "win_loss"
    assert p["easy_winter"] is False


@pytest.mark.parametrize("players", [0, 1, 5, 6, -1])
def test_R001_invalid_player_count_rejected(players):
    """R-001/R-003: players outside 2..4 must not load (OpenSpiel does not enforce it itself)."""
    with pytest.raises((ValueError, pyspiel.SpielError)):
        _load(players=players)


@pytest.mark.parametrize("returns", ["score", "WIN_LOSS", "wins"])
def test_R001_invalid_returns_rejected(returns):
    """R-001: returns must be exactly win_loss or margin."""
    with pytest.raises((ValueError, pyspiel.SpielError)):
        _load(returns=returns)


def test_R001_unknown_parameter_rejected():
    """R-001: only the four listed parameters exist (`tactical` arrives in Phase 7)."""
    with pytest.raises((ValueError, pyspiel.SpielError)):
        _load(tactical=True)


# ---------------------------------------------------------------- GameType and GameInfo


@pytest.mark.parametrize("returns", RETURNS)
def test_R001_game_type_fields(returns):
    """PLAN 5.2: sequential, explicit-stochastic, imperfect information, terminal rewards,
    players 2-4; utility ZERO_SUM for win_loss and GENERAL_SUM for margin (D7)."""
    t = _load(returns=returns).get_type()
    assert t.short_name == "python_lignum"
    assert t.dynamics == pyspiel.GameType.Dynamics.SEQUENTIAL
    assert t.chance_mode == pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC
    assert t.information == pyspiel.GameType.Information.IMPERFECT_INFORMATION
    assert t.reward_model == pyspiel.GameType.RewardModel.TERMINAL
    assert t.min_num_players == 2
    assert t.max_num_players == 4
    want = (
        pyspiel.GameType.Utility.ZERO_SUM
        if returns == "win_loss"
        else pyspiel.GameType.Utility.GENERAL_SUM
    )
    assert t.utility == want
    assert t.provides_observation_string
    assert t.provides_observation_tensor
    assert t.provides_information_state_string
    assert t.provides_information_state_tensor


def test_R001_game_type_parameter_specification():
    """PLAN 5.2: the parameter specification lists exactly the four parameters with defaults."""
    spec = dict(_load().get_type().parameter_specification)
    assert set(spec) == {"players", "joinery", "returns", "easy_winter"}
    assert spec["players"] == 2
    assert spec["joinery"] is True
    assert spec["returns"] == "win_loss"
    assert spec["easy_winter"] is False


@pytest.mark.parametrize("players", PLAYERS)
@pytest.mark.parametrize("joinery", BOOLS)
def test_R001_game_info_counts(players, joinery):
    """ACTIONS 1.2: num_distinct_actions=440 and max_chance_outcomes=103 for every setting."""
    game = _load(players=players, joinery=joinery)
    assert game.num_distinct_actions() == 440
    assert game.max_chance_outcomes() == 103
    assert game.num_players() == players


@pytest.mark.parametrize("players", PLAYERS)
def test_R001_utility_bounds_win_loss(players):
    """D7: sole winner +1, losers -1/(n-1), zero-sum: bounds contain those values, sum is 0."""
    game = _load(players=players, returns="win_loss")
    assert game.max_utility() >= 1.0
    assert game.min_utility() <= -1.0 / (players - 1) + 1e-9
    assert game.utility_sum() == 0.0


@pytest.mark.parametrize("players", PLAYERS)
def test_R001_utility_bounds_margin(players):
    """D7: margin is clipped to [-1, 1], so the declared bounds contain that interval."""
    game = _load(players=players, returns="margin")
    assert game.max_utility() >= 1.0
    assert game.min_utility() <= -1.0


@pytest.mark.parametrize("players", PLAYERS)
def test_R001_game_length_bounds_positive_and_consistent(players):
    """OPENSPIEL_NOTES: max_game_length counts decisions only; history length adds chance
    nodes. ACTIONS 2: setup alone has up to 37 chance nodes, whole game up to 152."""
    game = _load(players=players)
    assert game.max_game_length() > 0
    assert game.max_chance_nodes_in_history() >= 37
    assert game.max_history_length() >= game.max_game_length()


def test_R001_easy_winter_and_returns_do_not_change_action_space():
    """R-001: returns and easy_winter do not change legal actions; game info and the first
    chance node are identical across them."""
    base = _load()
    for returns, easy in itertools.product(RETURNS, BOOLS):
        g = _load(returns=returns, easy_winter=easy)
        assert g.num_distinct_actions() == base.num_distinct_actions()
        assert g.max_chance_outcomes() == base.max_chance_outcomes()
        assert g.new_initial_state().chance_outcomes() == base.new_initial_state().chance_outcomes()


def test_R002_joinery_flag_keeps_first_chance_node():
    """R-002: setup differs only by the joinery items; the first chance node (AREAS3) is the
    same distribution with joinery true or false."""
    a = _load(joinery=True).new_initial_state().chance_outcomes()
    b = _load(joinery=False).new_initial_state().chance_outcomes()
    assert a == b


@pytest.mark.parametrize("players", PLAYERS)
def test_R003_first_chance_outcome_count_by_players(players):
    """R-003/ACTIONS 2: AREAS3 picks a k-subset of the 6 areas, k = 4/3/2 for 2/3/4 players,
    uniformly: C(6,k) equiprobable outcomes (15, 20, 15)."""
    k = {2: 4, 3: 3, 4: 2}[players]
    outs = _load(players=players).new_initial_state().chance_outcomes()
    assert len(outs) == comb(6, k)
    for _, p in outs:
        assert p == pytest.approx(1 / comb(6, k))


# ---------------------------------------------------------------- R-031 initial state, determinism


@pytest.mark.parametrize("players", PLAYERS)
def test_R031_initial_state_is_chance_node(players):
    """R-031/ACTIONS 2: setup begins with chance nodes (AREAS3 first); nobody acts yet."""
    s = _load(players=players).new_initial_state()
    assert s.is_chance_node()
    assert s.current_player() == pyspiel.PlayerId.CHANCE
    assert not s.is_terminal()
    outs = s.chance_outcomes()
    assert outs
    assert sum(p for _, p in outs) == pytest.approx(1.0)
    assert all(0 <= a < 103 for a, _ in outs)
    assert sorted(s.legal_actions()) == sorted(a for a, _ in outs)
    assert list(s.returns()) == [0.0] * players


@pytest.mark.parametrize("players", PLAYERS)
def test_R031_same_chance_outcomes_same_state(players):
    """R-031: parameters plus the same chance outcomes give the same state, independent of
    game or state object identity."""
    for seed in range(3):
        strings = []
        for _ in range(2):
            s = _load(players=players).new_initial_state()
            _play_chance(s, random.Random(seed), 15)
            strings.append(str(s))
        assert strings[0] == strings[1]


def test_R031_replay_action_list_reproduces_state():
    """R-031: applying a recorded action list to a fresh state reproduces string and history."""
    game = _load(players=3)
    s = game.new_initial_state()
    acts = _play_chance(s, random.Random(7), 12)
    t = game.new_initial_state()
    for a in acts:
        t.apply_action(a)
    assert str(t) == str(s)
    assert t.history() == s.history() == acts


def test_R031_clone_is_independent_and_equal():
    """State skeleton: clone() equals the original; later moves do not leak across."""
    s = _load().new_initial_state()
    c = s.clone()
    assert str(c) == str(s)
    s.apply_action(s.chance_outcomes()[0][0])
    assert str(c) != str(s)
    assert c.history() == []


def test_R031_different_chance_outcomes_give_different_strings():
    """CLAUDE.md: distinct states never print alike. Each first chance outcome (a different
    AREAS3 draw) yields a different string, all different from the root."""
    root = _load(players=2).new_initial_state()
    outs = root.chance_outcomes()
    assert len(outs) > 1
    strings = set()
    for a, _ in outs:
        s = root.clone()
        s.apply_action(a)
        strings.add(str(s))
    assert len(strings) == len(outs)
    assert str(root) not in strings


@pytest.mark.parametrize("players", PLAYERS)
def test_R031_successive_states_along_a_history_print_differently(players):
    """CLAUDE.md: each applied chance outcome changes the state, hence its string."""
    s = _load(players=players).new_initial_state()
    rng = random.Random(1)
    seen = {str(s)}
    for _ in range(10):
        if not s.is_chance_node():
            break
        _play_chance(s, rng, 1)
        assert str(s) not in seen
        seen.add(str(s))


# ---------------------------------------------------------------- R-028..R-030 observer contract


@pytest.mark.parametrize("players", PLAYERS)
def test_R030_state_str_equals_full_information_observer(players):
    """R-030/CLAUDE.md: State.__str__ is the observer string with private_info=ALL_PLAYERS and
    perfect_recall=False."""
    game = _load(players=players)
    s = game.new_initial_state()
    obs = _full_observer(game)
    assert str(s) == obs.string_from(s, 0)
    _play_chance(s, random.Random(3), 8)
    assert str(s) == obs.string_from(s, 0)


def test_R030_default_observer_interface():
    """OPENSPIEL_NOTES: make_py_observer(None) returns an observer with a flat float32 tensor,
    a dict of views onto it, set_from and string_from."""
    game = _load()
    obs = game.make_py_observer()
    s = game.new_initial_state()
    obs.set_from(s, 0)
    assert obs.tensor.ndim == 1
    assert obs.tensor.dtype == np.float32
    assert isinstance(obs.string_from(s, 0), str)
    assert obs.dict
    for v in obs.dict.values():
        assert np.shares_memory(v, obs.tensor)


@pytest.mark.parametrize("players", PLAYERS)
def test_R030_tensor_size_constant_and_declared(players):
    """R-030: the tensor has one constant size equal to the game's declared size, in every
    state, for every seat, for observation and information state."""
    game = _load(players=players)
    s = game.new_initial_state()
    rng = random.Random(5)
    for _ in range(6):
        for p in range(players):
            assert len(s.observation_tensor(p)) == game.observation_tensor_size()
            assert len(s.information_state_tensor(p)) == game.information_state_tensor_size()
            assert isinstance(s.observation_string(p), str)
            assert isinstance(s.information_state_string(p), str)
        if not s.is_chance_node():
            break
        _play_chance(s, rng, 1)


def test_R028_public_observer_is_same_for_every_seat():
    """R-028/R-030: a public-only view (private_info=NONE) is identical for every seat."""
    game = _load(players=3)
    s = game.new_initial_state()
    _play_chance(s, random.Random(2), 10)
    pub = _public_observer(game)
    assert len({pub.string_from(s, p) for p in range(3)}) == 1
    tens = []
    for p in range(3):
        pub.set_from(s, p)
        tens.append(np.array(pub.tensor, copy=True))
    assert all(np.array_equal(tens[0], t) for t in tens)


def test_R029_private_fields_empty_before_any_pick():
    """R-029: the only hidden data is a cutting-area pick (round 2 onward). With no pick made,
    each seat's private view equals the public view on every named field, and any field named
    only in the private view is all zeros."""
    game = _load(players=4)
    s = game.new_initial_state()
    _play_chance(s, random.Random(11), 5)
    pub = _public_observer(game)
    pub.set_from(s, 0)
    pub_dict = {k: np.array(v, copy=True) for k, v in pub.dict.items()}
    priv = _private_observer(game)
    for p in range(4):
        priv.set_from(s, p)
        for name, view in priv.dict.items():
            if name in pub_dict:
                assert np.array_equal(view, pub_dict[name]), name
            else:
                assert not np.any(view), name


def test_R029_information_state_string_is_deterministic():
    """R-029/OPENSPIEL_NOTES: information-state strings are a pure function of the state and
    seat (IS-MCTS keys its tree on them)."""
    s = _load(players=2).new_initial_state()
    assert s.information_state_string(0) == s.information_state_string(0)
    t = _load(players=2).new_initial_state()
    assert s.information_state_string(0) == t.information_state_string(0)


def test_R030_private_observer_accepts_both_recall_settings():
    """R-030: leak tests on picks arrive with unit 5. Interface only: the private observer
    works with perfect_recall False and True and has the same tensor size for every seat."""
    game = _load()
    s = game.new_initial_state()
    for pr in (False, True):
        o = _private_observer(game, perfect_recall=pr)
        o.set_from(s, 0)
        n0 = len(o.tensor)
        o.set_from(s, 1)
        assert len(o.tensor) == n0


# ---------------------------------------------------------------- seat numbering, action strings


@pytest.mark.parametrize("players", PLAYERS)
def test_R032_seats_numbered_from_zero(players):
    """CLAUDE.md: seats print as P0..P(n-1). The 1-based 'Player 1' / 'P<n>' (n = players,
    one past the last seat) never appears in any state, observation or info-state string."""
    game = _load(players=players)
    s = game.new_initial_state()
    _play_chance(s, random.Random(4), 10)
    texts = [str(s)]
    texts += [s.observation_string(p) for p in range(players)]
    texts += [s.information_state_string(p) for p in range(players)]
    for t in texts:
        assert not re.search(r"\bPlayer\s*\d", t)
        assert not re.search(rf"\bP{players}\b", t)


def test_R032_chance_action_to_string_uses_chance_names():
    """ACTIONS 2: action_to_string at a chance node returns lignum.actions.chance_name(id),
    unique per outcome, so a replay log can be read back."""
    s = _load().new_initial_state()
    names = set()
    outs = s.chance_outcomes()
    for a, _ in outs:
        name = s.action_to_string(pyspiel.PlayerId.CHANCE, a)
        assert name == A.chance_name(a)
        assert name.startswith("AREAS3")
        names.add(name)
    assert len(names) == len(outs)


@pytest.mark.parametrize(
    "decision",
    [("DONE",), ("TAKE_LOAN",), ("PICK_AREA", 3), ("MOVE_TO", 5), ("HIRE_BEARER",)],
)
def test_R032_decision_action_to_string_uses_action_names(decision):
    """ACTIONS 3: a decision ID prints as lignum.actions.action_name(id), starting with the
    table name; it does not name a seat (ACTIONS 1.1)."""
    s = _load().new_initial_state()
    aid = A.encode(*decision)
    text = s.action_to_string(0, aid)
    assert text == A.action_name(aid)
    assert text.startswith(decision[0])
    assert not re.search(r"[Pp]layer", text)


def test_R032_decision_action_strings_unique_for_all_ids():
    """ACTIONS 3: every decision ID 0..439 has its own string."""
    s = _load().new_initial_state()
    assert len({s.action_to_string(0, a) for a in range(440)}) == 440


def test_R032_state_string_qualifies_board_side():
    """R-032: location numbers differ between board sides (13 = Tasks on base, a token spot on
    joinery), so the full state string must say which side is in play: with the same first
    chance outcome, joinery=true and joinery=false print differently."""
    out = {}
    for joinery in BOOLS:
        s = _load(joinery=joinery).new_initial_state()
        s.apply_action(s.chance_outcomes()[0][0])
        out[joinery] = str(s)
    assert out[True] != out[False]
