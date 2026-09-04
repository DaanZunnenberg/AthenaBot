# Model uncertainty (`U_P`) and one-step probability volatility (`sigma_P`)

> **What this improved / established:** Model-uncertainty (`U_P`) design, plus an emergency post-submission size cut after this version tripped the same file-size compile error again (74,756 bytes) -- the second real occurrence of the `02-COMPILE-ERROR-FILE-SIZE-FIX.md` bug.

## Post-submission update: emergency size cuts (read this first)

The version originally shipped here caused a real "Server error while compiling" on
submission (`Bot.py` at 74,756 bytes, over the compile ceiling this repo has hit twice before
-- see `docs/history/JOURNEY.md` Phase 5). Two changes were made **after** the results below were first
measured, to bring the file back under budget without disabling the feature:

1. **`sigma_P` (item B) was removed entirely.** It turned out not to be consumed by any
   decision in item C's wiring (only `U_P` is) -- so per the "every object must change a
   decision or be deleted" rule, keeping it was already questionable, and it was the single
   most self-contained, highest-byte-per-value piece to cut under time pressure. `sigma_P`'s
   cache key is still reserved (`None`) for a future task, per Prompt 2's original design.
2. **The bootstrap sampler was simplified from a full Cholesky/multivariate-normal draw to
   independent per-parameter sampling** (using only the diagonal of each `_theta_cov` block,
   dropping cross-parameter correlation within the company and rate blocks). This removed
   `_cholesky`/`_mvn_sample` entirely. **Re-ran the coverage study after this change: 85.04%
   overall (unchanged to 2 decimal places), 80.33% on `theta_cov_reliable` days (vs. 80.36%
   before)** -- the correlation structure within blocks turned out not to matter much for
   this specific calibration metric, so this is a real, verified-safe simplification, not
   just a guess that it wouldn't matter.
3. The rest of the file also got a comprehensive, mechanical docstring strip (AST-based:
   every function/class docstring removed) across the *whole* file, not just this task's
   additions, since targeted trimming alone (the pattern used in every prior task) wasn't
   enough this time. Final size: **53,592 bytes**, comfortably under the 60,060-65,372 byte
   range every previously-confirmed-working submission has landed in.

