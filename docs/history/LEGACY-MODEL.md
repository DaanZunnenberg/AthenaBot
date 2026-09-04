# Mathematical Specification — `Bot.py`

This document derives every piece of mathematics implemented in the current `Bot.py`: the
generative market model supplied by the harness, the exact pricing engine
(`_BinaryOptionPricer`, shared by both `price_option_from_parameters` and `price_option`), the
estimation layer (`_SufficientStats` / `_ParameterEstimator`, driven by `warm_up` and
`on_step_advance`), and the market-making layer (`quote`, `respond_to_fok`, and the risk
ledger `_cash` / `_used_margin` / `_legacy_reserved`).

Every symbol used anywhere below appears in the notation table in §1. Nothing is assumed known.

---

## 1. Notation

### 1.1 Market state

| Symbol | Code | Meaning |
|---|---|---|
| $t$ | — | Day index, $t = 0, 1, 2, \dots$ (one simulation step = one day) |
| $r_t$ | `values[FED_FUNDS_RATE_UNDERLYING_ID]` | Fed funds rate level on day $t$ |
| $A_t$ | `values[AJARAI_UNDERLYING_ID]` | AjarAI valuation on day $t$ (strictly positive) |
| $T_t$ | `values[THERIODIC_UNDERLYING_ID]` | Theriodic valuation on day $t$ (strictly positive) |
| $\Delta_t$ | `rate_change` | Realised daily rate change, $\Delta_t := r_t - r_{t-1}$ |
| $s_t$ | `sector_shock` | Shared daily sector shock, $s_t \sim \mathcal N(0, \sigma_s^2)$ i.i.d. |
| $\varepsilon^A_t,\ \varepsilon^T_t$ | `idiosyncratic_shock` | Idiosyncratic daily shocks, $\mathcal N(0,\sigma_A^2)$ and $\mathcal N(0,\sigma_T^2)$, mutually independent and independent of $s_t$ |
| $\mathcal F_t$ | — | Information available at the close of day $t$ |

### 1.2 Generative parameters (`MarketParameters`)

| Symbol | Field | Meaning |
|---|---|---|
| $\mu_A,\ \mu_T$ | `ajarai_drift`, `theriodic_drift` | Constant daily log-return drift per company |
| $\beta_A,\ \beta_T$ | `ajarai_rate_beta`, `theriodic_rate_beta` | Sensitivity of daily log return to $\Delta_t$ |
| $\gamma_A,\ \gamma_T$ | `ajarai_sector_beta`, `theriodic_sector_beta` | Loading on the shared sector shock |
| $\sigma_A,\ \sigma_T$ | `ajarai_idio_std_dev`, `theriodic_idio_std_dev` | Idiosyncratic daily volatilities |
| $\sigma_s$ | `sector_std_dev` | Volatility of the shared sector shock |
| $p^{\uparrow},\ p^{\downarrow}$ | `rate_up_probability`, `rate_down_probability` | Untilted base probabilities of a one-step rate move up / down |
| $\kappa$ | `rate_reversion_strength` | Mean-reversion tilt strength, $\kappa \in [0,1]$ |
| $\bar r$ | `rate_target` | Mean-reversion target level |
| $\delta$ | `rate_step` | Rate grid spacing (`RATE_STRIKE_GRID` $= 0.25$) |

### 1.3 Contract description (`BinaryOption`)

| Symbol | Code | Meaning |
|---|---|---|
| $n$ | `steps_until_expiry` | Days remaining until settlement |
| $K$ | `strike` | Threshold the observable must reach |
| $w_F, w_A, w_T$ | `_leg_weights` | Leg weights on FED, AJR, THR respectively; $0$ if that leg is absent |
| $X_n$ | `observable_value` | Terminal observable, $X_n := w_F r_n + w_A A_n + w_T T_n$ |
| $\Pi$ | `expiry_valuation` | Settlement payoff, $\Pi = \mathbb 1\{X_n \ge K\}$ |

### 1.4 Derived pricing quantities (`_BinaryOptionPricer`)

| Symbol | Code | Meaning |
|---|---|---|
| $\tilde p^{\uparrow}(r),\ \tilde p^{\downarrow}(r)$ | `tilted_rate_probabilities` | Level-dependent tilted transition probabilities |
| $\pi_n(\rho)$ | `_rate_lattice` | $\mathbb P(r_n = \rho \mid \mathcal F_0)$, the terminal rate law |
| $m_A(\rho),\ m_T(\rho)$ | `mean_a`, `mean_t` | Conditional mean of $\log A_n$, $\log T_n$ given $r_n = \rho$ |
| $v_A,\ v_T,\ c$ | `var_a`, `var_t`, `cov` | Conditional variances and covariance of $(\log A_n, \log T_n)$ |
| $\varsigma_A,\ \varsigma_T$ | `sd_a`, `sd_t` | $\sqrt{v_A},\ \sqrt{v_T}$ |
| $\rho_{AT}$ | `rho` | Log-space correlation, $c/(\varsigma_A\varsigma_T)$ |
| $k(\rho)$ | `k_eff` | Effective strike after folding in the FED leg |
| $\Phi,\ \phi$ | `_norm_cdf`, `_phi` | Standard normal CDF and PDF |
| $P_j$ | `_get_cached_fair` | Model fair value of option $j$, $P_j \in [0,1]$ (from whichever `MarketParameters` the caller supplies — true or estimated; see §3) |

### 1.5 Estimation (`_SufficientStats` / `_ParameterEstimator`)

