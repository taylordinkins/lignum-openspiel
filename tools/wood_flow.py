"""Wood-flow funnel tables (cut -> transported -> sawing area -> sawn -> outcome), per round.

    uv run python -m tools.wood_flow playtest/reports/<id>.json      # one report / replay history
    uv run python -m tools.wood_flow --tournament --players 2 --games 100 --seed 21 \
        --bots heuristic-v2,heuristic-v1                              # any tools.tournament args

The first form replays the history under ``tools.ledger.Ledger`` and prints each seat's table; a
history that stops before the end says so and reports the rounds it covers. The second form is
``tools.tournament`` (whose text report contains the same tables as means per game).
Counters are defined in ``tools/ledger.py`` (module docstring). Cells: pieces; hardwood alone in
the second table of each pair.
Exit codes: 0 ok, 1 an action was illegal, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, TextIO, cast

from tools.ledger import WOOD_GAUGES, WOOD_KEYS, Ledger
from tools.replay import ReplayError, load_game, parse

ROUNDS = range(1, 9)
# (counter, header) in funnel order; shown for all wood and again for hardwood.
COLUMNS = (
    ("cut", "cut"),
    ("move_bearer", "bear"),
    ("move_wagon", "wagon"),
    ("move_sledge", "sledge"),
    ("move_raft", "raft"),
    ("arr_saw", "arrSaw"),
    ("arr_sale", "arrSale"),
    ("sawn", "sawn"),
    ("sold", "sold"),
    ("dried", "dried"),
    ("tasks", "tasks"),
    ("joinery", "joinry"),
    ("heated", "heat"),
    ("other_in", "othIn"),
    ("saw_extra", "sawXtr"),
    ("unexplained", "unexpl"),
)
GAUGE_COLUMNS = (
    ("avail_sale", "@sale"),
    ("avail_d1", "@dry1"),
    ("avail_d2", "@dry2"),
    ("avail_d3", "@dry3"),
)


class IllegalHistoryAction(Exception):
    """The history holds an action that is illegal (or follows the end of the game)."""

    def __init__(self, index: int) -> None:
        super().__init__(index)
        self.index = index


def aggregate(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean per game of Ledger.wood_flow() entries (one per game and seat)."""
    n = len(games)
    keys = [k + sfx for k in WOOD_KEYS for sfx in ("", "_hw")]
    gkeys = [k + sfx for k in WOOD_GAUGES for sfx in ("", "_hw")]
    rounds: dict[str, dict[str, float]] = {}
    gauges: dict[str, dict[str, float]] = {}
    for r in ROUNDS:
        rounds[str(r)] = {k: sum(g["rounds"].get(r, {}).get(k, 0) for g in games) / n for k in keys}
        gauges[str(r)] = {
            k: sum(g["gauges"].get(r, {}).get(k, 0) for g in games) / n for k in gkeys
        }
    total = {k: sum(v[k] for v in rounds.values()) for k in keys}
    return {
        "games": n,
        "rounds": rounds,
        "total": total,
        "gauges": gauges,
        "unsold": statistics.fmean(g["unsold"] for g in games) if games else 0.0,
        "unsold_hw": statistics.fmean(g["unsold_hw"] for g in games) if games else 0.0,
    }


def format_flow(label: str, flow: dict[str, Any], rounds: range = ROUNDS) -> list[str]:
    """Two tables (all wood, hardwood) for one aggregate; ``flow`` is ``aggregate``'s output."""
    lines: list[str] = []
    for sfx, title in (("", "all wood"), ("_hw", "hardwood")):
        lines.append(
            f"{label} wood flow, {title} (mean pieces per game; @ = held at task phase start)"
        )
        head = f"{'rnd':<4}" + "".join(f"{h:>8}" for _, h in COLUMNS + GAUGE_COLUMNS)
        lines.append(head)
        for r in [*rounds, 0]:
            row = flow["total"] if r == 0 else flow["rounds"][str(r)]
            gau = None if r == 0 else flow["gauges"][str(r)]
            cells = "".join(f"{row[k + sfx]:>8.2f}" for k, _ in COLUMNS)
            cells += "".join(
                f"{'' if gau is None else format(gau[k + sfx], '.2f'):>8}" for k, _ in GAUGE_COLUMNS
            )
            lines.append(f"{'all' if r == 0 else r:<4}" + cells)
        unsold = flow["unsold" + sfx]
        lines.append(f"unsold at game end (still in play): {unsold:.2f}")
    return lines


def replay_flow(replay: Any) -> tuple[Ledger, int, bool]:
    """Replay ``replay`` under a Ledger; returns (ledger, actions applied, terminal)."""
    game = load_game(replay)
    state = game.new_initial_state()
    ledger = Ledger(state)
    for index, action in enumerate(replay.history):
        if state.is_terminal() or action not in state.legal_actions():
            raise IllegalHistoryAction(index)
        ledger.apply(action)
    return ledger, len(replay.history), state.is_terminal()


def run_file(path: Path, out: TextIO) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        replay = parse(cast(object, data), None, {})
        ledger, applied, terminal = replay_flow(replay)
    except IllegalHistoryAction as error:
        print(f"wood_flow: action {error.index} of the history is illegal", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, ReplayError) as error:
        print(f"wood_flow: {error}", file=sys.stderr)
        return 2
    st = ledger.state
    if terminal:
        print(f"{path.name}: complete game, {applied} actions", file=out)
    else:
        print(
            f"{path.name}: PARTIAL history, {applied} actions, stopped in round {st.round} "
            f"(not terminal; rounds beyond {st.round} are empty, round {st.round} is incomplete)",
            file=out,
        )
    covered = range(1, min(st.round, 8) + 1)
    for seat, flow in enumerate(ledger.wood_flow()):
        print(file=out)
        agg = aggregate([flow])
        for line in format_flow(f"P{seat}", agg, covered):
            print(line, file=out)
    return 0


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--tournament":
        from tools.tournament import main as tournament_main

        return tournament_main(args[1:], out)
    parser = argparse.ArgumentParser(description="Wood-flow funnel of one action history.")
    parser.add_argument("file", type=Path, help="report, replay export or action-list JSON")
    return run_file(parser.parse_args(args).file, out)


if __name__ == "__main__":
    sys.exit(main())
