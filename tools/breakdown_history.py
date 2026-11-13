"""Per-seat dollar breakdown and funnels of recorded games (e.g. human playtest reports).

    uv run python -m tools.breakdown_history playtest/reports            # every *.json in a dir
    uv run python -m tools.breakdown_history a.json b.json [--partial]

Each file is a report or replay export as read by ``tools.replay`` (``game``, ``params``,
``history``). The history is replayed through ``tools.ledger.Ledger``. A game is complete when its
history reaches the terminal state (the seats have final dollars, R-083); reports filed mid-game
are listed as partial and left out of the mean. Reports of one game (same seed and salt, filed at
different moments) count once, as the longest history. ``--partial`` also prints the tables of
partial games (money so far, no final sale). Exit codes: 0 ok, 1 an illegal action in a history,
2 bad input.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast

from tools.ledger import COMPONENTS, FUNNEL_KEYS, SPENDING_KEYS, WINTER_KEYS, Ledger
from tools.replay import Replay, ReplayError, load_game, parse


@dataclass
class Analysis:
    name: str
    key: tuple[Any, ...]
    actions: int
    complete: bool
    seats: list[str]
    final: list[int] | None
    breakdown: list[dict[str, int]]  # components so far (loan_repayment only when complete)
    detail: list[dict[str, dict[str, int]]]
    funnels: list[dict[str, int]]


def analyse_history(replay: Replay, name: str = "", seats: list[str] | None = None) -> Analysis:
    """Replay ``replay.history`` through the ledger. Raises ReplayError on an illegal action."""
    game = load_game(replay)
    state: Any = game.new_initial_state()
    ledger = Ledger(state)
    for index, action in enumerate(replay.history):
        if state.is_terminal() or action not in state.legal_actions():
            raise ReplayError(f"{name}: action {action} at step {index} is illegal")
        ledger.apply(action)
    complete = bool(state.is_terminal())
    parts = ledger.breakdown() if complete else [dict(p) for p in ledger.parts]
    return Analysis(
        name=name,
        key=(),
        actions=len(replay.history),
        complete=complete,
        seats=seats or [f"P{s}" for s in range(state.n)],
        final=[int(x) for x in state.final] if complete else None,
        breakdown=parts,
        detail=ledger.detail(),
        funnels=ledger.funnels(),
    )


def load_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        files.extend(sorted(p.glob("*.json")) if p.is_dir() else [p])
    return files


def analyse_file(path: Path) -> Analysis:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayError(f"{path}: {error}") from error
    replay = parse(data, None, {})
    record = cast(dict[str, Any], data) if isinstance(data, dict) else {}
    result = analyse_history(replay, path.name)
    kinds = record.get("seats")
    if isinstance(kinds, list) and len(cast(list[object], kinds)) == len(result.breakdown):
        result.seats = [f"P{i} {k}" for i, k in enumerate(cast(list[object], kinds))]
    result.key = (record.get("seed"), record.get("salt")) if "seed" in record else (path.name,)
    return result


def dedupe(items: list[Analysis]) -> list[Analysis]:
    """One entry per game (same seed and salt): the one with the longest history."""
    best: dict[tuple[Any, ...], Analysis] = {}
    for a in items:
        if a.key not in best or a.actions > best[a.key].actions:
            best[a.key] = a
    return list(best.values())


def seat_row(a: Analysis, seat: int) -> dict[str, float]:
    """Flat per-seat numbers: components, winter and spending parts, funnels."""
    row: dict[str, float] = {c: float(a.breakdown[seat][c]) for c in COMPONENTS}
    for key in WINTER_KEYS:
        row["w." + key] = float(a.detail[seat]["winter"][key])
    for key in SPENDING_KEYS:
        row["s." + key] = float(a.detail[seat]["spending"][key])
    for key, value in a.detail[seat]["winter_info"].items():
        row["i." + key] = float(value)
    for key in FUNNEL_KEYS:
        row["f." + key] = float(a.funnels[seat][key])
    row["final"] = float(a.final[seat]) if a.final else 0.0
    return row


def format_rows(rows: list[tuple[str, dict[str, float]]], out: TextIO) -> None:
    memo = [(k, k[2:]) for k in rows[0][1] if k.startswith("i.")]
    sections = [
        ("dollars by component", [(c, c) for c in COMPONENTS] + [("final", "final")]),
        (
            "winter and spending sub-components ($)",
            [("w." + k, k) for k in WINTER_KEYS] + [("s." + k, k) for k in SPENDING_KEYS],
        ),
        ("winter memo (units; forgiven $ and forced items are not extra money)", memo),
        (
            "funnels (tasks: taken, pieces, completed; joinery: joiners, placed, sold)",
            [("f." + k, k) for k in FUNNEL_KEYS],
        ),
    ]
    for title, cols in sections:
        print(f"\n{title}", file=out)
        width = max(9, *(len(label) + 1 for _, label in cols))
        print(f"{'seat':<22}" + "".join(f"{label:>{width}}" for _, label in cols), file=out)
        for label, row in rows:
            print(
                f"{label:<22}" + "".join(f"{row[key]:>{width}.1f}" for key, _ in cols),
                file=out,
            )


def report(items: list[Analysis], show_partial: bool, out: TextIO) -> None:
    unique = dedupe(items)
    done = [a for a in unique if a.complete]
    print(f"{len(items)} file(s), {len(unique)} distinct game(s), {len(done)} complete.", file=out)
    for a in sorted(items, key=lambda x: x.name):
        state = "complete" if a.complete else "PARTIAL (not at the end of the game)"
        print(f"  {a.name}: {a.actions} actions, {state}", file=out)
    if not done:
        print("\nNo complete game: nothing to average.", file=out)
    for a in done:
        print(f"\n=== {a.name} (complete, final dollars {a.final}) ===", file=out)
        format_rows([(a.seats[s], seat_row(a, s)) for s in range(len(a.seats))], out)
    if done:
        rows = [seat_row(a, s) for a in done for s in range(len(a.seats))]
        mean = {k: statistics.fmean(r[k] for r in rows) for k in rows[0]}
        print(f"\n=== mean over {len(rows)} seat(s) of {len(done)} complete game(s) ===", file=out)
        format_rows([("mean", mean)], out)
    if show_partial:
        for a in unique:
            if not a.complete:
                print(f"\n=== {a.name} (PARTIAL, {a.actions} actions, money so far) ===", file=out)
                format_rows([(a.seats[s], seat_row(a, s)) for s in range(len(a.seats))], out)


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(description="Dollar breakdown and funnels of recorded games.")
    parser.add_argument("paths", nargs="+", type=Path, help="history JSON files or directories")
    parser.add_argument("--partial", action="store_true", help="also print partial games")
    args = parser.parse_args(argv)
    try:
        files = load_files(args.paths)
        if not files:
            raise ReplayError("no .json files found")
        items = [analyse_file(f) for f in files]
    except ReplayError as error:
        print(f"breakdown_history: {error}", file=sys.stderr)
        return 2
    report(items, args.partial, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
