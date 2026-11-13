"""Generate the golden playthroughs in tests/playthroughs/ (deterministic, fixed seeds).

    uv run python -m tools.make_playthroughs [--out DIR]

Each file is a replay export that ``tools.replay`` accepts (``game``, ``params``, ``history``) plus
``trace`` (one ``[player, action, action_text, digest]`` row per applied action, the digest being
the SHA-1 prefix of the state string and every seat's observation string after the action) and the
final ``returns`` and ``final_dollars``. Regenerating goldens needs a stated reason in the commit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pyspiel

from tools.sim_common import Combo, combo_params, load, random_playout

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "playthroughs"

# (name, seed, combo): 2/3/4 players, both path sides, both return modes, both winter modes.
PLAYTHROUGHS: list[tuple[str, int, Combo]] = [
    ("p2_joinery_win_loss_std", 7, (2, True, "win_loss", False)),
    ("p3_base_margin_easy", 16, (3, False, "margin", True)),
    ("p4_joinery_margin_std", 25, (4, True, "margin", False)),
    # Phase 4: planned work, huts, buildings and craftwork sets all occur (unit 15).
    ("p4_joinery_phase4_std", 44, (3, True, "margin", False)),
]


def digest(state: pyspiel.State) -> str:
    parts = [str(state)]
    if not state.is_terminal():
        parts += [state.observation_string(p) for p in range(state.get_game().num_players())]
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()[:16]


def record(seed: int, combo: Combo) -> dict[str, Any]:
    """Play the seeded random game and record history, trace and results."""
    game = load(combo)
    trace: list[list[Any]] = []
    replay = game.new_initial_state()

    def step(state: pyspiel.State) -> None:
        action = state.history()[-1]
        player = replay.current_player()
        trace.append([player, action, replay.action_to_string(player, action), ""])
        replay.apply_action(action)
        trace[-1][3] = digest(replay)

    final = random_playout(game, seed, step)
    return {
        "game": "lignum",
        "params": combo_params(combo),
        "seed": seed,
        "history": [int(a) for a in final.history()],
        "trace": trace,
        "returns": [float(r) for r in final.returns()],
        "final_dollars": [int(x) for x in getattr(final, "final", ())],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate golden playthroughs.")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--only", nargs="+", help="generate only these golden names")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, seed, combo in PLAYTHROUGHS:
        path = args.out / f"{name}.json"
        if args.only and name not in args.only:
            continue
        data = record(seed, combo)
        path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(f"{path}: {len(data['history'])} actions, returns {data['returns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
