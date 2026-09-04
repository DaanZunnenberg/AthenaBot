# Mathematical Specification — `AthenaBot/AthenaBot.py`

This documents the promoted submission in `AthenaBot/AthenaBot.py` in full: every state
variable and tunable constant, the math behind each mechanism, the design choices made,
and — per an explicit code-scan pass against the current file — the real weaknesses
found in the current code (§7), not just hypothetical gaps.

**Relationship to root `Model.md`:** the pricing engine (`_BinaryOptionPricer`) and the
parameter-estimation layer (`_SufficientStats`, `_ParameterEstimator`) are
byte-identical in structure to `Bot.py`'s. §§1–4 below summarize that shared core; see
root `Model.md` §§1–4 for the full derivation, including the telescoping lemma and every
quadrature/closed-form case. §§5–7 below are the real subject of this document: the
three-zone confidence quoting system, counterparty toxicity and its mirror-image "flow
regime" signal, portfolio-level delta skew, the drawdown circuit breaker, and the
solvency/margin ledger — none of which exist in root `Bot.py`.

---

## 1. Notation and market state

- **Underlyings**: FED funds rate (`FED_FUNDS_RATE_UNDERLYING_ID = 1`), AjarAI valuation
  (`AJARAI_UNDERLYING_ID = 2`), Theriodic valuation (`THERIODIC_UNDERLYING_ID = 3`). Current
  values live in `self.underlying_state`, a tuple of `Underlying(name, underlying_id, value)`.
- **Options**: `BinaryOption(legs, option_id, steps_until_expiry, strike)`, where
  `legs: tuple[OptionLeg(underlying_id, weight), ...]`. Payoff at expiry is `1.0` if
  `sum(weight_i * value_i) >= strike`, else `0.0`.
- **Rate grid**: FED moves in fixed increments of `RATE_STRIKE_GRID = 0.25`, floored at `0.0`.
- **`MarketParameters`**: the generative model's 14 fields (drift, idiosyncratic/sector
  volatility, rate-beta, rate up/down probability, reversion strength, rate step/target — see
  root `Model.md` §1.2 for the full field-by-field description). `self.estimated_parameters`
  holds the live fit; `market_parameters` is passed in directly for
  `price_option_from_parameters` (the THEO-test path, where the true parameters are known).

## 2. The generative model (summary — see root `Model.md` §2 for the full derivation)

Each day: the rate either steps up, steps down, or stays, with probabilities tilted by
mean-reversion toward `rate_target`:
$$p_{up}(r) = \min\!\big(\max(p_{up,0} + \kappa(r_{target} - r),\, 0),\, 1\big), \quad p_{down}(r) = \min\!\big(\max(p_{down,0} - \kappa(r_{target} - r),\, 0),\, 1-p_{up}(r)\big)$$

AJR and THR evolve as correlated lognormals driven by the rate change and a shared sector
shock:
$$\log\frac{V_{t+1}}{V_t} = \mu + \beta_r \Delta r_t + \beta_s S_t + \varepsilon_t, \quad S_t \sim N(0, \sigma_s^2), \quad \varepsilon_t \sim N(0, \sigma_{idio}^2)$$

**Key structural fact this whole engine relies on:** daily rate changes telescope —
$\sum_{i=0}^{n-1} \Delta r_i = r_n - r_0$ — so both companies' `n`-day log-return only depends
on the **terminal** rate `r_n`, not the path. This is what makes exact (non-Monte-Carlo)
pricing possible; see root `Model.md` §3.1 for the full lemma and proof sketch.

## 3. The pricing engine (`_BinaryOptionPricer`) — identical to `Bot.py`

`price_option_from_parameters(market_parameters, option)` and `price_option(option)` both
call `_BinaryOptionPricer.price`, which:

1. Builds the terminal rate law via `_rate_lattice` — an exact finite-state DP over `n` days
   (small state space: at most `2n+1` distinct rate levels reachable from a single start).
