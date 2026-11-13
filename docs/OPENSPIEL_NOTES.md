# OpenSpiel 2.0.2 notes for a Python game

Ported from `taylordinkins/kingisdead` (PLAN.md D2) and extended by Lignum's Phase 0 spike;
the new material is the last section, **Hidden sequential picks and imperfect-information bots**.
The inherited findings were checked against the installed 2.0.2 (`.venv/lib/python3.12/site-packages/open_spiel/`).
Most claims are exercised by `tests/test_openspiel_api.py`; the few that are not are labelled
"checked in source (file:line)" (paths relative to `open_spiel/python/`). The tests use the toy game `tests/support/toy_chance_game.py` (`python_lignum_toy`, shaped like our game:
2-3 players, bag-draw setup chance nodes, two consecutive decisions by one player, shared win).

## Registration

```python
import pyspiel

GAME_TYPE = pyspiel.GameType(
    short_name="python_lignum_toy",
    long_name="...",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    min_num_players=2,
    max_num_players=3,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=True,
    provides_observation_tensor=True,
    parameter_specification={"players": 2},  # name -> default value (defines the type)
)


class MyGame(pyspiel.Game):
    def __init__(self, params=None):
        params = dict(params or {})
        n = int(params.get("players", 2))
        info = pyspiel.GameInfo(
            num_distinct_actions=...,
            max_chance_outcomes=...,
            num_players=n,
            min_utility=-1.0 / (n - 1),
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=...,
        )  # player decisions only, see below
        super().__init__(GAME_TYPE, info, params)


pyspiel.register_game(GAME_TYPE, MyGame)  # at import time
```

- `pyspiel.load_game("python_lignum_toy(players=3)")` works once the module has been imported (the
  import is what registers it; `open_spiel.python.games` does this for the bundled games).
  Missing params fall back to `parameter_specification` defaults; `get_parameters()` returns
  `{"players": 3}`. Unknown params raise `pyspiel.SpielError`.
- `min_num_players`/`max_num_players` are NOT enforced by `load_game` for Python games
  (`players=4` loads fine). Validate in `Game.__init__` (we raise `ValueError`, which propagates).
