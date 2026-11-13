# pyright: basic, reportMissingImports=false
"""Fit the per-component value regression from collected games (Phase 7 unit 3a).

    uv run --group bots python -m tools.fit_value --data data/bot_games

Input: ``<data>/*.jsonl.gz`` and ``manifest.json`` written by ``tools/collect_games.py``
(format: docs/BOT_DATA.md, schema 1). Every recorded decision gives one sample per seat: that
seat's raw features, the opponent's money and loan_repay, and the round. Targets are the realised
future dollars per component, ``footer.breakdown[seat][c] - row.acc[seat][c]``, for wood_sales,
joinery, tasks, office, craftwork, winter, loan_repayment and ``rest`` (all other components).
A ridge regression per component is fitted on standardised features and the standardisation is
folded into the coefficients, so a runtime needs only ``intercept + sum(coef * feature)``.
Games (not rows) are split by seed into train and validation. The hand-set value is the baseline:
its parts map onto components as in docs/BOT_DATA.md (the ``money`` part is current money, not a
future payoff, so it is left out; ``plans``, ``buildings`` and ``income`` go to ``rest``).
Needs the optional ``bots`` dependency group (numpy, scikit-learn). Exit codes: 0 ok, 2 bad input.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from tools.collect_games import PLAYERS

SCHEMA_VERSION = 1
FIT_COMPONENTS: tuple[str, ...] = (
    "wood_sales",
    "joinery",
    "tasks",
    "office",
    "craftwork",
    "winter",
    "loan_repayment",
    "rest",
)
# hand-set part -> fit component (the money part is excluded: it is not a future payoff)
PART_TO_COMPONENT = {
    "wood": "wood_sales",
    "joinery": "joinery",
    "tasks": "tasks",
    "office": "office",
    "craft": "craftwork",
    "winter": "winter",
    "loan": "loan_repayment",
    "plans": "rest",
    "buildings": "rest",
    "income": "rest",
}
EXTRA_NAMES = ("opp_money", "opp_loan_repay", "round")


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_games(data: Path) -> list[list[dict[str, Any]]]:
    """Every game file as its list of records (header, rows..., footer), sorted by seed."""
    games: list[list[dict[str, Any]]] = []
    for path in sorted(data.glob("*.jsonl.gz"), key=lambda p: int(p.name.split(".")[0])):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            games.append([json.loads(line) for line in fh if line.strip()])
    return games


def build_samples(games: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Arrays per sample: X, Y (components), base (hand-set parts by component), round, seed."""
    import numpy as np

    header = games[0][0]
    feats: list[str] = header["feature_names"]
    parts: list[str] = header["part_names"]
    comps: list[str] = header["components"]
    imax = feats.index("money")
    irep = feats.index("loan_repay")
    X: list[list[float]] = []
    Y: list[list[float]] = []
    B: list[list[float]] = []
    rnd: list[int] = []
    seeds: list[int] = []
    for rec in games:
        h, footer = rec[0], rec[-1]
        if h["feature_names"] != feats or h["components"] != comps or h["part_names"] != parts:
            raise ValueError(f"seed {h['seed']}: header names differ from the first game")
        for row in rec[1:-1]:
            for s in (0, 1):
                f = row["f"][s]
                o = row["f"][1 - s]
                X.append([*f, o[imax], o[irep], row["round"]])
                fut = [footer["breakdown"][s][i] - row["acc"][s][i] for i in range(len(comps))]
                by = dict(zip(comps, fut, strict=True))
                direct = {c: by[c] for c in FIT_COMPONENTS if c != "rest"}
                direct["rest"] = sum(fut) - sum(v for c, v in direct.items())
                Y.append([direct[c] for c in FIT_COMPONENTS])
                base = dict.fromkeys(FIT_COMPONENTS, 0.0)
                for p, v in zip(parts, row["v"][s], strict=True):
                    if p in PART_TO_COMPONENT:
                        base[PART_TO_COMPONENT[p]] += v
                B.append([base[c] for c in FIT_COMPONENTS])
                rnd.append(row["round"])
                seeds.append(h["seed"])
    return {
        "X": np.array(X, dtype=float),
        "Y": np.array(Y, dtype=float),
        "B": np.array(B, dtype=float),
        "round": np.array(rnd),
        "seed": np.array(seeds),
        "feature_names": [*feats, *EXTRA_NAMES],
    }


def split_seeds(
    seeds: list[int], val_fraction: float, split_seed: int
) -> tuple[set[int], set[int]]:
    """Deterministic game-level split: (train seeds, validation seeds)."""
    ordered = sorted(seeds)
    random.Random(split_seed).shuffle(ordered)
    n_val = max(1, round(len(ordered) * val_fraction)) if len(ordered) > 1 else 0
    return set(ordered[n_val:]), set(ordered[:n_val])


