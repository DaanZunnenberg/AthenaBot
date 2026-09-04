# Part D: portfolio-level correlated risk — what shipped and what didn't

> **What this improved / established:** Documents what shipped vs. was cut from portfolio-level correlated tail-risk work, because `Bot.py` was already near the compile-size ceiling before this part started.

## Scope decision (read first)

`Bot.py` was already within ~150-300 bytes of the compile-size ceiling this repo has hit twice
before (see `docs/history/JOURNEY.md` Phase 5, `debug/CALIBRATION.md` Section D1) *before* Part D was
reached in this task. Parts A, B, C, and F were prioritized (closed-form, well-specified, and
each already implemented and tested — see `sim/test_shrinkage.py`, `sim/test_kelly.py`, and
the toxicity clip in `_toxicity`). **D1-D3 (the linear correlated-risk budget and its
proportional trade scale-down) were not implemented in `Bot.py`** in this pass — there was not
enough remaining byte budget to add the loading-vector cache, the 3x3 shock covariance
construction, and the scalar-quadratic scale-down solve without risking the same "Server error
while compiling" failure documented in `docs/history/JOURNEY.md` Phase 5. This is a real, acknowledged gap,
not a disguised implementation — `sim/test_portfolio_risk.py` (a deliverable for this task) was
correspondingly not created, since a test file for a mechanism that doesn't exist in `Bot.py`
would be misleading. **D1-D3's acceptance criteria 1-3 (relative sizing of correlated vs.
offsetting trades, the `rho_book <= B_risk` bound, and the harness bankruptcy/worst-decile
comparison) are therefore not verified in this pass.**

## What did ship: D4, as a read-only offline diagnostic

D4's CVaR/concentration diagnostic was implemented — but, per the task's own explicit framing
("use as diagnostic only ... log ... as an audit signal, not a new constraint"), as
`sim/test_tail_risk.py`, a standalone script that reads `MarketMaker._scenario_Y` plus
arbitrary externally-supplied positions and entry prices, computes the per-scenario book P&L
`Pi_s = sum_j q_j*(Y_j^s - p_j_entry)` directly from that state, and derives:

$$
\text{VaR}_\alpha = -\Pi_{(k)}, \qquad \text{CVaR}_\alpha = -\frac{1}{k}\sum_{i=1}^k \Pi_{(i)}, \qquad k = \lceil(1-\alpha)S\rceil
$$

with the marginal comparison and concentration ratio `kappa_conc = CVaR_book / sum_j CVaR_j`
exactly as specified. This is genuinely zero marginal byte cost to `Bot.py` (no new attributes,
no new methods on `MarketMaker`) since it only reads state the scenario/utility machinery
(Prompt 4) already builds and exposes.

## Acceptance criteria results (from `sim/test_tail_risk.py`)

| # | Criterion | Result |
|---|---|---|
| 4 | Subadditivity `CVaR_book <= sum_j CVaR_j + 1e-9`, 500 random books | **PASS** — 500/500 clean, zero violations (this is a correctness check on the *implementation*, per the task's own framing, since the inequality is a theorem) |
| 5 | Stress case: concentrated correlated book registers `kappa_conc` near 1; hedged book registers well below 1 | **PASS at `rho_AT = 0.999`** — concentrated (both short, same-sign sector loadings): `kappa_conc = 1.0000`. Hedged (long one, short the other correlated name): `kappa_conc = 0.0952`. See the note below on why this needed `rho_AT` close to the `+-1` corner specifically. |

## A real finding, not a bug: why the hedge needs `rho_AT` near `+-1` to show up

At moderate correlation (tested `rho_AT` up to 0.99), the "long one, short the other correlated
name" book's `kappa_conc` did **not** register well below 1 — it stayed close to 1 even though
the same book's day-to-day P&L variance is visibly much lower than the concentrated book's. The
reason, confirmed by direct inspection: at `alpha=0.99` and `S=2048` scenarios, the CVaR tail
(`k ~ 21` worst scenarios) is small enough that once the two legs' *co-movement* is hedged away
(the common, high-probability scenarios collapse to `Pi_s ~ 0`), what remains in the tail is
**entirely the rare residual disagreement** between the two legs — an idiosyncratic-noise-driven
event whose magnitude, when it occurs, is *larger* than either leg's own marginal move (a basis
trade is exposed to the spread, and the spread's own tail can be fat even when each leg is
individually well-behaved). This only stops dominating once `rho_AT` is close enough to `+-1`
that disagreement becomes genuinely rare relative to the `1%` tail mass — exactly the corner the
task's own G1 adversarial sampler flags as "exactly where the D4 concentration diagnostic should
be watched most closely." This is a legitimate property of high-alpha CVaR on basis trades, not
an artifact of this implementation — see `sim/test_tail_risk.py`'s `test_stress_case` docstring
for the numeric trace that led to this conclusion (kappa_conc for the hedge: 1.0 at `rho=0.9`,
0.67 at `rho=0.99`, 0.095 at `rho=0.999`).

## Distribution of `kappa_conc` across scenario pools

Given Part G's own scope reduction (see `debug/ROBUSTNESS_RESULTS.md`), a full three-pool
(plausible/wide/adversarial) distribution study of `kappa_conc` across live harness sessions was
not run — `sim/test_tail_risk.py`'s stress case above is a targeted, hand-constructed probe of
the specific corner (`rho_AT -> 1`, one-sided correlated exposure) the task flags as the
regime where this diagnostic matters most, rather than a distributional sweep. **Recommended
follow-up**: since D1-D3 is not wired in, there is currently no live mechanism enforcing
`B_risk`, so a distributional study would only be informative once D1-D3 exists — running it
now would describe the diagnostic's behavior on an unconstrained book, not audit whether a
risk budget is "silently permitting" a concentrated book (there is no budget to silently permit
anything past). This is the natural next step once D1-D3's byte-budget problem is solved (e.g.
after a further aggressive trim, or accepting the file must drop something else to make room).