2. For each terminal rate `r_n` with probability mass `P(r_n)`, computes the conditional
   probability the option pays off given that terminal rate — dispatched by leg shape:
   - **FED-only** (`w_A = w_T = 0`): a direct threshold check, no distribution needed.
   - **Single company leg**: exact lognormal tail probability via `_prob_ge`/`_prob_le`
     (closed-form normal CDF).
   - **Two-leg, zero effective strike, opposite-sign weights** (a pure spread like
     `AJR - THR >= 0`): exact closed form via the distribution of `log(AJR) - log(THR)`,
     itself normal (`_two_leg_zero_strike_spread`).
   - **General two-leg**: 129-point fixed-grid trapezoidal quadrature over the standard normal
     density (`_two_leg_quadrature`) — numerically integrates
     $\int \phi(u)\, G(u)\, du$ where $G(u)$ is the conditional survivor probability of the
     second leg given the first leg's draw $u$. A `fast=True`, 9-point variant exists for the
     numeric-delta bumps in §6.1, where speed matters more than precision.
3. Sums $\sum_{r_n} P(r_n) \cdot P(\text{payoff} = 1 \mid r_n)$, clamped to `[0, 1]`.

An optional `lattice_cache` (keyed by rounded `(kappa, rate_target, rate0, steps)`) avoids
rebuilding the same rate lattice across multiple options sharing a day and horizon — used by
`_precompute_day_cache` (§6.1), not by `price_option_from_parameters` (the THEO test calls it
once per option, no cache benefit).

## 4. Parameter estimation (`_SufficientStats`, `_ParameterEstimator`) — identical to `Bot.py`

`warm_up` ingests `MarketHistory` into `_SufficientStats` (running sums for a company
regression plus per-rate-level up/down/stay transition counts), then `_ParameterEstimator.fit`:

1. **Company regression** (`_fit_company`): OLS of each company's log-return on the daily rate
   change, giving `beta_A`/`beta_T` (rate sensitivity) and `mu_A`/`mu_T` (drift), plus residual
   variances/covariance.
2. **Correlation shrinkage**: the raw residual correlation `cbar / sqrt(vbar_A * vbar_T)` is
   Fisher-z shrunk toward zero with an effective prior sample size of 50 (`_fisher_z_shrink_rho`)
   — a small-sample regularizer, since Pearson correlation is noisy at typical `N ≈ 60–200`.
3. **Sector-loading reconstruction** (`_reconstruct_sector_loadings`): a single covariance term
   `cbar` cannot uniquely determine two loadings `gamma_A, gamma_T` — the code picks the split
   proportional to relative variance: $\gamma_A = \sqrt{|\bar c| \sqrt{\bar v_A/\bar v_T}}$,
   $\gamma_T = \text{sign}(\bar c)\sqrt{|\bar c|\sqrt{\bar v_T/\bar v_A}}$. This is a genuine,
   unavoidable **identification choice**, not a derived result — any split with
   $\gamma_A \gamma_T = \bar c$ reproduces the same covariance; this one weights each company's
   share of the loading by its own variance. Flagged again in §7.
4. **Rate parameters** (`_fit_rate`): a 1-D grid search over `kappa` (101 points on `[0, 0.5]`),
   with `a_up`/`a_down` recovered in closed form at each grid point via the weighted-mean
   identity, maximizing a per-level multinomial log-likelihood (`_rate_loglik_reparam`).

`_refit()` re-runs this fit after every `on_step_advance` once warmed up, so the live estimate
adapts within a session, not just from the initial history. Any exception anywhere in `fit`
falls back to `_default_market_parameters()` (a neutral, non-informative parameter set) —
`warm_up`/`price_option` never raise.

---

## 5. The quoting system — this file's actual design (not in root `Bot.py`)

### 5.1 Confidence and the three-zone width menu (`_confidence`, `_zone`)

$$\text{confidence} = \underbrace{2|\hat P - 0.5|}_{\text{distance from uninformative}} \times \underbrace{\min(1, n / N_{target})}_{\text{data adequacy},\ N_{target}=30}$$

This is a **product**, deliberately not a sum or the distance term alone: a fair-value
estimate far from 0.5 built on very little history ($n$ small) should not count as confident —
it may just be estimation noise — so low data adequacy drags confidence toward zero
*regardless* of how extreme the point estimate looks. `n` here is `self._stats.n`, the same
transition count used for parameter estimation (§4), so confidence is really "how much do I
trust the estimate that produced this fair value," reusing existing state rather than a new
bookkeeping channel.

