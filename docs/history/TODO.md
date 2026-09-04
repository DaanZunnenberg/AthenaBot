# TODO

> **Status: all five steps below are done in `Bot.py`.** This file was the original
> step-by-step build plan and is kept as-is — it's still the right mental map of the six
> `MarketMaker` methods and their dependency order, and useful if any of them ever needs to be
> rebuilt from scratch. It is **not** a live task list anymore. Current tuning work happens in
> `experimental/` (see its `README.md` and `Scores.md`), not by reopening these steps — new
> ideas become new numbered `Bot_[4-digit].py` variants layered on top of a working baseline,
> not edits back into this build sequence. For where the project actually stands, see
> `docs/history/JOURNEY.md`'s "Where things stand now".

Six functions live in `MarketMaker`, but only five need real logic (`name` is done). Build them
in the order below — each step only needs logic from a step already finished, so you can test as
you go instead of debugging everything at once.

```
Step 1: price_option_from_parameters   (pure math, no dependencies)
Step 2: warm_up                        (needs step 1's math to know what to estimate)
Step 3: price_option                   (needs step 2's estimates)
Step 4: quote                          (needs step 3)
Step 5: respond_to_fok                 (needs step 3)
```

---

## Step 1 — `price_option_from_parameters(self, market_parameters, option)`

**Change this function first.** It's isolated math with no dependency on anything else you
write, it's the only thing the THEO test grades directly, and steps 3–5 all end up calling the
same math (just with estimated instead of true parameters).

**Inputs you're given:**
- `market_parameters: MarketParameters` — the *true* numbers describing how FED/AJR/THR move
  each day (drift, volatility, rate probabilities, etc. — see the field docs on
  `MarketParameters` in `Bot.py`).
- `option: BinaryOption` — has `option.legs` (which underlying(s) and weights),
  `option.strike`, and `option.steps_until_expiry` (how many days out it settles).
- Implicitly: `self.underlying_state` — the current value of FED/AJR/THR *today*.

**What it must return:** a single `float` in `[0, 1]` — the probability that, `n` days from
now (`n = option.steps_until_expiry`), the weighted sum of the option's legs is `>= strike`.

**Worked example:** Option = "FED >= 2.0 in 3 days", current FED = 1.75, `rate_step = 0.25`.
Reaching `>= 2.0` in exactly 3 steps needs the rate to go up at least once net. You'd walk the
rate's discrete distribution forward 3 days using `market_parameters.tilted_rate_probabilities`
(recompute the tilt at each day, since it depends on the current rate value) and
`next_rate_value`, and sum the probability mass of end states `>= 2.0`. For a 3-day horizon the
whole tree only has `3^3 = 27` paths, so brute-force enumeration is fine.

**Break it into three cases, easiest first:**
1. **Single leg on FED** (e.g. `FED >= 3.0` in `n` days): enumerate/DP over the rate's discrete
   grid walk (small state space — exact and cheap). This alone should pass part of THEO.
2. **Single leg on AJR or THR** (e.g. `AJR >= 500` in `n` days): the log-value is
   `drift + rate_beta*rate_change + sector_beta*sector_shock + idiosyncratic_noise`, summed
   over `n` days. `rate_change` per day depends on the (random) rate path; `sector_shock` is a
   fresh Gaussian draw shared by both companies each day. Monte Carlo (simulate many paths using
   the same update rules as `MarketParameters.advance_step`, and average the payoff) is the
   simplest way to get this right; revisit for a closed form later if needed.
3. **Two-leg spreads** (e.g. `AJR >= THR`, i.e. `AJR - THR >= 0`): same Monte Carlo approach,
   but simulate AJR and THR *together* each path (they share the same `rate_change` and
   `sector_shock` draws that day) so their correlation is preserved — don't price them as if
   independent.

**Done when:** you can hand-verify a couple of simple cases (e.g. `steps_until_expiry = 0`
should just check today's value against the strike directly) and the THEO test score improves.

---

## Step 2 — `warm_up(self, market_history)`

**Change this second**, once you know exactly which `MarketParameters` fields your Step 1 code
actually reads — estimate only those.

**Input you're given:** `market_history: MarketHistory`, i.e.
`market_history.values_by_underlying_id` — a dict from `underlying_id` to a tuple of daily
values, e.g. `{FED_FUNDS_RATE_UNDERLYING_ID: (2.0, 2.25, 2.25, 2.0, ...), AJARAI_UNDERLYING_ID:
(100.0, 101.3, ...), THERIODIC_UNDERLYING_ID: (80.0, 79.5, ...)}`, all the same length.

**What it must do:** *not* return anything — instead, compute your best estimate of the
`MarketParameters` fields and save them as attributes on `self` (e.g.
`self.estimated_parameters = MarketParameters(...)`), so `price_option` (step 3) can read them
later.

**How to estimate each piece:**
- `rate_up_probability` / `rate_down_probability` / `rate_reversion_strength` /
  `rate_target`: look at consecutive pairs of FED values. Each day it either goes `+rate_step`,
  `-rate_step`, or stays flat. Count how often each happens; since the probabilities are tilted
  by `reversion_strength * (rate_target - rate_value)`, a simple linear regression of "did it go
  up" vs. "distance from an assumed target" recovers the reversion slope (or just try a few
  `rate_target` guesses and fit the rest).
  *Example:* if the rate is at 1.75 most of the time and it goes up far more often than down
  when below 2.0, and down more often than up when above 2.0, that's evidence of reversion
  toward `rate_target ≈ 2.0`.
