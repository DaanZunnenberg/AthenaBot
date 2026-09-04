# `experimental/scores/` — per-bot scorecards

One `<Name>_Scores.md` per bot in `../src/`: the hypothesis behind the change, the exact diff
from its parent (with line references), a LOCAL-HARNESS-ONLY comparison via `sim/harness.py`
(clearly labeled as such -- it cannot reproduce HackerRank's competitor-MM ranking, see
`sim/README.md`), and, once submitted, the full real per-test HackerRank breakdown
(Status/Output/Notes for all 20 tests, running summary, overall score).

The cross-bot leaderboard aggregating all of these (score, SCORED-only subtotal, total P&L,
outright #1 finishes, bankruptcies) is `../Scores.md`, one level up, not in this folder.

See `../README.md` for the conventions these scorecards follow (append-only, never edited
after the fact except to add real HackerRank output or fix a lineage header).