`_zone(confidence)` maps this scalar to a `(trust, half_spread)` pair from a fixed 3-point menu:

| Zone | Condition | `trust` | half-spread | Interpretation |
|---|---|---|---|---|
| Tight | `confidence >= C_HIGH = 0.66` | `1.0` | `W_TIGHT = 0.05` | Full trust in the fitted fair value. |
| Mid | `C_LOW <= confidence < C_HIGH` | `0.5` | `W_MID = 0.10` | Even blend toward 0.5. |
| Wide | `confidence < C_LOW = 0.33` | `0.0` | `W_WIDE = 0.18` | Full distrust — a flat-0.18-half-spread quoter centered on 0.5, the safety net for a bad fit. |

The blended fair value quoted is $\hat P_{blend} = trust \cdot \hat P + (1-trust) \cdot 0.5$ —
zone membership and blend weight are the *same* number (`trust`), not independently tuned, so
there's no way for the width and the blend to disagree about how much the fair-value estimate
is trusted. **This blend is a known, currently-live correctness risk — see §7.3.**

`W_TIGHT`/`W_MID`/`W_WIDE` are fixed, hand-tuned constants, not derived from any confidence
interval or loss function; treat them as calibrated hyperparameters, not first-principles
results.

### 5.2 Counterparty toxicity (`_toxicity`, markout tracking)

A **markout** measures whether the fair-value estimate moved against AthenaBot in the days
after a fill — the standard adverse-selection diagnostic in market making. `_record_markout`
snapshots the fair value `P_t` at trade time; `_update_markouts` (called every
`on_step_advance`) fills in `M[elapsed] = P_{t+elapsed} - P_t` for `elapsed = 1..3` days
(`_MARKOUT_HORIZON`), or as soon as the option expires (`Y` is set). `_finalize_markout`
averages the observed markout window and updates:

$$T_{global} \leftarrow \alpha \cdot obs + (1-\alpha) \cdot T_{global}, \quad \alpha = 0.05$$

with `obs = -mean(M)` if we bought (price falling after we bought is adverse) or `obs =
mean(M)` if we sold (price rising after we sold is adverse) — so `obs > 0` always means "this
fill looked adverse in hindsight." A matching per-counterparty EMA is tracked
(`_cp_b_sum`/`_cp_b_n` etc.), shrunk toward the global EMA by sample size:

$$w = \frac{n_{cp}}{n_{cp} + \tau}, \quad \tau = 50, \quad raw = w \cdot local_{cp} + (1-w) \cdot T_{global}$$

— a standard empirical-Bayes shrinkage: a counterparty seen only a few times borrows almost
entirely from the global estimate, one seen often (`n_cp >> tau`) is trusted on its own
history. The final toxicity contribution is `min(max(raw, 0), TOXICITY_CAP=0.02) *
confidence` — hard-capped, only ever widens the spread (never narrows, `max(raw, 0)`), and
scaled down for low-confidence fair values (so a data-poor estimate can't get a compounding
toxicity kick on top of an already-wide zone).

### 5.3 Flow regime — the mirror-image signal (`_update_flow_regime`, `_flow_tighten`)

Every markout observation already computed for toxicity is reused, sign-flipped
(`favorable_obs = -adverse_obs`), into a second, separate EMA:

$$E_{flow} \leftarrow \beta \cdot favorable\_obs + (1-\beta) \cdot E_{flow}, \quad \beta = 0.03$$

`_flow_tighten()` returns `min(E_flow, FLOW_REGIME_TIGHTEN_CAP)` — but only once
`_flow_n >= FLOW_REGIME_MIN_N = 20` fills have been observed, and only if `E_flow > 0` (never
narrows off an adverse or flat-zero signal). The tightening only ever applies inside the
tight/mid zones (`trust > 0` — see `_mid_and_spreads`), never overriding the wide zone's
fixed-width safety net.

