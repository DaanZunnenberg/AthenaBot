# Scenario set, book certainty equivalent, indifference quoting

> **What this improved / established:** Replaces the heuristic fixed-spread quoting layer with exponential-utility indifference pricing from a shared Monte Carlo scenario set -- a real design change at the time it was written; cross-check against `docs/history/LEGACY-MODEL.md` before assuming it matches current `Bot.py` exactly.

Replaces the heuristic reservation-price/fixed-spread quoting layer (`_reservation_price`,
`_quote_half_spread`, `_quote_quantities`, and their constants) with exponential-utility
indifference pricing derived once per day from a shared Monte Carlo scenario set, per the
task's items A-G. `U_P` (Prompt 3) is unchanged and still feeds the quoted margin.

## What shipped

- **B (scenario set)**: `MarketMaker._generate_scenarios`, called from `on_step_advance`.
  `S = 2048` paths of `(r, log A, log T)` simulated day-by-day out to the longest live
  maturity, using the estimated rate kernel (`tilted_rate_probabilities`/`next_rate_value`,
  the same functions `_BinaryOptionPricer` uses) for the discrete component and antithetic
  Gaussian draws (`z`, `1-u` for the discrete draw, `-z` for the Gaussian shocks) for the
  continuous ones, seeded `2_000_003 * day_index + 29` off a dedicated `random.Random`
  instance. Only the step counts actually needed by a live option's `steps_until_expiry` are
  snapshotted (`(r, A, T)` per scenario), not every intermediate day, to bound memory.
  `steps_until_expiry == 0` uses the same `SETTLEMENT_AFTER_ADVANCE` convention as the
  pricer (one more diffusion step, per `debug/CONVENTION.md`) rather than a separate rule.
- **B (sanity check)**: `_scenario_sanity_check`, run once per day, compares the scenario
  mean of `Y_j` against the cached `P_j` from `price_option` to `4*sqrt(P(1-P)/S)` and logs
  (non-fatally, into `_estimation_events`) any option where they disagree.
- **C (book CE)**: `_u_s` (length `S`) is maintained incrementally: reset once per day from
  currently-held positions (`_recompute_u_s`, `O(n_held * S)`), then updated multiplicatively
  after every fill (`_apply_fill_to_u`, `O(S)`) per the task's `u_s <- u_s * exp(-gamma*Q*(Y_j^s-p))`
  rule. `(U0_j, U1_j)` partitions are cached per option lazily (`_ensure_partition`) and the
  whole cache is invalidated on every fill, since a fill rescales `u_s` for every scenario and
  therefore every option's partition, not just the traded one -- this is a deliberately
  conservative reading of "recompute the affected partitions." `_indifference_bid`/`_ask`
  implement the closed-form formulas directly (log-sum-exp-style clamping via
  `exp(min(gQ, 700))` to avoid overflow), no root-finding.
- **D (quoting)**: `quote()` now prices both sides from `_indifference_bid`/`_ask` at the sizes
  chosen by `_size_bid`/`_size_ask`, adds `margin = m0 + c_U * U_P_j` (`T_b = T_a = 0` per the
  task, reserved for a future toxicity task), and reuses the existing `_round_quote_prices` /
  degenerate-quote fallback. `gamma = 0.05`, `m0 = 0.01`, `c_U` reuses the existing `_C_U = 1.0`
  constant from Prompt 3 rather than duplicating it.
- **E (sizing)**: `_size_bid`/`_size_ask` do the direct `Q = 1..Q_hard` search the task
  describes, stopping at the first `Q` that fails the feasibility gate (`_gate_passes`, the
  worst-case-cash/position-cap/gross-cap check carried over from the old `respond_to_fok`) --
  early-stopping rather than scanning the full range, since both feasibility and (for the bid
  side) `b_j(Q) >= b_min` are monotonically non-improving in `Q` in this construction.
  `Q_hard` reuses the existing `_position_cap` fail-safe rather than introducing a new
  constant. **`b_min` is not specified numerically by the task; it is set to `0.0`** (a bid
  must simply stay non-negative) -- the ask side has no symmetric threshold since the task
  only names `b_min`. This is the one place a real judgment call was made without a task-given
  number; see "Known simplifications" below.
- **F (FOK)**: `respond_to_fok` now accepts a counterparty buy iff
  `price >= a_j(Q) + margin` and a counterparty sell iff `price <= b_j(Q) - margin`, both
  still gated by `_gate_passes`. The old fixed `_FOK_EDGE` constant is gone.
