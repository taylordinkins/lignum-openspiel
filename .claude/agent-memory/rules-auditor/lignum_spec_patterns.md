---
name: lignum-spec-patterns
description: Recurring defect classes in Lignum RULES_SPEC audits (first seen Phase 1 unit 2, R-033..R-063, 2026-11-04): scope leaks, double-placed seats in examples, forward-ref paraphrases, over-generalised C-clarifications, supply arithmetic
metadata:
  type: project
---

Seen in the Phase 1 unit 2 audit (R-033..R-063, 2026-11-04). Check these first on every Lignum spec unit.

- **Seasonal-scope "never/only" leaks.** A seasonal-round rule states a universal ("firewood storage
  can never be sold", "sawing-area wood cannot be sold", "the only way into the woodpile") that winter
  or PW rules break: Base p.16 forced shortfall sale "even from the sawing and heating areas",
  Overtime PW (Base p.18) puts hardwood on the woodpile. Grep each "never/only/always" against Base
  p.16-18 and Exp p.3-4.
- **Examples that put one seat in two places.** R-039's example had P0 sharing area 2 and alone in
  area 6 (a seat picks one area). Tabulate each seat's single choice per example.
- **Forward-reference sentences paraphrase later rules wrongly.** R-057 said joinery wood without a
  joiner gets "no bonus"; Exp p.3 says it cannot be sold at all. Check every "later unit" sentence.
- **PLAN C-clarifications over-generalise the FAQ.** C13 "used or sold tokens leave the game (FAQ)":
  the Official FAQ is about craftwork only; Base p.18 says sold equipment returns to supply. Re-read
  the FAQ answer itself before treating a C-line as FAQ-backed (the FAQ is fetchable with curl).
- **Supply-limit arithmetic vs refill recipes.** Count fills x per-fill need vs component count with
  seats hoarding: wagons 2x6=12 > 10 (4p/3p); fodder 8 can all sit on 4 sawmills. "Shortage cannot
  arise" claims fail unless equipment is treated as unlimited.
- **"A seat may do nothing" vs forced moves** (third-area sale, can't-pause drying).
- Turn order that must survive cleanup: winter phases use the fall clearing order (Base p.16), but
  cleanup moves foremen to 0; the spec must keep the order as state.

- **Stale "later unit" markers after a unit lands** (unit 3, 2026-11-04): the intro paragraph, the
  "Forward references" section and in-rule "(later unit)" notes in earlier units keep saying
  winter/loans/scoring are deferred. Grep "later unit" after each unit and list the stale ones.
- **Open questions escalated that sources already settle** (unit 3): O-U3-1 (card art shows no
  player-count rows), O-U3-8 (Base p.17 "remains there until the end of the game"), O-U3-6
  ("most dollars" wins). Before endorsing an O-question, check card art, Base p.11/p.13/p.17 and the
  FAQ; only escalate what no source covers.
- **Qualifiers dropped from paraphrased quotes**: Base p.16 shortfall "even from the sawing and
  heating areas *if necessary*" implies a priority the spec omitted. Diff quotes word by word.

- **General rule not updated when a later entry adds an exception** (unit 4): R-089 "used only in its
  target round" vs R-093 year-wide Food Supply; R-053 "river wood cannot move" vs Waterchannel. Grep
  the general rule each time a user answer widens a specific one.
- **User answers stretched past their scope** (unit 4): "whole planned year" became "from the round it
  is planned", which lets a plan pay in its planning round against Base p.7 "may never immediately use".
- **Cross-unit FAQ misses**: the FAQ has Official answers on hut-worker winter firewood (first action 2,
  whoever does it), Cutting PW extra woodcutters ($1 each), hut food "unoccupied area only", hut drying
  may mix disks and logs. Grep the FAQ by topic for every unit, not just the cited answers.
- **Stale "still to be settled" notes** in earlier entries after a unit settles them (R-027, R-070 vs R-117).

- **Phase invariants broken by window actions** (full audit, 2026-11-04): R-059 "by the end of phase 6
  the third area is empty" ignores a drying hut used at the start of the seat's drying-phase turn
  (C5 window). Check every "after phase X, Y holds" claim against hut/loan windows in later phases.
- **Multi-round examples that skip in-round phase order**: R-096's example sold area-3 wood "in that
  round's selling phase" though selling (6) precedes drying (7). Walk examples phase by phase, and
  across winter (no drying, no selling).
- **Priority clause narrower than practice**: "Sources and priority" let only D-numbers override the
  rulebook, while R-073/R-093 override rulebook text by user answers. Check the clause each audit.
- **PLAN C-lines and D-lines left stale after user answers**: C13/C18 vs D23 (unlimited equipment),
  D7 "both zero-sum" vs R-086 clip, C15 "no cutting token" vs rulebook "another player's". Diff
  every C/D line the spec cites against the entry.

- **Phase-1 close audit (2026-11-04, spec APPROVED):** no blockers; recurring classes were
  (a) examples with structurally impossible premises: R-096 "target round 1" (plans target ≥ 2),
  R-114 "a card that needs unmilled hardwood" (no such card in data). Check plan targets, printed
  seasons and data existence for every example. (b) Amendments appended to an entry without
  deleting the older clause: R-097 "before the round's other steps" + "automatic steps come first";
  "(current turn) order" undefined in winter (clearing order ≠ starting track). (c) ACTIONS phase
  gating narrower/wider than the spec: STORE_PIECE "never in winter" vs R-114 allowing any Tasks
  phase with task placement (round 8 N4); R-099 "up to 2 workers into another area" lost in
  TAKE_WOOD. (d) Winter windows: ACTIONS has none in N5/N6 although R-100 lists every winter-phase
  turn; outcome-equivalent (N4 window precedes, own board unchanged, area food only decreases), so NOTE.
  (e) Paraphrases of the final river sale ("sold if of one kind") in R-053/R-098.

**Why:** spec units are scoped by phase, so authors write locally true universals and paraphrase
rules owned by later units.
**How to apply:** run these checks on each new unit, and at full-spec audit re-check the earlier units.
