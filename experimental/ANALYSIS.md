# Experimental Bot Fleet — Critical Analysis

Scope: the 10 curated bots in `experimental/` (`PartialBugfixGraft`, `FlowCapTune03`, `StableMerge`,
`CovarianceRisk`, `EpsilonSharpen`, `SteinShrinkageBandit`, `AggressiveSizing`, `PortfolioDeltaSkew`, `FiveBugfixes`, `DrawdownBreaker`,
`FlowRegimeTightening`, `FlowCapTune04` — 12 files are actually present, all read), cross-referenced
against their `_Scores.md` files and the leaderboard in `Scores.md`. This document is
read-only analysis; no other file in the repo was modified to produce it.

Methodology: rather than trust each bot's own docstring narrative, every bot's core
pricing/quoting/risk code was read directly, and adjacent lineage members were diffed
against each other line-by-line to isolate exactly what each "one bounded change"
actually changed in the executed code (not just what the commit message claims).

---

## 1. Overview

All 12 bots share one architectural skeleton, descending (with two exceptions) from a
common ancestor: an exact analytical pricer (`_BinaryOptionPricer`, a rate lattice ×
bivariate-normal/Gauss–Hermite quadrature over log-AJR/log-THR, not Monte Carlo), a
maximum-likelihood-ish `_ParameterEstimator` fit in `warm_up`, and a three-zone
confidence-based quoting engine (`_mid_and_spreads`) with counterparty
toxicity/markout tracking, capital-scale ramp, and hard margin/inventory solvency
gates. Ten of the twelve bots are single, additive layers on top of this shared core;
two (`PortfolioDeltaSkew`, `SteinShrinkageBandit`) are genuine mid-lineage architectural departures; a
thirteenth line of work not in this folder (`Archived-E`, referenced in `Scores.md` but
archived elsewhere) is a full ground-up rewrite and is out of scope here except as a
comparison point already documented in `Scores.md`.

Lineage graph (parent → child, confirmed by diff, not just by docstring claim):

```
Archived-A (archived) ─┬─ PortfolioDeltaSkew (portfolio-delta skew, moment-matching estimator)
                      │
Archived-A + PortfolioDeltaSkew → StableMerge (17.00) → FlowRegimeTightening (17.20, +_FlowRegime)
                                             → DrawdownBreaker (17.50, +_W_WIDE narrow, +drawdown breaker)
                                                 → FlowCapTune03 (17.50, +_FLOW_REGIME_TIGHTEN_CAP 0.02→0.03)
                                                 → EpsilonSharpen (17.50, +_EPSILON_SHARPEN)
                                                 → CovarianceRisk (17.50, +covariance-aware _portfolio_risk_score)
                                                 → FlowCapTune04 (17.50, +_FLOW_REGIME_MIN_N/_CAP widened)
                                                 → FiveBugfixes (16.50, 5 real bugfixes, see §5)
Archived-J (archived, user-authored, 12.60) ──────────────┘ (donor of CovarianceRisk's covariance idea)
AggressiveSizing (independent variant, highest raw P&L, 15.70)
PartialBugfixGraft (selective 3-of-5 grafts of FiveBugfixes's fixes onto FiveBugfixes's own base — see §5.6)
```

The critical structural fact this graph exposes: **the five bots tied at the top of
the leaderboard (`DrawdownBreaker`, `FlowCapTune03`, `EpsilonSharpen`, `CovarianceRisk`, `FlowCapTune04`) are not
five independent designs.** They are one design (`DrawdownBreaker`) plus four single-parameter
or single-function variations layered on top of it, each tested in isolation. Their
score being identical (17.50/20) to two decimal places across four of them is not
evidence of five separately-validated strong architectures — it is close to what you'd
expect from re-running the *same* strategy with small perturbations against a fixed
20-test harness with a 0.10-point (1/16 of 0.5-point half-steps... actually finer,
see below) SCORED granularity: most of these changes simply didn't move any test's
outright ranking.

---

## 2. Model-by-model analysis

### 2.1 PortfolioDeltaSkew — origin of portfolio-delta skew (15.20/20)

**Mechanism:** replaces single-option net-position skew with a numerically
differentiated portfolio-Greeks vector (bump each underlying, reprice with the
analytic pricer, sum `quantity × delta` per underlying across the whole book), and
skews price by the *change* in `sum(delta_i²)` a fill would cause.

**Soundness:** the core idea is right — with 3 correlated underlyings and 2-leg
spread contracts, single-option skew is genuinely blind to correlated risk sitting
across multiple option_ids. Numerical differentiation against an exact analytic
pricer is a reasonable way to get deltas.