- **G (deletions)**: `_reservation_price`, `_quote_half_spread`, `_quote_quantities`,
  `_INVENTORY_COEFFICIENT`, `_TIME_HORIZON_STEPS`, `_BASE_HALF_SPREAD`,
  `_UNCERTAINTY_HALF_SPREAD`, `_FOK_EDGE`, `_SIZE_SKEW`, `_INVENTORY_SCALE`, `_BASE_QUANTITY`
  all removed. `_POSITION_CAP_FRACTION`/`_GROSS_CAP_FRACTION` (via `_position_cap`/
  `_gross_cap`) are now used only inside `_gate_passes`, i.e. only as hard fail-safes, per the
  task.

## Entry-price tracking (new, required for `Pi_s`)

`Pi_s = sum_j q_j*(Y_j^s - p_j_entry)` needed a volume-weighted average entry price per
option, which nothing in the codebase tracked before. Added `self._entry_price: dict[int,
float]`, updated in `on_trade` via `_update_entry_price`: weighted-average when a fill
increases a position in the same direction, unchanged when a fill reduces it (standard
cost-basis convention -- realized P&L on the reduction flows through `_cash` already, not
through `p_entry`), reset to the fill price on a sign flip. Cleared on settlement
(`_settle_expired_positions`).

## Known simplifications / deviations from a maximally literal reading

- **`b_min = 0.0`**, not task-specified -- see item E above.
- **Partition invalidation is book-wide per fill**, not per-option, since `u_s` is genuinely
  global. This is `O(n_live_options * S)` amortized over the day rather than `O(S)` per fill,
  which is more conservative than the task's stated cost model but still well inside the
  400ms budget (see below).
- **`T_b_j = T_a_j = 0`** exactly as instructed (Prompt 5 will supply toxicity terms).

## Acceptance criteria (`sim/test_utility.py`)

| # | Criterion | Result |
|---|---|---|
| 1 | Scenario-vs-pricer consistency, every live option, every day | **PASS** -- 3844/3844 checks within `4*sqrt(P(1-P)/S)` over 20 sessions x 8 days x 6 options/day |
| 2 | Closed-form vs. analytic flat-book case, `1e-10` | **PASS** -- max observed deviation `2.22e-15` (float roundoff), 50 random cases x 3 sizes |
| 3 | Quote ordering invariants (`bid<offer`; both weakly worse with size; hedge beats naked) | **PASS** -- 3a: bid<offer and weakly-worse-with-size held for every quoted option across 10 sessions x 6 days x 6 options/day; 3b: constructed an anticorrelated pair (`ajarai_sector_beta=+1`, `theriodic_sector_beta=-1`) with a long AJR position and confirmed the THR-hedging bid (`0.502149`) strictly beats the naked bid (`0.481268`) |
| 4 | Median day < 400ms, 50-option universe | **PASS** -- 87-89ms median (15 days, universe held at 50 concurrent options) |
| 5 | 200 sessions, common random numbers: mean score improves vs. Prompt 3, bankruptcy rate does not increase | **PASS** -- mean score **1.6450 -> 9.4418** (`sim/baseline.csv` vs. this task, same `SessionConfig`, `base_seed=1`), bankruptcy rate **0.0 -> 0.0** unchanged. Mean fill rate dropped (6.38% -> 4.45%) alongside the large PnL gain -- consistent with the new pricing being more selective (it only takes trades where the closed-form indifference price clears its margin) rather than trading more often at worse prices. |

Run with `python3.11 sim/test_utility.py` (set `UTILITY_TEST_SESSIONS=20` to shorten
criterion 5 for a quick local check; defaults to 200 to match the task).

## File size

`Bot.py`: 53,592 -> 61,896 bytes. Still inside the 60,060-65,372 byte range every previously
confirmed-working HackerRank submission has landed in (`docs/history/JOURNEY.md` Phase 5), and under the
65,536-byte leading-theory ceiling. Re-verify size after any further additions (Prompt 5's
toxicity terms are the next planned change to this file).

## Regression check

`sim/test_ledger.py` (6/6 suites) and `sim/test_pricer.py` (unchanged: 220/220 bounds, 220/220
strike monotonicity, 205/205 martingale at `steps>=2`, 220/220 MC cross-check, the same
documented 4/15 `n==0` boundary discrepancies as before) both pass unaffected -- this task did
not touch the pricer or the ledger accounting, only `quote`/`respond_to_fok` and what feeds
them.