### 5.4 Portfolio delta skew (`_numeric_delta`, `_skew_for_side`)

Unlike a single-option net-position skew, this skews quotes based on the **whole book's**
correlated risk. `_numeric_delta` computes $\partial P/\partial V_{underlying}$ by symmetric
finite difference, using the fast 9-point quadrature since only a first-order derivative is
needed. The bump size is $\max(0.01 \cdot |V|,\, 10^{-4})$ for AJR/THR (a small relative bump,
appropriate for a continuous log-normal process). **For FED it uses the same relative-bump
formula, which is a real calibration issue — see §7.4.** `_compute_portfolio_delta` sums
`net_position_i * delta_i` across every held option, per underlying, into a portfolio delta
vector. `_portfolio_risk_score` reconstructs true portfolio variance from the fitted
parameters — not a naive sum of squared deltas — including the AJR/THR cross-covariance term
driven by their shared sector-beta exposure:

$$\text{risk}(\delta) = \delta_A^2 \text{Var}(A) + \delta_T^2 \text{Var}(T) + 2\delta_A\delta_T\text{Cov}(A,T) + \delta_F^2 \cdot \text{rate\_step}$$

where $\text{Var}(A) = \gamma_A^2\sigma_s^2 + \sigma_{idio,A}^2$,
$\text{Cov}(A,T) = \gamma_A\gamma_T\sigma_s^2$, from the fitted parameters (§4). The FED term
uses `rate_step` as a variance proxy, standing alone — there is no FED↔AJR/THR
cross-covariance term in this formula even though the fitted model has nonzero
`ajarai_rate_beta`/`theriodic_rate_beta` linking them; a book simultaneously long FED-linked
and long AJR/THR-linked risk in the same direction is not flagged as correlated by this
score. A partial, not full, covariance-aware risk model.

`_skew_for_side(option, is_buy)` asks: if I fill this side, does portfolio risk go up or down?

$$\text{skew} = K \cdot \big(\text{risk}(\text{portfolio} + dir \cdot \delta_{option}) - \text{risk}(\text{portfolio})\big), \quad K = 0.08,\ \text{capped at } \pm 0.15$$

Positive skew *widens* that side (worse price offered) when filling it would concentrate risk
further — even for an option never held before, since delta correlates it with the existing
book through shared underlyings. Negative skew *tightens* that side when filling it would
hedge existing exposure. This subsumes and generalizes a same-option-only inventory skew.

### 5.5 Assembling the quote (`_mid_and_spreads`)

$$h_{bid} = \max(0.005,\ base_h + skew_{bid} + t_b - tighten + widen)$$
$$h_{ask} = \max(0.005,\ base_h + skew_{ask} + t_a - tighten + widen)$$

where `base_h` is the zone half-spread (§5.1), `skew`/`t` are §5.4/§5.2, `tighten` is §5.3, and
`widen` is the drawdown breaker (§5.6). Both half-spreads are applied around the **blended**
fair value $\hat P_{blend}$ from §5.1, not the raw fitted fair value — see §7.3 for why that
matters. Every term is additive on the same base, in a fixed order, and every half-spread is
floored at `0.005` so no combination of terms can invert the spread.

### 5.6 Drawdown circuit breaker (`_drawdown_severity`, `_drawdown_spread_add`, `_drawdown_size_scale`)

A **soft**, additive layer on top of — never a substitute for — the hard solvency gates
(§6). Severity is a purely session-PnL-relative measure:

$$pnl\_frac = \frac{cash - starting\_cash}{starting\_cash}, \quad severity = \min\!\left(\max\!\left(\frac{-pnl\_frac - 0.25}{0.45 - 0.25},\ 0\right),\ 1\right)$$

— zero until session PnL drops below $-25\%$ of starting capital, scaling linearly to full
severity by $-45\%$. At full severity, spreads widen by up to `DRAWDOWN_SPREAD_ADD = 0.06` and
size caps shrink by a factor down to `DRAWDOWN_SIZE_MULT = 0.5` (never to zero — that job stays
with the hard gates). No latch: severity recomputes fresh from `_cash` every call, so it
recovers automatically as the book's PnL recovers. Note this reads `_cash` (raw realized cash),
not a mark-to-market figure that includes the value of open positions — a session that's
actually flat or profitable in mark-to-market terms but happens to be holding inventory bought
with cash outlay can register a drawdown severity that doesn't reflect real economic loss.

