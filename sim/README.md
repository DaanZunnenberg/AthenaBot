# `sim/` — offline harness for `Bot.py`

Local replica of the HackerRank exchange loop, so `MarketMaker` behaviour can be iterated on
without burning a submission. Imports `Bot.py` from the repo root; never the other way around
-- `Bot.py` stays a single, stdlib-only file, since that's the artifact actually submitted.

Requires Python 3.11+ (matches `Bot.py`'s use of `enum.StrEnum`) and `numpy`:

```bash
python3.11 -m pip install numpy
```

## Files

- `harness.py` -- the day-loop simulator: `sample_parameters`, `generate_history`,
  `generate_option_universe`, `run_session` (one session), `run_batch` (many sessions with
  common random numbers across configs). Also a `WARNING: bankruptcy rule unverified` printed
  at import time -- see "Scoring caveat" below.
- `counterparties.py` -- `NoiseCounterparty`, `InformedCounterparty`, `MixedCounterparty`,
  used by `harness.py`'s day loop to generate RFQ responses and FOK orders.
- `test_estimation.py` -- recovery-statistics suite for the `warm_up` estimation layer
  (`_SufficientStats`/`_ParameterEstimator` in `Bot.py`): 100 synthetic replications at
  N=200 checking `beta_i`/`vbar`/`cbar`/`kappa` recovery and rate-MLE convergence against
  known ground truth, plus a unit test that the sector-loading reconstruction reproduces the
  target company moments through `_BinaryOptionPricer._company_moments`. Run with
  `python3.11 sim/test_estimation.py`; results are written up in `debug/ESTIMATION.md`.
- `test_pricer.py` -- invariant suite for `price_option_from_parameters` (bounds, strike
  monotonicity, complement identity, martingale property, Monte Carlo cross-check) against
  the true `MarketParameters`, independent of `harness.py`.

## Running a batch

```bash
python3.11 sim/harness.py
```

Runs 200 sessions (`base_seed=1`, the default `SessionConfig`: 30 burn-in days, 20 live days,
6 new options/day, `$10` starting cash, a 50/50 noise/informed `MixedCounterparty`), prints
`mean_score` / `p5_score` (5th percentile) / `bankruptcy_rate` / `mean_fill_rate`, and writes
one row per session to `sim/baseline.csv`.

To run a custom batch (e.g. after changing `Bot.py`'s quoting logic), import the pieces
directly:

```python
from sim.harness import SessionConfig, run_batch, write_csv

cfg = SessionConfig(n_live_days=30, n_options_per_day=8)
batch = run_batch(n_sessions=200, config=cfg, base_seed=1)
print(batch.mean_score, batch.p5_score, batch.bankruptcy_rate)
write_csv(batch, "sim/my_run.csv")
```

**Common random numbers**: `run_batch(n, cfg_a, base_seed=1)` and `run_batch(n, cfg_b,
base_seed=1)` see identical market paths and counterparty behaviour session-by-session (every
random draw inside `run_session` derives from that session's `np.random.default_rng(seed)`),
so a mean-score delta between two configs reflects the config change, not sampling noise --
provided both configs only draw randomness from the `rng` they're handed (true of every
counterparty in `counterparties.py`).

## Running the pricer invariant suite

```bash
python3.11 sim/test_pricer.py
```

Generates 220 random `(MarketParameters, option)` cases spanning all leg shapes (single-leg
FED/AJR/THR, spreads, non-unit-weight spreads, three-leg combinations), expiries 1-20, and
strikes at 9 moneyness levels (0.2x-2.5x), and runs:

1. **Bounds** -- `0 <= P <= 1` for all 220.
2. **Strike monotonicity** -- exact, zero-tolerance `K1 < K2 => P(K1) >= P(K2)`.
3. **Complement identity** -- `P(w, K) + P(-w, -K) == 1` (within `1e-9`) for the 157 cases
   with no FED leg (continuous observable).
4. **Martingale property** -- `E_t[P_{t+1}] == P_t`, exact 3-branch rate DP times a
   Gauss-Hermite grid (16 nodes/dim for single-company-leg cases per the task spec; 9
   nodes/dim, documented as a pragmatic deviation, for two-company-leg cases needing a 3rd
   quadrature dimension). Split into `[4]` (`steps_until_expiry >= 2`, tolerance `1e-6`/`1e-4`)
   and `[4b]` (`steps_until_expiry == 1`, the n=1->n=0 settlement boundary -- see
   `debug/CONVENTION.md` for why failures there are an expected, documented consequence of the
   settlement patch and not a pricer defect).
5. **Monte Carlo cross-check** -- `M=400,000` paths per case, vectorized in numpy (a
   from-scratch reimplementation of `MarketParameters.advance_step`'s update rules, since the
   stdlib `random`-based original isn't vectorizable), compared against a `4*sqrt(P(1-P)/M)`
   bound.

**Kill criterion**: if tests 4 or 5 fail on more than 1 of the 220 cases (excluding the
documented `[4b]` boundary cases), the script prints a report naming the failing cases and
stops rather than a plain pass/fail summary. As of the change described in
`debug/CONVENTION.md`, all tests pass except the 4 documented `[4b]` boundary cases (verified:
0/205 martingale failures for `steps_until_expiry >= 2`, i.e. the underlying DP/quadrature
engine itself is exact).

Runtime: ~3 minutes on a laptop CPU (dominated by test 5's 220 x 400,000-path simulations and
test 4's nested Gauss-Hermite grids for two-company-leg cases).

## Scoring caveat

The README only specifies the *live* grader's scoring in relative terms ("full credit for
ranking #1 in PnL among competing market makers, zero for bankruptcy, partial for solvency")
-- a ranking this single-agent harness has no way to reproduce without a model of competing
market makers, which isn't documented anywhere in this repo. Per the task's fallback
instruction, `run_session`'s `score` field is **worst-case terminal cash**: `0.0` on
bankruptcy, else the session's actual final cash balance (see the `WARNING` printed at
`sim/harness.py` import time, and the comment at its `score = ...` assignment). Treat
`mean_score`/`p5_score` as a solvency-and-absolute-PnL proxy, not a prediction of HackerRank
leaderboard rank.