| Symbol | Code | Meaning |
|---|---|---|
| $N$ | `stats.n` | Count of admissible transitions accumulated (both company values strictly positive on both endpoints) |
| $d_t$ | `d` | Realised rate change of a single accumulated transition, $d_t = r_t - r_{t-1}$ |
| $\ell^A_t,\ \ell^T_t$ | `log_ajr`, `log_thr` | Log returns of a single transition, $\ell^i_t = \log(V^i_t/V^i_{t-1})$ |
| $\hat\beta_A,\ \hat\beta_T$ | `beta_A`, `beta_T` | OLS slope of $\ell^i$ on $d$ |
| $\hat\mu_A,\ \hat\mu_T$ | `mu_A`, `mu_T` | OLS intercept of $\ell^i$ on $d$ |
| $\bar v_A,\ \bar v_T$ | `vbar_A`, `vbar_T` | Residual variance of $\ell^i$ about the fitted line, before/after shrinkage (context-dependent, see §4.3) |
| $\bar c$ | `cbar` | Residual cross-moment of $(\ell^A, \ell^T)$ about their fitted lines, before/after shrinkage |
| $\hat\rho_{\text{raw}}$ | `rho_raw` | Raw (unshrunk) residual correlation, $\bar c/\sqrt{\bar v_A\bar v_T}$ |
| $\hat\rho$ | `rho_shrunk` | Fisher-$z$-shrunk residual correlation |
| $\bar v_{\text{pool}}$ | `v_pool` | Pooled variance, $(\bar v_A+\bar v_T)/2$, used to shrink $\bar v_A,\bar v_T$ toward each other |
| $\hat a^{\uparrow}, \hat a^{\downarrow}$ | `a_up`, `a_down` | Estimated rate-model intercepts at $\bar r = 0$ (see §4.5) |
| $\hat\kappa$ | `kappa` | Estimated mean-reversion strength, grid-searched |
| $g_t$ | `grid_steps` | Rate move classified onto the grid, $g_t = \operatorname{round}(d_t/\delta)$ |
| $(n_t^{\uparrow}, n_t^{\downarrow}, n_t^{0})$ | `rate_level_counts[level]` | Up/down/stay move counts observed from a given previous rate level |

### 1.6 Market making and risk ledger (`MarketMaker`)

| Symbol | Code | Meaning |
|---|---|---|
| $q_j$ | `_net_position(j)` | Signed net inventory in option $j$ |
| $\lambda_C$ | `_capital_scale` | Capital-aggression scale, $\lambda_C \in [0,1]$; see §5.6 |
| $h$ | `_current_h_base` | Bandit-adjusted, capital-scaled base half-spread |
| $h_{\text{adj}}$ | `_h_base_adj` | Bandit's additive state, random-walked once per day |
| $T_b,\ T_a$ | `_T_b_global`, `_T_a_global` | Global adverse-selection toxicity (EWMA), our bid/ask side |
| $T_{b,k},\ T_{a,k}$ | `_toxicity(k)` | Per-counterparty $k$ toxicity, shrunk toward the global estimate |
| $\tau$ | `_TAU` | Shrinkage constant, $w_k = N_k/(N_k+\tau)$ |
| $M_h$ | `entry['M'][h]` | Markout at horizon $h\in\{1,2,3\}$ days, $M_h = P_{j,t+h} - P_{j,t}$ using the day-cached fair value |
| $C$ | `_cash` | Literal running cash ledger: debited by price paid on a buy, credited by price received on a sell, credited by settlement payoff |
| $L$ | `_legacy_reserved` | Non-netting reserve ledger: debited by the max-loss amount on every trade, credited only by the realised settlement outcome |
| $W$ | `_worst_case_cash` | $W = C - (\text{sum of outstanding short quantities})$ |
| $F$ | `_feasible_cash` | $F = \min(W, L)$ |
| $M$ | `_used_margin` | Cumulative per-trade max-loss debit, released in full (not payoff-adjusted) at settlement |
| $\text{Av}$ | `_available_margin` | $\text{Av} = \min(C_0 - M,\ F)$ |
| $C_0$ | `_starting_cash` | Session starting cash |
| $\mathcal R$ | `_reserve` | Reserve floor, $\mathcal R = 0.05\,C_0$ |
| $u$ | `_utilisation_cap` | Per-option-type utilisation cap on margin, as a fraction of $C_0$ |
| $Q_{\max}$ | `_Q_MAX` | Absolute per-quote size ceiling ($50$) |
| $N_{\max}$ | `_MAX_NET_PER_OPTION` | Cap on $\lvert q_j\rvert$ after a prospective trade ($10$) |

---

## 2. The generative model

### 2.1 Rate dynamics

The rate lives on the lattice $\delta\mathbb Z_{\ge 0}$. Transition probabilities are tilted
toward the target $\bar r$:

$$
\tilde p^{\uparrow}(r) = \min\Big(\max\big(p^{\uparrow} + \kappa(\bar r - r),\,0\big),\,1\Big)
$$

$$
\tilde p^{\downarrow}(r) = \min\Big(\max\big(p^{\downarrow} - \kappa(\bar r - r),\,0\big),\,1 - \tilde p^{\uparrow}(r)\Big)
$$

The tilt $\kappa(\bar r - r)$ is positive below target (pushing up) and negative above
(pushing down); the clamps guarantee $\tilde p^{\uparrow} + \tilde p^{\downarrow} \le 1$, with
the residual mass $\tilde p^{0}(r) = 1 - \tilde p^{\uparrow}(r) - \tilde p^{\downarrow}(r)$
assigned to "no change". The transition itself is

$$
r_{t+1} = \max\big(r_t + \delta\,\xi_{t+1},\ 0\big), \qquad
\xi_{t+1} \in \{+1, 0, -1\}
$$

with $\xi_{t+1}$ drawn according to $(\tilde p^{\uparrow}, \tilde p^{0}, \tilde p^{\downarrow})$
evaluated at $r_t$. The floor at $0$ merges a down-move at the boundary into the stay-mass;
note that in that case the *realised* change is $\Delta_{t+1} = 0$, not $-\delta$. This matters
in §3.1.

### 2.2 Company dynamics

For $i \in \{A, T\}$:

$$
\log V^i_{t+1} \;=\; \log V^i_t \;+\; \underbrace{\mu_i}_{\text{drift}} \;+\; \underbrace{\beta_i \Delta_{t+1}}_{\text{rate}} \;+\; \underbrace{\gamma_i s_{t+1}}_{\text{sector}} \;+\; \underbrace{\varepsilon^i_{t+1}}_{\text{idio}}
$$

