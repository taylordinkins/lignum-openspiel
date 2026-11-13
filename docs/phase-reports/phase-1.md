# Phase 1 report: rules spec and component data

**Branch:** `phase-1/rules-spec` · **Date:** 2026-11-04 · **Status:** complete, awaiting your review. The spec is back to APPROVED only after you flip the Status line (it is AMENDING for the R-114 ruling below).

## Exit criteria (PLAN.md §7)

| Criterion | Evidence |
|---|---|
| User approves spec and card tables | Unit 13: you reviewed and set APPROVED (`c297ff1`, `1d40745`). Later amendments are listed below |
| rules-auditor checked spec vs rulebooks/FAQ and data vs images/photos | Unit 5 (spec audit) and unit 11 (`docs/phase-reports/phase-1-data-audit.md`): **PASS**, 0 blockers, no data value disagrees with its source. Close review: see Reviews |

## Full-run results

`ruff check` clean · `ruff format --check` clean · `pyright` 0 errors · fast `pytest -q` **136 passed, 2 xfailed** · `pytest -m slow` **241 passed** · `tools.check_third_party` OK.

## Counts

117 rules (R-001..R-117) · 440 decision ids and 103 chance ids (`docs/ACTIONS.md`) · cards: 19 task, 19 placement, 8 winter (16 halves), 10 planned work · 10 buildings.

## What landed (`git log --oneline master..HEAD`)

| Commit | Unit |
|---|---|
| `1acf189` | Approved task list recorded in PLAN.md |
| `cfe58f7` | 1. Spec skeleton, components, setup, path sides (R-001..R-032) |
| `386758a` | O-1..O-5 resolved with user answers; D23 |
| `bab1afb` | 2. Round structure, supply path, wood-work phases, drying (R-033..R-063); C5, D23 amended |
| `789a796` | 3. Winter, loans, joiners, final sale, scoring, returns (R-064..R-086) |
| `3d07ec3` | 4. Planned work, huts, market, buildings, easy_winter (R-087..R-117); O-U4-1..12 resolved |
| `60dfd69` | 5. Spec audit fixes; R-073 extra sales, R-059/R-101, R-099; O-U5-1 resolved |
| `8fe07eb`, `5e95a6f` | 6. `cards.yaml` and your confirmation of the readings |
| `335b6e6` | 7. `buildings.yaml`, `planned_work.yaml` |
| `9a48190`, `6b20a15` | 8. `path.yaml`, `setup.yaml`; wood prices and drying bonuses |
| `584b521` | 9. `docs/ACTIONS.md`; A1/A3/A6/A8 resolved; R-072, R-081, R-097, R-100 amended |
| `10276c1` | 10. `docs/SCENARIOS.md` |
| `303940d` | 11. Data audit PASS; base numbers moved into `setup.yaml` |
| `2eaef68` | 12. `tests/data/` counts, schema, cross-refs, action-to-rule mapping |
| `c297ff1`, `1d40745` | 13. User review; spec APPROVED |

## Reviews at close

- **rules-auditor:** FAIL before fixes, with 2 must-fix findings (R-114 against ACTIONS contradiction on round 8 storage; the R-096 example) and 3 should-fix findings (F3-F5). All fixed; none of the should-fix items was deferred.
- **code-reviewer:** APPROVE with fixes. SCENARIOS 9.4 loan case and the test-parser problems were fixed.
- Spec wording fixes from the close: R-096 example, R-097 order (new step 3a of R-034), R-053/R-098 river wood sold automatically at the final sale, R-012 step order (SP follows the path fill).

## New decisions (user answers 2026-11-04, PLAN §9)

- A1/A3/A6/A8 of ACTIONS (R-072, R-081, R-097, R-100).
- Base printed numbers go into data (D25).
- R-114: the piece may be committed in round 8's Tasks phase and moved in that same phase; the building is **one piece per game**, never refilled once the piece has moved.
- R-099: PW Cutting's moved workers all go into one other cutting area.
- R-102: in winter every cutting area is free for the food hut.
- `TAKE_LOAN` is legal at the final sale while loans < 2 (ACTIONS §1.7, SCENARIOS 9.4).
- PLAN §3 gains D24 (action vocabulary), D25 (base numbers in data), D26 (scenario format). Appendix A's winter row is settled by R-117.

## Deferred (PLAN.md §9 Backlog, tagged "Phase 1 close")

- ACTIONS has no N5/N6 hut windows; state this in §4.
- `setup.yaml` `supply.fodder` and `supply.mill_workers` sit beside the unlimited marker; add a comment.
- SCENARIOS hard-codes the joiner supply of 6 in places; point to `supply.joiners`.
- The `test_data_crossrefs` docstring overstates its coverage.
- `sawmill_pads`, `player_board_extensions` and `joiners_on_path` have no test.

## Left open for a later pass

ACTIONS items A2, A4, A5, A7 and A9-A12 are structure-only: the id layout is fixed but their detailed semantics get settled when the engine lands (Phase 2 and 4).

## For your review

Flip the spec Status back to APPROVED once the R-114 amendment (one piece per game) looks right.
