# pyright: reportPrivateUsage=false
"""Fitted value function (Phase 7 unit 3b): pure-Python evaluation of ``data/bots/value_fit.yaml``.

``tools/fit_value.py`` fits, per ledger component c, the future dollars the seat will still earn
from a state: ``future_c = intercept_c + sum(coef_c[f] * feature[f])`` (ridge, standardisation
already folded into the coefficients). Features are ``lignum.bots.features`` plus the opponent's
money and owed repayment and the round. No numpy: the runtime reads the YAML only.

Composition of the value of a seat (non-terminal state)::

    value = money_now + sum over components c of  part_c

where ``part_c`` is the fit's ``future_c`` for the components listed in the profile's
``value.fitted_components`` and the hand-set term (``lignum.bots.value``) for all others.
The components and their hand-set equivalents (the fit's baseline mapping, tools/fit_value.py):

  wood_sales      wood zones              craftwork       craftwork sets
  joinery         joinery pieces          winter          minus the weighted winter shortfall
  tasks           held tasks (no Office)  loan_repayment  minus the owed repayment (R-077)
  office          Office bonus            rest            plans + buildings + joiner income

``money_now`` is never predicted (it is exact) and the targets are realised future dollars
(final component minus the amount accrued so far), so ``final = money_now + sum(future_c)`` and no
component is counted twice or dropped: ``rest`` is whatever the other components do not cover
(spending, loan proceeds, joiner income, plans, buildings). With every component fitted the value
is the plain regression of final dollars; with none it equals the hand-set ``value()``.
Profile keys (in ``value:``): ``value_fit`` (path of the fit YAML, relative to the repo root) and
``fitted_components`` (list of the component names above).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from lignum.bots.features import FEATURE_NAMES, features
from lignum.bots.value import (  # pyright: ignore[reportPrivateUsage]
    _craft_value,
    _future_income,
    _joinery_value,
    _task_value,
    _winter_cost,
    _wood_zone_value,
    value,
)
from lignum.bots.weights import BOTS_DIR, value_weights
from lignum.game import PHASE_SF, LignumState
from lignum.rules import SetupTables, building_param, has_building

EXTRA_NAMES = ("opp_money", "opp_loan_repay", "round")
COMPONENTS = (
    "wood_sales",
    "joinery",
    "tasks",
    "office",
    "craftwork",
    "winter",
    "loan_repayment",
    "rest",
)
ROOT = BOTS_DIR.parent.parent
_IMONEY = FEATURE_NAMES.index("money")
_IREPAY = FEATURE_NAMES.index("loan_repay")

Weights = Mapping[str, Any]
Linear = tuple[float, tuple[tuple[int, float], ...]]  # intercept, ((feature index, coef), ...)
# Coefficients by component, the value weights the fit was trained with (feature scale) and the
# game parameters (players, joinery, easy_winter) it covers.
Fit = tuple[dict[str, Linear], Weights, tuple[int, bool, bool]]


@cache
def load_fit(path: str, components: tuple[str, ...]) -> Fit:
    """Coefficients of the listed components as (intercept, sparse coefficient list), the training
    value weights and the game parameters of the fit. Raises on a missing or malformed file."""
    p = Path(path)
    with open(p if p.is_absolute() else ROOT / p, encoding="utf-8") as f:
        fit = yaml.safe_load(f)
    names = [*FEATURE_NAMES, *EXTRA_NAMES]
    if fit["feature_names"] != names:
        raise ValueError(f"{path}: feature_names differ from lignum.bots.features")
    index = {n: i for i, n in enumerate(names)}
    out: dict[str, Linear] = {}
    for c in components:
        if c not in COMPONENTS:
            raise ValueError(f"unknown fitted component {c!r}")
        spec = fit["components"][c]
        out[c] = (
            float(spec["intercept"]),
            tuple((index[n], float(v)) for n, v in spec["coef"].items()),
        )
    gp = fit["game_params"]
    params = (int(gp["players"]), bool(gp["joinery"]), bool(gp["easy_winter"]))
    return out, value_weights(fit["data"]["value_profile"]), params


def _hand(c: str, state: LignumState, t: SetupTables, seat: int, w: Weights, dead: bool) -> float:
    """Hand-set term of component ``c`` (same as ``value_parts``)."""
    if c == "wood_sales":
        return _wood_zone_value(state, t, seat, w)
    if c == "joinery":
        return _joinery_value(state, t, seat, w)
    if c == "tasks" or c == "office":
        office = 0.0
        if has_building(t, state.held_buildings, seat, "office"):
            office = len(state.held_tasks[seat]) * building_param(
                t, "office", "money_per_task_card"
            )
        return office if c == "office" else _task_value(state, t, seat, w, dead) - office
    if c == "craftwork":
        return 0.0 if dead else _craft_value(state, t, seat, w)
    if c == "winter":
        return -_winter_cost(state, t, seat, w)
    if c == "loan_repayment":
        return -float(t.loan_repay[state.loans[seat]])
    plans = sum(1 for p in state.plans if p[0] == seat and p[3] >= state.round)
    live = (
        0.0
        if dead
        else w["plan_value"] * plans + w["building_value"] * len(state.held_buildings[seat])
    )
    return live + _future_income(state, t, seat, w)


def fitted_value(state: LignumState, seat: int, w: Weights) -> float:
    """Value of ``seat`` at a non-terminal state with the composition in the module docstring."""
    fitted = tuple(w["fitted_components"])
    coefs, train_w, params = load_fit(w["value_fit"], fitted)
    if (state.n, state.joinery, state._tkey[2]) != params:  # not the games the fit covers
        hand = {k: v for k, v in w.items() if k not in ("value_fit", "fitted_components")}
        return value(state, seat, hand)
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    dead = state.round >= t.winter_rounds[1] and state.phase >= PHASE_SF
    row = features(state, seat, train_w)  # the weights the fit was trained with
    others = [features_money_repay(state, o, w) for o in range(state.n) if o != seat]
    row.append(sum(o[0] for o in others) / len(others))
    row.append(sum(o[1] for o in others) / len(others))
    row.append(state.round)
    v = float(state.money[seat])
    for c in COMPONENTS:
        lin = coefs.get(c)
        if lin is None:
            v += _hand(c, state, t, seat, w, dead)
        else:
            b, terms = lin
            for i, k in terms:
                b += k * row[i]
            v += b
    return v


def features_money_repay(state: LignumState, seat: int, w: Weights) -> tuple[float, float]:
    """An opponent's (money, owed repayment): the only features of theirs the fit uses."""
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    return float(state.money[seat]), float(t.loan_repay[state.loans[seat]])
