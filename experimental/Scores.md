# AthenaBot Experimental Scoreboard

Master comparison of every experimental bot in this folder. Each bot has a paired
`Bot_[4-digit]_Scores.md` with the full 20-test-case breakdown (Status/Output/Notes per
test, Running summary, Overall points) — this file is the cross-bot summary, not a
replacement for those.

All scores below come from real HackerRank submissions (not local-harness estimates).
Every bot in `experimental/` has now been submitted — no pending entries remain.

Every bot's `name` property now returns `"AthenaBot"` instead of
plain `"AthenaBot"` (cosmetic attribution only, no quoting/pricing/risk logic changed).
Scores/P&L below predate this change and are unaffected by it.

## Per-bot summary

### FokInventoryCapFix — 17.70/20 (new top score, most #1 finishes, highest P&L among score leaders)
**Strengths:** Fixes a real, independently-verified risk-control gap in `CovarianceRisk`
(and its whole `DrawdownBreaker` lineage): `respond_to_fok` previously enforced only a margin
check, never the `_MAX_NET_PER_OPTION` inventory cap that `quote()` already enforces —
repeated FOKs against the same option could push net inventory ~20x past the stated
cap. `FokInventoryCapFix` closes this by declining any FOK that would breach the cap, with no
other logic changed (pricing, quoting, skew, toxicity, flow-regime, drawdown breaker,
and `CovarianceRisk`'s covariance-aware portfolio risk score are all byte-identical). Net
effect on real HackerRank: **11 of 16 outright #1 finishes** (previous high: 10) and
**$223.07 total P&L** (previous high among score leaders: $203.73, `DrawdownBreaker`) — both
new records — for a new top score of **17.70/20**, surpassing the five-way tie at
17.50/20.
**Weaknesses:** One test (SCORED 12) scored worse than `CovarianceRisk` (0.70→0.40) —
expected and correctly attributed: since the fix can only make `respond_to_fok` *more*
conservative, declining a FOK that would have breached the cap forgoes whatever edge
that fill carried in that specific session. The net effect across all 20 tests was
positive here, but a single submission can't fully separate the fix's effect from
ordinary counterparty-RNG variance — see `scores/FokInventoryCapFix_Scores.md` and `ANALYSIS.md` §4.

### Archived-A — 16.60/20
**Strengths:** The original source of the three-zone confidence quoting, counterparty
toxicity/markout tracking, and capital-scale ramp that every later winner is built on.
Zero bankruptcies, ranks #1 outright in 8 of 16 SCORED sessions on its own.
**Weaknesses:** Uses a simpler single-option net-position skew rather than looking at
the whole book's correlated risk — later bots that fixed this (StableMerge onward) beat it.

### Archived-B — 16.40/20
**Strengths:** Richest quoting stack among the original 9 variants — zone-assignment
hysteresis (avoids flickering spread width near confidence boundaries) plus an
order-flow-tilt layer reading realized trade direction. Second-highest raw P&L among
originals ($167.51).
**Weaknesses:** Never became the base for a winning mixture — its hysteresis/flow-tilt
approach wasn't carried forward, so its edge over the plain three-zone approach appears
smaller than its complexity would suggest.

### Archived-C — 15.70/20
**Strengths:** Epistemic-uncertainty ensemble (perturbs directional model parameters,
reprices under each draw, uses ensemble disagreement as a confidence signal) uniquely
wins SCORED 1 and SCORED 2 outright (1.00 each) where every other bot in the whole
comparison scores only 0.40 there.
**Weaknesses:** Noisier than the deterministic three-zone approach elsewhere — lower
aggregate score (15.70 vs. 17.50) despite the standout wins on those two tests.

### AggressiveSizing — 15.70/20
**Strengths:** Highest raw P&L of every scored bot in this comparison ($208.34) —
takes bigger, higher-conviction positions that pay off in dollar terms.
**Weaknesses:** Doesn't convert that P&L into as many #1 finishes (7 of 16) as the score
leaders — big wins on some sessions don't offset narrow losses on others under the
rank-based scoring rule.

### Archived-D — 15.70/20
**Strengths:** Combines Archived-C's ensemble confidence engine with Archived-A's proven
risk gates — a deliberately different third architecture from the two zone-based
lineages, useful as a hedge against both of them being wrong in the same way.
**Weaknesses:** Inherits Archived-C's core weakness (noisier ensemble underperforms the
deterministic approach in aggregate) without adding a compensating strength of its own.

