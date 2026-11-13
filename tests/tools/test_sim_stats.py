"""Fast test for tools/sim_stats.py: 5 games of one configuration, with invariants."""

import json
from pathlib import Path

from tools import sim_stats


def run(tmp_path: Path, jobs: int) -> dict[str, object]:
    out = tmp_path / f"r{jobs}.json"
    argv = ["--games", "1", "--players", "2", "--seed", "3", "--jobs", str(jobs)]
    argv += ["--invariants", "--json", str(out), "--violations", str(tmp_path / "v.json")]
    assert sim_stats.main(argv) == 0
    return json.loads(out.read_text())


def test_report_is_complete_and_independent_of_jobs(tmp_path: Path) -> None:
    one, two = run(tmp_path, 1), run(tmp_path, 2)
    assert one == two
    assert one["games"] == 8 and one["violations"] == 0
    d = one["by_players"]["2"]  # type: ignore[index]
    assert d["games"] == 8
    assert set(d["dollars"]) == {"min", "mean", "max", "stdev"}
    assert d["steps"]["min"] > 0
    assert "loans_distribution" in d and "winners" in d
    assert not (tmp_path / "v.json").exists()