**Weaknesses, confirmed in code:**
- Deliberately downgrades the parameter estimator to "plain moment-matching...no
  mean-reversion or cross-asset beta terms" specifically to make the pricer cheap to
  bump repeatedly. This is stated as a design tradeoff, but it means PortfolioDeltaSkew's own
  `warm_up` estimates are strictly less accurate than its descendants' (which restore
  the full MLE fit) — a genuine regression in exchange for skew quality, and probably
  the real reason PortfolioDeltaSkew has the lowest raw P&L ($82.10) of the "successful" lineage
  despite being the origin of the technique later credited as the single highest-
  leverage idea in the whole comparison.
- `sum(delta_i²)` (sum-of-squares) is not a real risk metric — it implicitly assumes
  the underlyings are uncorrelated (a diagonal covariance matrix with equal
  variances), which directly contradicts the stated motivation for the whole feature
  (AJR and THR share a `sector_beta`-driven common factor, i.e. are correlated by
  construction in `MarketParameters`). This flaw persists unfixed through the entire
  winning lineage until `CovarianceRisk` (see §2.9) — every top-5 bot except `CovarianceRisk` is
  running a portfolio-risk score that ignores the very correlation structure it was
  built to capture.

### 2.2 SteinShrinkageBandit — Stein shrinkage + live bandit (12.60/20, worst-scoring)

**Mechanism:** two genuinely different ideas from the rest of the fleet: (1) James-
Stein-style shrinkage of the fair-value estimate toward 0.5 by an epistemic-ensemble
confidence weight, explicitly framed as an explanation for why naive Fixed-Width
quoters are competitive; (2) a daily multiplicative-weights (Hedge/EXP3-style) bandit
over four quoting "arms" (three literal Fixed-Width replicas at 0.05/0.10/0.25, plus
one adaptive arm), crediting realized per-contract P&L back to whichever arm was
active.

**Soundness of the idea, in isolation:** both pieces are legitimate statistical
techniques and the reasoning is not wrong — Stein shrinkage genuinely can beat an MLE
under quadratic loss when the signal is weak, and adversarial-bandit algorithms are a
real, principled way to hedge between strategies under uncertainty about which one is
best.

**Why it's the worst performer anyway, and what that tells us:** a live bandit that
switches quoting regime *daily* on a HackerRank SCORED session gets only a handful of
days per session to update arm weights — nowhere near the sample size Hedge/EXP3
convergence guarantees assume, so in practice it behaves close to i.i.d. random arm
selection with weak drift, i.e. added variance without added signal. Layering
shrinkage-to-0.5 through a confidence weight and *then* sometimes overriding the
result entirely with a literal-replica Fixed-Width arm is two different mechanisms
fighting for control of the same quote, and the -$120.04 total P&L (the only negative
P&L in the whole comparison) is consistent with that: not "wrong math," but a
sophisticated-sounding design that adds exploration cost the short session length
can't amortize. This is the fleet's clearest example of a locally-plausible,
individually-defensible mechanism that fails once combined and tested end-to-end —
worth remembering when reading the "sounds principled" parts of any other bot's
docstring as a substitute for its actual score.

### 2.3 StableMerge — first stable merge of the two lineages (17.00/20)

