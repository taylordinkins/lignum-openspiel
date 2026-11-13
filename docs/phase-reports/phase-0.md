# Phase 0 report: scaffold and spike

**Branch:** `phase-0/scaffold` · **Date:** 2026-11-04 · **Status:** complete, awaiting your review

## Exit criteria (PLAN.md §7)

| Criterion | Evidence |
|---|---|
| Green suite | `uv run ruff check .` clean · `ruff format --check` 44 files clean · `uv run pyright` (strict) 0 errors · `uv run pytest -q -rxX` **73 passed, 2 xfailed** (the two marker self-tests) · `uv run pytest -q -m slow` **241 passed** in 29 s · `uv sync --locked` ok |
| Spike notes committed | `docs/OPENSPIEL_NOTES.md`, last section "Hidden sequential picks and imperfect-information bots"; decision recorded as **D22** |

## What landed (one commit per unit)

| Commit | Unit |
|---|---|
| `b7d34c2` | **1. Scaffold.** `uv` project (Python 3.12, `open-spiel==2.0.2`, pytest, hypothesis, ruff, strict pyright), `pending`/`regression`/`slow` markers, `typings/pyspiel.pyi`, `.github/workflows/ci.yml`, `CLAUDE.md`. Advisory third-party check `tools/check_third_party.py` (**D21**, your call to be more lenient than kingisdead): it warns about assets outside `third_party/` and `assets/generic/` and fails only with `--strict` |
| `3a5ad99` | **2. `.claude/` port.** Six agents, four skills, `engine.md`/`spec.md` rules, four hooks and `settings.json`, adapted to Lignum (sources: rulebooks in `third_party/rules/`, the ludex.dev FAQ, card images; spot audits for money, scoring, winter, loans, drying and planned-work timing). `web.md` waits for Phase 3 |
| `bfa5304` | **3. Art.** `tools/fetch_assets.py` run once: **86 files, 3.0 MB** in `third_party/art/`, plus `manifest.json` (source URL, size, sha256 per file; 18 icon positions in the sprite sheet). Counts match Appendix A: 19 task, 19 placement, 8 winter, 10 planned work. robots.txt allows all; a rerun downloads 0 |
| `97d4ee2` | **4. Spike.** `spike/hidden_picks.py` toy game, `spike/bots.py`, `tests/spike/`; kingisdead's OpenSpiel API tests ported so the inherited notes stay tested |

## kingisdead backlog fixes (Phase 0 list)

| Item | Fix | Tests |
|---|---|---|
| `protect_spec.py` false positives on Bash | Each Bash segment is judged by its own command: it must be a writer *and* name the spec, a glob matching it, or a directory holding it. `grep … RULES_SPEC.md && rm tests/x.py` now passes. Newly blocked: `rm -rf docs`, `cd docs && rm …`, interpreter writes, `git rm/mv` on the spec, and `git merge/pull/rebase/cherry-pick/revert/am/apply` while the spec is APPROVED (the last group was another kingisdead backlog item) | 9 new allowed and 16 new blocked cases in `tests/test_hooks.py` |
| Missing `tools/replay.py` | Generic replayer: reports, nested exports or bare lists; checks legality at every step; prints seats as `P0…`; exit 1 pinpoints the illegal step. `/triage-report` now calls it | `tests/tools/test_replay.py` |
| Player numbering from 0 | Rule in `CLAUDE.md` and `.claude/rules/engine.md`; also a `code-reviewer` checklist item | — |
| `State.__str__` via the observer | Rule in `engine.md`; the spike implements it (a full-information observer cached on the game) | `test_str_shows_everything_via_observer` |
| Also fixed, while porting | `block_engine_reads.py`: a bare `lignum` blocks only as a path argument (`pytest -k lignum` works now). It also blocks `git diff/show/log -p/cat-file/blame` outside `docs/` and `tests/`, and `inspect.getsource` | 12 new cases |

## Spike findings (details in `docs/OPENSPIEL_NOTES.md`)

1. **Hidden picks are an observer concern.** D5's encoding works as plain sequential decisions. At the last seat's pick, its information-state string and tensor, and its observation string and tensor, are identical across every combination of earlier picks, tested for 2–4 players. pyspiel requests the info-state observer as (public, perfect recall, own private info) and the observation observer without perfect recall (verified with a spy).
2. **The C++ `MCTSBot` and `ISMCTSBot` segfault on any Python game in 2.0.2**, including OpenSpiel's own `python_tic_tac_toe` and `python_kuhn_poker`. A slow canary test fails if a future version fixes this.
3. **Python IS-MCTS works** when given a resampler. Over 200 2-player toy games at 100 simulations: 0.96 win rate against random (21 ms per decision), and +0.28 mean return against determinized MCTS (100 sims × 4 worlds), which itself wins 0.90 against random. **D22:** Lignum uses Python IS-MCTS, with determinized MCTS as the fallback.

## Reviews

Phase 0 changes no rules, so I didn't run `rules-auditor` or `code-reviewer`; the agents only became usable in unit 2. I can run `code-reviewer` on `git diff master...HEAD` before you merge if you'd like.

## Decisions added to PLAN.md §3

- **D21:** the third-party asset check is advisory.
- **D22:** the bot family is Python IS-MCTS (this settles §5.7).

## Deferred (PLAN.md §9 Backlog)

- The player aid PDF isn't in the repo yet.
- ludex.dev has no images of the Buildings cards, the Joinery board side or the player-board extension. Those come from the photos and rulebooks, as already planned.
- The new git block in `protect_spec.py` is broad, so you run merges while the spec is locked.
- Hook tests are marked slow.
- Delete `spike/` once `lignum/` covers it.

## For your review

- `.claude/` adaptations, especially `agents/rules-auditor.md` (source order and component-data checks) and the two hook rewrites.
- `CLAUDE.md`.
- D21 and D22 in PLAN.md §3.
- Optionally, browse `third_party/art/` to check that the images are the ones you want.
