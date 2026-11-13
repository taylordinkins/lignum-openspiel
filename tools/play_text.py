"""Play Lignum in the terminal (human seats by action id, other seats a bot).

    uv run python -m tools.play_text --players 3 --seed 7 --human 0          # P0 is you
    uv run python -m tools.play_text --players 2 --seed 1 --auto             # all random

Seats are shown as P0..P3. A human seat sees its own observation string and the numbered legal
actions (id and name); enter the id, or ``q`` to quit. Chance and bot seats use a seeded RNG.
Exit codes: 0 finished, 1 quit, 2 bad input.
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Any, TextIO

import pyspiel

from lignum import actions as A
from lignum.bots.plan import format_plan, task_plan
from lignum.game import PHASE_PK, PHASE_W5
from tools.replay import ReplayError, load_game

SIDES = ("joinery", "base")
BOTS = ("random",)


def parse_seats(text: str, players: int) -> set[int]:
    seats: set[int] = {int(p) for p in text.replace(",", " ").split()}
    if any(not 0 <= s < players for s in seats):
        raise ValueError(f"seats must be in 0..{players - 1}, got {sorted(seats)}")
    return seats


def choose_human(
    state: pyspiel.State, seat: int, inp: TextIO, out: TextIO, view: bool = True
) -> int | None:
    legal = state.legal_actions()
    if view:
        print(f"\n{state.observation_string(seat)}", file=out)
    print(f"P{seat} to act. Legal actions:", file=out)
    for a in legal:
        print(f"  {a:4d}  {state.action_to_string(seat, a)}", file=out)
    while True:
        print("action id (q to quit)> ", end="", file=out, flush=True)
        line = inp.readline()
        if not line or line.strip().lower() in ("q", "quit"):
            return None
        try:
            choice = int(line.strip())
        except ValueError:
            choice = -1
        if choice in legal:
            return choice
        print(f"not a legal action id: {line.strip()!r}", file=out)


def play(
    game: pyspiel.Game,
    seed: int,
    human: set[int],
    out: TextIO,
    inp: TextIO,
    verbose: bool = False,
    show_plan: bool = False,
) -> int:
    rng = random.Random(seed)
    state: Any = game.new_initial_state()
    step = 0
    shown: set[tuple[int, int]] = set()
    while not state.is_terminal():
        player = state.current_player()
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            action = rng.choices(actions, weights=probs)[0]
            who = "chance"
        elif player in human:
            picked = choose_human(state, player, inp, out)
            if picked is None:
                print("quit", file=out)
                return 1
            action, who = picked, f"P{player}"
        else:
            action = rng.choice(state.legal_actions())
            who = f"P{player}"
        if (
            show_plan
            and not state.is_chance_node()
            and state.phase == PHASE_W5
            and (
                state.round,
                player,
            )
            not in shown
        ):  # bot planner diagnostics, once per seat and round
            shown.add((state.round, player))
            print(f"P{player} {format_plan(task_plan(state, player))}", file=out)
        hidden = (
            player not in human
            and not state.is_chance_node()
            and state.phase == PHASE_PK
            and A.decode(action).name == "PICK_AREA"
        )
        if hidden:  # R-038: another seat's pick stays hidden until the reveal
            print(f"{step:5d} {who:>6}: picked", file=out)
        elif verbose or player in human or who != "chance":
            print(f"{step:5d} {who:>6}: {action} ({state.action_to_string(player, action)})",
                  file=out)  # fmt: skip
        state.apply_action(action)
        step += 1
    print(f"\n--- final state after {step} steps ---\n{state}", file=out)
    print(f"returns: {state.returns()}", file=out)
    return 0


def main(argv: list[str] | None = None, out: TextIO = sys.stdout, inp: TextIO = sys.stdin) -> int:
    parser = argparse.ArgumentParser(description="Play Lignum in the terminal.")
    parser.add_argument("--players", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--side", choices=SIDES, default="joinery", help="path side")
    parser.add_argument("--returns", choices=("win_loss", "margin"), default="win_loss")
    parser.add_argument("--easy-winter", action="store_true")
    parser.add_argument("--bot", choices=BOTS, default="random", help="policy of non-human seats")
    parser.add_argument("--human", default="", help="human seats, e.g. 0 or 0,2")
    parser.add_argument("--auto", action="store_true", help="all seats random, non-interactive")
    parser.add_argument("--plan", action="store_true", help="print each seat's task plan per round")
    parser.add_argument("--verbose", action="store_true", help="also print chance outcomes")
    args = parser.parse_args(argv)
    try:
        human: set[int] = set() if args.auto else parse_seats(args.human, args.players)
        from tools.replay import Replay

        game = load_game(
            Replay(
                game="lignum",
                params={
                    "players": args.players,
                    "joinery": args.side == "joinery",
                    "returns": args.returns,
                    "easy_winter": args.easy_winter,
                },
            )
        )
        return play(game, args.seed, human, out, inp, args.verbose, args.plan)
    except (ValueError, ReplayError, pyspiel.SpielError) as error:
        print(f"play_text: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
