# Golden playthroughs

Generated once by `uv run python -m tools.make_playthroughs` (fixed seeds, uniform random play).
Checked by `tests/test_playthroughs.py`: the history is replayed, every step's action text and
state digest must match the trace, the invariant checker runs at every step, and the final returns
and dollars must match. Files are also readable by `uv run python -m tools.replay <file> --steps`.

| File | Seed | Players | Path side | Returns | Winter |
|---|---|---|---|---|---|
| p2_joinery_win_loss_std.json | 7 | 2 | joinery | win_loss | standard |
| p3_base_margin_easy.json | 16 | 3 | base | margin | easy |
| p4_joinery_margin_std.json | 25 | 4 | joinery | margin | standard |
| p4_joinery_phase4_std.json | 44 | 3 | joinery | margin | standard |

Do not regenerate without saying why in the commit message.

Seeds were picked so each game has a decisive result: uniform random play usually ends with every
seat bankrupt and tied.

The first three predate Phase 4 and use little of it (at most a few planned works and craftwork sets);
`p4_joinery_phase4_std.json` (added in Phase 4 unit 15) uses planned work, huts, buildings and craftwork
sets. Generate a single file with `--only <name>`; the older three were left untouched.
