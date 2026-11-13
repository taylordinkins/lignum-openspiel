"""Component data loader (R-004..R-011, R-013, R-075).

All card, path and setup values are read from data/components/*.yaml; nothing is hard-coded here.
Sequences keep YAML order (ACTIONS 1.5 indexes tasks, buildings and PW cards by that order).
"""

from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import yaml

DEFAULT_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "components"


class Record(Mapping[Any, Any]):
    """Immutable ordered mapping that also allows attribute access for string keys."""

    __slots__ = ("_d",)

    def __init__(self, d: Mapping[Any, Any]) -> None:
        object.__setattr__(self, "_d", dict(d))

    def __getitem__(self, key: Any) -> Any:
        return self._d[key]  # pyright: ignore[reportUnknownVariableType]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __getattr__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, "_d")[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}")

    def __repr__(self) -> str:
        return f"Record({self._d!r})"


def _freeze(v: Any) -> Any:
    if isinstance(v, dict):
        return Record({k: _freeze(x) for k, x in v.items()})  # pyright: ignore[reportUnknownVariableType]
    if isinstance(v, list):
        return tuple(_freeze(x) for x in v)  # pyright: ignore[reportUnknownVariableType]
    return v


@dataclass(frozen=True)
class Requirement:
    kind: str
    milled: bool
    drying: int


@dataclass(frozen=True)
class Task:
    id: str
    reward: int
    requirements: tuple[Requirement, ...]


@dataclass(frozen=True)
class PlacementCard:
    id: str
    areas: Mapping[int, tuple[str, ...]]
    food_areas: tuple[int, ...]


@dataclass(frozen=True)
class Half:
    food: int
    heating: int


@dataclass(frozen=True)
class WinterCard:
    id: str
    year: int
    halves: Mapping[str, Half]


@dataclass(frozen=True)
class PlannedWork:
    id: str
    name: str
    seasons: tuple[str, ...]
    params: Mapping[str, Any]


@dataclass(frozen=True)
class Building:
    id: str
    name: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class Location:
    id: str
    number: int
    kind: str
    name: str
    capacity: int


@dataclass(frozen=True)
class ForestClearing:
    slots: tuple[str, ...]
    capacity_per_slot: int


@dataclass(frozen=True)
class Path:
    sides: Mapping[str, tuple[Location, ...]]
    token_spot_count: int
    forest_clearing: ForestClearing


# Setup is a Record: attributes equal the setup.yaml top-level keys (nested mappings likewise).
Setup = Record


@dataclass(frozen=True)
class Components:
    tasks: tuple[Task, ...]
    placement: tuple[PlacementCard, ...]
    winter: tuple[WinterCard, ...]
    planned_work: tuple[PlannedWork, ...]
    buildings: tuple[Building, ...]
    path: Path
    setup: Record


def _read(d: pathlib.Path, name: str) -> dict[str, Any]:
    with (d / name).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_components(data_dir: pathlib.Path | str | None = None) -> Components:
    """Load and freeze all component data; FileNotFoundError if a file or the dir is missing."""
    d = DEFAULT_DATA_DIR if data_dir is None else pathlib.Path(data_dir)
    cards = _read(d, "cards.yaml")
    pw = _read(d, "planned_work.yaml")
    bld = _read(d, "buildings.yaml")
    path = _read(d, "path.yaml")
    setup = _read(d, "setup.yaml")
    fc = path["forest_clearing"]
    return Components(
        tasks=tuple(
            Task(
                t["id"],
                t["reward"],
                tuple(Requirement(q["kind"], q["milled"], q["drying"]) for q in t["requirements"]),
            )
            for t in cards["tasks"]
        ),
        placement=tuple(
            PlacementCard(
                p["id"],
                Record({a: tuple(w) for a, w in p["areas"].items()}),
                tuple(p["food_areas"]),
            )
            for p in cards["placement"]
        ),
        winter=tuple(
            WinterCard(
                w["id"],
                w["year"],
                Record({k: Half(h["food"], h["heating"]) for k, h in w["halves"].items()}),
            )
            for w in cards["winter"]
        ),
        planned_work=tuple(
            PlannedWork(p["id"], p["name"], tuple(p["seasons"]), _freeze(p["params"]))
            for p in pw["planned_work"]
        ),
        buildings=tuple(
            Building(b["id"], b["name"], _freeze(b["params"])) for b in bld["buildings"]
        ),
        path=Path(
            sides=Record(
                {
                    side: tuple(
                        Location(
                            loc["id"], loc["number"], loc["kind"], loc["name"], loc["capacity"]
                        )
                        for loc in v["locations"]
                    )
                    for side, v in path["sides"].items()
                }
            ),
            token_spot_count=path["token_spot_count"],
            forest_clearing=ForestClearing(tuple(fc["slots"]), fc["capacity_per_slot"]),
        ),
        setup=_freeze(setup),
    )