### Archived-E — 15.50/20 (ground-up architectural rewrite)
**Strengths:** The only bot in the comparison not built on the shared three-zone/
toxicity/portfolio-skew lineage — a genuinely different architecture (direct Monte
Carlo joint-path pricing, a real Bayesian per-counterparty adverse-selection posterior,
per-underlying fill-rate-adaptive aggression, Kelly-fraction sizing, and a relative-
value consistency check between spread options and their single-leg anchors). Zero
bankruptcies, zero errors, passed THEO on the first fully-working submission
(max_error=0.0019). Landed mid-pack overall despite abandoning every incremental fix
the rest of the lineage relies on, which is a reasonable outcome for a first attempt at
a structurally different design.
**Weaknesses:** Went through three rounds of real-submission bugs before scoring
anything: (1) `from Bot import (...)` would have failed outright on HackerRank, only
masked locally because `sim/harness.py` puts `Bot.py` on `sys.path`; (2) missing the
required `price_option` method the grader calls internally for RFQ/FOK trace logging,
invisible locally because the harness never calls it; (3) `price_option_from_parameters`
reused the live-quoting path's aggressive path-count throttling, starving longer-dated
options down to ~400 Monte Carlo paths and failing THEO's accuracy check
(max_error=0.0207) — fixed by decoupling THEO's one-off pricing calls from the
per-RFQ compute budget. A manual header-splice while fixing bug (1) also silently
truncated two unrelated methods (`OptionLeg`'s `@dataclass` decorator, `MarketParameters
.tilted_rate_probabilities`/`advance_step`) that happened not to be exercised by this
bot's own logic but were caught and fixed via a full diff against the canonical
`Bot.py` template before resubmission. Illustrates a real gap in the local verification
process: `sim/harness.py` cannot catch either of bugs (1) or (2), since it doesn't
enforce the standalone-file constraint or exercise the grader-only logging path.

### PortfolioDeltaSkew — 15.20/20
**Strengths:** Source of the portfolio-level cross-underlying delta skew (aggregates
Greeks across the whole open book into one risk score) that turned out to be the single
highest-leverage idea in the whole comparison once transplanted into other bots.
**Weaknesses:** Lowest raw P&L of the non-bankrupt-adjacent bots ($82.10) as a
standalone bot — the idea was worth more to other architectures than to its own.

### Archived-F — 15.10/20
**Strengths:** Most aggressive tuning of Archived-B's zone-hysteresis/flow-tilt stack
(raised capital-scale utilization, tighter high-confidence spread floor) — solid raw P&L
($179.50).
**Weaknesses:** The extra aggression didn't convert into more #1 finishes than its more
conservative parent; spends more margin for a similar rank outcome.

### Archived-G — 15.10/20
**Strengths:** Solid, unremarkable original variant — decent raw P&L ($176.92), no
bankruptcies.
**Weaknesses:** No standout mechanism; consistently mid-pack, never the best or worst on
any individual test.

### Archived-H — 14.50/20
**Strengths:** No bankruptcies, moderate P&L ($121.86).
**Weaknesses:** Below-average score with no compensating strength identified — a
generically weaker original variant.

### Archived-I — 13.50/20
**Strengths:** None distinguishing — ties the current root `Bot.py`'s score exactly.
**Weaknesses:** Only 3 of 16 SCORED sessions won outright, lowest P&L ($78.74) among
non-bankrupt-adjacent bots.

### Archived-J — 12.60/20 (user-authored)
**Strengths:** Hand-written on the same codebase as DrawdownBreaker, with the
aggression dial turned up (tighter FOK acceptance edge, near-expiry spread shrinking,
dropped defensive widening). Decent P&L for its score ($173.62, 7th-highest overall)
and 7 outright wins — when it wins, it wins big.
**Weaknesses:** Hits the 0.40 score floor on 7 of 16 SCORED tests, losing by large
margins to naive Fixed-Width/Lattice competitors — analysis confirmed this is the same
risk dial as the wins, not a separable mechanism, so the floor-losses and the big wins
can't be decoupled. One genuinely isolable piece (a covariance-aware portfolio risk
score, distinct from the aggression changes) was extracted and grafted separately —
see CovarianceRisk, which ties for the top score.

### SteinShrinkageBandit — 12.60/20
**Strengths:** Still avoids outright bankruptcy despite the worst showing in the set.
**Weaknesses:** Lowest score and only bot with **negative total P&L** (-$120.04) — the
worst-performing variant tested.

### StableMerge — 17.00/20
**Strengths:** First bot to combine Archived-A's proven stack with PortfolioDeltaSkew's portfolio
skew — confirmed the cross-underlying skew idea is a genuine, portable improvement
(beat both parents outright). Zero bankruptcies, 8/16 outright wins.
**Weaknesses:** Superseded by FlowRegimeTightening/DrawdownBreaker, which extend the same base further.

### Archived-K — 17.00/20
**Strengths:** Tested and definitively ruled out a size-cap hypothesis (bounded
hedge-size boost) — valuable negative result, not a design flaw. PnL and rank were
byte-identical to its parent on 19/20 tests, confirming the hypothesis (not the
underlying bot) was wrong.
**Weaknesses:** The added logic is effectively dead code in practice — simulated/real
counterparties rarely request enough size for the extra headroom to matter.

### FlowRegimeTightening — 17.20/20
**Strengths:** Added a `_FlowRegime` tracker that narrows spreads on favorable markouts,
specifically targeting Fixed-Width-style competitors identified as the main source of
losses (7 of 16 SCORED sessions). Confirmed pricing engine is already exact
(THEO max_error=0.0000) so no Monte Carlo rebuild was needed. 9/16 outright wins.
**Weaknesses:** Two specific gap tests remained (SCORED 9 and SCORED 16, both scoring
0.40/0.80) — addressed by DrawdownBreaker.

### DrawdownBreaker — 17.50/20 (tied top score, best P&L among top-3)
**Strengths:** Layers two targeted fixes onto FlowRegimeTightening: a narrower defensive-fallback
zone (`_W_WIDE` 0.25→0.18) and a bounded per-session drawdown circuit breaker
(triggers past -25% drawdown, widens spreads/cuts size, never weakens hard solvency
gates). Both target tests flipped to 1.00. **Highest P&L ($203.73)** among the three
bots tied at 17.50/20 — the fixes net-improved rather than traded off.
**Weaknesses:** Two tests (SCORED 2, SCORED 6) remain stuck at the 0.40 floor across
nearly every bot in this comparison — most likely genuine competitor RNG variance
rather than a fixable weakness.

### FlowCapTune03 — 17.50/20 (tied top score)
**Strengths:** Narrow, mechanistically-justified fix targeting DrawdownBreaker's Test 18
near-tie: raised the `_FlowRegime` spread-narrowing cap (0.02→0.03) so the tight zone
can reach parity with Fixed Width 0.05's own half-spread. Ties for the top score.
**Weaknesses:** Second-lowest P&L of the three 17.50 bots ($202.87) — the fix didn't
cost points but also didn't clearly pay off versus its parent on the tie-break metric.

### EpsilonSharpen — 17.50/20 (tied top score, most #1 finishes)
**Strengths:** Built to test whether competitor-PnL-denial is a distinct lever from
ordinary edge-capture — investigation found it isn't (the `MarketMaker` interface never
exposes competitor identity or quotes), so this ships an honestly-labeled minor
refinement (a small, bounded price-sharpen only at full confidence) rather than a
fabricated new mechanism. **Most outright #1 finishes of any bot in the comparison
(10 of 16)**, despite ranking 3rd on the point/P&L tie-break.
**Weaknesses:** Lowest P&L of the three 17.50 bots ($199.17) — wins more sessions
outright but by narrower margins on average.

### CovarianceRisk — 17.50/20 (tied top score)
**Strengths:** The most surgical graft in the comparison — swaps only `DrawdownBreaker`'s
naive sum-of-squares portfolio risk aggregation for `Archived-J`'s covariance-aware
version (real variance/covariance reconstructed from the fitted `MarketParameters`,
including the AJR/THR cross-covariance term), leaving every other subsystem
byte-identical. Confirms the covariance-aware risk score is a genuine, isolable
improvement — extracted cleanly from a much lower-scoring bot (`Archived-J`, 12.60/20)
without carrying over any of its aggression-driven floor-losses. Ties for the top
score, 9 outright wins, zero bankruptcies.
**Weaknesses:** Lowest P&L of the four bots tied/near the top ($193.85) — the more
accurate risk signal didn't translate into larger wins on the sessions it already won,
just parity with the simpler aggregation it replaced.

## Table 1 — Comparison table (score, P&L, and placement)

| Bot | Total /20 | SCORED /16 | Total P&L ($) | #1 finishes (of 16) | Bankruptcies |
|---|---|---|---|---|---|
| **FokInventoryCapFix** | **17.70** | 13.70 | **$223.07** | **11** | 0 |
| DrawdownBreaker | 17.50 | 13.50 | $203.73 | 9 | 0 |
| FlowCapTune03 | 17.50 | 13.50 | $202.87 | 9 | 0 |
| EpsilonSharpen | 17.50 | 13.50 | $199.17 | 10 | 0 |
| CovarianceRisk | 17.50 | 13.50 | $193.85 | 9 | 0 |
| FlowCapTune04 | 17.50 | 13.50 | $188.02 | 10 | 0 |
| FlowRegimeTightening | 17.20 | 13.20 | $195.63 | 9 | 0 |
| StableMerge | 17.00 | 13.00 | $157.83 | 8 | 0 |
| Archived-K | 17.00 | 13.00 | $157.68 | 8 | 0 |
| Archived-A | 16.60 | 12.60 | $140.98 | 8 | 0 |
| Archived-B | 16.40 | 12.40 | $167.51 | 7 | 0 |
| AggressiveSizing | 15.70 | 11.70 | **$208.34** | 7 | 0 |
| Archived-D | 15.70 | 11.70 | $148.80 | 6 | 0 |
| Archived-C | 15.70 | 11.70 | $148.80 | 6 | 0 |
| Archived-E | 15.50 | 11.50 | $98.79 | 4 | 0 |
| PortfolioDeltaSkew | 15.20 | 11.20 | $82.10 | 5 | 0 |
| Archived-F | 15.10 | 11.10 | $179.50 | 6 | 0 |
| Archived-G | 15.10 | 11.10 | $176.92 | 6 | 0 |
| Archived-H | 14.50 | 10.50 | $121.86 | 6 | 0 |
| Bot.py (root) | 13.50 | 9.50 | $78.74 | 3 | 0 |
| Archived-I | 13.50 | 9.50 | $78.74 | 3 | 0 |
| Archived-J | 12.60 | 8.60 | $173.62 | 7 | 0 |
| SteinShrinkageBandit | 12.60 | 8.60 | -$120.04 | 2 | 0 |

**FokInventoryCapFix now leads on every axis that matters** — highest score, highest P&L, and
most outright #1 finishes of any bot in the comparison, with zero bankruptcies. It's
the strongest candidate to promote to the graded `Bot.py`, ahead of the previous
five-way tie at 17.50/20 (`DrawdownBreaker`/`FlowCapTune03`/`EpsilonSharpen`/`CovarianceRisk`/`FlowCapTune04`). Note
`AggressiveSizing` still posts a very high raw P&L ($208.34) with a much lower score — a
reminder that HackerRank's scoring rewards *rank*, not P&L magnitude, so bigger swings
don't always convert to more points.

## Table 2 — Ranked by score (Total /20)

| Rank | Bot | Total /20 |
|---|---|---|
| 1 | FokInventoryCapFix | 17.70 |
| 2 | DrawdownBreaker | 17.50 |
| 3 | FlowCapTune03 | 17.50 |
| 4 | EpsilonSharpen | 17.50 |
| 5 | CovarianceRisk | 17.50 |
| 6 | FlowCapTune04 | 17.50 |
| 7 | FlowRegimeTightening | 17.20 |
| 8 | StableMerge | 17.00 |
| 9 | Archived-K | 17.00 |
| 10 | Archived-A | 16.60 |
| 11 | Archived-B | 16.40 |
| 12 | AggressiveSizing | 15.70 |
| 13 | Archived-D | 15.70 |
| 14 | Archived-C | 15.70 |
| 15 | Archived-E | 15.50 |
| 16 | PortfolioDeltaSkew | 15.20 |
| 17 | Archived-F | 15.10 |
| 18 | Archived-G | 15.10 |
| 19 | Archived-H | 14.50 |
| 20 | Bot.py (root) | 13.50 |
| 21 | Archived-I | 13.50 |
| 22 | Archived-J | 12.60 |
| 23 | SteinShrinkageBandit | 12.60 |

## Table 3 — Ranked by P&L ($)

| Rank | Bot | Total P&L ($) |
|---|---|---|
| 1 | FokInventoryCapFix | $223.07 |
| 2 | AggressiveSizing | $208.34 |
| 3 | DrawdownBreaker | $203.73 |
| 4 | FlowCapTune03 | $202.87 |
| 5 | EpsilonSharpen | $199.17 |
| 6 | FlowRegimeTightening | $195.63 |
| 7 | CovarianceRisk | $193.85 |
| 8 | FlowCapTune04 | $188.02 |
| 9 | Archived-F | $179.50 |
| 10 | Archived-G | $176.92 |
| 11 | Archived-J | $173.62 |
| 12 | Archived-B | $167.51 |
| 13 | StableMerge | $157.83 |
| 14 | Archived-K | $157.68 |
| 15 | Archived-D | $148.80 |
| 16 | Archived-C | $148.80 |
| 17 | Archived-A | $140.98 |
| 18 | Archived-H | $121.86 |
| 19 | Archived-E | $98.79 |
| 20 | PortfolioDeltaSkew | $82.10 |
| 21 | Bot.py (root) | $78.74 |
| 22 | Archived-I | $78.74 |
| 23 | SteinShrinkageBandit | -$120.04 |

`FokInventoryCapFix` now tops both the score table and the P&L table simultaneously — the first
bot in this comparison to do so. `AggressiveSizing` remains the highest-P&L bot among the
non-leading pack, still well below the leaders on score — the two tables measure
different things (score rewards consistently ranking #1 across sessions; P&L rewards
total dollar magnitude regardless of rank), and they don't always agree on "best."
