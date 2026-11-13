"""The web card viewer's generated card data must match data/components."""

from tools.export_card_data import OUT, render


def test_card_data_json_is_current() -> None:
    assert OUT.read_text() == render(), "run: uv run python -m tools.export_card_data"