where $V^A \equiv A$ and $V^T \equiv T$. The single shared draw $s_{t+1}$ is the only source of
contemporaneous correlation between the two companies beyond their common exposure to
$\Delta_{t+1}$.

> **Implementation note.** `advance_company_value` applies `round(·, 2)` to the resulting level
> each day. The pricing engine (§3) and estimator (§4) both treat the underlying as continuous
> and do not model this rounding.

### 2.3 Contract payoff

An option pays

$$
\Pi = \mathbb 1\{X_n \ge K\}, \qquad X_n = w_F r_n + w_A A_n + w_T T_n .
$$

There is no discounting and no risk-neutral change of measure in this environment, so the fair
value is simply the physical probability

$$
\boxed{\;P^\star = \mathbb P\big(X_n \ge K \mid \mathcal F_0\big)\;}
$$

Everything in §3 is a calculation of this one object.

---

## 3. The pricing engine (`_BinaryOptionPricer`, shared by `price_option_from_parameters` and `price_option`)

Both grader-facing pricing methods reduce to the same call: `price_option_from_parameters`
passes the grader's true `MarketParameters`, and `price_option` passes
`self.estimated_parameters` (falling back to $P=0.5$ if `warm_up` hasn't run or estimation
failed). There is no separate approximate pricer — a single exact engine is used everywhere.

### 3.1 The telescoping lemma

**Lemma.** The cumulative rate contribution to a company's terminal log value depends on the
rate path only through its *endpoint*:

$$
\sum_{t=1}^{n} \Delta_t \;=\; \sum_{t=1}^{n}(r_t - r_{t-1}) \;=\; r_n - r_0 .
$$

*Proof.* Immediate telescoping. The only thing that could break it is if the code's per-day
`rate_change` were something other than the realised difference $r_t - r_{t-1}$ — for instance
$-\delta$ recorded on a down-move that was clipped at the zero floor. It is not: `advance_step`
computes `rate_change = round(rate_value - current_rate_value, 2)` *after* the floor is
applied. The rounding to two decimals is exact because rates live on the $\delta = 0.25$ grid.
$\square$

Summing the per-day recursion of §2.2:

$$
\log A_n = \log A_0 + n\mu_A + \beta_A (r_n - r_0) + \gamma_A S_n + E^A_n,
\qquad S_n := \sum_{t=1}^n s_t,\quad E^A_n := \sum_{t=1}^n \varepsilon^A_t
$$

and symmetrically for $T$.

### 3.2 Conditional distribution given the terminal rate

The shocks $(S_n, E^A_n, E^T_n)$ are constructed from draws that are independent of the entire
rate path. Hence conditioning on $r_n = \rho$ leaves their joint law unchanged, and

$$
\begin{pmatrix}\log A_n \\ \log T_n\end{pmatrix}
\;\Big|\; \{r_n = \rho\}
\;\sim\;
\mathcal N\!\left(
\begin{pmatrix} m_A(\rho) \\ m_T(\rho)\end{pmatrix},
\begin{pmatrix} v_A & c \\ c & v_T \end{pmatrix}
\right)
$$

with

$$
m_A(\rho) = \log A_0 + n\mu_A + \beta_A(\rho - r_0), \qquad
m_T(\rho) = \log T_0 + n\mu_T + \beta_T(\rho - r_0)
$$

$$
v_A = n\big(\gamma_A^2\sigma_s^2 + \sigma_A^2\big), \qquad
v_T = n\big(\gamma_T^2\sigma_s^2 + \sigma_T^2\big), \qquad
c = n\,\gamma_A\gamma_T\sigma_s^2 .
$$

Note that $v_A, v_T, c$ are **free of $\rho$** — the rate enters only the means. This is what
makes the mixture in §3.4 cheap: `_company_moments` is computed once per option, not once per
lattice node. This is the central structural fact; it replaces Monte Carlo with an exact
one-dimensional mixture, and it is *why* the engine is deterministic and reproducible across
calls.

### 3.3 The terminal rate law (`_rate_lattice`)

Let $\pi_k(\cdot)$ denote the law of $r_k$. Then $\pi_0 = \delta_{r_0}$ and