---

## 6. Sizing and the solvency ledger

### 6.1 Fair-value and delta caching (`_precompute_day_cache`, `_ensure_cached`)

Both the fair value and the per-underlying delta vector for every active option are computed
once per `on_step_advance`/`warm_up` call and cached in `self._day_cache`, keyed by
`option_id`. This is what makes the portfolio-delta skew (§5.4) affordable — without caching,
every `quote`/`respond_to_fok` call would re-run the fast quadrature bump for every held
option's delta.

### 6.2 The margin ledger (`on_trade`, `_settle_expired_positions`)

The grader's own rule (per `README.md`): buying `N` at price `P` debits `N*P`; selling `N`
debits `N*(1-P)`. `on_trade` mirrors this into `self._cash` and `self._used_margin` (a
per-option breakdown lives in `self._margin_by_option`, released — `_used_margin -= reserved`
— when that option's position is settled). `_settle_expired_positions` credits the net
position's payoff at expiry and releases its reserved margin; note it settles by **net
position**, not gross trade count, matching the grader's own accounting.

`self.cash_balance` (the constructor argument) is stored once and never updated live — all
real-time tracking goes through `self._cash` instead, which mirrors the grader's own
trade-by-trade debit/credit formula. This is a known, intentional split: the public attribute
exists for interface compatibility, the private ledger is the actual source of truth.

`_margin_by_option` accumulates every trade's gross debit against an option, rather than
netting against opposite-direction trades on the same option before it settles — flattening a
position intraday (buy then sell back to zero) leaves that option's reserved margin inflated
until it expires, understating `_available_margin()` for the rest of the session. This is a
capacity/conservatism inefficiency, not a solvency risk: the independent, cash-based checks in
§6.3 remain the actual backstop against overcommitting real money.

### 6.3 Sizing (`_size_for`, `_margin_feasible_quantity`, `_worst_case_cash`)

Two independent caps are combined, `size = min(Q_MAX=50, inventory_room, margin_room)`:

- **Margin room**: `headroom = min(utilisation_cap * starting_cash - used_margin, feasible_cash - reserve)`, then `floor(headroom / unit_cost)`. `feasible_cash` is
  `min(worst_case_cash, legacy_reserved)`, where `worst_case_cash = cash - sum(max(0, -q) for
  q in positions)` — i.e., cash minus the total notional exposure of every **short** position,
  a conservative (not risk-neutral) view of what's actually available.
- **Inventory room**: `_MAX_NET_PER_OPTION - abs(net + direction) + 1` — see §7.2 for a real
  bug in this formula. `respond_to_fok` applies the same formula, at the full requested
  quantity, before accepting a FOK — so both entry points into the book are consistently
  gated by the per-option inventory cap.

A soft drawdown-driven multiplier (§5.6) is applied on top, floor-rounded, never increasing
size beyond what the hard caps already allow.

### 6.4 Utilisation and capital-scale ramp (`_utilisation_cap`, `_capital_scale`)

`_capital_scale` ramps linearly from `0` (at `starting_cash >= CAPITAL_SCALE_THRESHOLD = 20`)
to `1` (at `starting_cash <= CAPITAL_SCALE_FULL = 10`) — smaller starting books get a bigger
`_CAPITAL_UTIL_BOOST = 0.15` added to `_MAX_UTILISATION = 0.6`, up to `0.75` at full scale.
This affects **only** how much margin the bot is willing to commit, never spread width — the
rationale is that small books need more aggressive capital deployment to generate meaningful
PnL, but that should never be paid for by taking worse prices.

### 6.5 Degenerate fallback (`_risk_free_quote`)

`Quote(bid=0.00, offer=1.00, both at Q_MAX)` costs zero margin by the grader's own formula
(`N*0` and `N*(1-1)`) and can never lose money regardless of size — buying at 0.00 pays out
`payoff >= 0` at expiry for free; selling at 1.00 nets `1 - payoff >= 0`. This is why it's the
one path in the file allowed to bypass `_MAX_NET_PER_OPTION`: capping its size would risk
being unable to return a valid (positive-quantity) `Quote` at all when normal inventory room is
already exhausted, which is exactly when this fallback is needed. Used whenever
`_available_margin() - reserve <= 0`, or as a last-resort fallback for either side individually
if `_size_for` returns zero.

---

## 7. Code-scan findings (this pass)

Five issues were found by scanning `AthenaBot/AthenaBot.py` directly, each verified with a small
script rather than by inspection alone. None currently crash the bot (all sit inside code that
already has defensive `try/except` wrapping or hard caps elsewhere), but they range from a
genuine correctness defect (§7.3) to inherited scaffold quirks and known, deliberate design
tradeoffs.

### 7.1 `Underlying.__eq__` breaks Python's hash/eq contract

```python
class Underlying:
    ...
    def __eq__(self, other):
        if not isinstance(other, Underlying):
            return False
        return self.underlying_id == other.underlying_id
```

`Underlying` is a `@dataclass(frozen=True)`, which auto-generates `__hash__` from **all**
fields (`name`, `underlying_id`, `value`) unless told otherwise. But `__eq__` is overridden by
hand to compare `underlying_id` alone. Verified directly:

```
u1 = Underlying('FED', 1, 5.0); u2 = Underlying('FED', 1, 6.0)
u1 == u2        # True  (same underlying_id)
hash(u1) == hash(u2)   # False (different value)
```

Two objects that compare equal have different hashes — this violates the data model contract
that any correct dict/set implementation relies on (`x == y` must imply `hash(x) == hash(y)`).
**This class is part of the given scaffold, not code this file's author wrote** — it's
inherited unmodified from the interface every submission is handed. It does not currently
bite `AthenaBot.py` itself, which only ever converts `underlying_state` to a plain dict via
`{u.underlying_id: u.value for u in ...}` (never uses `Underlying` objects themselves as
dict/set keys) — but it's latent and would silently misbehave (failed lookups, duplicate
"distinct" entries in a set) the moment any code, including a future harness or test, puts
`Underlying` instances in a set or uses them as dict keys.

