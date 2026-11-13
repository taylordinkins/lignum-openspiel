# Phase 3 report: Server + web shell

**Branch:** `phase-3/server-shell` · **Date:** 2026-11-06 · **Status:** complete, awaiting your merge and ✋ playtest #1.

## Exit criteria (PLAN.md §7)

The criterion is human: you play one hotseat game and one against random, and file reports. Mechanical evidence that the shell is ready:

| Check | Evidence (final run) |
|---|---|
| Lint, format, types | `ruff check` clean, `ruff format --check` 125 files clean, `pyright` 0 errors |
| Fast tests | `pytest -q -rxX`: **1358 passed, 3 xfailed** (R-063 buildings, Phase 4; two marker self-tests) |
| Slow tests | `pytest -q -m slow -rxX`: **265 passed** |
| Web | `typecheck` clean, `npm test` **58 passed** (9 files), `build` ok, `check:api` clean |
| Playwright smoke | `npm run e2e`: **4 passed** (full game to the end, hotseat curtain, export/import, report) |
| Third-party location | `tools.check_third_party`: all assets under `third_party/` or `assets/generic/` |
| Pending markers | only R-063 (Phase 4, not claimed here) |

## Reviews

- **code-reviewer:** first pass CHANGES NEEDED (1 must-fix: the client could show one seat's hidden pick to another). Re-check: **fixed**, no blocker or must-fix remains.
- **rules-auditor:** first pass FAIL (3 must-fix). Re-check: all fixed; a new major finding (Back past round-start draws) was fixed after your decision and re-checked (2989 Back attempts against an independent oracle, 0 disagreements, no valid Back refused).

## Findings fixed

1. **Seed was an oracle** (R-029/R-038): the seed was sent to every seat and bot picks and chance draws derived from it, so a seat could compute a bot's hidden pick. Seed removed from views and exports; a per-session salt now goes into bot and chance keys; imports get a fresh salt. (An explicit seed in a create request means an empty salt: reproducible, opt-in.)
2. **Back across a reveal** (R-038): Back is refused once the pick has been revealed. Dev-mode Rewind is unrestricted.
3. **Winter cards missing from the view** (R-028): the visible winter food and heating requirements are in the view (from data) and on the text board.
4. **Client view-seat leak**: `deriveViewSeat` falls back to the first human seat; data for a different seat than the view seat is treated as loading and the curtain's reveal is disabled; mutation endpoints take `?seat=` so responses match the viewer; Retry goes through `useGame`.
5. **Back past round-start chance draws** (found in re-check): Back is refused across a round-start chance run (replaying the same number of actions re-deals the same cards).

**Existing tests edited (needs your OK):** the seed left the API, so `tests/server/test_api.py`, `test_lignum_labels.py` and `test_lignum_sessions.py` no longer expect `seed` in exports, and `test_export_import_in_progress_then_continue` compares only the imported history prefix (an imported game gets a fresh salt). Web fixtures dropped `seed: 1`, and four POST expectations gained `query: { seat: 0 }`. No assertion was weakened beyond what the behaviour change requires. The Back-barrier tests were written after the implementation, not before.

## Deferred (PLAN.md §9 Backlog)

Eleven should-fix and minor items, including: polling can stall after a repeated error, `?seat=` validated after the mutation, public R-028 items missing from the view (fodder slots, task card contents, PW cards, building supply), mislabelled "Sawmill food/pay" on the text board, inline-bot error mapping, the Back over-refusal when one run spans a reveal, curtain autofocus, and `npm audit` findings.

## New decisions

D28: seed and salt stay server-side; Back is a barrier at reveals and at round-start chance runs; `/import` is a trusted load-any-position tool (exports are not signed).
