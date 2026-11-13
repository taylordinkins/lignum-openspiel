"""Tests for the advisory third-party asset check (PLAN.md D11, D21)."""

from tools.check_third_party import stray_assets


def test_assets_under_allowed_dirs_pass() -> None:
    paths = [
        "third_party/art/cards/task_01.png",
        "third_party/rules/lignum_rulebook.pdf",
        "assets/generic/board.svg",
        "lignum/game.py",
    ]
    assert stray_assets(paths) == []


def test_assets_elsewhere_are_reported() -> None:
    paths = ["web/public/board.PNG", "docs/rules.pdf", "web/src/font.woff2", "README.md"]
    assert stray_assets(paths) == ["docs/rules.pdf", "web/public/board.PNG", "web/src/font.woff2"]
