# Lignum — UI polish plan (generic theme)

**Status:** IN PROGRESS · 2026-11-17 · branch `ui/generic-polish`
**Scope:** the web shell (`web/src/shell/`), the app frame, and the chrome of the Lignum plugin
(`web/src/games/lignum/`): panels, bars, tables, dialogs. The board and sawmill SVG art is kept.
Only the **generic** theme is designed for; the official theme code stays but gets no new work.
No rules behaviour changes: what may be clicked still comes only from the legal actions.

Reference: the Bus web UI (`../Bus-openspiel/web`, its `docs/UI_DESIGN.md` §3a, §6.8). Lignum
ports its *functions* and component system, not its look (Bus is red/cream map art; Lignum is
woodland).

## 1. Where we start

The board art is good; everything around it is unstyled browser HTML: Times New Roman, default
form controls, a one-line toolbar, a plain "Your move" box, bare tables. Bot moves land all at
once. No settings, no seat panels, no results screen.

## 2. Look (design tokens)

One source of truth, `web/src/theme/tokens.css` (CSS custom properties on `:root`); components
use tokens, never raw hex (SVG presentation attributes mirror values in a TS module).

- **Paper:** cream stock like the board's cards: `--paper` #f6eedb, `--paper-raised` #fcf8ec,
  `--paper-sunk` #efe4c8, `--paper-deep` #e6d6b0 (page), `--paper-edge` #d6c096 (hairlines).
- **Inks (bark):** `--ink` #22190f, `--ink-soft` #4a3a26, `--ink-muted` #6b5840 (AA on paper).
- **Forest (primary):** `--forest` #2f5d3a, `--forest-dark` #1e3f27, `--forest-tint` #dfe9d6.
- **Wood (frames):** `--wood` #8a5a2b, `--wood-dark` #5e3b1a, `--wood-light` #c99a5b —
  the board's Planned Work panel; framed panels use a wood frame with a thin cream rule inside.
- **Accent / glow:** `--glow` #ffd24a, `--glow-soft`, `--amber` #d99a00 (the existing highlight).
- **Status:** `--danger` #a3341f (loans, errors), `--ok` #2f7d3a, `--focus` #1f5f99.
- **Seats:** `--seat-0..3` = `SEAT_COLORS` (red, blue, green, gold) with `--seat-ink-*`;
  seat identity also always printed as `P0`…`P3`.
- **Type:** display *Fraunces* (soft serif, matches the board's Georgia italic lettering),
  text *Source Sans 3*; self-hosted via `@fontsource` (offline-safe), Georgia / system fallbacks.
  Scale 11/12/13/15/17/20/26/36/56 px. **Space** 4 px grid; **radii** 3/5/8/12; **depth**
  warm paper shadows; **motion** 120/200 ms, zeroed under `prefers-reduced-motion`.

## 3. Functions ported from Bus

| Bus function | Lignum version |
|---|---|
| Design system: tokens, `base.css` (buttons primary/secondary/ghost/icon, chips, segmented control, fields, dialogs, alerts, toasts, spinner, tooltips, focus ring), `icons.tsx` | Same structure, woodland tokens |
| Lobby: hero + wordmark, framed numbered "New game" form, seat cards with seat tiles, *Continue a game* (import), *At the table* tips | Lignum fields: players, seats, Joinery toggle, returns, seed |
| Game screen: prompt bar (seat band, phase title, one-sentence prompt, Back), side column (wordmark, Lobby, icon toolbar with tooltips), log card filling the rest | Board views (Board / Sawmills / Cards / Task Cards / Details) become a segmented tab strip; the "Your move" action chips stay (they are a primary input in Lignum) |
| Seat panels (seat band, score, tags START / TO ACT, acting panel raised) | Money, loans, food, joiners, hired workers, held tasks, buildings; turn-order / to-act tags; hover highlights nothing new |
| Settings dialog (`settings.ts`, localStorage, try/catch) | Bot pace 0–2 s (default 0.8 s); "text view only" moves here |
| Bot playback (`playback.ts`, `GET /api/games/{id}?at=N`, Skip to my turn) | Same; frames are rendered per seat so hidden picks never leak |
| Curtain: full-screen pattern, seat-colour band, framed card, "Pass to Pn" | Same, woodland pattern |
| Results panel at END | Winners, final dollars per seat, scoring breakdown link to Details |
| Error toast, loading spinner, turn toast in hotseat | Same |

Not ported: Bus's board motion layer and zoom rail (Lignum's board is sprite-based; a later
unit can add them), scenarios in the lobby.

## 4. Units (each one commit, checks green)

1. **Foundations.** `tokens.css`, `base.css`, fonts, `icons.tsx`, page background; existing
   `layout.css`, `board.css`, `sawmill.css`, `cards.css` raw colours moved onto tokens.
2. **Lobby.** Bus-style hero and framed form; import becomes *Continue a game*; tips card.
   The app `<h1>` becomes the wordmark (lobby hero, game side column).
3. **Game screen layout.** Prompt bar, side column, icon toolbar, segmented board views,
   restyled "Your move" chips and action log card (round headers, current-step marker).
4. **Seat panels** from `view.seats` (public fields only, R-028).
5. **Dialogs and states.** Report, Settings, Curtain, results panel, error toast, spinner.
6. **Bot pacing.** Server `?at=N` frames (+ tests), `playback.ts`, `settings.ts`, Skip to my turn.
7. **Plugin chrome.** Details tables (TextBoard, ScoringPanel, WorkerRoster), Cards / Task
   Cards panels, HutPicker, CutAllPanel, woodpile bar, phone/tablet tab layout (< 900 px).
8. **QA.** Generic-theme Playwright layout spec (no page scroll at 1366×660 and 1440×800,
   2p and 4p), screenshots, code review, full checks.

## 5. Constraints

- Accessible names and labels the tests and e2e use stay stable ("Players", "Seat P0",
  "Seed (optional)", "Create game", "Joinery and Buildings expansion", board-view buttons,
  "Game board", the game line). Tests change only where the UI intentionally changed, with
  equal assertion strength, named in the commit message.
- Seats are `P0`…`P3` everywhere; colour never the only seat cue.
- Desktop game screen is exactly one viewport; panes scroll inside.
- Checks before each commit: `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`,
  `cd web && npm run typecheck && npm test` (+ `npm run check:api` after server changes).