- `GameInfo.num_players` must be set from the parameter, so `GameInfo` is built inside
  `__init__`, not at module level, when the player count is a parameter
  (the iterated-prisoner's-dilemma example does the same).
- Registering the same game twice does not raise (harmless under pytest's importlib mode). Checked
  by hand, no test; the registry is C++ and not in the wheel (call site: `pybind11/python_games.cc:241`).
- Python games are "global Python objects": game and state classes must stay importable for
  pickling (see serialization).

## max_game_length excludes chance nodes

`GameInfo.max_game_length` is the maximum number of *player decisions* summed over players.
`pyspiel.random_sim_test` enforces it: it counts only non-chance actions and fails with
`game_length <= game.MaxGameLength()` otherwise. Chance nodes are bounded separately by
`Game.max_chance_nodes_in_history()`, which defaults to `max_game_length` (a loose bound). A Python
game may override it as a method on the `Game` subclass (`PyGame` forwards it; the toy game does).
Derived: `max_history_length() = max_game_length + max_chance_nodes_in_history`, and
`max_move_number()` is the same sum. Declare both exactly so tensors/buffers sized from them
(e.g. in RL code) are correct.

**`max_chance_nodes_in_history` is not enforced by anything.** Overriding it to 1 still passes
`random_sim_test(serialize=True)`. The Phase 2 sim tests must therefore assert
`len(history) <= game.max_history_length()` and that the chance-node count stays within the
declared bound. The toy game's test asserts `==` only because its game length is fixed; ours
varies, so use `<=`. Counting setup chance nodes into
`max_game_length` (as PLAN.md originally assumed) is wrong in 2.0.2.

## State API (what `pyspiel.State` subclasses implement)

Required: `current_player()`, `_legal_actions(player)`, `_apply_action(action)`,
`_action_to_string(player, action)`, `is_terminal()`, `returns()`, `__str__`.
Chance games also: `chance_outcomes()` returning `[(action, prob), ...]`. Note the underscore
prefixes: you implement `_legal_actions`/`_apply_action`/`_action_to_string`; callers use the
public `legal_actions()`/`apply_action()`/`action_to_string()`.

- `current_player()` returns `pyspiel.PlayerId.CHANCE` (-1) for chance nodes and
  `pyspiel.PlayerId.TERMINAL` (-4) at the end, else the seat. A player acting twice in a row is
  simply `current_player()` returning the same seat for consecutive states.
- `_legal_actions` must be sorted ascending, empty at terminal. `legal_actions()` at a chance
  node returns the chance action ids (the `chance_outcomes()` keys).
- `chance_outcomes()` probabilities may depend on state (bag counts); omit zero-probability
  outcomes. Chance actions share the action-id space with nothing else: ids only need to be
  `< max_chance_outcomes`, and apply via `apply_action` like any other action. The history
  records them as `-1:<action>`.
- `returns()` must be defined before terminal too; return zeros. The default `rewards()` is zeros
  before terminal and equals `returns()` at terminal (e.g. `[1.0, -0.5, -0.5]` for a 3-player sole
  win; asserted in the tests); `rl_environment` relies on that. With `RewardModel.TERMINAL` MCTS and
  `random_sim_test` only read returns at the end.
- `clone()` has a working default for Python states and the clone is independent (the toy game's
  lists are not shared); no override is needed for correctness. We may override for speed later.
  The default builds `game.new_initial_state()` and then `copy.deepcopy`s every entry of the state's
  `__dict__` (`pybind11/python_games.cc:156-165`). **Static tables (adjacency, action tables) must
  live on the game or at module level, never on the state**, or every MCTS clone copies them.
- `history()`, `move_number()`, `is_chance_node()`, `legal_actions_mask()` etc. are provided.
- `information_state_string/tensor` fall back to the observation even when
  `provides_information_state_*` is False; harmless, don't rely on it. Checked in source
  (`pybind11/python_games.cc:90-93,312-316`: the info-state observer is the same
  `make_py_observer`), not tested.
- Optional (tic_tac_toe shows them): `_to_struct`, `_action_to_struct`, `_struct_to_actions`,
  `_to_observation_struct`, and `new_initial_state(self, state=None)` for struct/JSON round
  trips. Not needed for Kuhn-style games; skip unless the server wants them.

## Chance outcomes and serialization

- Sampling is the caller's job: tests and bots pick from `chance_outcomes()` by probability.
  MCTS handles chance nodes inside its tree, but `MCTSBot.step()` on a chance root returns
  `pyspiel.INVALID_ACTION` (-1) and does nothing, so the driver must apply chance itself.
- `state.serialize()` (default on `PyState`) returns
  `history=-1:0,-1:1\nmove_number=2\n__dict__=<base64 pickle of state.__dict__>`.
  `pyspiel.serialize_game_and_state(game, state)` wraps it with the game string, and
  `pyspiel.deserialize_game_and_state(text)` rebuilds the game via `load_game` and the state from
  the pickled `__dict__`. Consequence: every attribute on the state must be picklable. The deserialized
  state keeps playing identically (tested). `pickle.dumps` of states and games also works.
- **Deserialization does not replay the history.** It parses the history into the C++ list and
  assigns the unpickled `__dict__` entries onto a fresh initial state; `_apply_action` is never
  called (`pybind11/python_games.cc:419-441`). An edited attribute survives the round trip. So: a
  serialized string is not checked against its own history; it breaks when state attributes are
  renamed between versions; and unpickling untrusted text runs arbitrary code.
  **Persist action histories (not `serialize()` output) for playtest reports and server replays,
  and never deserialize client-supplied strings.** (PLAN D18.)
- Playthrough text (`generate_playthrough`) only emits `SerializeState()` for
  `SAMPLED_STOCHASTIC` games; ours is `EXPLICIT_STOCHASTIC`. Checked in source
  (`python/algorithms/generate_playthrough.py:390-391`), not tested.

## Observer pattern (PyObserver)

`Game.make_py_observer(self, iig_obs_type=None, params=None)` returns an object with:

- `tensor`: one flat `np.float32` array of constant size;
- `dict`: name -> reshaped *view* onto `tensor` (so write through the views, never rebind them);
- `set_from(state, player)`: refill `tensor` (call `tensor.fill(0)` first);
- `string_from(state, player)`: the observation string.

`iig_obs_type` is `None` for the default observation; imperfect-information games branch on its
`public_info`/`private_info`/`perfect_recall` fields. For a perfect-information game, ignore it
and return the same observer. `params` must be falsy unless you support observation params.
`state.observation_tensor(p)`, `state.observation_string(p)`, `game.observation_tensor_size()` and
`open_spiel.python.observation.make_observation(game)` (-> `.set_from`, `.tensor`, `.dict`,
`.string_from`) all go through it. `game.observation_tensor_shape()` is flat (`[size]`); the named
shapes appear in playthroughs (`ObservationTensor(0).hands`) via `tensors_info`.
`IIGObserverForPublicInfoGame` (observation.py) is a helper for fixed-public-info games; not needed.

## Test and bot call signatures

```python
pyspiel.random_sim_test(
    game,
    num_sims,
    serialize,
    verbose,
    mask_test=True,
    state_checker_fn=...,
    mean_field_population=-1,
    observer=None,
    specific_initial_state=None,
)
# serialize=True exercises serialize/deserialize (works for Python games)

from open_spiel.python.algorithms import mcts

bot = mcts.MCTSBot(
    game,
    uct_c,
    max_simulations,
    evaluator,
    solve=True,
    random_state=None,
    child_selection_fn=...,
    dirichlet_noise=None,
    verbose=False,
    dont_return_chance_node=False,
)
evaluator = mcts.RandomRolloutEvaluator(n_rollouts=1, random_state=None, max_length=None)
action = bot.step(state)  # at player nodes only
policy, action = bot.step_with_policy(state)

from open_spiel.python.algorithms import generate_playthrough

text = generate_playthrough.playthrough(
    game_string, action_sequence, seed=None, alsologtostdout=False, observation_params_string=None
)
```

- `MCTSBot` requires TERMINAL rewards and SEQUENTIAL dynamics (checked in source,
  `python/algorithms/mcts.py:247-250`, raises `ValueError` otherwise; not tested); it needs
  `game.max_utility()`.
  Zero-sum n-player is handled as max^n. It plays consecutive same-player decisions fine (each
  `step` call searches from the current state). With `solve=True` terminal children are proven,
  so a last-move choice is found even with ~30 simulations.
- `generate_playthrough` takes a game *string*, so the game must be registered (module imported)
  first; `action_sequence=[]` means fully random with `seed`. Same seed gives identical text.
  Golden playthroughs for Lignum will need chance outcomes seeded the same way.
- Speed: Python games are slow in MCTS; the toy runs 15-simulation searches instantly, but real
  Phase 6 budgets need profiling. `state.clone()` is on the MCTS hot path.

## Differences from 1.x and surprises

- `max_game_length` excludes chance nodes (see above); `max_chance_nodes_in_history()` can be overridden.
- The 2.0.2 example games (tic_tac_toe) show optional struct APIs (`_to_struct`,
  `new_initial_state(state=None)`); I did not compare with 1.x, but Kuhn-style games need none of it.
- `load_game` does not enforce min/max player counts for Python games.
- Python state serialization is a pickle of `__dict__`; no need to hand-write `serialize`.
- `random_sim_test` is a good guard: it fails loudly on a wrong `max_game_length`.

## Template for lignum/game.py

```python
GAME_TYPE = pyspiel.GameType(short_name="python_lignum", information=IMPERFECT_INFORMATION, ...,
                             parameter_specification={"players": 2, "joinery": True,
                                                      "returns": "win_loss", "easy_winter": False})

class LignumGame(pyspiel.Game):
    __init__(params)                    # validate players in 2..4, build GameInfo, super().__init__
    max_chance_nodes_in_history()       # setup draws only (optional override, exact bound)
    new_initial_state()
    make_py_observer(iig_obs_type=None, params=None)

class LignumState(pyspiel.State):
    __init__(game)                      # picklable attributes only
    current_player()                    # CHANCE / TERMINAL / seat; same seat for sub-steps
    _legal_actions(player)              # sorted; depends on phase machine
    chance_outcomes()                   # [(action, prob)] from remaining counts
    _apply_action(action)               # dispatches chance vs player, advances phase
    _action_to_string(player, action)
    is_terminal()
    returns()                           # zeros until terminal; shared win formula afterwards
    __str__()
    clone()                             # optional speed override

class LignumObserver:               # tensor (float32 flat), dict (views), set_from, string_from
pyspiel.register_game(GAME_TYPE, LignumGame)    # at import of lignum.game
```

## Hidden sequential picks and imperfect-information bots (Lignum Phase 0 spike)

Toy game: `spike/hidden_picks.py` (`python_spike_hidden_picks`, 2–4 players, `rounds` param):
chance deals wood to `players + 1` areas; seats pick an area in turn, each pick hidden until all
have picked (D5's "turn-based simultaneous" encoding); then a public keep-or-move decision; shared
areas split wood evenly with the remainder staying (C4). Bots: `spike/bots.py`. Every claim below
is exercised by `tests/spike/test_hidden_picks.py` unless marked otherwise.

### Encoding hidden picks

- Declare `information=IMPERFECT_INFORMATION` and `provides_information_state_string/tensor=True`.
  The picks stay ordinary sequential decisions; nothing in OpenSpiel needs `SIMULTANEOUS`.
- Hiding is entirely the observer's job. `make_py_observer(iig_obs_type, params)` is called with:
  - `IIGObservationType(perfect_recall=False)` (private SINGLE_PLAYER) for `observation_*`;
  - `perfect_recall=True, public_info=True, private_info=SINGLE_PLAYER` for
    `information_state_*`.
  Both are requested lazily, on the first `*_string`/`*_tensor` call, with `params={}` (falsy),
  once per game object (tested by spying on `make_py_observer`).
  Branch on `private_info` (`pyspiel.PrivateInfoType.NONE / SINGLE_PLAYER / ALL_PLAYERS`),
  `public_info` and `perfect_recall`. The constructor's `perfect_recall` is keyword-required.
- What is public: *that* a seat has picked (and whose turn it is), never *what* it picked until the
  reveal. What is private: the observer's own pick. After the reveal, all picks are public.
- Tested invariance: at the last seat's pick, its information-state string **and tensor** and its
  observation string and tensor are identical across every combination of earlier seats' picks
  (2, 3 and 4 players), while the picker's own view changes with its pick.
- Perfect recall must include the past. Two histories with equal points and wood but different
  earlier picks give equal observations and different information states (tested). For Lignum,
  per-round public logs (deals, revealed picks, final areas) on the state are enough; it doesn't
  need the full action history in the tensor.
- **Phase 2 deviation (decided 2026-11-06):** the engine's `information_state_string(p)` currently
  equals `observation_string(p)`; `perfect_recall` is stored but unused, and past rounds' revealed
  picks are not carried. Public state is almost Markov, so Phase 2 play and sims are unaffected.
  **Phase 6 must implement the per-round log (revealed picks, final areas) when `recall` is true,
  with the test above, before IS-MCTS keys a tree on this string.**
- `State.__str__` = the observer with `private_info=ALL_PLAYERS, perfect_recall=False`, cached on
  the game (`HiddenPicksGame.full_observer`). States that differ only in a hidden pick print
  differently (tested). This is the pattern CLAUDE.md now requires.
- `random_sim_test(serialize=True)` passes for players 2–4 and rounds 1–3 (300 sims each, slow
  test). The invariance tests above, not `random_sim_test`, are what check the hiding.

### Bots

| Bot | Works on a Python game in 2.0.2? | Notes |
|---|---|---|
| `pyspiel.MCTSBot` (C++) | **No: segfault** (exit −11) | Also on OpenSpiel's own `python_tic_tac_toe`; fine on C++ `tic_tac_toe` |
| `pyspiel.ISMCTSBot` (C++) | **No: segfault** | Also on `python_kuhn_poker`; fine on C++ `kuhn_poker` |
| `open_spiel.python.algorithms.ismcts.ISMCTSBot` | **Yes** | Needs a resampler (below) |
| `open_spiel.python.algorithms.mcts.MCTSBot` | Yes, but it sees the true state | Only use it on determinized samples |

- The C++ crashes happen with the evaluator and state held in variables too, so they aren't a
  temporary's lifetime. The cause is inside the wheel and wasn't investigated further.
  `tests/test_cpp_bot_canary.py` (slow) runs them in a
  subprocess and **fails once they stop crashing**, so an OpenSpiel upgrade will flag it.
- Python IS-MCTS keys its tree by `(current_player, information_state_string)`, so the info-state
  string must be exact: equal for indistinguishable states, different otherwise. At each
  simulation it calls the resampler on the root and asserts the sample's key equals the root's.
- Resampling: Python IS-MCTS calls `bot.set_resampler(cb)`'s `cb(state, player)`, or else
  `state.resample_from_infostate(player, pyspiel.UniformProbabilitySampler(0., 1.))`. A Python
  method of that name on the state *is* found by Python attribute lookup, so either route works;
  the C++ bots never get that far. `UniformProbabilitySampler` is a callable returning a float.
  The spike's resampler clones the state and redraws only the picks hidden from `player`
  (uniform over areas, i.e. it ignores opponents' likely preferences, standard for IS-MCTS).
  For Lignum the hidden part is the same: other seats' cutting-area picks in the current round.
- IS-MCTS and Python MCTS return `pyspiel.INVALID_ACTION` at chance nodes (tested): the driver
  samples chance itself, as in kingisdead.
- Determinized MCTS (`DeterminizedMCTSBot`): draw D worlds with the resampler, run Python
  `MCTSBot.mcts_search` on each (`simulations // D` each), sum root-child `explore_count`s, play
  the most visited. Simple and fast, but it suffers strategy fusion (it plans as if it knew the
  hidden picks).

Measured on the toy (2 players, 2 rounds, 200 games, seats alternated, this WSL2 machine; scratch
script, not a test):

| Match | Mean return | Win rate | Time per decision |
|---|---|---|---|
| IS-MCTS 100 sims vs random | +0.95 | 0.96 | 21 ms |
| Determinized MCTS 100 sims × 4 worlds vs random | +0.85 | 0.90 | 11 ms |
| IS-MCTS 100 vs determinized 100×4 | +0.28 | 0.29 (most others tied) | 21 ms |

The slow test `test_search_bots_beat_random` asserts mean return > 0.3 over 60 games for each.

### Decision for PLAN.md §5.7

Use **Python IS-MCTS** (`open_spiel.python.algorithms.ismcts.ISMCTSBot`) with a Lignum resampler
that redraws unrevealed cutting-area picks. It accepts our Python imperfect-information game on
2.0.2 and beat determinized MCTS head to head. Keep `DeterminizedMCTSBot` as a cheaper fallback
and as a second opponent in tournaments. Don't use the C++ bots on `python_lignum` (segfault).
Speed: the toy's 20 ms per 100-sim decision is a floor; Lignum's states and legal-action lists
are far larger, so the Phase 6 budget needs profiling (`clone()` and `information_state_string`
are on the hot path; cache static tables on the game, see "State API").

### Template additions for `lignum/game.py`

```python
class LignumState(pyspiel.State):
    def resample_from_infostate(self, player_id, probability_sampler):  # IS-MCTS resampler
        ...  # clone; redraw other seats' unrevealed cutting-area picks; nothing else is hidden
    def __str__(self):
        return self.get_game().full_observer().string_from(self, 0)


class LignumObserver:  # branches on iig_obs_type.private_info / public_info / perfect_recall
    ...  # public: who has picked; private: own pick until reveal; perfect recall: per-round logs
```

