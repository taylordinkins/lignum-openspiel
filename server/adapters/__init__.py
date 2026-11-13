"""Adapter registry. The real Lignum adapter registers itself here (Phase 3 unit 2)."""

from __future__ import annotations

import importlib
from collections.abc import Callable

from server.adapters.base import GameAdapter

_FACTORIES: dict[str, Callable[[], GameAdapter]] = {}


def register_adapter(name: str, factory: Callable[[], GameAdapter]) -> None:
    _FACTORIES[name] = factory


def get_adapter(name: str) -> GameAdapter:
    try:
        return _FACTORIES[name]()
    except KeyError:
        raise KeyError(f"no adapter registered for game {name!r}") from None


def default_adapters() -> dict[str, GameAdapter]:
    """One instance of every registered adapter, keyed by game name."""
    return {name: factory() for name, factory in _FACTORIES.items()}


importlib.import_module("server.adapters.lignum")  # registers "lignum"