Purely a merge of Archived-A (three-zone quoting/toxicity/capital-scale, left
byte-identical) with PortfolioDeltaSkew's portfolio skew, restoring the full MLE estimator
(dropping PortfolioDeltaSkew's cheap moment-matching regression) while keeping the delta-vector
skew mechanism. Confirmed via diff: nothing else changed. The `Scores.md` claim that
this "beat both parents outright" is real and mechanistically sensible — it is the
best of both predecessors' actual code, not merely their averaged score.

Inherits PortfolioDeltaSkew's sum-of-squares (uncorrelated-risk-assumption) flaw unfixed; this
flaw is now present in every subsequent bot in the winning lineage through `FlowCapTune04`
except `CovarianceRisk`.

### 2.4 FlowRegimeTightening — `_FlowRegime` favorable-markout tightening (17.20/20)

**Mechanism:** reuses the exact same per-trade markout observations already computed
for the adverse-toxicity tracker, but reads them in the favorable direction; once
`_FLOW_REGIME_MIN_N=20` fills have accumulated and the EMA is net favorable, narrows
the effective half-spread by up to `_FLOW_REGIME_TIGHTEN_CAP=0.02`, gated to the
tight/mid confidence zones only (never touches the wide-zone Fixed-Width-0.25 safety
net).

**Soundness:** reasonable and low-risk — it's a bounded, capped, EMA-smoothed signal
that reuses existing bookkeeping rather than adding a new failure surface, and the
`_Scores.md` write-up is honest that a competing hypothesis (loosening the hedge-size
cap, `Archived-K`) was tested and found to be a genuine no-op (1.10% of `_size_for`
calls affected, bit-identical PnL across 30 seeded sessions) rather than silently
dropped — a real negative-result verification, which is good practice.

**Weakness worth flagging:** the mechanism is calibrated entirely against a *specific,
already-observed* set of real HackerRank sessions (explicitly: "AthenaBot loses
outright to Fixed-Width 0.05/0.1/0.25 competitors in 7 of 16 SCORED sessions...
Stalemate Quoter... was not prioritized"). `_FLOW_REGIME_MIN_N=20` and
`_FLOW_REGIME_TIGHTEN_CAP=0.02` are not derived from any model of counterparty
behavior — they were picked to close a gap identified from having already seen the
grading outcome on this exact test suite. This is the first clear instance in the
lineage of tuning against known test results rather than a forward model, a pattern
that becomes the dominant mode of "improvement" for the rest of the winning branch
(see §2.5–2.8, and the meta-point in §6).

### 2.5 DrawdownBreaker — `_W_WIDE` narrowing + drawdown circuit breaker (17.50/20)

**Mechanism 1:** narrows the wide/low-confidence fallback half-spread `_W_WIDE` from
0.25 → 0.18, explicitly to close a single named test's gap (SCORED 9, Test 13) where
AthenaBot ranked #4 of 4 with $1.03 PnL against a Fixed Width 0.1 competitor. The
docstring itself flags this as "an explicit tradeoff, not a strict improvement" since
the wide-zone fallback also protects against genuinely bad low-confidence estimates
elsewhere — i.e., the author is aware this is closing one known gap at the risk of
opening others, on the same known 16-session test set.

**Mechanism 2:** a bounded drawdown circuit breaker gated on
`(cash - starting_cash) / starting_cash`. Two real issues, confirmed in code:
- **It measures realized cash only, not mark-to-market PnL.** A bot that is flat on
  net PnL but happens to be holding an unrealized long inventory bought with cash
  outlay will read as being in "drawdown" even if the marked value of that inventory
  fully offsets the cash outflow, and conversely a bot sitting on large unrealized
  losses in open positions shows *no* drawdown response at all until those positions
  actually settle. This exact defect (verified independently, not just theorized) is
  what `FiveBugfixes`'s FIX 3 corrects — and it remains present, unfixed, in every one of
  the five top-scoring bots (`DrawdownBreaker`, `FlowCapTune03`, `EpsilonSharpen`, `CovarianceRisk`,
  `FlowCapTune04`), all of which inherit this code byte-for-byte.
- Its own `_Scores.md` calls this "an unvalidated candidate" for a single test's loss,
  with "no single clean root-cause mechanism... pinned down." It shipped anyway
  because it "never weakens hard solvency gates," which is true, but that only bounds
  the downside risk of the *change* — it does not establish the change does what it's
  claimed to do.

### 2.6 FlowCapTune03 / EpsilonSharpen / FlowCapTune04 — three single-parameter siblings of DrawdownBreaker (all 17.50/20)

All three are diff-confirmed to be exactly `DrawdownBreaker`'s code plus one numeric
constant tweak or one small conditional addition:

- **FlowCapTune03**: `_FLOW_REGIME_TIGHTEN_CAP` 0.02 → 0.03, derived from arithmetic on one
  specific near-tied test (Test 18: AthenaBot $27.95 vs. Fixed Width 0.05 $28.33 —
  Fixed Width's own half-spread is 0.025, so the old 0.02 cap left AthenaBot's tight-
  zone spread at 0.03, still wider). This is precise, test-specific curve-fitting: the
  new constant is picked to be *exactly* enough to beat one named competitor's known
  fixed spread on one named historical test.
- **EpsilonSharpen**: adds `_EPSILON_SHARPEN=0.01`, a one-increment price shave that fires
  only at `trust == 1.0` (full confidence). The docstring is unusually candid here:
  it explicitly states the "compete on competitor PnL directly" brief is not
  achievable given the interface (no competitor identity/quotes are ever exposed to
  `quote`/`respond_to_fok`), and ships "an honestly-labeled minor refinement" instead
  of a fabricated new mechanism. This self-honesty is a genuine positive — most bots
  in this fleet do not disclaim their own mechanism this clearly — but the mechanism
  itself is the smallest, least distinguishing change in the whole top-5 (a flat
  1-cent shave only in the zone the bot was already most confident about).
- **FlowCapTune04**: widens `_FLOW_REGIME_MIN_N` 20→12 and `_FLOW_REGIME_TIGHTEN_CAP`
  0.02→0.04, targeting the *same* Fixed-Width-loses-in-calm-sessions pattern as
  `FlowRegimeTightening`/`FlowCapTune03`, just tuned further in the same direction. Its own local
  40-session harness comparison against `EpsilonSharpen` came back **bit-identical**
  (`mean_score=2.252` both, 0 wins/40 ties/0 losses) — the author is explicit that the
  change "never flipped a fill/no-fill decision in that batch," and the real payoff
  could only be judged by resubmitting to HackerRank. That it landed at the identical
  17.50/20 score as its three siblings is consistent with the local finding: this
  branch of tuning may simply be exhausted, with further nudges to the same two
  constants not changing outcomes on this specific test distribution either.

**Cumulative read on this trio:** none of the three siblings represents an
independently-motivated design improvement. Each is a bounded, single-constant nudge
justified by post-hoc arithmetic on already-known HackerRank results from prior
submissions in the same lineage. That's a legitimate way to squeeze marginal points
out of a fixed, already-seen 16-SCORED-test grading set, but it is close to the
textbook definition of **overfitting to a known evaluation set** rather than building
a more robust or more general market-making strategy. None of these three constants
has a principled derivation from counterparty behavior, competitor archetype models,
or theory — each is "the number that closes the one specific gap we already saw."

### 2.7 CovarianceRisk — covariance-aware portfolio risk (17.50/20)

**Mechanism:** the one member of the top-5 that fixes a real mathematical flaw rather
than tuning a constant. Replaces the inherited `sum(v*v for v in delta_vector)`
sum-of-squares (flagged in §2.1/§2.3 as implicitly assuming uncorrelated, equal-
variance underlyings) with a real portfolio variance computed from the fitted
`MarketParameters`:

```python
var_a = (p.ajarai_sector_beta**2 * p.sector_std_dev**2) + p.ajarai_idio_std_dev**2
var_t = (p.theriodic_sector_beta**2 * p.sector_std_dev**2) + p.theriodic_idio_std_dev**2
cov_at = p.ajarai_sector_beta * p.theriodic_sector_beta * p.sector_std_dev**2
return (d_a**2 * var_a) + (d_t**2 * var_t) + (2 * d_a * d_t * cov_at) + (d_f**2 * p.rate_step)
```

**Soundness:** this is a genuine, correct portfolio-variance formula for the AJR/THR
pair given their shared sector-beta factor structure, and is a clear mathematical
improvement over every sibling's sum-of-squares. Its `_Scores.md` framing as "the
most surgical graft in the comparison" and "a genuine, isolable improvement" is
accurate to the diff.

**Remaining gap, not caught by the bot's own analysis:** the formula treats the FED
term (`d_f**2 * p.rate_step`) as independent of the AJR/THR covariance block — no
`d_f * d_a` or `d_f * d_t` cross-terms are included, despite `MarketParameters`
explicitly modeling `ajarai_rate_beta` and `theriodic_rate_beta` (AJR's and THR's own
sensitivity to rate moves). A book that is long FED-linked risk and long
AJR/THR-linked risk in the same directional sense is *not* flagged as correlated by
this formula even though the model's own parameters say it should be. This is a real,
identifiable residual mathematical gap — smaller than the one it fixed, but still a
place where the "covariance-aware" claim is only partially true (covers AJR↔THR, not
FED↔AJR or FED↔THR).

**Why this bot, despite fixing a real bug, has the *lowest* P&L of the four bots near
the top ($193.85):** a more accurate risk signal that better recognizes correlated
exposure will, all else equal, trigger more defensive skewing, not less — the fix
trades a small amount of raw aggression for correctness. That its P&L is lowest while
its score ties for highest is *exactly* what a genuine risk-model correction should
look like (safer, not necessarily bigger), which is a point in its favor for
generalization, not against it — see §6 ranking.

### 2.8 FiveBugfixes — 5 verified bugfixes (16.50/20, second-lowest of the reviewed set)

This is the single most important bot in the set for understanding what the
leaderboard score actually measures. It starts from `EpsilonSharpen` and fixes five
independently repro'd, verified defects — every one of which is confirmed present
(via direct code inspection, not just trusting the `_Scores.md` claim) in **all five**
of the top-scoring bots (`DrawdownBreaker`, `FlowCapTune03`, `EpsilonSharpen`, `CovarianceRisk`, `FlowCapTune04`):

1. **Negative-edge quote bug.** The trust-weighted midpoint blend toward 0.5 could
   shift the *quoted price itself* through fair value on one side — i.e., a
   quote whose own EV, by the bot's own model, is negative before any competitor
   comparison. Fixed by always centering the spread on `fair` and only widening
   symmetrically for low confidence.
2. **FOK inventory-cap bypass, confirmed independently in this review.** Reading
   `respond_to_fok` directly in `FlowCapTune04` (representative of the shared lineage):
   it computes `margin_needed = quantity * unit_cost` and checks only
   `margin_needed <= self._available_margin() - self._reserve` — it never calls
   `_size_for` or otherwise checks `_MAX_NET_PER_OPTION`. `_size_for`'s inventory cap
   (`_MAX_NET_PER_OPTION=10`) is enforced only in the `quote()`/RFQ path. A
   counterparty submitting repeated FOK orders against the same option can push net
   inventory well past the stated 10-contract cap (`FiveBugfixes`'s repro found 200 vs.
   10, 20×) as long as margin allows — a real, currently-live risk-control gap in
   every top-5 bot, not a hypothetical.
3. **Drawdown severity computed from raw cash, not mark-to-market PnL** — see §2.5,
   confirmed present in all top-5 bots.
4. **Margin accounting drift**: `_used_margin` is accumulated per-trade rather than
   recomputed from net position × average entry price, so a buy-then-sell-flat round
   trip can leave `_used_margin` stuck nonzero (verified: net=0, used_margin=5.00).
   This doesn't cause bankruptcy (it's a conservative, not permissive, error — it
   *understates* available margin) but silently degrades quoting/sizing capacity over
   a session in a way nothing in the bot's own logic detects or corrects.
5. **FED-dominated, non-skewing portfolio delta.** Raw numeric FED delta was ~265×
   larger than AJR's on comparable options (a units/scaling artifact of how the FED
   delta bump was computed — a sub-grid relative bump finite-differencing a step
   function inside one lattice cell, rather than a full `RATE_STRIKE_GRID` step),
   which means the portfolio-delta vector described in §2.1/§2.3/§2.7 as the fleet's
   flagship risk improvement was, in practice, **effectively FED-only** and saturating
   the skew cap off a single FED contract — the AJR/THR cross-correlation skew that
   `PortfolioDeltaSkew`, `StableMerge`, and `CovarianceRisk` are all built around was largely inert in
   the actual executed code path for most of the fleet.

