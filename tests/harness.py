"""Shared test harness for rule tests (written from docs/ACTIONS.md and docs/SCENARIOS.md only).

The implementer does not edit this file; if it is wrong, say so. It imports nothing from the
engine except `lignum.game` (to register the game) and, lazily, `lignum.scenario.dump_scenario`.

Public API
----------
load_game(**params) -> pyspiel.Game
    Load "python_lignum" with the given parameters (players, joinery, returns, easy_winter).
    `params` values may be bool/int/str; bools are rendered as true/false.

as_game(game_or_params) -> pyspiel.Game
    Accepts a Game, a dict of parameters, or a game string.

Chance-ID layout (independent reading of ACTIONS section 2, plain integers):
    AREAS3 0..19, WINTER 20..27 (20 + 2c + h), TASK_DRAW 28..46, PW_DRAW 47..56,
    PLACEMENT_DRAW 57..75, BUILDING_DRAW 76..85, CRAFT_DRAW 86..90, SPOT_TOKEN 91..102.
chance_family(action) -> (family_name, param)
    param is the rank for AREAS3, (c, h) for WINTER, and the single index otherwise.
CHANCE_BASE, CHANCE_COUNT: dicts family -> first id / number of ids.
PICK_AREA(a) -> decision id 2 + a (ACTIONS section 3);  DONE = 0; TAKE_LOAN = 1; MOVE_TO(l) = 7 + l.

phase_of(state) -> str
    "SC" at any chance node, "TERMINAL" at a terminal state, otherwise the "phase" of
    snapshot(state) (ACTIONS section 4 codes: SP, TR, ...).
snapshot(state) -> dict
    The resolved scenario dict of the state, i.e. lignum.scenario.dump_scenario(state)
    (docs/SCENARIOS.md section 8). Only valid at decision nodes. The test files rely on:
    parameters, round, phase, current_player, turn_order, seats[i].{money,loans,food,fodder,
    equipment,craftwork,hired,woodpile,joiners,buildings,foreman,cutting_area},
    cutting_areas[i].wood.{firewood,softwood,hardwood}, path.{bearers,woodcutters,sawyers_free,
    sawyers_paid,fodder,joiner,tokens}, planned_work.laid_out,
    supply.{tasks_laid_out,winter,buildings,craftwork_removed}.
seats(snap), areas(snap) -> list
    Normalise list-or-map forms of the "seats" and "cutting_areas" fields to lists indexed 0...
tokens(snap) -> dict[int, str]
    path.tokens with integer printed-number keys.

sample_chance(state, rng) -> int
    Pick a chance outcome with a random.Random according to chance_outcomes() probabilities.
apply_actions(state, actions, check=True) -> state
    Apply an explicit action list (chance ids at chance nodes, decision ids elsewhere). With
    check=True each action must be in legal_actions() first (and have probability > 0 at chance
    nodes), else AssertionError naming the index. Returns the same state object.
play_setup(game_or_params, seed=0, picks=None, stop_phase=None) -> state
    New initial state; at chance nodes apply seeded random outcomes (random.Random(seed));
    at SP nodes apply `picks[i]` (the i-th decision) if given, else the lowest legal action.
    Stops at the first node that is not SC or SP (round 1 TR) and returns that state. With
    stop_phase="SP" it returns at the first SP node instead (chance run done, no pick yet).
setup_history(state) -> list[int]   state.history() as plain ints.
replay(game_or_params, actions, check=True) -> state
    new_initial_state + apply_actions.
"""

from __future__ import annotations

import random

import pyspiel

CHANCE_BASE = {
    "AREAS3": 0,
    "WINTER": 20,
    "TASK_DRAW": 28,
    "PW_DRAW": 47,
    "PLACEMENT_DRAW": 57,
    "BUILDING_DRAW": 76,
    "CRAFT_DRAW": 86,
    "SPOT_TOKEN": 91,
}
CHANCE_COUNT = {
    "AREAS3": 20,
    "WINTER": 8,
    "TASK_DRAW": 19,
    "PW_DRAW": 10,
    "PLACEMENT_DRAW": 19,
    "BUILDING_DRAW": 10,
    "CRAFT_DRAW": 5,
    "SPOT_TOKEN": 12,
}

DONE = 0
TAKE_LOAN = 1


def PICK_AREA(a: int) -> int:
    return 2 + a


def MOVE_TO(loc: int) -> int:
    return 7 + loc


def chance_family(action: int):
    """(family, param) for a chance outcome id (ACTIONS section 2)."""
    for fam, base in CHANCE_BASE.items():
        if base <= action < base + CHANCE_COUNT[fam]:
            off = action - base
            if fam == "WINTER":
                return fam, (off // 2, off % 2)
            return fam, off
    raise ValueError(f"not a chance outcome id: {action}")


def load_game(**params) -> pyspiel.Game:
    import lignum.game  # noqa: F401  (registers python_lignum)

    if not params:
        return pyspiel.load_game("python_lignum")
    body = ",".join(
        f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in params.items()
    )
    return pyspiel.load_game(f"python_lignum({body})")


def as_game(game_or_params) -> pyspiel.Game:
    if isinstance(game_or_params, pyspiel.Game):
        return game_or_params
    if isinstance(game_or_params, str):
        import lignum.game  # noqa: F401

        return pyspiel.load_game(game_or_params)
    return load_game(**dict(game_or_params or {}))


def snapshot(state) -> dict:
    from lignum.scenario import dump_scenario

    return dump_scenario(state)


def phase_of(state) -> str:
    if state.is_terminal():
        return "TERMINAL"
    if state.is_chance_node():
        return "SC"
    from lignum.game import PHASE_NAMES  # direct read: a dump refuses mid-turn nodes (S-MIDTURN)

    return PHASE_NAMES[state.phase]


def _as_list(x, base):
    if isinstance(x, dict):
        return [x[k] for k in sorted(x, key=lambda k: int(k))]
    return list(x)


def seats(snap):
    return _as_list(snap["seats"], 0)


def areas(snap):
    return _as_list(snap["cutting_areas"], 1)


def tokens(snap) -> dict[int, str]:
    return {int(k): v for k, v in snap["path"]["tokens"].items()}


def sample_chance(state, rng: random.Random) -> int:
    outs = state.chance_outcomes()
    return rng.choices([a for a, _ in outs], [p for _, p in outs])[0]


def apply_actions(state, actions, check: bool = True):
    for i, a in enumerate(actions):
        if check:
            if state.is_chance_node():
                ok = a in {x for x, p in state.chance_outcomes() if p > 0}
            else:
                ok = a in state.legal_actions()
            assert ok, f"action #{i} ({a}) not legal at {state}"
        state.apply_action(a)
    return state


def play_setup(game_or_params=None, seed: int = 0, picks=None, stop_phase=None):
    game = as_game(game_or_params)
    state = game.new_initial_state()
    rng = random.Random(seed)
    n_pick = 0
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(sample_chance(state, rng))
            continue
        ph = phase_of(state)
        if ph == "SP":
            if stop_phase == "SP":
                return state
            legal = state.legal_actions()
            a = picks[n_pick] if picks is not None else legal[0]
            n_pick += 1
            state.apply_action(a)
            continue
        return state
    return state


def setup_history(state) -> list[int]:
    return [int(a) for a in state.history()]


def replay(game_or_params, actions, check: bool = True):
    return apply_actions(as_game(game_or_params).new_initial_state(), actions, check)
