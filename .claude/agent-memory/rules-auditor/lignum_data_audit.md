---
name: lignum-data-audit
description: Recipes and recurring defect classes for auditing data/components/*.yaml against Lignum card art, board/sawmill/extension images and rulebook (first seen Phase 1 unit 11, 2026-11-04)
metadata:
  type: project
---

First full data audit: Phase 1 unit 11 (2026-11-04). All 19 tasks, 19 placement, 8 winter, 10 PW,
10 buildings, both path sides and the setup tables matched the sources; no transcription errors.

Recipes that worked:
- `uv run --with pillow python -I <scratch>/montage.py out.png cols scale label=path ...` to tile
  4 cards per image (plain `uv run python` has no PIL). Crop + 2x upscale to tell olive softwood
  disks from black hardwood disks on placement cards.
- **Winter cards: rotate 180 deg before reading the bottom half.** Upside-down 6 reads as 9 (w1-4
  bottom 6/6, w2-4 top 6). Exp p.2's winter inset (w1-4, "x 9" = upside-down 6) cross-checks it.
- Independent cross-checks in the rulebook: Base p.5 placement example = placement_05; Base p.13
  task examples $17 = task_11, $18 = task_04; Exp p.1 inset shows "14" on the joinery-side Tasks
  block (glare hides it in the photo).
- `third_party/art/manifest.json` has sha256 per asset; verify all 86 match before reading.
- ACTIONS.md task-slot count (48) = sum of requirements in cards.yaml; recount on any re-transcription.

Recurring defect class (unit 11): **variant numbers in data, base numbers only in the spec.**
PW/building params (Heating Supply 6, Small Joinery +4, Field $0, Drying Area Upgrade 2) are data,
but the base values they modify (sawing yield 1/3/4, joinery +3, fodder $1, drying capacity 1 disk
or 2 logs) plus location/market prices, loan repay 7/16, joiner $1/+1 food, winter 2 firewood,
sledge 2 + max 3 food are printed on board/sawmill/extension/loan art yet live only in RULES_SPEC.
Raised as SHOULD-FIX + ASK USER; check whether the user settled a policy before re-raising.

Also seen (duplicate keys removed in unit 11): duplicated keys in setup.yaml (buildings_drawn twice, joiners twice, 13 token count in
two files) - drift risk; PLAN §9 backlog line about board.webp "Buildings one spot" misattributes
(board.webp is the 20-location side, which has no Buildings location).

**How to apply:** on every data re-transcription or Phase 2 data-loader review, rerun the
montage/rotation recipe and the cross-checks above, and grep the spec for numbers missing from data.