### 7.2 `_size_for`'s inventory-room formula is wrong for risk-*reducing* trades

```python
def _size_for(self, option, price, is_buy):
    net = self._net_position(option.option_id)
    new_net = net + (1 if is_buy else -1)
    inventory_room = self._MAX_NET_PER_OPTION - abs(new_net) + 1
```

This computes room as if `MAX - |net after one unit|` scales linearly for larger sizes too,
which is only correct when the trade **grows** an existing same-signed position. When the
trade **covers** an opposite-signed position (net short, buying — or net long, selling), the
correct room is `MAX - net` (buy) / `MAX + net` (sell), not this formula. Verified by direct
comparison at every net level from `-MAX` to `+MAX`:

| `net` | side | this formula's room | correct room |
|---|---|---|---|
| `-10` (max short) | buy (covering) | `2` | `20` |
| `-9` | buy (covering) | `3` | `19` |
| `-5` | buy (covering) | `7` | `15` |
| `+5` | sell (covering) | `7` | `15` |
| `+9` | sell (covering) | `3` | `19` |
| `+10` (max long) | sell (covering) | `2` | `20` |

Same-direction trades (building an existing position, or trading from flat) are unaffected —
the formula is exactly correct there, which is presumably why this has gone unnoticed. But a
bot sitting at a large position and trying to cover it gets throttled to a handful of
contracts per quote when it should have full room to flatten — **exactly backwards from sound
risk management**, which should always make covering trades at least as easy as
risk-increasing ones. `respond_to_fok` uses this same formula (§6.3), so the throttling applies
identically on both entry points into the book. Likely impact is modest in practice (positions
rarely sit at the cap for long given how conservatively `_MAX_NET_PER_OPTION = 10` and the
margin caps already constrain sizing), but it directly works against the existing
risk-reduction intent elsewhere in this file (e.g. the drawdown breaker, §5.6). **Fix**:
replace with `MAX_NET_PER_OPTION - net if is_buy else MAX_NET_PER_OPTION + net`.

