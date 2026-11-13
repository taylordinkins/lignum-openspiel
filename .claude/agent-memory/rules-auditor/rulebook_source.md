---
name: rulebook-source
description: Where the Lignum rulebooks, FAQ, player aid, photos and card images live, plus how to read them (PDFs have no text layer; FAQ fetch recipe; page map)
metadata:
  type: reference
---

- Rulebooks (committed, D11): `third_party/rules/lignum_rulebook.pdf` (2nd edition, 20 pp) and
  `third_party/rules/joinery_expansion_rulebook.pdf` (4 pp). No text layer: render with
  `pdftoppm -r 110 -png <pdf> <scratch>/p` and Read the PNGs (110 dpi is legible).
- Base page map: p.2 overview/board; p.4-5 setup + fill path + placement; p.6 picks/food/travel
  rules; p.7 path locations + PW; p.8 PW cost + where acquisitions go; p.9 clearing, phase track,
  woodcutting; p.10 log arrival, transport, bearer; p.11 wagon, raft, sledge; p.12 sawing, tasks;
  p.13 tasks winter, selling prices; p.14 drying, player order, cleanup; p.15 cleanup end, huts;
  p.16 winter; p.17 final sale, loans, 3p/2p; p.18 PW cards; p.19 tactical; p.20 tips + FAQ.
  Exp: p.1 setup, p.2 joiners, p.3 income + joinery placement/final sale, p.4 buildings.
- Player aid: `third_party/rules/player_aid.txt` (text extract of John Priebe's v05.15.18; PDF not
  in the repo as of 2026-11-04).
- FAQ: https://www.ludex.dev/lignum/faq/ — `curl -sSL` works from the sandbox; strip tags with a
  small `python3 -I` script into the scratchpad. 37 answers, 34 Official (2026-11-04). Only answers
  marked **Official** rank above the player aid.
- FAQ notes (2026-11-04): "When do I pay back loans" ($7/$16, no repayment during play) is NOT
  marked Official; the winter-bankruptcy answer IS Official (two table options; D9 picks option 1);
  sledge FAQ (Official) says extra food is "beyond what you need for feeding".
- Winter cards: 4 per year (`third_party/art/winter/winter-{1,2}-{1..4}.webp`), each half one Food
  and one Heating value, no player-count rows. Read webp directly with the Read tool; for crops,
  rotation or montages use `uv run --with pillow python -I` (PIL is not in the project env).
  Bottom winter halves are upside down: rotate 180 deg (6/9 trap), see [[lignum-data-audit]].
- Card images: `third_party/art/` with `manifest.json` (source URL, sha256 per image), fetched by
  `tools/fetch_assets.py` from https://www.ludex.dev/lignum/cards/.
- Photos: `third_party/rules/photos/board_joinery_side.jpg` (22-location side),
  `player_board_extension.jpg` (Joinery & Buildings extension), `buildings.jpg` (all 10 building
  tiles).
- `data/components/` exists from Phase 1 units 7-8; audited in unit 11 (2026-11-04).
- Printed numbers outside the rulebook text: board location coins (bearer/fodder/woodcutter/task
  $1, PW "?", sawyer 0/1), Market panel (saw $1, food $1, sets 2x/3x/4x = $2/$4/$6), per-player
  tables on each location panel; sawmill.webp (fodder 2/3, max 4 saws, prices 5/4/2/3/1, drying
  0/+1/+2, sawing yield 1/3/4); extension photo (+3 final-sale bonus, $1 income, +1 food winter);
  loan.webp 4->/<-7, loan-back.webp "Loan 2" 4->/<-16.
