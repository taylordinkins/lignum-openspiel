---
paths:
  - "lignum/**/*.py"
  - "tests/**/*.py"
  - "tools/**/*.py"
---

# Engine conventions

- `lignum/rules.py` is pure: no pyspiel import, no I/O, no randomness. `game.py` only adapts it
  to the pyspiel `Game`/`State` API. Randomness exists only as explicit chance nodes.
- Keep state small and cheap to copy (tuples, small ints, frozen dataclasses). MCTS clones states
  constantly; avoid per-state dicts of lists and deep object graphs.
- Use the named constants in `lignum/actions.py` for action IDs; never write numeric literals.
- Every function that implements a rule names its rule ID in the docstring (e.g. "Implements R-021").
- Rule tests target the public harness (`tests/harness.py`) and scenario JSON in `tests/scenarios/`,
  not engine internals, so they survive refactors. Name them `test_R###_<behaviour>`.
- Invariants (worker, fodder, joiner and equipment conservation, money ≥ 0, drying capacity, etc.;
  PLAN.md §6) are checked in the random-simulation tests; add a new invariant whenever a bug slips
  past the existing ones.
- Card and path values come from `data/components/*.yaml` (D12); never hard-code them.
- Players (seats) are numbered from 0 everywhere: state fields, observation strings, spec examples,
  test names and log text. Never introduce a 1-based "Player 1".
- `State.__str__` returns the observer's string for the full-information view (e.g.
  `make_py_observer(game, IIGObservationType(perfect_recall=False, private_info=ALL_PLAYERS))`),
  so two distinct states never print alike. Don't hand-write a separate summary.
- Hidden information (cutting-area picks, D5) must never appear in another seat's observation or
  information-state string or tensor until it is revealed; test this for every hidden field.
- Fixing a bug from a playtest report: first add a failing test in `tests/regressions/`, then fix.
