# Lignum — OpenSpiel

Python OpenSpiel game (`lignum/`) of *Lignum* 2nd edition with the *Joinery and Buildings*
expansion; later a FastAPI server (`server/`) and React/TS web UI (`web/`), both ported from
`../kingisdead`. Plan and phases: `PLAN.md` (read only the current phase and §3–§4 as needed).
Rules contract: `docs/RULES_SPEC.md` (from Phase 1). OpenSpiel gotchas: `docs/OPENSPIEL_NOTES.md`.
Default branch is `master`; work happens on `phase-N/<slug>` branches merged by PR.

## Commands
- Install: `uv sync`
- Fast tests: `uv run pytest -q` · one rule: `uv run pytest -q -k R012` · slow sims: `uv run pytest -q -m slow`
- Lint/format/types: `uv run ruff check .` · `uv run ruff format .` · `uv run pyright`
- Replay an action history: `uv run python -m tools.replay <file.json> [--steps]`
- Play in the terminal: `uv run python -m tools.play_text --players 3 --seed 7 [--human 0] [--auto]`
- Fetch official art: `uv run python -m tools.fetch_assets [--dry-run]` (writes `third_party/art/`)
- Asset-location check (advisory): `uv run python -m tools.check_third_party`
- Server: `uv run uvicorn server.app:app --reload` (`LIGNUM_DEV=1` enables rewind) · both servers: `tools/dev.sh`
- Web: `cd web && npm ci && npm run dev|test|typecheck|build|e2e|check:api`

## Model and agent policy
The main session orchestrates; it delegates rather than writing large changes itself.
- Workhorse (Sonnet): `implementer` writes code, `spec-test-writer` writes tests from the spec.
- Cheap (Haiku): `Explore` for searching, `sim-runner` for long test/sim runs and their output.
- QA (Opus): `rules-auditor` checks spec and data conformance, `code-reviewer` checks for bugs.
  Use them at phase close, and as spot audits for units touching money, scoring, winter, loans,
  drying or planned-work timing.
- Workflow skills: `/start-phase N`, `/next-task`, `/close-phase`, `/triage-report <file>`.

## Rules
- IMPORTANT: no rule behaviour without a `docs/RULES_SPEC.md` entry. Ambiguity → stop, add it to
  PLAN.md §9, ask the user. Never resolve a rules question by guessing.
- Rules sources, in priority order: the rulebooks in `third_party/rules/`, **Official** answers in
  the ludex.dev FAQ, the player aid (`third_party/rules/player_aid.txt`), then PLAN.md §3–§4.
- Once the spec's Status is APPROVED it is locked (a hook enforces this). Propose amendments to the user.
- Card values live only in `data/components/*.yaml`; code never hard-codes them.
- Players (seats) are numbered from 0 everywhere: engine, tests, spec examples, logs, server, UI
  labels (`P0`…`P3`). Never show "Player 1" for seat 0.
- `State.__str__` delegates to the observer's string, so distinct states never print alike.
- Tests written ahead of code carry `@pytest.mark.pending("R-012")` (rules) or `@pytest.mark.regression("<report id>")` (playtest bugs, strict xfail); remove the marker when the rule or fix lands.
- Never edit a test to make it pass, and never regenerate `tests/playthroughs/` golden files without
  saying why in the commit message.
- Action IDs are frozen once Phase 2 closes: replays and playtest reports depend on them.
- The Stop/SubagentStop check hook is off (too slow to run every reply). Before committing run `uv run ruff check .`, `uv run pyright` and `uv run pytest -q` (or `python3 .claude/hooks/check.py`); don't commit red.
- Third-party material (rulebooks, photos, official art) lives only under `third_party/`, which is
  gitignored (removed from master 2026-11-12; earlier history still has it). Local copies are the
  rules sources; a fresh clone lacks them. The official theme is off unless
  `VITE_LIGNUM_OFFICIAL_THEME=1`; generic is the default. CI warns about assets elsewhere.
- Commit at each green step with a message that names the rule IDs or task it covers.