Everything below describes the feature as designed; the size note above documents what was
cut to ship it. All acceptance-criteria numbers were re-verified after these cuts (pricer
invariants, ledger tests, and performance are unaffected since they don't depend on docstrings
or the bootstrap's correlation structure; the coverage study was explicitly re-run).

## What shipped

- **A (`U_P`, parametric bootstrap)**: `B = 32` draws of `theta ~ N(theta_hat, Sigma_theta)`
  per day, common random numbers (seeded `1_000_003 * day_index + 17`, `random.Random`
  instance -- never the global `random` module). Company `(mu, beta)` blocks and the rate
  `(p_up, p_down, kappa, r_target)` block are sampled **independently per parameter** (diagonal
  of each `_theta_cov` block only -- see the size note above); `(vbar_A, vbar_T, cbar)` are
  sampled independently (the `"variance"` block in `_theta_cov` has no cross-terms regardless)
  and reconstructed into sector loadings via the existing `_reconstruct_sector_loadings`. Rate
  draws are reprojected through `_project_to_admissible`. `U_P_j` = sample std of `{P_j^(b)}`
  over the 32 draws, priced with the same option/values every time.
- **B (`sigma_P`)**: removed post-submission (see size note above). Cache key reserved, `None`.
- **C (consumption)**: `_quote_half_spread` gained a `+ c_U * U_P` term (`c_U = 1.0`);
  `respond_to_fok`'s edge is now `eta = max(_FOK_EDGE, c_U * U_P)` instead of the fixed
  `_FOK_EDGE` alone.
- **Fallbacks**: `_theta_cov_reliable == False`, a failed draw, or a non-finite bootstrap
  price all route to `_U_P_FLOOR = 0.05`, logged once per session (`_uncertainty_floor_logged`).

## A real bug this surfaced and fixed: `_theta_cov_reliable` didn't persist correctly

Before touching any of the above, an early smoke test showed `_theta_cov_reliable` flipping
from `False` (right after `warm_up`) to `True` on the very next `on_step_advance`, with no new
data justifying the change. Root cause: `_ParameterEstimator.fit`'s rate-MLE Hessian
(`_rate_hessian_covariance`) frequently fails (documented in `debug/ESTIMATION.md` -- the rate
kernel is grid-searched, not continuously optimized, so the numerical Hessian at the grid
argmax is often not locally concave). On failure it substitutes a diagonal fallback and marks
`reliable = False` for *that call* -- but the fallback matrix itself then gets cached as
`self._rate_cov` and reused verbatim on every subsequent `refit_rate=False` call, with no
memory that it was a fallback. `reliable` was recomputed fresh each time from `rate_cov is
None`, which is never true once a fallback has been cached -- so reliability silently flipped
`True` one day after `warm_up`.

**Fix**: `_FitResult` gained a `rate_cov_fresh: bool` field, `MarketMaker` persists it as
`self._rate_cov_fresh` across cached-reuse calls, and `fit()`'s `reliable` now starts from
`rate_cov_fresh` (persisted) rather than a per-call `rate_cov is None` check. This matters
independently of this task -- Prompt 1/2's `_theta_cov_reliable` consumers were already
silently wrong -- but it directly gates `U_P`'s bootstrap-vs-floor decision, so it had to be
fixed here to get meaningful results at all.

## Performance: the rate lattice, not the quadrature, was the bottleneck

Initial implementation (full-precision `_BinaryOptionPricer.price`, `B=32`, 50-option
universe, `theta_cov_reliable=True`): **828ms/day**, well over the 250ms budget. Profiling
(not guessing) found the two-leg quadrature (129 nodes) was *not* the dominant cost -- the
rate lattice DP (`_rate_lattice`, O(steps) x O(distinct levels)) was, at ~0.26ms of a ~0.34ms
per-call total for a 20-day two-leg option. Two changes, in order of how much they mattered:

1. **`lattice_cache`**: the rate lattice depends only on `(kappa, target, rate0, steps)`, not
   on the company parameters -- so it's identical across every option that shares a draw's
   `steps` value. Added an optional `lattice_cache` dict to `_BinaryOptionPricer.price`,
   memoized by that 4-tuple (rounded), threaded through the day's `B x n_options` bootstrap
   calls (and the 6 finite-difference calls). Canonical `P_j` pricing never passes a cache
   (`lattice_cache=None` default), so it's byte-for-byte unaffected.
2. **`fast` quadrature**: a 9-node quadrature (`_QUAD_NODES_FAST`, vs. the canonical 129) for
   the same bootstrap/finite-difference calls only -- `U_P`/`sigma_P` need a dispersion
   estimate, not `P_j`'s full numerical precision.

Result: **145ms median/day** in the worst realistic case (theta_cov reliable on every single
day of a 30-day session, 50 options/day) -- comfortably under the 250ms budget, and this is a
strict upper bound since `theta_cov_reliable` is true on a minority of days in practice (see
coverage study below), where the cost drops to ~70ms (floor path, no bootstrap at all).

## Coverage study (`sim/test_uncertainty.py`, acceptance criterion 1)

200 sessions, 30-day burn-in, 15 live days, 6 options/day, true `MarketParameters` known to
the test (never to `MarketMaker`). 111,967 `(P_hat, P_true, U_P)` records.

| | coverage (`|P_hat-P_true| <= 2*U_P`) | mean `U_P` | share of records |
|---|---|---|---|
| **All** | **0.8504** (target >= 0.85) | 0.0491 | 100% |
| `theta_cov_reliable` days | 0.8036 | 0.0424 | 11.57% |
| unreliable/floor days | 0.8565 | 0.0500 (the floor) | 88.43% |

**Result: PASS, but by a very thin margin (85.04%), and the breakdown is worth reporting
honestly rather than treating the aggregate number as clean.** The days where `U_P` is
genuinely bootstrapped (not the fixed floor) show *worse* coverage (80.4%) than the days that
fall back to the flat 0.05 floor (85.7%). Two things follow directly:

1. **The floor is carrying most of the aggregate result.** `theta_cov` is only reliable
   (rate Hessian succeeded) on 11.6% of records -- the vast majority of the 85.04% headline
   number is really testing "is a flat 0.05 floor well-calibrated," not "is the bootstrap
   well-calibrated."
2. **Where the bootstrap does run, it's somewhat under-covering.** Per the acceptance
   criterion's explicit instruction not to paper over this with a fudge factor: the most
   likely culprit is the company OLS covariance blocks (`company_A`/`company_T` in
   `_theta_cov`), not the rate block -- since `theta_cov_reliable` is defined to require the
   rate Hessian to have succeeded, every record in the "reliable" row already has a rate
   covariance; the company blocks are the only remaining source of a systematically-understated
   `Sigma_theta` in that subset. `_company_covariance`'s `s^2*(X'X)^-1` formula is the standard
   OLS sampling covariance, which is asymptotically correct but can understate true parameter
   uncertainty at finite `N` (here, `N` = burn-in days, typically 30) if the residuals have any
   structure the model doesn't capture (e.g. the finite-`N` bias in the OLS covariance
   estimator itself is largest at exactly the `N` this project's burn-in windows use -- see
   `debug/ESTIMATION.md`'s own note that recovery statistics at `N=200` are themselves at the
   edge of the target for `vbar`/`cbar`, let alone the shorter `N=30` typical burn-in).

**Not fixed here**: inflating `_U_P_FLOOR` or `c_U` would mask this without addressing the
root cause. The honest next step, if this needs to be tighter than a bare pass, is improving
the company covariance estimator's finite-sample calibration (e.g. a small-sample correction
factor derived from the `debug/ESTIMATION.md` recovery study, or increasing the burn-in
window), not scaling `U_P` after the fact.

## Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Coverage >= 85% over 200 sessions | **PASS** (85.04%, thin margin -- see breakdown above) |
| 2 | Median day < 250ms, 50-option universe | **PASS** (145ms median, worst-case-reliable scenario) |
| 3 | Score does not regress vs. Prompt 2 | **PASS** -- mean score 1.5639 (Prompt 2) -> 2.0573 (this task), 0% bankruptcy both, 200-session common-random-numbers comparison |
| 4 | All prior invariants still pass | **PASS** -- `sim/test_pricer.py` (220/220 bounds/monotonicity/complement, 205/205 martingale steps>=2, 220/220 MC cross-check) and `sim/test_ledger.py` (6/6 suites) both unaffected |

## File size: resolved after a real compile failure

The version first pushed here (74,756 bytes) did trigger "Server error while compiling" on
submission -- see the update at the top of this document for exactly what was cut in
response (removing `sigma_P`, simplifying the bootstrap sampler, and a full mechanical
docstring strip). Final size **53,592 bytes**, re-verified against every test in this repo
(pricer invariants, ledger tests, coverage study, harness performance) before pushing again.