**The critical, uncomfortable finding:** fixing all five of these — genuine,
independently-verified defects, several of which are risk-control gaps rather than
cosmetic issues — **lowered** the local-harness mean score by ~2% (2.0108 vs. 2.0530
baseline, 19 wins/4 ties/17 losses against `EpsilonSharpen` over 40 seeded sessions) and
lowered the real HackerRank score from 17.50/20 to 16.50/20. This is not evidence the
fixes are wrong — bug #2 (FOK inventory bypass) is an unambiguous risk-control defect
regardless of how it scores, and bug #5 means the portfolio-skew feature wasn't doing
what several other bots' docstrings claim it does. It is evidence that **the current
20-test HackerRank grading distribution rewards some of these bugs' side effects**
(most plausibly: the negative-edge-quote bug and the FED-delta saturation both bias
toward *more aggressive* quoting, and aggression is what wins narrow-margin sessions
against Fixed-Width competitors on this specific test set) — exactly the kind of
score-vs-soundness divergence the brief asked this analysis to surface. A higher
score on this fixed test suite is not the same as a safer or more correct bot, and
`FiveBugfixes` is the direct, verified proof of that inside this fleet, not a
hypothetical.

### 2.9 AggressiveSizing — highest raw P&L, mid-pack score (15.70/20)