def fit_ridge(X: Any, y: Any, alpha: float) -> tuple[Any, float]:
    """Ridge on standardised X; returns (coef, intercept) in raw feature units."""
    import numpy as np
    from sklearn.linear_model import Ridge

    mean = X.mean(axis=0)
    std = X.std(axis=0)
    ok = std > 1e-12
    Z = (X - mean) / np.where(ok, std, 1.0)
    model = Ridge(alpha=alpha).fit(Z[:, ok], y)
    coef = np.zeros(X.shape[1])
    coef[ok] = model.coef_ / std[ok]
    intercept = float(model.intercept_ - (coef * mean).sum())
    return coef, intercept


def errors(pred: Any, y: Any) -> dict[str, float]:
    import numpy as np

    d = pred - y
    return {
        "rmse": float(np.sqrt((d**2).mean())) if len(d) else 0.0,
        "mae": float(np.abs(d).mean()) if len(d) else 0.0,
    }


def fit(
    data: Path, out: Path, val_fraction: float, split_seed: int, alpha: float
) -> dict[str, Any]:
    import numpy as np

    games = load_games(data)
    if not games:
        raise ValueError(f"no *.jsonl.gz games in {data}")
    for g in games:
        if g[0].get("schema") != SCHEMA_VERSION:
            raise ValueError(f"seed {g[0].get('seed')}: schema {g[0].get('schema')} != 1")
    s = build_samples(games)
    train_seeds, val_seeds = split_seeds([g[0]["seed"] for g in games], val_fraction, split_seed)
    tr = np.isin(s["seed"], list(train_seeds))
    va = np.isin(s["seed"], list(val_seeds))
    if not va.any() or not tr.any():
        raise ValueError("need at least 2 games for a held-out split")
    X, Y, B = s["X"], s["Y"], s["B"]
    coefs: dict[str, Any] = {}
    pred = np.zeros_like(Y)
    for j, c in enumerate(FIT_COMPONENTS):
        coef, b = fit_ridge(X[tr], Y[tr, j], alpha)
        coefs[c] = {
            "intercept": b,
            "coef": {n: float(v) for n, v in zip(s["feature_names"], coef, strict=True) if v != 0},
        }
        pred[:, j] = X @ coef + b

    def table(mask: Any) -> dict[str, Any]:
        t: dict[str, Any] = {"rows": int(mask.sum())}
        for j, c in enumerate(FIT_COMPONENTS):
            t[c] = {
                "fit": errors(pred[mask, j], Y[mask, j]),
                "hand": errors(B[mask, j], Y[mask, j]),
            }
        t["total"] = {
            "fit": errors(pred[mask].sum(axis=1), Y[mask].sum(axis=1)),
            "hand": errors(B[mask].sum(axis=1), Y[mask].sum(axis=1)),
        }
        return t

    by_round = {int(r): table(va & (s["round"] == r)) for r in sorted(set(s["round"][va].tolist()))}
    manifest_path = data / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    seeds = sorted(g[0]["seed"] for g in games)
    mix: dict[str, int] = {}
    for g in games:
        key = ",".join(g[0]["seats"])
        mix[key] = mix.get(key, 0) + 1
    result: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "git_sha": git_sha(),
        "data": {
            "seed_min": seeds[0],
            "seed_max": seeds[-1],
            "games": len(games),
            "mix": mix,
            "matchups": manifest.get("matchups"),
            "every": games[0][0].get("every"),
            "value_profile": games[0][0].get("value_profile"),
            "collector_git_sha": manifest.get("git_sha"),
        },
        "split": {
            "val_fraction": val_fraction,
            "split_seed": split_seed,
            "train_games": len(train_seeds),
            "val_games": len(val_seeds),
            "train_rows": int(tr.sum()),
            "val_rows": int(va.sum()),
        },
        "game_params": {"players": PLAYERS, "joinery": True, "easy_winter": False},
        "model": {"kind": "ridge", "alpha": alpha},
        "feature_names": s["feature_names"],
        "components": coefs,
        "held_out": {"overall": table(va), "by_round": by_round},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(result, sort_keys=False))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fit per-component future-dollar regressions.")
    ap.add_argument("--data", type=Path, default=Path("data/bot_games"))
    ap.add_argument("--out", type=Path, default=Path("data/bots/value_fit.yaml"))
    ap.add_argument("--val-fraction", type=float, default=0.2)
    ap.add_argument("--split-seed", type=int, default=0)
    ap.add_argument("--alpha", type=float, default=10.0, help="ridge strength (standardised X)")
    a = ap.parse_args(argv)
    try:
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError:
        print("numpy/scikit-learn missing: run `uv sync --group bots`", file=sys.stderr)
        return 2
    try:
        r = fit(a.data, a.out, a.val_fraction, a.split_seed, a.alpha)
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    o = r["held_out"]["overall"]
    print(f"{r['data']['games']} games, held-out rows {o['rows']}; RMSE/MAE fit vs hand-set ($)")
    for c in (*FIT_COMPONENTS, "total"):
        f, h = o[c]["fit"], o[c]["hand"]
        fit_s = f"{f['rmse']:6.2f}/{f['mae']:6.2f}"
        print(f"  {c:15s} fit {fit_s}   hand {h['rmse']:6.2f}/{h['mae']:6.2f}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
