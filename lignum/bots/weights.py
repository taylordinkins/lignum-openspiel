"""Bot weight profiles (Phase 7 unit 1a): YAML files under ``data/bots/``.

A profile name ``p`` is ``data/bots/<p with - and . as _>.yaml``: ``heuristic`` is the tunable
working copy, ``heuristic-v1`` the frozen Phase 6 bot. Each file holds the heuristic's stop /
plan / pick weights and a ``value:`` section with the value-function weights. Loaded profiles are
cached and returned as read-only (recursively ``MappingProxyType``, lists as tuples), so no bot can
mutate weights shared with another; copy with ``copy.deepcopy`` or ``dict(...)`` to tweak.
"""

from __future__ import annotations

import pathlib
from collections.abc import Mapping
from functools import cache
from types import MappingProxyType
from typing import Any, cast

import yaml

BOTS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "bots"
HEURISTIC_YAML = BOTS_DIR / "heuristic.yaml"
DEFAULT_PROFILE = "heuristic"


def profile_path(profile: str) -> pathlib.Path:
    """Path of a profile's YAML file (``-`` and ``.`` in the name become ``_``)."""
    return BOTS_DIR / (profile.replace("-", "_").replace(".", "_") + ".yaml")


def _freeze(x: Any) -> Any:
    if isinstance(x, dict):
        d = cast("dict[str, Any]", x)
        return MappingProxyType({k: _freeze(v) for k, v in d.items()})
    if isinstance(x, list):
        return tuple(_freeze(v) for v in cast("list[Any]", x))
    return x


def thaw(x: Any) -> Any:
    """Mutable deep copy of a frozen profile (dicts and lists)."""
    if isinstance(x, Mapping):
        return {k: thaw(v) for k, v in cast("Mapping[str, Any]", x).items()}
    if isinstance(x, tuple):
        return [thaw(v) for v in cast("tuple[Any, ...]", x)]
    return x


@cache
def _load(path: pathlib.Path) -> Mapping[str, Any]:
    with open(path, encoding="utf-8") as f:
        return _freeze(yaml.safe_load(f))


def load_weights(path: pathlib.Path = HEURISTIC_YAML) -> Mapping[str, Any]:
    """The tuning weights in ``path`` (cached per path, so the default profile is always the same
    read-only object)."""
    return _load(path)


def load_profile(profile: str = DEFAULT_PROFILE) -> Mapping[str, Any]:
    return load_weights(profile_path(profile))


def value_weights(profile: str = DEFAULT_PROFILE) -> Mapping[str, Any]:
    """The ``value:`` section of a profile."""
    return load_profile(profile)["value"]
