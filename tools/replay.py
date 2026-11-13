"""Rebuild a game from an action history and print it (used by /triage-report).

Input is a JSON file: a playtest report or replay export (``game``, ``params``, ``history``), or a
bare list of action ids together with ``--game``. Every action is checked against the legal actions
before it is applied, so an illegal step in a report is pinpointed rather than silently accepted.

    uv run python -m tools.replay playtest/reports/<id>.json            # final state
    uv run python -m tools.replay <file> --steps                        # every step
    uv run python -m tools.replay history.json --game python_lignum --param players=3

Exit codes: 0 replayed, 1 an action was illegal (the step, the state and the legal actions are
printed), 2 bad input.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO, cast

import pyspiel

# Modules that register Python games with pyspiel on import; missing ones are skipped.
GAME_MODULES = ("lignum.game",)
# Report fields use the server's names; pyspiel parameters may differ.
PARAM_ALIASES = {"num_players": "players"}


@dataclass
class Replay:
    game: str
    params: dict[str, Any] = field(default_factory=lambda: {})
    history: list[int] = field(default_factory=lambda: [])


def check_history(raw: object) -> list[int]:
    items = cast(list[object], raw) if isinstance(raw, list) else None
    if items is None or not all(type(a) is int for a in items):
        raise ReplayError("history must be a list of integer action ids")
    return cast(list[int], items)


class ReplayError(Exception):
    """Bad input: unreadable file, unknown game, malformed history."""


def register_games() -> None:
    for name in GAME_MODULES:
        try:
            found = importlib.util.find_spec(name)
        except ModuleNotFoundError:
            found = None
        if found is not None:
            importlib.import_module(name)


def parse(data: object, game: str | None, extra: dict[str, Any]) -> Replay:
    if isinstance(data, list):
        if game is None:
            raise ReplayError("a bare action list needs --game")
        replay = Replay(game=game, history=check_history(cast(object, data)))
    elif isinstance(data, dict):
        record = cast(dict[str, Any], data)
        if "history" not in record and isinstance(record.get("export"), dict):
            record = cast(dict[str, Any], record["export"])
        name = game or record.get("game")
        if not isinstance(name, str):
            raise ReplayError("no game name in the file; pass --game")
        params = cast(dict[str, Any], record.get("params") or {})
        replay = Replay(
            game=name, params=dict(params), history=check_history(record.get("history", []))
        )
    else:
        raise ReplayError("expected a JSON object or list")
    replay.params = {PARAM_ALIASES.get(k, k): v for k, v in {**replay.params, **extra}.items()}
    return replay


def load_game(replay: Replay) -> pyspiel.Game:
    register_games()
    names = [replay.game]
    if not replay.game.startswith("python_"):
        names.append("python_" + replay.game)
    registered = set(pyspiel.registered_names())
    for name in names:
        if name in registered:
            return pyspiel.load_game(name, replay.params)
    raise ReplayError(f"unknown game {replay.game!r} (tried {', '.join(names)})")


def player_label(state: pyspiel.State) -> str:
    player = state.current_player()
    if player == pyspiel.PlayerId.CHANCE:
        return "chance"
    if player == pyspiel.PlayerId.TERMINAL:
        return "terminal"
    return f"P{player}"


def run(replay: Replay, steps: bool, out: TextIO) -> int:
    game = load_game(replay)
    state = game.new_initial_state()
    print(f"game: {game}  actions: {len(replay.history)}", file=out)
    for index, action in enumerate(replay.history):
        legal = state.legal_actions()
        if state.is_terminal() or action not in legal:
            print(f"\nstep {index}: action {action} is illegal for {player_label(state)}", file=out)
            print(f"legal: {legal}\n{state}", file=out)
            return 1
        if steps:
            text = state.action_to_string(state.current_player(), action)
            print(f"{index:4d} {player_label(state):>8}: {action} ({text})", file=out)
        state.apply_action(action)
    print(f"\n--- state after {len(replay.history)} actions ({player_label(state)}) ---", file=out)
    print(state, file=out)
    if state.is_terminal():
        print(f"returns: {state.returns()}", file=out)
    return 0


def parse_param(text: str) -> tuple[str, Any]:
    key, sep, value = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError(f"expected key=value, got {text!r}")
    try:
        return key, json.loads(value)
    except json.JSONDecodeError:
        return key, value


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(description="Rebuild a game from an action history.")
    parser.add_argument("file", type=Path, help="report, replay export or action-list JSON")
    parser.add_argument("--game", help="pyspiel game name (overrides the file)")
    parser.add_argument("--param", action="append", default=[], type=parse_param, metavar="K=V")
    parser.add_argument("--steps", action="store_true", help="print every action as it is applied")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
        replay = parse(data, args.game, dict(cast(list[tuple[str, Any]], args.param)))
        return run(replay, args.steps, out)
    except (OSError, json.JSONDecodeError, ReplayError) as error:
        print(f"replay: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
