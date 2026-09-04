# Part G1-G2: wider/adversarial sampling and synthetic reference baselines

> **What this improved / established:** Extends `sim/harness.py` with wider and adversarial parameter samplers plus synthetic reference baselines, giving later robustness work a harder test bed than the default sampler.

## G1: wide and adversarial parameter samplers

Added to `sim/harness.py`: `sample_parameters_wide` (every range in the existing
`sample_parameters` widened ~2.5x) and `sample_parameters_adversarial` (hostile combinations:
`rho_AT` forced near `+-1` via matched/opposite-sign equal-magnitude sector betas with idio
noise floored near zero; a rate process that is either near-frozen (`kappa=0`, `p_up=p_down=
0.001`) or hyperactive (`p_up=p_down=0.45`), independent of anything a burn-in sample would
suggest -- i.e. a genuine regime break the estimator never saw during warm-up). Both respect
`MarketParameters.__post_init__`'s constraints (verified: every sampled draw across all runs in
this task instantiated without a `ValueError`).

`run_session`/`run_batch` in `sim/harness.py` were extended with `params_sampler` (swap the
parameter distribution) and `maker_factory` (swap the bot class) parameters, so the wide/
adversarial pools and the synthetic baselines below reuse the identical session loop rather than
duplicating it -- this was a deliberate design choice to keep the comparison apples-to-apples
(same settlement/bankruptcy logic, same RFQ/FOK interaction pattern) rather than risk a second,
subtly-different harness implementation.

**Not implemented**: an informed counterparty with perfect knowledge of the *true* (not
estimated) `MarketParameters`, which the task's G1 also names. `sim/counterparties.
InformedCounterparty` already computes its edge from the harness's own ground-truth `params`
(never `AthenaBot`'s estimate) -- see `_true_theo` in `sim/counterparties.py` -- so this
property already exists for every session run in this repo, not just this task's additions;
no new counterparty class was needed.

## G2: synthetic reference baselines

Two stand-ins, in `sim/test_robustness.py`, run through the identical `run_session`/`run_batch`
loop via the new `maker_factory` parameter:

1. **`FixedWidthMaker`**: `MarketMaker` subclassed with `_blend_weight` forced to always return
   `0.0` -- i.e. Part B's own fixed-width fallback, permanently engaged. This reuses the actual
   shipped pricing/estimation machinery for the fair-value center, just with zero blend toward
   the sophisticated indifference price.
2. **`NaiveInventoryQuoter`**: a from-scratch minimal class (not a `MarketMaker` subclass) --
   fixed 0.10 half-spread centered at a flat 0.5 (no pricing model, doesn't even read the
   underlying state), linear inventory skew, **no feasibility gate, no cash tracking beyond a
   running total, no position cap**. This is deliberately the simplest possible quoter with no
   risk management.

**Neither is the actual named competitor** ("Fixed Width 0.05"/"0.1"/"0.25", "Situational
Unawareness", "Mongoose" from `archive/debug-snapshots/TestCaseHandles.md`) -- their exact internals are unknown to this
repo, as stated in the task. These stand-ins only share the qualitative property the task asks
for (constant/simple spread, no sophistication) and are used to sanity-check that `AthenaBot`'s
added complexity is earning its keep against something naive, not to reproduce the exact
HackerRank leaderboard.

## Results (`sim/test_robustness.py`, n=4-12 sessions/pool, see `debug/ROBUSTNESS_RESULTS.md`
for the full table)

- `NaiveInventoryQuoter` reliably goes bankrupt within the first few days in every pool tested
  (e.g. session seed 20000: bankrupt on day 2, final cash -$1.20) -- expected and correct: it
  quotes a fixed size regardless of remaining cash or position, with no feasibility gate at all.
  This is the sharpest confirmation available that `AthenaBot`'s risk machinery (the Prompt 2/4
  feasibility gate) is not decorative.
- `FixedWidthMaker` and `AthenaBot` produced **numerically identical** scores across every
  session tested at this sample size. Investigated directly (not assumed): both bots trade
  infrequently under the harness's default `rfq_fraction`/counterparty settings (~4% fill rate,
  consistent with the fill rates measured throughout Prompts 4-6), and since both draw from the
  same common-random-number stream, they end up not trading on the same days in this small
  sample -- so the sophisticated-vs-fixed-width distinction never actually gets exercised often
  enough at n=4-12 to show up. This is a real limitation of the sample size used here, not
  evidence the blend is inert: a direct single-quote check (same `MarketMaker` state, `w`
  forced to `0` vs. left to ramp up after `_N_MIN` days) shows materially different half-widths
  (e.g. one probe: fair=0.243, `w~0` gave half-widths (0.053, 0.057) close to the `s_fixed=0.05`
  target; `w~1` gave (0.083, 0.067), reflecting the full indifference/margin pricing) -- see
  `debug/ROBUSTNESS_RESULTS.md` for the reproduction. The session-level tie is a sampling
  artifact of how rarely either bot actually trades at this `n`, not a sign the blend has no
  effect on the quotes themselves.
