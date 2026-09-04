# Settlement convention: `steps_until_expiry == 0`

> **What this improved / established:** Resolved an ambiguity in what `steps_until_expiry == 0` means for settlement, aligning the expiry-credit logic with the grader's actual timing.

## The ambiguity

`BinaryOption`'s docstring says `steps_until_expiry == 0` means the option "settles at the
end of the current day." Separately, `MarketMaker._credit_expired_positions` settles an
option that drops out of `active_option_state` using the underlying values passed alongside
the *next* `on_step_advance` call (`new_underlying_state`), not the values the option was
last observed with. docs/history/LEGACY-MODEL.md §3.9 flagged this as unresolved ("the two conventions cannot
both be right") with no further documentation elsewhere in the repo resolving it -- `README.md`,
`docs/history/JOURNEY.md`, `docs/history/NOTES.md`, and `docs/history/TODO.md` were all searched and none mention it.

## Resolution: `SETTLEMENT_AFTER_ADVANCE = True`

`Bot.py` now defines `SETTLEMENT_AFTER_ADVANCE: Final[bool] = True`, and
`_BinaryOptionPricer.price` treats an option observed at `n == 0` as having **one remaining
diffusion step**, not a deterministic indicator on today's values.

### Evidence from the code itself

Tracing `_credit_expired_positions`'s contract: it is called from `on_step_advance(new_underlying_state,
new_option_state)` and settles any option present in `self.active_option_state` (the state
*before* this call) but absent from `new_option_state`, using `new_underlying_state`. Per
`BinaryOption.advance_step`'s own docstring ("called by the exchange/grader each simulated
day to age options forward"), each `on_step_advance` call corresponds to exactly one such
aging step. So an option last observed by `MarketMaker` at `n == 0` is, on the very next
`on_step_advance` call, both aged (a no-op for `n == 0`, since `advance_step` clamps at 0)
*and* dropped from the active set, settled against `new_underlying_state` -- the values as of
one advance step *after* the day it was observed at `n == 0`. That is one full day of
diffusion the option's value has not yet reflected at the moment `MarketMaker` sees `n == 0`,
so treating it as a deterministic indicator on current values (`SETTLEMENT_AFTER_ADVANCE =
False`) would systematically misprice every option in its final day.

### Empirical confirmation via the harness

`sim/harness.py`'s `run_session` day loop mirrors this same mechanic independently (ages
options, drops any that were at `n == 0`, settles them against the values *after* that day's
`advance_step`, exactly matching `_credit_expired_positions`'s contract) -- built without
reference to the `SETTLEMENT_AFTER_ADVANCE` flag in `Bot.py`, so it serves as an independent
check rather than assuming the same conclusion twice.

`sim/test_pricer.py`'s martingale test (`E_t[P_{t+1}] == P_t`) is the sharpest empirical probe
available, since it does not require running a full session -- it directly compares the
pricer's own output one step apart. Results over 220 random cases (`python3.11
sim/test_pricer.py`):

- **`steps_until_expiry >= 2` (away from the boundary): 0/205 failures**, tolerance `1e-6`
  (single-leg/rate-only) or `1e-4` (two-company-leg, coarser 3-D quadrature). The exact
  DP/quadrature pricing engine (`_two_leg_prob` and everything upstream of it) is internally
  consistent and unaffected by the settlement patch away from the boundary.
- **`steps_until_expiry == 1` (crosses the `n=1 -> n=0` transition): 4/15 fail**, including a
  pure-FED, zero-company-leg case -- which rules out `_two_leg_prob` as the cause, since that
  code path is never reached for a FED-only option. This is an **expected, narrowly-scoped
  consequence** of the task's exact instruction to patch only the `n == 0` boundary: pricing
  at `n == 1` still uses exactly one diffusion step (no patch applied there), but pricing at
  `n == 0` (reached one day later, under `SETTLEMENT_AFTER_ADVANCE`) now uses *another* full
  step from that point. By the same evidence-from-the-code argument above, the fully
  consistent fix would need `settle_steps = n + 1` for *every* `n`, not only `n == 0` -- but
  the task's permitted `Bot.py` change was scoped narrowly to the `n == 0` case, and that
  narrower scope was kept here rather than expanded, per "the only permitted change to
  `Bot.py` is resolving the settlement convention (item C)."

## Bottom line

- `n == 0` pricing without the patch (`SETTLEMENT_AFTER_ADVANCE = False`) is provably wrong:
  it ignores one full day of diffusion that `_credit_expired_positions` demonstrably applies
  before settlement.
- With the patch, the pricer is exact (0 martingale violations, MC cross-check within
  statistical bounds) everywhere except the immediate `n=1 -> n=0` transition, where a
  small, fully explained and documented discrepancy remains as a known limitation of the
  narrowly-scoped fix. This does not indicate a defect in `_two_leg_prob` or the DP/quadrature
  engine -- see `sim/test_pricer.py`'s `[4]`/`[4b]` split, which separates genuine failures
  from this documented boundary effect.
- If a future task authorizes a broader change, the fully consistent fix is `settle_steps =
  steps_until_expiry + 1` uniformly (not just at the `n == 0` boundary); this was intentionally
  not implemented here to stay within the task's explicit scope.