$$
\pi_{k+1}(\rho') = \sum_{\rho}\pi_k(\rho)\Big[
\tilde p^{\uparrow}(\rho)\,\mathbb 1\{\rho' = u(\rho)\} +
\tilde p^{\downarrow}(\rho)\,\mathbb 1\{\rho' = d(\rho)\} +
\tilde p^{0}(\rho)\,\mathbb 1\{\rho' = \rho\}
\Big]
$$

where $u(\rho) = \max(\rho + \delta, 0)$ and $d(\rho) = \max(\rho - \delta, 0)$.

Two points of care, both handled correctly in code:

1. $\tilde p^{\uparrow}, \tilde p^{\downarrow}$ are recomputed at **every visited level on
   every step** — the tilt is level-dependent, so freezing them at $r_0$ would be wrong.
2. At the boundary $\rho = 0$, $d(0) = 0$, so down-mass is automatically merged into
   stay-mass by dictionary accumulation.

The support size grows at most linearly: $|\operatorname{supp}\pi_n| \le n+1$, so the DP is
$O(n^2)$ in the worst case.

`price` accepts optional `fast`/`lattice_cache` arguments (a 9-node coarse quadrature and a
memoised rate lattice keyed on `(kappa, rate_target, r_0, steps)`), but neither
`price_option_from_parameters` nor `price_option` currently passes them — both call sites use
the defaults (`fast=False`, `lattice_cache=None`), so every live call runs the full 129-node
quadrature and rebuilds the lattice from scratch.

### 3.4 The mixture

Fold the FED leg into an effective strike — once $r_n = \rho$ is fixed, $w_F\rho$ is a known
constant:

$$
k(\rho) := K - w_F \rho .
$$

Then by the tower property,

$$
\boxed{\;
P^\star = \sum_{\rho \in \operatorname{supp}\pi_n} \pi_n(\rho)\; q(\rho),
\qquad
q(\rho) := \mathbb P\big(w_A A_n + w_T T_n \ge k(\rho) \,\big|\, r_n = \rho\big)
\;}
$$

The remainder of §3 computes $q(\rho)$. Four cases are dispatched by `_two_leg_prob` /
`_conditional_probability`.

### 3.5 Case 0: FED-only contract ($w_A = w_T = 0$)

$$
q(\rho) = \mathbb 1\{w_F \rho \ge K\}
$$

and the mixture reduces to summing lattice mass over in-the-money terminal rates.

### 3.6 Case 1: single company leg

Suppose only one company leg is present, say weight $w$ on a variable $V$ with
$\log V \sim \mathcal N(m, \varsigma^2)$, and effective strike $k$. Dividing by $w$ isolates $V$
but **flips the inequality when $w < 0$**:

$$
q =
\begin{cases}
\mathbb P\!\left(V \ge k/w\right), & w > 0\\[4pt]
\mathbb P\!\left(V \le k/w\right), & w < 0
\end{cases}
$$

For a lognormal with $\varsigma > 0$:

$$
\mathbb P(V \ge \theta) =
\begin{cases}
1, & \theta \le 0 \quad(\text{since } V > 0 \text{ a.s.})\\[4pt]
\Phi\!\left(\dfrac{m - \log\theta}{\varsigma}\right), & \theta > 0
\end{cases}
\qquad
\mathbb P(V \le \theta) =
\begin{cases}
0, & \theta \le 0\\[4pt]
\Phi\!\left(\dfrac{\log\theta - m}{\varsigma}\right), & \theta > 0
\end{cases}
$$

**Degenerate variance.** If $\varsigma < \epsilon_{\min} = 10^{-12}$ the variable is effectively
the constant $e^{m}$ and the probability collapses to the indicator $\mathbb 1\{e^m \ge \theta\}$
(resp. $\le$).

If one of the two company legs is degenerate but the other is not, the degenerate leg is folded
into the strike as a constant, $k \mapsto k - w_{\text{deg}}e^{m_{\text{deg}}}$, reducing to
this case.

### 3.7 Case 2: zero-strike opposite-sign spread — exact

If $k(\rho) = 0$ and $w_A w_T < 0$, the event is scale-invariant and reduces to a single
Gaussian threshold on the log-difference. Take $w_A > 0 > w_T$:

$$
w_A A_n + w_T T_n \ge 0
\iff \frac{A_n}{T_n} \ge \frac{-w_T}{w_A}
\iff D \ge \theta,\quad D := \log A_n - \log T_n,\ \ \theta := \log\frac{-w_T}{w_A}
$$

Since $D \mid \{r_n = \rho\} \sim \mathcal N\!\big(m_A(\rho) - m_T(\rho),\, v_A + v_T - 2c\big)$,

$$
q(\rho) = \Phi\!\left(\frac{m_A(\rho) - m_T(\rho) - \theta}{\sqrt{v_A + v_T - 2c}}\right).
$$

The mirror case $w_T > 0 > w_A$ swaps the roles. The sector shock does **not** cancel from $D$
in general (its contribution to $\operatorname{Var}(D)$ is $n\sigma_s^2(\gamma_A-\gamma_T)^2$),
so using $v_A + v_T - 2c$ rather than $v_A + v_T$ is essential. This branch gives named
zero-strike spread contracts (e.g. `AJR - THR >= 0`) a closed form with no quadrature error.

### 3.8 Case 3: general two-leg — conditional quadrature

In the general case write $\log A_n = m_A + \varsigma_A U$ with $U \sim \mathcal N(0,1)$. By the
bivariate normal conditioning formula,

$$
\log T_n \,\big|\, U = u \;\sim\; \mathcal N\!\Big(m_T + \rho_{AT}\varsigma_T u,\ \ \varsigma_T^2(1 - \rho_{AT}^2)\Big),
\qquad \rho_{AT} = \frac{c}{\varsigma_A\varsigma_T}.
$$

Conditioning on $U = u$ makes the $A$ leg a known constant, so the inner probability is a
*single-leg* problem of the form §3.6:

$$
g(u) := \mathbb P\Big(w_T T_n \ge k - w_A e^{m_A + \varsigma_A u} \,\Big|\, U = u\Big)
$$

and

$$
q = \int_{-\infty}^{\infty} \phi(u)\, g(u)\, \mathrm du .
$$

**Quadrature.** The integral is evaluated by the trapezoidal rule on a fixed grid
$u_i = -8 + ih$, $h = 0.125$, $i = 0,\dots,128$ (the live path; the coarse 9-node variant of
§3.3 is unused):

$$
q \approx \sum_{i=0}^{128} \omega_i\, \phi(u_i)\, g(u_i),
\qquad \omega_i = \begin{cases} h/2, & i \in \{0,128\}\\ h, & \text{otherwise}\end{cases}
$$

$\rho_{AT}$ is clamped to $[-0.999, 0.999]$ so the conditional variance stays strictly
positive, and the result is clipped to $[0,1]$ to absorb floating-point drift. Fixed nodes, no
sampling — repeated calls with identical inputs return bit-identical floats.

### 3.9 Terminal / boundary case

`price` treats `steps_until_expiry <= 0` specially:

$$
n' = \begin{cases} 1, & n = 0 \\ n, & n > 0 \end{cases}
$$

Since `BinaryOption.__post_init__` already rejects `steps_until_expiry < 0`, and
`SETTLEMENT_AFTER_ADVANCE` is a hard-coded `True` constant, the `n=0` case always takes one
more step of diffusion ($n'=1$) rather than being priced as a deterministic indicator on
today's values; the indicator branch (`option.expiry_valuation(values)`, for `n < 0`) is
therefore unreachable in practice. This is a settled convention, not an open question.

---

## 4. Estimation (`warm_up`, `on_step_advance` → `_SufficientStats` / `_ParameterEstimator`)

### 4.1 Sufficient statistics (`_SufficientStats.add_transition`)

Every observed one-day transition $(r_{t-1},A_{t-1},T_{t-1}) \to (r_t,A_t,T_t)$ — whether from
the `warm_up` burn-in history (`_ingest_history`) or from a live step during the session
(`_ingest_live_transition`, called once per day after `warm_up` has run) — is folded into a
fixed-size sufficient-statistics accumulator, never storing raw history:

$$
N,\quad \textstyle\sum d_t,\ \sum d_t^2,\quad \sum \ell^A_t,\ \sum(\ell^A_t)^2,\ \sum d_t\ell^A_t,
\quad \sum \ell^T_t,\ \sum(\ell^T_t)^2,\ \sum d_t\ell^T_t,\quad \sum \ell^A_t\ell^T_t
$$

A transition only contributes to these sums if both company values are strictly positive on
both endpoints (needed for $\log$); `_ingest_history` additionally skips any day where either
rate endpoint is negative. There is no separate minimum-sample admissibility gate — each
downstream fit (§4.2, §4.5) handles small $N$ on its own via a degenerate/default branch.

Independently, every transition's rate move is also classified onto the grid,
$g_t = \operatorname{round}(d_t/\delta)$, and tallied into `rate_level_counts[prev_rate]` as
$(n^{\uparrow}, n^{\downarrow}, n^{0})$ according to $\operatorname{sign}(g_t)$ — keyed on the
exact previous rate level, not a coarser bucket.

### 4.2 Company regression (`_fit_company`)

For $i \in \{A,T\}$, OLS-regress $\ell^i_t$ on $d_t$ using the accumulated sums (sample means
denoted with a bar):

$$
\hat\beta_i = \frac{S_{d\ell^i}}{S_{dd}}, \qquad \hat\mu_i = \bar\ell^i - \hat\beta_i\bar d,
\qquad S_{dd} := \textstyle\sum d_t^2 - N\bar d^2,\ \ S_{d\ell^i} := \sum d_t\ell^i_t - N\bar d\,\bar\ell^i
$$

If $N < 3$ or $S_{dd} < 10^{-12}$ (degenerate: no rate variation to regress against), fall back
to $\hat\beta_i = 0,\ \hat\mu_i = \bar\ell^i$ (or all-zero if $N<3$).

Residual variance and cross-moment, with $\operatorname{dof} = \max(N-2,1)$:

$$
\bar v_i = \frac{S_{\ell^i\ell^i} - \hat\beta_i S_{d\ell^i}}{\operatorname{dof}},
\qquad
\bar c = \frac{S_{\ell^A\ell^T} - \hat\beta_A S_{d\ell^T}}{\operatorname{dof}}
$$

both clipped at $0$ from below (`vbar_i`), using the standard OLS identity that the residual
cross-sum $\sum e^A_t e^T_t$ equals $S_{\ell^A\ell^T} - \hat\beta_A S_{d\ell^T}$ (since OLS
residuals are orthogonal to both the regressor and the constant).

### 4.3 Correlation and variance shrinkage (`fit`)

Only when the company fit is non-degenerate ($S_{dd}\ge10^{-9}$, $\bar v_A,\bar v_T>0$):

$$
\hat\rho_{\text{raw}} = \frac{\bar c}{\sqrt{\bar v_A \bar v_T}},
\qquad
\hat z = \operatorname{atanh}\!\big(\operatorname{clip}(\hat\rho_{\text{raw}},-0.999,0.999)\big),
\qquad
\hat\rho = \tanh\!\left(\frac{(N-3)\hat z}{(N-3)+n_0}\right),\quad n_0=50
$$

a Fisher-$z$ shrinkage of the residual correlation toward $0$ (returns $0$ outright if
$N \le 3$). Independently, the two residual variances are shrunk toward their pooled average:

$$
\bar v_{\text{pool}} = \frac{\bar v_A + \bar v_T}{2}, \qquad
\bar v_A \leftarrow 0.8\,\bar v_A + 0.2\,\bar v_{\text{pool}}, \qquad
\bar v_T \leftarrow 0.8\,\bar v_T + 0.2\,\bar v_{\text{pool}}
$$

and the covariance is then reconstructed from the *shrunk* quantities, $\bar c \leftarrow
\hat\rho\sqrt{\bar v_A\bar v_T}$, discarding the original (unshrunk) residual covariance
entirely.

### 4.4 Sector-loading reconstruction (`_reconstruct_sector_loadings`)

The engine only ever consumes $(v_A, v_T, c)$ (§3.2), not $(\gamma_A,\gamma_T,\sigma_A,\sigma_T)$
individually, so the split is under-identified and a specific decomposition is chosen. Fixing
$\sigma_s = 1$ (`MarketParameters.sector_std_dev`):

$$
\gamma_A = \sqrt{\lvert\bar c\rvert\sqrt{\bar v_A/\bar v_T}}\,,
\qquad
\gamma_T = \operatorname{sign}(\bar c)\sqrt{\lvert\bar c\rvert\sqrt{\bar v_T/\bar v_A}}\,,
\qquad
\sigma_i^2 = \max(\bar v_i - \gamma_i^2,\ 0)
$$

By construction $\gamma_A\gamma_T = \bar c$, and $\gamma_A^2 = \lvert\bar c\rvert\sqrt{\bar
v_A/\bar v_T} \le \bar v_A$ by Cauchy–Schwarz ($\lvert\bar c\rvert \le \sqrt{\bar v_A\bar v_T}$),
so $\sigma_i^2 \ge 0$ always. If either $\bar v_i \le \epsilon_{\min}=10^{-12}$, both loadings
are set to $0$ and $\sigma_i^2 = \bar v_i$.

### 4.5 Rate parameters (`_fit_rate` / `_fit_up_down_given_kappa` / `_rate_loglik_reparam`)

The engine consumes only the affine map $r \mapsto (\tilde p^{\uparrow}(r),
\tilde p^{\downarrow}(r))$ (§2.1), which is reparametrised with the mean-reversion target fixed
at $\bar r = 0$:

$$
\tilde p^{\uparrow}(r) = \operatorname{clip}\big(a^{\uparrow} - \kappa r,\ 0,\ 1\big),
\qquad
\tilde p^{\downarrow}(r) = \operatorname{clip}\big(a^{\downarrow} + \kappa r,\ 0,\ 1-\tilde p^{\uparrow}(r)\big)
$$

Comparing to §2.1's $\tilde p^{\uparrow}(r) = p^{\uparrow}+\kappa(\bar r - r)$, this is exactly
the original 4-parameter model with $\bar r$ fixed at $0$ and $a^{\uparrow} := p^{\uparrow}$,
$a^{\downarrow} := p^{\downarrow}$ — one dimension short of the original parametrisation, but
the *map* itself (all that pricing needs) is fully general.

For a fixed $\kappa$, the multinomial MLE for $(a^{\uparrow},a^{\downarrow})$ has the closed
form (pretending the clamps are inactive — a method-of-moments estimator over all observed
levels and their totals $n_t = n_t^{\uparrow}+n_t^{\downarrow}+n_t^{0}$):

$$
\hat a^{\uparrow}(\kappa) = \operatorname{clip}\!\left(\frac{1}{N}\sum_{\text{level}}\big(n^{\uparrow} + \kappa \cdot \text{level}\cdot n\big),\ \epsilon,\ 1-\epsilon\right),
\qquad
\hat a^{\downarrow}(\kappa) = \operatorname{clip}\!\left(\frac{1}{N}\sum_{\text{level}}\big(n^{\downarrow} - \kappa \cdot \text{level}\cdot n\big),\ \epsilon,\ 1-\hat a^{\uparrow}-\epsilon\right)
$$

$\kappa$ itself is chosen by a 101-point grid search over $[0, 0.5]$
(`_KAPPA_MAX`, `_KAPPA_SEARCH_STEPS`), maximising the exact multinomial log-likelihood (with the
clamps active this time) at each grid point's closed-form $(\hat a^{\uparrow},\hat a^{\downarrow})$:

$$
\hat\kappa = \operatorname*{arg\,max}_{\kappa \in \{0, 0.5/100,\ 2\cdot 0.5/100,\ \dots,\ 0.5\}}\ \ell\big(\hat a^{\uparrow}(\kappa), \hat a^{\downarrow}(\kappa), \kappa\big)
$$

If total observations across all levels is below $5$, the defaults $(\hat a^{\uparrow},
\hat a^{\downarrow},\hat\kappa) = (0.2, 0.2, 0.1)$ are returned without fitting.

### 4.6 Assembly and refit cadence

`fit` builds the final `MarketParameters` from §4.2–§4.5 with `sector_std_dev=1.0`,
`rate_step=RATE_STRIKE_GRID`, and — per §4.5's reparametrisation — `rate_target=0.0`,
`rate_up_probability=` $\hat a^{\uparrow}$, `rate_down_probability=` $\hat a^{\downarrow}$,
`rate_reversion_strength=` $\hat\kappa$ (each re-clipped defensively before construction). If
any field is non-finite, or any exception is raised anywhere in `fit` or `_ingest_history`,
the estimate falls back to `_default_market_parameters()` (a flat, uncorrelated,
zero-rate-beta prior) — `warm_up` never leaves `estimated_parameters` unset.

`_refit()` re-runs `_ParameterEstimator.fit` from the cumulative `_SufficientStats` on **every**
`on_step_advance` once `_warmed_up` is true (not just once at the start of the session), so the
estimate incorporates each day's realised transition before that day's quotes are computed —
cheap, since it is $O(\text{number of distinct rate levels observed})$, not $O(N)$.

---

## 5. Market making (`quote`, `respond_to_fok`, and the risk ledger)

### 5.1 Fair-value cache

$P_j$ is computed at most once per option per day: `_precompute_day_cache` populates
`_day_cache` for every active option at the end of `warm_up` and on every `on_step_advance`
(after the day's estimate refit), and `_get_cached_fair`/`_ensure_cached` serve every
subsequent `quote`/`respond_to_fok` call that day from this cache rather than recomputing.

### 5.2 Quote construction (`quote`)

With inventory skew $\text{skew} = k_S\, q_j$ ($k_S=$ `_SKEW_K` $=0.01$):

$$
\text{mid} = \operatorname{clip}\big(P_j - \text{skew},\ 0,\ 1\big)
$$

A long position ($q_j>0$) lowers the reservation center (encourages selling / discourages
further buying); a short position raises it. The half-spreads:

$$
h = \max\big(0.005,\ h_{\text{bandit}} + \mathbb 1_{\text{FED leg}}\cdot p_F - \mathbb 1_{\text{AJR-THR spread}}\cdot d_S\big)
$$

with $p_F=$ `_FED_LEG_PREMIUM` $=0.03$ and $d_S=$ `_SPREAD_DISCOUNT` $=0.015$ (FED single-leg
options are widened, AJR–THR spreads are tightened — see §7's note on why), and $h_{\text{bandit}}$
from §5.3. Toxicity (§5.4) widens each side individually:

$$
h_{\text{bid}} = h + T_{b,k}, \qquad h_{\text{ask}} = h + T_{a,k}
$$

$$
\text{bid} = \big\lfloor 100\,\operatorname{clip}(\text{mid}-h_{\text{bid}},0,1)\big\rfloor/100,
\qquad
\text{offer} = \big\lceil 100\,\operatorname{clip}(\text{mid}+h_{\text{ask}},0,1)\big\rceil/100
$$

(floor/ceil so rounding only ever widens the true half-spread). If rounding collapses the
market ($\text{bid}\ge\text{offer}$), or `_available_margin() - `$\mathcal R$ $\le 0$ at the
top of `quote`, the whole quote falls back to the degenerate riskless pair $(0.00,\ 1.00)$ at
size $Q_{\max}$ (buying at $0$ or selling at $1$ costs no margin by construction). Sizes
$q_{\text{bid}}, q_{\text{ask}}$ come from §5.5; if either resolves to $0$ (no margin/inventory
room on that side), *that side alone* is replaced by its own zero-risk boundary price
($0.00$ buy / $1.00$ sell) at $Q_{\max}$, while the other side keeps its live price if it has
room — degeneracy is handled per side, not by discarding the whole quote.

### 5.3 Adaptive spread bandit (`_update_spread_bandit`, `_current_h_base`)

Once per day, if that day's quote count exceeds an adaptation window $w$, $h_{\text{adj}}$
random-walks by $\pm 0.005$ (`_BANDIT_STEP`) based on the realised same-day fill rate:

$$
\text{win\_rate} = \frac{\text{day\_trade\_count}}{\text{day\_quote\_count}},
\qquad
h_{\text{adj}} \mathrel{+}= \begin{cases} +0.005, & \text{win\_rate} > 0.35 \\ -0.005, & \text{win\_rate} < 0.35 \end{cases}
$$

clamped so that $H_{\text{base}} + h_{\text{adj}} \in [0.01,\ 0.12]$ (`_BANDIT_MIN`,
`_BANDIT_MAX`; $H_{\text{base}}=$ `_H_BASE` $=0.04$). The window itself shrinks with the
capital-aggression scale (§5.6): $w = \max(5,\ 20(1-0.5\lambda_C))$, so low-capital sessions
start adapting after as few as $10$ quotes instead of $20$. The resulting base half-spread is
then itself scaled down by $\lambda_C$:

$$
h_{\text{bandit}} = \operatorname{clip}(H_{\text{base}}+h_{\text{adj}},\ 0.01,\ 0.12)\ \cdot\ \big(1 - 0.35\,\lambda_C\big)
$$

### 5.4 Adverse-selection toxicity (markouts)

For every fill, the markout $M_h = P_{j,t+h} - P_{j,t}$ is recorded at each available
$h\in\{1,2,3\}$ days after the fill (`_record_markout`/`_update_markouts`, using the day-cached
$P_j$), finalised once either $h$ reaches $3$ or the option itself settles first (whichever
comes first — an option expiring inside the 3-day horizon is finalised on fewer than 3
observations). The per-fill realisation $m = \overline{M_h}$ (mean of whatever horizons were
observed) updates the **global** EWMA ($\alpha=$ `_MARKOUT_ALPHA` $=0.05$):

$$
T_b \leftarrow \alpha(-m) + (1-\alpha)T_b \ \ (\text{fill was a buy}),
\qquad
T_a \leftarrow \alpha\, m + (1-\alpha)T_a \ \ (\text{fill was a sell})
$$

Per-counterparty running sums accumulate a plain (non-decaying) mean, $T_{\cdot,k}^{\text{local}}
= (\text{sum of that counterparty's obs})/N_k$, shrunk toward the global EWMA:

$$
T_{b,k} = w_k\, T_{b,k}^{\text{local}} + (1-w_k)\,T_b, \qquad w_k = \frac{N_k}{N_k+\tau}, \quad \tau=30
$$

and symmetrically for $T_{a,k}$. Both are floored at $0$ and capped at `_T_MAX`$=0.1$ in
`_toxicity`'s return — a negative measured toxicity (favourable realised flow) never tightens
the quote below the base spread.

### 5.5 Sizing (`_size_for` / `_margin_feasible_quantity`)

For a prospective trade of one unit on side $\text{is\_buy}$:

$$
\text{inventory\_room} = N_{\max} - \big\lvert q_j + \mathbb 1_{\text{is\_buy}} - \mathbb 1_{\lnot\text{is\_buy}}\big\rvert + 1
$$

$$
\text{headroom} = \min\Big(u\cdot C_0 - M,\ \ F - \mathcal R\Big),
\qquad
\text{margin\_room} = \Big\lfloor \frac{\text{headroom}}{\text{unit\_cost}} \Big\rfloor,
\quad \text{unit\_cost} = \begin{cases}\text{price}, & \text{is\_buy} \\ 1-\text{price}, & \lnot\text{is\_buy}\end{cases}
$$

$$
Q = \max\big(0,\ \min(Q_{\max},\ \text{inventory\_room},\ \text{margin\_room})\big)
$$

both quantities clamped at $0$ from below (no negative size); $Q=0$ signals no room on that
side, handled by §5.2's per-side fallback. The utilisation cap $u$ (`_utilisation_cap`) is
`_MAX_UTILISATION`$=0.6$, adjusted $-0.2$ for a FED-leg option, $+0.2$ for an AJR–THR spread
(§7's confidence-weighted risk budget: measured pricing error is lowest on spreads, highest on
FED singles), $+0.2\lambda_C$ from the capital scale (§5.6), clipped to $[0.05, 0.95]$.

### 5.6 Capital-aggression scale (`_capital_scale`)

Computed once at `__init__` from `cash_balance`, ramping linearly from $0$ at $C_0=20$ to $1$ at
$C_0=10$, and clamped at both ends:

$$
\lambda_C = \operatorname{clip}\!\left(\frac{20 - C_0}{20-10},\ 0,\ 1\right)
$$

It appears in exactly four places — §5.2/5.3's spread tightening, §5.5's utilisation boost,
§5.3's bandit window, and §5.7's FOK edge threshold — and is by construction exactly $0$ for
$C_0 \ge 20$, so none of those formulas differ from their $\lambda_C=0$ form above that
capital level. It does not touch the hard solvency machinery of §5.8 at all — it only spends
down margin-of-safety that is cheap to spend when the book is small.

### 5.7 FOK acceptance (`respond_to_fok`)

Let $p$ be the FOK's price and $Q$ its (uncapped) requested quantity. The side we would take is
determined by the counterparty's order type: a counterparty **buy** means we would sell; a
counterparty **sell** means we would buy. The code computes:

$$
\text{edge} = \begin{cases} P_j - p, & \text{counterparty order type} = \text{BUY (we sell)} \\ p - P_j, & \text{counterparty order type} = \text{SELL (we buy)} \end{cases}
$$

$$
\text{required} = \Big(0.02 - 0.01\,\lambda_C\Big) + \text{toxicity} + 0.05\cdot\frac{Q\cdot\text{unit\_cost}}{C_0}
$$

Accept iff $\text{edge} \ge \text{required}$ **and** $Q\cdot\text{unit\_cost} \le
\text{Av} - \mathcal R$ (the same margin gate as §5.5, evaluated at the full requested $Q$ as a
worst case for split fills).

> **This `edge` formula is inverted relative to our actual expected profit.** Selling at $p$
> when fair value is $P_j$ profits us $p - P_j$ (we want to sell *above* fair); buying at $p$
> profits us $P_j - p$ (we want to buy *below* fair). The code has these swapped: the "we sell"
> branch computes $P_j - p$ (the *counterparty's* edge, not ours) and the "we buy" branch
> computes $p - P_j$. Concretely, `quote()`'s own bid/ask construction (§5.2) gets this right
> (buy low at `mid - h_bid`, sell high at `mid + h_ask`), so this is a local inconsistency in
> `respond_to_fok` alone, not a project-wide sign convention. Traced against a real VERBOSE log:
> a FOK "buy 0.01" with $P_j=0.2174$ (i.e. a counterparty offering to buy from us at $1$¢ when
> the contract is worth ~$22$¢ — a bad trade for us to accept as seller) computes
> $\text{edge}=P_j-p=+0.2074$, clears the small `required` threshold, and is **accepted** — the
> bot sold at $0.01$ solely because the *counterparty's* windfall was large, not because of any
> edge to us. This documents current behaviour exactly as coded; it is very likely a real bug
> and a material contributor to FOK-driven losses, not an intentional design choice.

### 5.8 Risk ledger

Every trade of signed quantity $\Delta q$ at price $p$ ($\Delta q>0$: we bought; $\Delta q<0$:
we sold $\lvert\Delta q\rvert$ units) updates three parallel ledgers (`on_trade`):

$$
d(\Delta q, p) = \begin{cases} \Delta q\, p, & \Delta q>0 \\ -\Delta q\,(1-p), & \Delta q<0 \end{cases}
\qquad\text{(the per-trade max-loss debit)}
$$

$$
C \mathrel{-}= \Delta q\, p \qquad\text{(literal cash: pay }p\text{ on a buy, receive }p\text{ on a sell)}
$$

$$
M \mathrel{+}= d(\Delta q, p), \qquad L \mathrel{-}= d(\Delta q, p)
$$

$M$ (margin used) and $L$ (legacy reserved, starting at $C_0$) move by the *same* amount but
from different baselines. At settlement of an expired option with realised payoff $\Pi\in\{0,1\}$
and net position $q$ (`_settle_expired_positions`):

$$
C \mathrel{+}= q\,\Pi \quad(q>0)\ \text{ or }\ (-q)(1-\Pi) \quad(q<0),
\qquad
L \mathrel{+}= \text{(the same expression)},
\qquad
M \mathrel{-}= \text{(the full originally-reserved debit for that option, regardless of }\Pi\text{)}
$$

$C$ and $L$ are updated identically (both track the realised outcome exactly), but $M$'s
release is *not* payoff-adjusted — it always gives back the entire cumulative debit that had
been reserved against that option, whatever $\Pi$ turned out to be. This asymmetry is masked in
practice because every gate takes a $\min$ with $F=\min(W,L)$ (§5.5/§5.7), and $L$ — unlike
$M$ — *is* payoff-adjusted, so $L$ is the effective backstop whenever $M$'s optimistic release
would otherwise have been the binding constraint.

$W$ (`_worst_case_cash`) is a second, independent read on solvency: $W = C -
\sum_j\max(0,-q_j)$, i.e. literal cash minus one dollar of assumed worst-case liability per
currently-short unit (not adjusted for a partial cover — buying back part of a short before
expiry is treated as a slight over-reservation, deliberately on the conservative side rather
than the unsafe one). $\text{Av} = \min(C_0 - M,\ \min(W, L))$ is the single number every sizing
and acceptance decision in §5.5–§5.7 is gated on.

---

## 6. Summary of modelling gaps

| # | Gap | Consequence | Status |
|---|---|---|---|
| G1 | `respond_to_fok`'s `edge` computes the *counterparty's* profit, not ours (§5.7) | The bot can accept FOKs that are bad for it (and reject FOKs that are good for it) whenever the counterparty's windfall is large enough to clear the small `required` threshold, regardless of our own sign | **Open — likely bug**, confirmed against a real VERBOSE trade log |
| G2 | `_used_margin`'s settlement release is not payoff-adjusted (§5.8) | Optimistic on its own; currently masked because every gate takes $\min$ with the payoff-adjusted $L$ | Open, low severity (protected by the `min`) |
| G3 | Per-counterparty toxicity uses a non-decaying running mean while the global estimate is an EWMA (§5.4) | A counterparty's very first few fills are weighted equally with fills from much later in a long session; intentional or not is undocumented | Open |
| G4 | The capital-aggression scale (§5.6) is fit to the outcome of a single historical HackerRank run (5/5 losses at $C_0=10$, ~even at $C_0\ge20$), not derived from the market-making math | Effective, but carries real overfitting risk if the grader's $C_0=10$ scenarios aren't representative of $C_0=10$ scenarios in general | Open, by design (see conversation history) |
| G5 | The confidence-weighted utilisation cap (§5.5) and per-option `_MAX_NET_PER_OPTION` cap have no cross-option concentration/correlation budget | A book can simultaneously lean on the per-option cap for many highly-correlated FED-leg or spread options at once with no portfolio-level check | Open |
| G6 | `_BinaryOptionPricer.price`'s `fast`/`lattice_cache` parameters are unused by both call sites (§3.3) | No live effect (dead optionality); the 129-node quadrature and a fresh lattice build run on every call | Not a correctness gap, just unused capacity |
