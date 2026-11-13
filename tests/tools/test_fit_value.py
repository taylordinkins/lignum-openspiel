"""tools.fit_value on a tiny synthetic dataset (needs the optional `bots` group)."""

import gzip
import json
from pathlib import Path

import pytest
import yaml

pytest.importorskip("numpy")
pytest.importorskip("sklearn")

from tools.fit_value import FIT_COMPONENTS, main  # noqa: E402

FEATS = ["money", "loan_repay", "tasks_held"]
PARTS = ["money", "wood", "tasks"]
COMPS = [
    "start",
    "wood_sales",
    "joinery",
    "tasks",
    "office",
    "craftwork",
    "winter",
    "loan_repayment",
    "spending",
]


def write_game(d: Path, seed: int) -> None:
    rows = []
    for k in range(6):
        rows.append(
            {
                "type": "row",
                "d": k,
                "step": k,
                "round": 1 + k,
                "phase": 0,
                "p": k % 2,
                "f": [[k + seed % 3, 0, k % 2], [k, 1, 0]],
                "v": [[k, 1.0, 2.0], [k, 0.0, 0.0]],
                "acc": [[10, k, 0, 0, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0, 0, 0, 0]],
            }
        )
    header = {
        "type": "header",
        "schema": 1,
        "seed": seed,
        "seats": ["a", "b"],
        "every": 1,
        "value_profile": "x",
        "feature_names": FEATS,
        "part_names": PARTS,
        "components": COMPS,
    }
    footer = {
        "type": "footer",
        "seed": seed,
        "breakdown": [[10, 8, 0, 3, 0, 0, -2, 0, -1], [10, 2, 0, 0, 0, 0, 0, 0, 0]],
    }
    with gzip.open(d / f"{seed}.jsonl.gz", "wt") as fh:
        for rec in (header, *rows, footer):
            fh.write(json.dumps(rec) + "\n")


def test_fit_writes_expected_keys(tmp_path: Path) -> None:
    for seed in range(200, 210):
        write_game(tmp_path, seed)
    (tmp_path / "manifest.json").write_text(json.dumps({"git_sha": "abc", "matchups": ["a,b:10"]}))
    out = tmp_path / "fit.yaml"
    assert main(["--data", str(tmp_path), "--out", str(out)]) == 0
    r = yaml.safe_load(out.read_text())
    assert r["schema"] == 1
    assert r["data"]["games"] == 10 and r["data"]["seed_min"] == 200
    assert r["split"]["val_games"] == 2
    assert set(r["components"]) == set(FIT_COMPONENTS)
    assert r["feature_names"][:3] == FEATS
    assert {"fit", "hand"} <= set(r["held_out"]["overall"]["total"])
    assert r["held_out"]["by_round"]
    # deterministic
    out2 = tmp_path / "fit2.yaml"
    main(["--data", str(tmp_path), "--out", str(out2)])
    assert yaml.safe_load(out2.read_text()) == r


def test_empty_dir_exits_2(tmp_path: Path) -> None:
    assert main(["--data", str(tmp_path), "--out", str(tmp_path / "o.yaml")]) == 2