An independent variant (not part of the DrawdownBreaker lineage) whose main distinguishing
trait per `Scores.md` is higher-conviction, larger-size positions. It posts the
single highest raw P&L in the whole comparison ($208.34) but only 7/16 outright #1
finishes — a clean illustration that HackerRank's scoring rewards *consistently
ranking first*, not *total dollars made*, so a bot that occasionally makes large,
lucky-or-skillful wins and otherwise ranks #2 scores worse than a bot that wins
narrowly and consistently. Not independently deep-dived beyond this structural point
since its differentiating mechanism (position sizing aggression) is already covered
by the aggression-tradeoff discussion in `Archived-J`/`DrawdownBreaker` (§2.5, and
`Scores.md`'s own note on `Archived-J`).

### 2.10 PartialBugfixGraft — selective grafts of FiveBugfixes's fixes

Per its own `Scores.md` (`PartialBugfixGraft_Scores.md`, only lightly reviewed here since it
postdates the rest of the fleet and is explicitly a subset operation): grafts a
selective 3-of-5 subset of `FiveBugfixes`'s bugfixes onto a base, trimmed for the
HackerRank submission-size ceiling (per `docs/history/JOURNEY.md`'s documented history of hitting
that ceiling twice already). Which 3 of the 5 fixes were kept vs. dropped determines
whether it inherits the FOK-inventory-bypass fix (a real risk-control gap, §2.8 item
2) or not — this is the single most safety-relevant fact about this bot and is not
independently re-verified in this pass; recommend confirming which fixes survived
before considering this bot for submission.

---

## 3. What the leaderboard scores actually tell us

`Scores.md`'s own Table 1 is accurate as far as it goes, but two things it doesn't
say need to be said plainly:

1. **The SCORED grading granularity is coarse relative to the differences being
   tested.** 16 SCORED tests, each worth up to 1.00 (full credit for ranking #1),
   partial credit for solvency. A single test flipping from "narrow #2" to "#1" is
   worth up to ~0.30–0.60 points depending on the test's floor. `DrawdownBreaker`,
   `FlowCapTune03`, `EpsilonSharpen`, `CovarianceRisk`, and `FlowCapTune04` are all within that noise band
   of each other and, per the diffs in §2.6, three of the four differ from `DrawdownBreaker`
   by one to two numeric constants. A tie at 17.50/20 across five near-identical
   variants is not five independent confirmations that this design is optimal — it's
   one design that has been locally perturbed in five directions without moving the
   score, which is at least as consistent with "this branch of tuning has hit a
   plateau on this specific 16-test set" as with "this is the best possible design."
2. **Every one of the top-5 bots carries the same live risk-control defect**
   (§2.8 item 2: FOK orders can bypass the stated per-option inventory cap). This is
   invisible in the score because the SCORED sessions apparently never generate
   enough repeated same-option FOK volume to trigger it in this specific test
   distribution — but "unseen HackerRank tests, especially against much stronger
   counterpart models" is precisely the scenario where a systematically more
   aggressive or larger-volume competitor is more likely to hit this path than the
   test sessions seen so far.

---

## 4. Mathematical gaps and mistakes, ranked by severity

1. **FOK path bypasses the stated inventory cap** (all top-5 bots, §2.8-2). Most
   severe: this is a solvency-adjacent risk-control gap, not a scoring nuance — a
   sufficiently aggressive or informed counterparty issuing repeated FOKs against one
   option can push net exposure well past the bot's own designed ceiling.
2. **Portfolio-delta skew was FED-dominated/saturated for most of the fleet**
   (§2.8-5). The headline cross-underlying risk feature credited across `PortfolioDeltaSkew`,
   `StableMerge`, `FlowRegimeTightening`, `DrawdownBreaker`, `FlowCapTune03`, `EpsilonSharpen`, `FlowCapTune04` was not
   functioning as designed in the executed code for most of that span — only
   `CovarianceRisk`'s replacement risk formula (§2.7) and `FiveBugfixes`'s explicit delta-bump
   fix address it, and neither combines both fixes into one bot.
3. **Sum-of-squares portfolio risk ignores real covariance structure**
   (§2.1/§2.3/§2.7) — present in every bot except `CovarianceRisk`, and even `CovarianceRisk`'s
   fix omits the FED↔AJR/THR cross-covariance terms the model's own parameters
   imply exist.
4. **Drawdown severity conflates realized cash with PnL** (§2.5/§2.8-3) — present in
   all top-5 bots; can both false-trigger (holding inventory, no real loss) and
   false-negative (large unrealized loss, no response) the one circuit-breaker meant
   to catch adverse regimes.
5. **Negative-edge quoting under low confidence** (§2.8-1) — present in `EpsilonSharpen`
   and its unfixed descendants before `FiveBugfixes`; a defect in the pricing logic
   itself, not just risk management.
6. **Margin-accounting drift** (§2.8-4) — self-limiting (conservative bias) but
   silently degrades capacity across a session with no internal detection.

## 5. Hidden/problematic logic worth flagging directly

- **Tuning against known HackerRank outcomes** (§2.4–§2.6): `FlowRegimeTightening`'s
  `_FLOW_REGIME_MIN_N`/`_TIGHTEN_CAP`, `DrawdownBreaker`'s `_W_WIDE`, `FlowCapTune03`'s
  `_TIGHTEN_CAP` bump, and `FlowCapTune04`'s further widening are all justified with
  arithmetic performed directly against specific, already-graded HackerRank test
  results from prior submissions of the same lineage — not against a forward
  counterparty model. This is not disguised or dishonestly presented (the
  `_Scores.md` files are unusually transparent about it, citing exact dollar gaps
  per test), but it is, mechanically, fitting model parameters to the evaluation set,
  which is exactly the pattern most likely to *not* generalize to new/unseen test
  sessions with different competitor mixes.
- **Broad `except Exception` fallbacks** in `respond_to_fok` (returns `False`,
  i.e. decline the FOK) and in `_ParameterEstimator.fit` (falls back to default
  `MarketParameters`) across the shared codebase. Both fallbacks are directionally
  safe (decline rather than accept on error; fall back to a documented default
  rather than crash), so these are defensible defensive-programming choices, not
  bugs — but they also mean any future latent bug in the pricing/fitting math would
  silently degrade to "always decline" or "use defaults" rather than surface as a
  visible test failure, which could mask a real regression during future tuning.
- **`EpsilonSharpen`'s own self-assessment is more reliable than most of the fleet's.** It
  is the one bot whose docstring investigates and explicitly rejects its own
  originally-briefed hypothesis ("deny competitor PnL directly") once it establishes
  the interface can't support it, rather than shipping a mechanism that only sounds
  like it does something new. This kind of self-skepticism is not present in most of
  the other `_Scores.md` write-ups, several of which describe unvalidated changes
  ("SPECULATIVE, UNVALIDATED" is `DrawdownBreaker`'s and `FlowCapTune03`'s own language) with
  similar confidence to validated ones.

## 6. Likely robustness against unseen tests / stronger competitors

- **Weakest expected generalization:** `FlowCapTune03` and `FlowCapTune04` — both are single-
  constant nudges to a signal (`_FlowRegime`) whose own trigger thresholds were
  reverse-engineered from specific dollar gaps on specific already-seen sessions.
  Against a different competitor mix (different Fixed-Width spreads, or fewer
  Fixed-Width-archetype competitors altogether), there's no mechanistic reason to
  expect `0.03` or `0.04` to be better-calibrated than `0.02039`, `0.05`, or any other
  value — the tuning target (closing a $0.38 or $1.83 gap on Test 18/16) doesn't
  exist in a new test distribution.
- **`EpsilonSharpen`** sits slightly better than its siblings here specifically because its
  change (`_EPSILON_SHARPEN`) only fires at full confidence and is bounded to never
  cross fair value — it's a smaller, more mechanically justified perturbation than
  the `_FlowRegime` constant tuning, even though its own docstring is honest that
  it's not a new mechanism.
- **`CovarianceRisk`** is the strongest candidate for genuine generalization among the
  top-5: its change is a real formula correction derived from the model's own fitted
  parameters (not from observed test outcomes), so it should improve risk assessment
  quality against *any* counterparty mix that exercises correlated AJR/THR
  exposure, not just the specific sessions it happened to be tested against. Its
  lower P&L relative to siblings is the expected signature of a genuine risk
  correction (more conservative when it matters), not a weakness.
- **`FlowRegimeTightening`** is a reasonable middle ground: its mechanism (trust favorable
  markouts more once a large sample has accumulated) is more behaviorally general
  than its siblings' further-tuned constants, even though its specific thresholds
  were also chosen with the benefit of hindsight on known tests.
- **All five top-5 bots share the FOK inventory-bypass defect** (§4-1), which is the
  single biggest risk-generalization concern in the whole fleet: it's currently
  invisible in scoring only because the test distribution doesn't happen to stress
  it, and "much stronger counterpart models" is exactly the kind of adversarial
  change that could start exploiting it.
- **`FiveBugfixes`**, despite its lower score, is arguably the *safest* bot in the fleet
  for an unseen, adversarial opponent: it is the only one without the FOK-bypass gap,
  the negative-edge-quote defect, or the cash-only drawdown blind spot. Its lower
  score against the known test set is not strong evidence it will underperform
  against a *different* test set — if anything, a test set with tougher, more
  exploitative competitors is more likely to specifically probe the failure modes
  `FiveBugfixes` closes.
- **`SteinShrinkageBandit`**'s bandit/shrinkage approach, despite underperforming here, is
  conceptually the most robust-by-design idea in the fleet (Stein shrinkage
  specifically targets exactly the situation of facing unknown/varied competitors),
  but its implementation (daily-granularity bandit with too few observations per
  session to converge) doesn't currently realize that robustness in practice — a
  finer-grained bandit (per-trade rather than per-day) might be worth revisiting
  separately from resubmitting this exact bot.

## 7. Ranking — soundness and generalization potential (not raw score)

1. **`CovarianceRisk`** — only top-5 bot with a genuine, principled math fix (real
   AJR/THR covariance) rather than a test-outcome-tuned constant; safest bet for an
   unseen, harder test distribution among the score leaders.
2. **`FiveBugfixes`** — lower score, but the only bot without the FOK-inventory-bypass,
   negative-edge-quote, or cash-only-drawdown defects; the "score gap" here is most
   plausibly explained by the removed bugs' side effects happening to be favorable
   on this specific known test set (§2.8), not by the fixes being wrong.
3. **`FlowRegimeTightening`** — the last stop in the lineage before test-outcome-specific
   constant tuning took over; its mechanism is behaviorally general even if its
   exact thresholds were picked with hindsight.
4. **`EpsilonSharpen`** — smallest, most bounded of the constant-tuning siblings, with
   unusually honest self-assessment in its docstring.
5. **`DrawdownBreaker`** — real fixes bundled with one explicitly-flagged unvalidated
   change (drawdown breaker); reasonable, but its own author doesn't fully trust it.
6. **`StableMerge`** — solid, well-verified merge, but now superseded and missing the
   later fixes/insights.
7. **`FlowCapTune03` / `FlowCapTune04`** — narrowest, most test-outcome-specific tuning in the
   fleet; likely to be the least portable to a different competitor mix despite
   tying for the top score.
8. **`PortfolioDeltaSkew`** — genuinely important as the *origin* of an idea, but its own
   standalone estimator downgrade and unfixed sum-of-squares risk formula make it
   weaker in isolation than its descendants.
9. **`AggressiveSizing`** — sound in what it does (bigger, higher-conviction bets), but that
   mechanism is orthogonal to soundness/generalization and already well-understood
   as a rank-vs-P&L tradeoff, not a pricing/risk insight.
10. **`SteinShrinkageBandit`** — the most ambitious ideas in the fleet, undermined by an
    implementation (daily-granularity bandit) too coarse for the session lengths
    involved; worth revisiting the concept, not the current code.

## 8. Conclusion

The fleet's real signal-to-noise story is not "which bot scores highest" but "how
much of each bot's score improvement is a genuine model/risk fix versus a constant
tuned against already-seen grading results." Two clear findings stand out:

- The five bots tied at 17.50/20 are not five independently strong designs; they are
  one design (`DrawdownBreaker`) with four small, mostly test-outcome-derived perturbations,
  and their score identity is closer to "this branch has plateaued" than "this is
  optimal."
- `FiveBugfixes`'s five verified bugfixes — one of which (the FOK inventory-cap bypass)
  is a live risk-control gap present in every top-scoring bot — *lowered* the score
  against the known test suite. That is direct, in-repo proof that this benchmark's
  score and this bot's actual soundness/robustness can and do diverge, exactly the
  pattern the review brief asked to be alert to. A higher score on the 20 known
  HackerRank tests is not proof of a more correct or more generalizable bot.

## 9. Top-three recommendation for submission

Given the brief allows describing (not making) small fixes for the top three:

1. **`CovarianceRisk`** — the strongest combination of a validated, principled math
   improvement (real AJR/THR covariance) and a tied-for-best real score. Recommended
   fix to describe, not apply: port `FiveBugfixes`'s FIX 2 (route `respond_to_fok`
   through `_size_for`'s inventory cap) and FIX 5's delta-bump correction (full
   `RATE_STRIKE_GRID` step instead of the sub-grid relative bump) on top of
   `CovarianceRisk`'s existing covariance formula — this would fix the FED-domination
   problem (§2.8-5) that currently still undermines even `CovarianceRisk`'s more accurate
   risk score, since a saturated/mis-scaled delta vector feeds badly into any risk
   formula regardless of how correct that formula's own covariance math is.
2. **`FiveBugfixes`** — recommended specifically *because* of its lower score, as the
   most defensible submission against a genuinely tougher/adversarial unseen
   competitor set: no live inventory-cap bypass, no negative-edge quoting, and a
   drawdown breaker that responds to real PnL rather than raw cash. Suggested minor
   fix to describe: its own `_Scores.md` shows it still uses the sum-of-squares
   portfolio risk score inherited from `EpsilonSharpen`'s ancestry rather than `CovarianceRisk`'s
   covariance-aware version — grafting that in would combine the fleet's two most
   substantively correct pieces (bug-clean risk-control code + covariance-aware
   risk math) into one bot, something no single existing bot currently has.
3. **`FlowRegimeTightening`** — the safest, most conservative of the "successful" lineage: its
   mechanism (trust an accumulated, large-sample favorable-markout signal) is more
   behaviorally general than its later siblings' single-test-tuned constants, it
   predates the drawdown-breaker mechanism that even its own descendants flag as
   unvalidated, and it ties near the top of the real leaderboard (17.20/20) without
   carrying `FlowCapTune03`/`FlowCapTune04`'s narrowest, most overfit-looking tuning. Suggested
   fix to describe: apply `FiveBugfixes`'s FIX 1 (stop letting the trust-weighted
   midpoint blend cross fair value) and FIX 2 (FOK inventory-cap enforcement), both
   independent, additive, low-risk corrections that don't touch `FlowRegimeTightening`'s own
   `_FlowRegime` mechanism.

Not recommended for submission despite tied top scores: `FlowCapTune03` and `FlowCapTune04`,
whose sole differentiating changes are narrowly tuned to specific already-graded
sessions with the weakest mechanistic justification for holding up against a
different competitor mix in this entire comparison.