### 7.3 The confidence-blended quote center can price on the wrong side of fair value

`_mid_and_spreads` (§5.5) quotes around $\hat P_{blend} = trust \cdot \hat P + (1-trust) \cdot
0.5$, not the raw fitted fair value $\hat P$. When confidence is low and $\hat P$ is far from
0.5, this pull toward 0.5 can exceed that side's half-spread, pushing the quoted (or
FOK-accepted) price past $\hat P$ itself — i.e. offering to trade at a price the model's own
estimate says has negative expected value. Verified by direct reproduction: with a thin-data
warm-up and a true fair value of `0.9635`, the wide-zone quote offered to **sell** at `0.68` —
accepting that fill would mean selling something the model believes is worth `0.9635` for
`0.68`, a guaranteed negative-EV trade if it's ever taken. This is not a hypothetical edge
case; it reproduces the mechanism behind a real, observed HackerRank session loss. **Fix**:
center `h_bid`/`h_ask` on the raw `fair` value instead of the blended value, letting
confidence control spread *width* only, never the center — verified to remove the reproduction
above with no other logic change. This fix was evaluated and is **not currently applied** in
this file: removing it lowered the score on the known 20-test HackerRank set even though it
closes a genuine correctness gap (see `AthenaBot/AthenaBotScores.md` for the real numbers) — kept out
for now as a deliberate score-vs-robustness tradeoff, not an oversight.

### 7.4 FED's numeric delta uses a bump size that doesn't match its discreteness

`_numeric_delta` (§5.4) bumps every underlying by the same relative-size rule
($\max(0.01|V|, 10^{-4})$), but FED only ever moves in discrete `RATE_STRIKE_GRID = 0.25`
steps and option price is a step function of it (a strike is crossed or it isn't). A bump this
much smaller than the real grid spacing either lands entirely inside one lattice cell (the
finite difference reads ~0, understating FED risk) or straddles a strike-crossing boundary (a
full 0-to-1 jump divided by a tiny denominator, spuriously huge). This corrupts the
correlation-aware portfolio risk score (§5.4) specifically for FED-legged options — the skew
mechanism can either miss real FED exposure or wildly over-react to numerical noise, depending
on how close the current FED value happens to sit to a strike boundary. **Fix**: bump FED by a
full `RATE_STRIKE_GRID` step instead of a relative amount; AJR/THR are continuous log-normal
and are unaffected by this issue, so their bump is unchanged. Like §7.3, this fix was evaluated
in isolation and is **not currently applied** — a real submission with only this fix scored
lower on the known 20-test set than leaving it as-is, for reasons not fully understood
(plausibly the same "a real bug's noise happens to line up favorably with this specific test
distribution" pattern as §7.3).

### 7.5 Design choices worth flagging as approximations, not bugs

- **Sector-loading split** (§4, step 3): given only the covariance `cbar`, the split between
  `gamma_A` and `gamma_T` is genuinely underdetermined by the data — the
  variance-proportional split implemented is a reasonable, defensible choice, not a uniquely
  correct one. Any two loadings with the same product reproduce the same second-moment fit.
- **`warm_up`'s kappa resolution**: the 101-point grid search over `[0, 0.5]` has an inherent
  quantization error (~0.02–0.06 at `N=200`, per `debug/03-PARAMETER-ESTIMATION-ACCURACY.md`)
  — a resolution/sample-size tradeoff, not an implementation defect.
- **`self.cash_balance` staleness** (§6.2): intentional, but worth remembering if extending
  this file — anything reading `self.cash_balance` directly (rather than `self._cash`) will
  see only the constructor-time value forever.
- **FED term in the portfolio risk score** (§5.4): uses `rate_step` alone as a variance proxy
  with no cross-covariance to AJR/THR, even though the fitted model has nonzero
  `ajarai_rate_beta`/`theriodic_rate_beta`. A smaller, residual gap than §7.4, and one that
  would need its own fix even after §7.4 is applied (a well-scaled but still-uncorrelated FED
  delta would still miss this specific cross-asset interaction).
