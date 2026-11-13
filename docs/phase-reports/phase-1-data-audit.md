# Phase 1 unit 11 — Component data audit

**Auditor:** rules-auditor (Opus), 2026-11-04, branch `phase-1/rules-spec` @ 10276c1
**Scope:** `data/components/{cards,planned_work,buildings,path,setup}.yaml` against the sources, read independently of earlier transcriptions; cross-check with `docs/RULES_SPEC.md`, `docs/ACTIONS.md`, `docs/SCENARIOS.md`.

## Verdict: PASS (0 BLOCKER, 3 SHOULD-FIX, 4 NOTE)

No data value disagrees with its source. The findings are completeness and consistency problems, not wrong values.

## Method
- Checked all 86 images in `third_party/art/manifest.json` against their sha256: 0 mismatches.
- Read each card image; 2x crops of the placement-card disk columns separated olive softwood from black hardwood disks.
- Rotated winter cards 180° to read the bottom halves upright.
- Rendered both rulebooks; read Base p.2–5, 13, 14, 17, 18, 20 and Exp p.1–4; read `player_aid.txt` in full. The ludex.dev FAQ has no component errata.
- A scratch script loaded every YAML and checked unique ids, counts, task-slot total, path numbering, token-spot sets, the 10-token path mix per player count and placement food areas.

## Verified (matches source)
| File / item | Source | Result |
|---|---|---|
| cards.yaml tasks 01–19 | `art/tasks/` | All 19 match (kind, milled/unmilled, drying 0/1/2, reward). Same-kind pieces at different dryness: task_08, task_10, task_14, task_15. Unmilled disks: task_13 (firewood), task_17 (softwood). 48 requirement slots. |
| cards.yaml placement 01–19 | `art/placement/` | All 19 match, including mixed areas p09 a3, p10 a5, p13 a6, p19 a4/a6. |
| cards.yaml winter (8 cards, 16 halves) | `art/winter/` | All match. |
| planned_work.yaml | `art/planned_work/`, Base p.18 | All 10 match. Drying prints F/S/H on green/yellow/red = spring/summer/fall. Winter only on Sawing, Heating Supply, Overtime. |
| buildings.yaml | `photos/buildings.jpg`, Exp p.4, Aid | Match. Tiles print no cost (free). |
| path.yaml base side | `art/boards/board.webp`, Base p.2 | 20 locations, 13 token spots, clearing A–D. |
| path.yaml joinery side | `photos/board_joinery_side.jpg`, Exp p.1 | 22 locations; Buildings 12 = 2 circles, Joiner 16 = 1. |
| setup.yaml by_players, starting holdings, supply | Base p.3–5, p.17; Exp p.1; Aid | Match. |
| setup.yaml wood_prices, drying_bonuses | Base p.13–14, `sawmill.webp` | Match. |
| setup.yaml sawmill, player_board_extension, loans | sawmill.webp, extension photo, loan images | Match. |
| Spec numeric statements | R-013, R-015, R-017, R-025, R-041, R-054, R-058, R-059, R-070, R-075, R-077, R-082, R-090..R-099, R-104..R-117 | All agree with data. |
| Ids used in docs | RULES_SPEC, ACTIONS, SCENARIOS | All exist in data. |

## Findings
| # | Class | Where | Finding |
|---|---|---|---|
| F1 | SHOULD-FIX | setup.yaml, path.yaml | About 20 numbers printed on the board, sawmill, extension and loan cards exist only as prose in the spec (location prices $1; Market saw/food $1 and craftwork sets $2/$4/$6; sawing yield 1/3/4 logs; drying capacity 1 disk or 2 logs; joinery bonus +3; joiner income $1 and +1 food; loan repayment 7/16; winter woodcutting 2 firewood; sledge 2 + up to 3 food; $3 per missing food/heating unit). Planned-work and building values that modify them are in data, so the engine would hard-code the base values. |
| F2 | SHOULD-FIX | setup.yaml | Duplicated numbers (`buildings_drawn`, joiners in supply, `path_token_total` vs `token_spot_count`, sawyer prices, `craftwork_tokens` vs `craftwork_by_type`). All agree today; keep one copy or add an equality data test. |
| F3 | SHOULD-FIX | setup.yaml `supply.unlimited` | Omits money, which the spec treats as unlimited (R-009). |
| N1 | NOTE | setup.yaml `supply.mill_workers: 4` | Per-seat pieces under "Component pools"; harmless. |
| N2 | NOTE | R-022 source line | Buildings capacity 2 is printed on the joinery board photo, not only a D20 decision. |
| N3 | NOTE | PLAN.md backlog | The "board.webp shows one foremen spot at Buildings" note mixes the sides: board.webp is the base side with no Buildings or Joiner location. |
| N4 | NOTE | cards.yaml placement | Food amount per area is implicit (1, user-confirmed). |

## Not verified
- Physical cards were not compared with the ludex.dev scans; the scans are the source.
- `player_aid.txt` is a text extract; the PDF is not in the repo.
- Joinery-side location 14: number unreadable in the photo, confirmed from the Exp p.1 inset.
- Raw-material and equipment physical counts are not in data (consistent with D23).

## ASK USER
1. (F1) Move the base numbers listed above into `data/components`, or keep them spec-only with named engine constants citing R-IDs?
