# Phase 5 report: Board UI

**Branch:** `phase-5/board-ui` · **Date:** 2026-11-09 · **Status:** complete, awaiting your merge and ✋ playtest #3.

## Exit criteria (PLAN.md §7)

You play a game through with official art from the Lobby's rulebook setup. (Setup editor descoped 2026-11-07; generic theme stays as the per-sprite fallback.)

| Check | Evidence |
|---|---|
| Lint, format, types | `ruff check` clean, `ruff format --check` 160 files clean, `pyright` 0 errors (re-run after fixes) |
| Fast tests | `pytest -q -rxX`: **2013 passed, 2 xfailed** (both marker self-tests), 0 xpassed (re-run after fixes) |
| Slow tests | `pytest -q -m slow -rxX`: **266 passed** (14m20s). Run before the close fix commit 5f0b24d, which changed only adapter display strings and two web components; not re-run |
| Web | `typecheck` clean; `vitest` **159 passed** (24 files); `build` OK; `check:api` no schema diff (re-run after fixes) |
| E2E | `npm run e2e`: **8 passed**, including the full official-theme game `web/e2e/official_game.spec.ts` (re-run after fixes) |
| Third-party location | `tools.check_third_party`: all tracked assets under `third_party/` or `assets/generic/` |
| Pending markers | none remain for Phase 5 rules (only the marker self-tests xfail) |
| Tasks | units 1–10 ticked, including 9a–9i. Unit 9's parent line said polish was open; ticked on the strength of 9a–9i by your decision |

No engine, spec or data files changed this phase (`lignum/`, `data/`, `docs/` untouched by the audit's scope check).

## Reviews

- **rules-auditor:** FAIL on first pass: 1 must-fix, 1 should-fix, 7 minor; hidden-information probe over 1050 seat-swap comparisons found 0 leaks; scoring (R-081..R-086) matches the engine. After the fix, re-check of the must-fix: **PASS**.
- **code-reviewer:** APPROVE: no blocker or must-fix; 2 should-fix, 4 minor.

## Findings fixed (commit 5f0b24d)

1. **Must-fix (rules-auditor):** server adapter labels still used spec terms ("log" = milled) after the UI-only relabel, so "log" meant opposite things on one sawmill pad. Adapter strings now say Log (unmilled) / Milled. Spec, data and action IDs unchanged. Your decision.
2. **Should-fix (code-reviewer):** building slot sprite id used the display name, so building art never rendered; now uses `cardSpriteId("building", name)`; test fixture uses real names.
3. **Should-fix (code-reviewer):** "Filled tasks" strip marked partly filled tasks done; now "Tasks with pieces placed" with no done flag.

## Findings deferred (PLAN.md §9 Backlog)

Winter card half in effect not marked on the sprite (should-fix); hard-coded fodder values and PW/sawyer prices; SF marker always on N6; terse building effect text; "Money held" column name; weak hidden-pick view test; stale previous-round picks shown during RS/PK; `_score` replay cost; popover key not reset; missing `board-joinery` fallback; `winter.sf_due` key not renamed (label already correct); `npm audit` triage. `HutPicker.test.tsx` fixture labels still say "disk" (not user-facing).

## New decisions

D31: UI wood terms (2026-11-09): "Log" = unmilled, "Milled" = milled in every user-facing string including server adapter labels; spec terms unchanged. Unit 9 ticked on the strength of 9a–9i.

## For playtest #3

Play a full game from the Lobby with the official theme (3 or 4 players, Joinery on), checking: Log/Milled wording in action labels and popovers, building art in the sawmill building slots, hut area splits, sale and drying prices on the pad, task cards tab, scoring breakdown at the end. Known gap: the active winter card half is shown only in the tooltip.