- `ajarai_rate_beta` / `theriodic_rate_beta`: compute each day's log-return
  (`math.log(value[t] / value[t-1])`) for AJR and for THR, and each day's rate change
  (`FED[t] - FED[t-1]`). Regress log-return on rate change (simple linear regression, or even
  just `covariance(log_return, rate_change) / variance(rate_change)`) to get the beta.
- `sector_std_dev` / `ajarai_sector_beta` / `theriodic_sector_beta`: after removing the
  rate-driven part of each day's log-return (the residual), AJR's and THR's residuals should
  still be correlated with each other through the shared `sector_shock`. The covariance between
  the two residual series tells you about the shared factor; what's left uncorrelated is
  idiosyncratic.
- `ajarai_idio_std_dev` / `theriodic_idio_std_dev`: standard deviation of what's left over after
  removing both the rate and sector components from each company's log-returns.
- `ajarai_drift` / `theriodic_drift`: the average log-return left unexplained by the rate/sector
  terms (i.e. the mean of the final residuals, if you haven't already centered them at 0).

**Done when:** printing your estimated `MarketParameters` next to reasonable expectations (e.g.
probabilities between 0 and 1, positive std devs, a `rate_target` near where the FED series
seems to hover) looks sane, and the VERBOSE test logs don't show wild mispricing.

---

## Step 3 — `price_option(self, option)`

**Change this third.** This is a thin wrapper, not new math.

**Input you're given:** `option: BinaryOption` only (no parameters passed in — unlike step 1).

**What it must do:** call the *same* pricing logic you wrote for
`price_option_from_parameters`, but pass in `self.estimated_parameters` (from `warm_up`)
instead of a `market_parameters` argument, and use the live `self.underlying_state` for
today's values.

**Simple example:** if step 1 looked like:
```python
def price_option_from_parameters(self, market_parameters, option):
    return self._price(market_parameters, option, self.underlying_state)
```
then step 3 is just:
```python
def price_option(self, option):
    return self._price(self.estimated_parameters, option, self.underlying_state)
```
(Refactor step 1 into a shared helper like `_price` if you haven't already — don't duplicate the
math.)

**Must stay side-effect-free** — no mutating `self.position`/`self.cash_balance` here, since the
grader also calls it just to log what you think an option is worth.

---

## Step 4 — `quote(self, option, counterparty_id)`

**Change this fourth.** Needs `price_option` (step 3) to already work.

**Inputs you're given:** `option: BinaryOption` (what to quote) and `counterparty_id: int`
(who's asking — you don't know if they want to buy or sell).

**What it must return:** a `Quote(bid_price, bid_quantity, offer_price, offer_quantity)`.
Requirements enforced by `Quote.__post_init__`: prices in `[0, 1]`, whole pennies (e.g. `0.42`,
not `0.4231`), `bid_price < offer_price`, and both quantities `> 0`.

**Simple example:** if `price_option(option)` returns `0.40` (i.e. you think there's a 40%
chance it pays off), a basic first version might be:
```python
def quote(self, option, counterparty_id):
    fair = self.price_option(option)
    spread = 0.04  # 4 cent half-spread on each side, tune this
    bid = round(max(fair - spread, 0.0), 2)
    offer = round(min(fair + spread, 1.0), 2)
    if bid >= offer:  # guard against a degenerate/crossed market near 0 or 1
        bid, offer = max(offer - 0.01, 0.0), min(bid + 0.01, 1.0)
    return Quote(bid_price=bid, bid_quantity=10, offer_price=offer, offer_quantity=10)
```
Then improve it: widen the spread when you're less confident (e.g. long-dated or spread
options), skew bid/offer based on `self.position.option_quantity_by_option_id[option.option_id]`
so you lean against growing an already-large position, and size quantities based on risk
appetite instead of a constant `10`.

---

## Step 5 — `respond_to_fok(self, option, fok_order)`

**Change this last.** Also needs `price_option` (step 3); reuses the same fair-value logic as
step 4.

**Inputs you're given:** `option: BinaryOption` and `fok_order: FokOrder`, which has
`fok_order.order_type` (`OrderType.BUY` or `OrderType.SELL` — the counterparty's side),
`fok_order.price`, and `fok_order.quantity`.

**What it must return:** `True` to accept the trade at `fok_order.price`, `False` to pass.
No partial accept — and if you accept, you might get less than `fok_order.quantity` if other
market makers accept too.

**Simple example:**
```python
def respond_to_fok(self, option, fok_order):
    fair = self.price_option(option)
    edge = 0.02  # minimum edge required to bother trading, tune this
    if fok_order.order_type == OrderType.BUY:
        # counterparty wants to buy from you -- accept if their price is above your fair value
        return fok_order.price >= fair + edge
    else:
        # counterparty wants to sell to you -- accept if their price is below your fair value
        return fok_order.price <= fair - edge
```
Then improve it: reject trades that would push `self.position` or cash-at-risk past a limit you
set, even if the edge looks good (remember bankruptcy ends the session).

---

## After all five: testing pass

- [ ] Run the VERBOSE tests; confirm no exceptions/bankruptcy.
- [ ] Hand-check `price_option_from_parameters` on a couple of simple constructed options
      (single leg, short horizon, `steps_until_expiry = 0`) before trusting spreads/long
      horizons.
- [ ] Tune `spread`/`edge`/position-sizing constants against the SCORED tests once correctness
      is solid — this is the main lever for PnL after everything above works.
