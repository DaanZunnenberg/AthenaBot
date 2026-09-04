# `experimental/` — tuning variants beyond `Bot.py`

Each idea for improving on the graded `Bot.py` becomes its own bot file, always starting from a
specific parent bot with its full stack untouched and layering on one small, bounded,
documented change — never a from-scratch rewrite. This keeps every tuning attempt
independently reproducible, comparable, and reversible: a regression here never overwrites a
working baseline, and `Bot.py` is only updated to promote a variant that's actually proven
better.

**Naming.** Bots here were originally named `Bot_[4-digit].py` (e.g. `EpsilonSharpen.py`), an
arbitrary numeric id with no information about what changed. They've since been renamed to
describe what each one actually added (e.g. `EpsilonSharpen.py` → `EpsilonSharpen.py`), diff-verified
against `ANALYSIS.md` rather than trusted from docstring claims alone. Every renamed file keeps
a `# --- Lineage ---` header comment stating its former numeric id and its parent, and every
renamed `_Scores.md` keeps a `**Parent:**` line for the same reason — old numeric ids still
appear throughout the prose in older docstrings/scorecards and are cross-referenced, not
scrubbed. `ANALYSIS.md`'s lineage graph is the authoritative parent/child map; individual
docstrings can be stale copy-paste artifacts from an earlier generation and should not be
trusted over it.

## Files

- `src/<Name>.py` — one `MarketMaker` implementation each, structurally identical to `Bot.py`
  (same six-method interface) so any of them could be promoted directly. Each file `import`s
  the shared interface classes (`BinaryOption`, `MarketHistory`, `MarketParameters`, etc.) from
  the private `src` submodule and contains only its own `MarketMaker` plus its own helper
  classes — the one exception is `AthenaBot/AthenaBot.py` itself, which stays fully
  self-contained since it must work as a standalone HackerRank submission. See `src/README.md`.
- `scores/<Name>_Scores.md` — that bot's own scorecard: the hypothesis behind the change, the
  exact diff from its parent (with line references), a LOCAL-HARNESS-ONLY comparison via
  `sim/harness.py` (clearly labeled as such — it cannot reproduce HackerRank's competitor-MM
  ranking, see `sim/README.md`), and, once submitted, the full real per-test HackerRank
  breakdown (Status/Output/Notes for all 20 tests, running summary, overall score). See
  `scores/README.md`.
- `Scores.md` — the cross-bot leaderboard: score, SCORED-only subtotal, total P&L, count of
  outright #1 finishes, bankruptcies, ranked two ways (by score, by P&L) since they don't
  always agree — see its own notes on why HackerRank's scoring rewards rank, not raw P&L.
  Covers every bot ever submitted, including the ones archived out of this folder (see below).
- `ANALYSIS.md` — the authoritative lineage graph (parent/child map) and deeper cross-bot
  analysis; both stay at the top level of this folder, not inside `src/` or `scores/`.

This folder holds a **curated 10** bots, not every variant ever tried: the 5 tied for the top
real-HackerRank score (`DrawdownBreaker`, `FlowCapTune03`, `EpsilonSharpen`, `CovarianceRisk`, `FlowCapTune04`), plus 5
chosen to show the actual journey rather than just the winners — strong intermediate
ancestors of the winning lineage (`FlowRegimeTightening`, `StableMerge`), the single highest-raw-P&L outlier
despite a lower score (`AggressiveSizing` — a reminder that rank and P&L magnitude aren't the same
thing), the originator of the portfolio-delta-skew technique later inherited by the top bots
(`PortfolioDeltaSkew`), and the worst-performing bot in the whole lineage (`SteinShrinkageBandit`, the only one with
negative total P&L, kept as a cautionary data point). Every other real, scored variant is
preserved unmodified in `archive/experiment-archive/` — nothing was deleted, only relocated;
see that folder's `README.md` for the full list and scores.

## Conventions to follow when adding a new variant

1. Never edit an existing bot file or its `_Scores.md` after the fact except to fill in real
   HackerRank output once submitted, or to add/correct a `# --- Lineage ---` header — treat
   past variants as an append-only log otherwise.
2. Name the new file for what it adds (PascalCase, short, one concept — e.g.
   `src/DrawdownBreaker.py`, not `DrawdownBreaker.py`), not a numeric id.
3. State the parent bot and the exact bounded change in the new bot's `# --- Lineage ---`
   header, its class docstring, and its `_Scores.md`'s `**Parent:**` line, including the
   hypothesis being tested and why it's expected to help.
4. Run a LOCAL-HARNESS-ONLY comparison against the parent (`sim/harness.py`'s `run_batch`,
   common random numbers) before submitting, and report it honestly even if it's a no-op or a
   regression — several entries in this folder are documented negative/null results, which is
   valuable signal, not something to hide.
5. Check file size (`wc -c`) before submitting — HackerRank's submission pipeline has a hard
   ceiling around 65,536 bytes; verbose docstrings have tripped this twice (`docs/history/JOURNEY.md`
   Phase 5 and Phase 8). If trimming is needed, trim prose only and verify the AST is
   unchanged aside from docstrings, to guarantee zero logic drift.
6. After a real submission, paste the HackerRank output into the new bot's
   `scores/<Name>_Scores.md` (matching the existing Status/Output/Notes format exactly) and
   update `Scores.md`'s leaderboard tables.
