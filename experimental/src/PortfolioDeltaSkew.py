import math
import random
from collections import defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Final

from src.taqf.akuna.market_types import (
    AJARAI_NAME,
    AJARAI_UNDERLYING_ID,
    BinaryOption,
    FED_FUNDS_RATE_NAME,
    FED_FUNDS_RATE_UNDERLYING_ID,
    FokOrder,
    MarketHistory,
    MarketParameters,
    OptionLeg,
    OrderType,
    Position,
    Quote,
    RATE_STRIKE_GRID,
    THERIODIC_NAME,
    THERIODIC_UNDERLYING_ID,
    Underlying,
    UNDERLYING_NAME_BY_ID,
)


# --- Lineage ----------------------------------------------------------------
# Adds: replaces single-option net-position skew with portfolio-level, cross-underlying delta skew.
# Parent: Archived-A (archived, not renamed -- see archive/experiment-archive/).
# ----------------------------------------------------------------------------

class _BinaryOptionPricer:
    _MIN_SD = 1e-12
    _QUAD_NODES = tuple((-8.0 + 0.125 * i for i in range(129)))
    _QUAD_STEP = 0.125
    _QUAD_NODES_FAST = tuple((-8.0 + 2.0 * i for i in range(9)))
    _QUAD_STEP_FAST = 2.0

    @staticmethod
    def _norm_cdf(z):
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    @classmethod
    def _phi(cls, u):
        return math.exp(-0.5 * u * u) / math.sqrt(2.0 * math.pi)

    @classmethod
    def _prob_ge(cls, mean_log, sd, threshold):
        if sd < cls._MIN_SD:
            return 1.0 if math.exp(mean_log) >= threshold else 0.0
        if threshold <= 0:
            return 1.0
        return cls._norm_cdf((mean_log - math.log(threshold)) / sd)

    @classmethod
    def _prob_le(cls, mean_log, sd, threshold):
        if sd < cls._MIN_SD:
            return 1.0 if math.exp(mean_log) <= threshold else 0.0
        if threshold <= 0:
            return 0.0
        return cls._norm_cdf((math.log(threshold) - mean_log) / sd)

    @classmethod
    def _single_leg_prob(cls, mean_log, sd, weight, k_eff):
        threshold = k_eff / weight
        return cls._prob_ge(mean_log, sd, threshold) if weight > 0 else cls._prob_le(mean_log, sd, threshold)

    @classmethod
    def _two_leg_both_degenerate(cls, mean_a, mean_t, w_a, w_t, k_eff):
        a, t = (math.exp(mean_a), math.exp(mean_t))
        return 1.0 if w_a * a + w_t * t >= k_eff else 0.0

    @classmethod
    def _two_leg_zero_strike_spread(cls, mean_a, mean_t, var_a, var_t, cov, w_a, w_t):
        sd_diff = math.sqrt(max(var_a + var_t - 2.0 * cov, 0.0))
        if w_a > 0:
            diff_mean, thr = (mean_a - mean_t, math.log(-w_t / w_a))
        else:
            diff_mean, thr = (mean_t - mean_a, math.log(-w_a / w_t))
        if sd_diff < cls._MIN_SD:
            return 1.0 if diff_mean >= thr else 0.0
        return cls._norm_cdf((diff_mean - thr) / sd_diff)

    @classmethod
    def _two_leg_quadrature(cls, mean_a, sd_a, mean_t, sd_t, cov, w_a, w_t, k_eff, fast=False):
        rho = max(-0.999, min(0.999, cov / (sd_a * sd_t)))
        total = 0.0
        nodes = cls._QUAD_NODES_FAST if fast else cls._QUAD_NODES
        step = cls._QUAD_STEP_FAST if fast else cls._QUAD_STEP
        last = len(nodes) - 1
        for i, u in enumerate(nodes):
            a = math.exp(mean_a + sd_a * u)
            k2 = k_eff - w_a * a
            m2 = mean_t + rho * sd_t * u
            s2 = sd_t * math.sqrt(max(1.0 - rho * rho, 1e-12))
            g = cls._prob_ge(m2, s2, k2 / w_t) if w_t > 0 else cls._prob_le(m2, s2, k2 / w_t)
            node_weight = step if 0 < i < last else step / 2.0
            total += node_weight * cls._phi(u) * g
        return min(max(total, 0.0), 1.0)

    @classmethod
    def _two_leg_prob(cls, mean_a, sd_a, mean_t, sd_t, cov, w_a, w_t, k_eff, fast=False):
        var_a, var_t = (sd_a * sd_a, sd_t * sd_t)
        if sd_a < cls._MIN_SD and sd_t < cls._MIN_SD:
            return cls._two_leg_both_degenerate(mean_a, mean_t, w_a, w_t, k_eff)
        if sd_a < cls._MIN_SD:
            return cls._single_leg_prob(mean_t, sd_t, w_t, k_eff - w_a * math.exp(mean_a))
        if sd_t < cls._MIN_SD:
            return cls._single_leg_prob(mean_a, sd_a, w_a, k_eff - w_t * math.exp(mean_t))
        if abs(k_eff) < 1e-09 and w_a * w_t < 0:
            return cls._two_leg_zero_strike_spread(mean_a, mean_t, var_a, var_t, cov, w_a, w_t)
        return cls._two_leg_quadrature(mean_a, sd_a, mean_t, sd_t, cov, w_a, w_t, k_eff, fast)

    @staticmethod
    def _leg_weights(option):
        w_f = w_a = w_t = 0.0
        for leg in option.legs:
            if leg.underlying_id == FED_FUNDS_RATE_UNDERLYING_ID:
                w_f = leg.weight
            elif leg.underlying_id == AJARAI_UNDERLYING_ID:
                w_a = leg.weight
            elif leg.underlying_id == THERIODIC_UNDERLYING_ID:
                w_t = leg.weight
        return (w_f, w_a, w_t)

    @staticmethod
    def _rate_lattice(market_parameters, rate0, steps):
        lattice = {rate0: 1.0}
        for _ in range(steps):
            next_lattice = {}
            for rate_value, rate_prob in lattice.items():
                if rate_prob <= 0:
                    continue
                up, down = market_parameters.tilted_rate_probabilities(rate_value)
                stay = 1.0 - up - down
                branches = ((market_parameters.next_rate_value(rate_value, 1), rate_prob * up), (market_parameters.next_rate_value(rate_value, -1), rate_prob * down), (rate_value, rate_prob * stay))
                for next_rate, branch_prob in branches:
                    next_lattice[next_rate] = next_lattice.get(next_rate, 0.0) + branch_prob
            lattice = next_lattice
        return lattice

    @staticmethod
    def _company_moments(market_parameters, steps):
        var_a = max(steps * (market_parameters.ajarai_sector_beta ** 2 * market_parameters.sector_std_dev ** 2 + market_parameters.ajarai_idio_std_dev ** 2), 0.0)
        var_t = max(steps * (market_parameters.theriodic_sector_beta ** 2 * market_parameters.sector_std_dev ** 2 + market_parameters.theriodic_idio_std_dev ** 2), 0.0)
        cov = steps * (market_parameters.ajarai_sector_beta * market_parameters.theriodic_sector_beta * market_parameters.sector_std_dev ** 2)
        return (var_a, var_t, cov)

    @classmethod
    def _conditional_probability(cls, terminal_rate, rate0, steps, market_parameters, log_ajarai0, log_theriodic0, sd_a, sd_t, cov, w_f, w_a, w_t, strike, fast=False):
        rate_change = terminal_rate - rate0
        k_eff = strike - w_f * terminal_rate
        if w_a == 0.0 and w_t == 0.0:
            return 1.0 if w_f * terminal_rate >= strike else 0.0
        mean_a = log_ajarai0 + steps * market_parameters.ajarai_drift + market_parameters.ajarai_rate_beta * rate_change
        mean_t = log_theriodic0 + steps * market_parameters.theriodic_drift + market_parameters.theriodic_rate_beta * rate_change
        if w_t == 0.0:
            return cls._single_leg_prob(mean_a, sd_a, w_a, k_eff)
        if w_a == 0.0:
            return cls._single_leg_prob(mean_t, sd_t, w_t, k_eff)
        return cls._two_leg_prob(mean_a, sd_a, mean_t, sd_t, cov, w_a, w_t, k_eff, fast)

    @classmethod
    def price(cls, market_parameters, values, option, fast=False, lattice_cache=None):
        steps = option.steps_until_expiry
        if steps <= 0:
            if steps == 0 and SETTLEMENT_AFTER_ADVANCE:
                steps = 1
            else:
                return option.expiry_valuation(values)
        w_f, w_a, w_t = cls._leg_weights(option)
        rate0 = values.get(FED_FUNDS_RATE_UNDERLYING_ID, market_parameters.rate_target)
        ajarai0 = values.get(AJARAI_UNDERLYING_ID, 1.0)
        theriodic0 = values.get(THERIODIC_UNDERLYING_ID, 1.0)
        ajarai0 = ajarai0 if ajarai0 > 0 else 1e-12
        theriodic0 = theriodic0 if theriodic0 > 0 else 1e-12
        if lattice_cache is None:
            rate_lattice = cls._rate_lattice(market_parameters, rate0, steps)
        else:
            key = (round(market_parameters.rate_reversion_strength, 6), round(market_parameters.rate_target, 6), round(rate0, 6), steps)
            rate_lattice = lattice_cache.get(key)
            if rate_lattice is None:
                rate_lattice = cls._rate_lattice(market_parameters, rate0, steps)
                lattice_cache[key] = rate_lattice
        var_a, var_t, cov = cls._company_moments(market_parameters, steps)
        sd_a, sd_t = (math.sqrt(var_a), math.sqrt(var_t))
        log_ajarai0, log_theriodic0 = (math.log(ajarai0), math.log(theriodic0))
        probability = 0.0
        for terminal_rate, rate_prob in rate_lattice.items():
            if rate_prob <= 0:
                continue
            conditional = cls._conditional_probability(terminal_rate, rate0, steps, market_parameters, log_ajarai0, log_theriodic0, sd_a, sd_t, cov, w_f, w_a, w_t, option.strike, fast)
            probability += rate_prob * conditional
        if not math.isfinite(probability):
            return 0.5
        return min(max(probability, 0.0), 1.0)


class MarketMaker:
    """Tenth overhaul: portfolio-level risk, not per-option risk.

    Every previous version -- whatever it did for fair value or spread width -- made
    the inventory-skew decision by looking at `net_position(this_one_option_id)` alone.
    That's a real blind spot: AJARAI, THERIODIC, and the FED rate are correlated, and
    several option shapes reference more than one of them, so the risk that actually
    matters is the combined sensitivity of the *whole current book* to a move in any one
    underlying -- not each position's own count in isolation. A trade that looks flat
    "per option" can still be piling onto an already-large correlated exposure across
    several different option_ids that all lean the same way, and a previous version has
    no way to see that, or to notice when a new trade would instead *offset* existing
    risk (a natural hedge) even though its own position count is nonzero.

    This version replaces the single-option inventory skew entirely with a portfolio
    Greeks calculation, computed fresh once per day:

    1. For every currently *held* position, estimate its delta (sensitivity of fair
       value to a small move in each underlying it references) by bumping that
       underlying's value up and down and re-pricing with the analytic model --
       standard numerical differentiation, nothing exotic.
    2. Sum `quantity * delta` across the whole book, per underlying, to get one
       portfolio-delta vector: "how much does my total book move if AJARAI/THERIODIC/
       the FED rate moves a little."
    3. When quoting *any* option (held or not), compute what a +1 (buy) or -1 (sell)
       fill would do to that portfolio-delta vector, and compare the portfolio's overall
       risk (sum of squared exposures) before and after. If taking that side would push
       an already-large correlated exposure further out, that side gets a worse price;
       if it would pull the book back toward flat -- a hedge, even for an option we've
       never touched before -- that side gets a *better* price than the flat base spread
       would otherwise offer.

    This is the genuinely new mechanism this round. Two smaller, deliberate
    simplifications support it rather than compete with it: the parameter fit is now
    plain moment-matching (sample mean/variance of log-returns, empirical up/down
    frequency for the rate, no mean-reversion or cross-asset beta terms) instead of the
    old maximum-likelihood estimator, both because it's simpler and because a smooth,
    cheap, easily-bumped pricer is exactly what numerical differentiation wants; and the
    base half-spread is a single flat constant, since the intelligence this version adds
    is entirely in the skew, not in a fancier width formula. `price_option_from_parameters`
    -- the grader's THEO check against the true parameters -- still uses the untouched
    exact analytic pricer, for the same reason as every prior version: there's no reason
    to approximate when handed ground truth.

    Everything from zones and hysteresis through toxicity, flow-tilt, the bandit, and
    the bootstrap simulator is gone. Only the required dataclasses, the analytic pricer,
    and the hard solvency gates below survive from any earlier version -- the last of
    those because bankruptcy protection isn't strategy, it's the floor every strategy
    here has to stand on.
    """

    _RESERVE_FRACTION = 0.05
    _MAX_UTILISATION = 0.6
    _MAX_NET_PER_OPTION = 10
    _Q_MAX = 50

    _MIN_HISTORY = 5        # below this many transitions, price_option falls back to 0.5

    # --- flat base spread: the width isn't where this version's intelligence lives ---
    _H_BASE = 0.06

    # --- portfolio Greeks ------------------------------------------------------------
    _DELTA_EPS = 0.01           # relative bump size for finite-difference deltas
    _PORTFOLIO_RISK_K = 0.08    # converts a change in portfolio risk score into a price skew
    _SKEW_CAP = 0.15            # hard cap on the per-side portfolio skew

    def __init__(self, underlying_initial_state, option_initial_state, cash_balance):
        self.underlying_state = underlying_initial_state
        self.active_option_state = option_initial_state
        self.cash_balance = cash_balance
        self.position = Position()
        try:
            starting_cash = max(float(cash_balance), 0.01)
        except Exception:
            starting_cash = 1.0
        self._starting_cash = starting_cash
        self._reserve = self._RESERVE_FRACTION * starting_cash
        self._used_margin = 0.0
        self._margin_by_option = {}
        self._cash = starting_cash
        self._legacy_reserved = starting_cash
        self._day_cache = {}
        self._day_portfolio_delta = {}
        self._warmed_up = False
        self.estimated_parameters = None

        # raw historical buffers -- moment-matching refits from these directly, no
        # incremental sufficient statistics needed
        self._rate_hist = []
        self._ajr_hist = []
        self._thr_hist = []

    # --- lifecycle -----------------------------------------------------------------

    def on_step_advance(self, new_underlying_state, new_option_state):
        self._day_cache = {}
        try:
            self._settle_expired_positions(new_underlying_state, new_option_state)
        except Exception:
            pass
        try:
            if self._warmed_up:
                self._ingest_live_point(new_underlying_state)
                self._refit()
        except Exception:
            pass
        self.underlying_state = new_underlying_state
        self.active_option_state = new_option_state
        try:
            self._precompute_day_cache()
        except Exception:
            pass

    def on_trade(self, option, price, quantity, counterparty_id):
        try:
            debit = quantity * price if quantity > 0 else -quantity * (1.0 - price)
            self._cash -= quantity * price
            self._used_margin += debit
            self._legacy_reserved -= debit
            self._margin_by_option[option.option_id] = self._margin_by_option.get(option.option_id, 0.0) + debit
        except Exception:
            pass
        try:
            self.position.add_option_quantity(option.option_id, quantity)
        except Exception:
            pass

    def warm_up(self, market_history):
        try:
            history = market_history.values_by_underlying_id
            self._rate_hist = list(history.get(FED_FUNDS_RATE_UNDERLYING_ID, ()))
            self._ajr_hist = list(history.get(AJARAI_UNDERLYING_ID, ()))
            self._thr_hist = list(history.get(THERIODIC_UNDERLYING_ID, ()))
            self._refit()
        except Exception:
            self.estimated_parameters = self._fallback_parameters()
        self._warmed_up = True
        try:
            self._precompute_day_cache()
        except Exception:
            pass

    def _ingest_live_point(self, new_underlying_state):
        new = {u.underlying_id: u.value for u in new_underlying_state}
        self._rate_hist.append(new[FED_FUNDS_RATE_UNDERLYING_ID])
        self._ajr_hist.append(new[AJARAI_UNDERLYING_ID])
        self._thr_hist.append(new[THERIODIC_UNDERLYING_ID])

    @staticmethod
    def _fallback_parameters():
        return MarketParameters(
            ajarai_drift=0.0, ajarai_idio_std_dev=0.01, ajarai_rate_beta=0.0, ajarai_sector_beta=0.0,
            rate_down_probability=0.2, rate_reversion_strength=0.0, rate_up_probability=0.2,
            sector_std_dev=0.0, theriodic_drift=0.0, theriodic_idio_std_dev=0.01,
            theriodic_rate_beta=0.0, theriodic_sector_beta=0.0, rate_step=RATE_STRIKE_GRID, rate_target=2.0,
        )

    def _refit(self):
        """Plain moment matching: sample mean/variance of log-returns, empirical
        up/down frequency for the rate. No mean-reversion term, no cross-asset betas --
        a deliberately cruder model than the old MLE estimator, traded for simplicity
        and for being cheap and smooth enough to numerically differentiate below."""
        try:
            n = min(len(self._rate_hist), len(self._ajr_hist), len(self._thr_hist))
            if n < self._MIN_HISTORY:
                self.estimated_parameters = self._fallback_parameters()
                return
            log_a = [math.log(self._ajr_hist[i] / self._ajr_hist[i - 1]) for i in range(1, n)
                     if self._ajr_hist[i - 1] > 0 and self._ajr_hist[i] > 0]
            log_t = [math.log(self._thr_hist[i] / self._thr_hist[i - 1]) for i in range(1, n)
                     if self._thr_hist[i - 1] > 0 and self._thr_hist[i] > 0]
            mu_a = sum(log_a) / len(log_a) if log_a else 0.0
            mu_t = sum(log_t) / len(log_t) if log_t else 0.0
            var_a = sum((x - mu_a) ** 2 for x in log_a) / max(len(log_a) - 1, 1) if len(log_a) > 1 else 1e-4
            var_t = sum((x - mu_t) ** 2 for x in log_t) / max(len(log_t) - 1, 1) if len(log_t) > 1 else 1e-4
            ups = downs = stays = 0
            for i in range(1, n):
                d = self._rate_hist[i] - self._rate_hist[i - 1]
                if d > RATE_STRIKE_GRID * 0.5:
                    ups += 1
                elif d < -RATE_STRIKE_GRID * 0.5:
                    downs += 1
                else:
                    stays += 1
            total = ups + downs + stays
            up_p = min(max(ups / total, 1e-3), 0.9) if total else 0.2
            down_p = min(max(downs / total, 1e-3), 0.9 - up_p) if total else 0.2
            params = MarketParameters(
                ajarai_drift=mu_a, ajarai_idio_std_dev=math.sqrt(max(var_a, 1e-8)),
                ajarai_rate_beta=0.0, ajarai_sector_beta=0.0,
                rate_down_probability=down_p, rate_reversion_strength=0.0, rate_up_probability=up_p,
                sector_std_dev=0.0, theriodic_drift=mu_t, theriodic_idio_std_dev=math.sqrt(max(var_t, 1e-8)),
                theriodic_rate_beta=0.0, theriodic_sector_beta=0.0,
                rate_step=RATE_STRIKE_GRID, rate_target=self._rate_hist[-1] if self._rate_hist else 2.0,
            )
            self.estimated_parameters = params
        except Exception:
            self.estimated_parameters = self._fallback_parameters()

    def _settle_expired_positions(self, new_underlying_state, new_option_state):
        """Credits NET position payoff at expiry (grader accounts per net position, not
        per gross trade), and releases the margin that was reserved against it."""
        new_ids = {opt.option_id for opt in new_option_state}
        values = {u.underlying_id: u.value for u in new_underlying_state}
        for option in self.active_option_state:
            if option.option_id in new_ids:
                continue
            quantity = self.position.option_quantity_by_option_id.get(option.option_id, 0)
            payoff = option.expiry_valuation(values)
            reserved = self._margin_by_option.pop(option.option_id, 0.0)
            self._used_margin = max(0.0, self._used_margin - reserved)
            if quantity == 0:
                continue
            self._cash += quantity * payoff
            self._legacy_reserved += quantity * payoff if quantity > 0 else -quantity * (1.0 - payoff)
            self.position.option_quantity_by_option_id[option.option_id] = 0

    # --- pricing -----------------------------------------------------------------

    @property
    def name(self):
        return "AthenaBot"

    def price_option_from_parameters(self, market_parameters, option):
        try:
            values = {u.underlying_id: u.value for u in self.underlying_state}
            result = _BinaryOptionPricer.price(market_parameters, values, option)
            return result if math.isfinite(result) else 0.5
        except Exception:
            return 0.5

    def price_option(self, option):
        try:
            return self._ensure_cached(option)["P"]
        except Exception:
            return 0.5

    def _price_from_estimate(self, option, values):
        try:
            if not self._warmed_up or self.estimated_parameters is None:
                return 0.5
            result = _BinaryOptionPricer.price(self.estimated_parameters, values, option, fast=True)
            return result if math.isfinite(result) else 0.5
        except Exception:
            return 0.5

    # --- portfolio Greeks --------------------------------------------------------

    def _numeric_delta(self, option, underlying_id, values):
        base_val = values.get(underlying_id, 0.0)
        bump = max(abs(base_val) * self._DELTA_EPS, 1e-4)
        up = dict(values)
        up[underlying_id] = base_val + bump
        down = dict(values)
        down[underlying_id] = max(base_val - bump, 0.0)
        p_up = _BinaryOptionPricer.price(self.estimated_parameters, up, option, fast=True)
        p_down = _BinaryOptionPricer.price(self.estimated_parameters, down, option, fast=True)
        if not (math.isfinite(p_up) and math.isfinite(p_down)):
            return 0.0
        return (p_up - p_down) / (2.0 * bump)

    def _option_delta_vector(self, option, values):
        deltas = {}
        if not self._warmed_up or self.estimated_parameters is None:
            return deltas
        for uid in {leg.underlying_id for leg in option.legs}:
            try:
                deltas[uid] = self._numeric_delta(option, uid, values)
            except Exception:
                deltas[uid] = 0.0
        return deltas

    def _ensure_cached(self, option):
        entry = self._day_cache.get(option.option_id)
        if entry is not None:
            return entry
        values = {u.underlying_id: u.value for u in self.underlying_state}
        fair = self._price_from_estimate(option, values)
        delta = self._option_delta_vector(option, values)
        entry = {"P": fair, "delta": delta}
        self._day_cache[option.option_id] = entry
        return entry

    def _precompute_day_cache(self):
        for option in self.active_option_state:
            self._ensure_cached(option)
        self._day_portfolio_delta = self._compute_portfolio_delta()

    def _compute_portfolio_delta(self):
        total = {}
        for option in self.active_option_state:
            qty = self._net_position(option.option_id)
            if qty == 0:
                continue
            entry = self._day_cache.get(option.option_id)
            if entry is None:
                continue
            for uid, d in entry["delta"].items():
                total[uid] = total.get(uid, 0.0) + qty * d
        return total

    @staticmethod
    def _portfolio_risk_score(delta_vector):
        return sum(v * v for v in delta_vector.values())

    def _skew_for_side(self, option, is_buy):
        """How much would filling this side change our *whole book's* correlated risk,
        not just this option's own position count? Positive result = this side would
        concentrate risk further (worse price offered); negative = this side would hedge
        existing exposure (better price offered), even for an option we've never held."""
        entry = self._ensure_cached(option)
        option_delta = entry["delta"]
        if not option_delta:
            return 0.0
        direction = 1.0 if is_buy else -1.0
        new_portfolio = dict(self._day_portfolio_delta)
        for uid, d in option_delta.items():
            new_portfolio[uid] = new_portfolio.get(uid, 0.0) + direction * d
        risk_before = self._portfolio_risk_score(self._day_portfolio_delta)
        risk_after = self._portfolio_risk_score(new_portfolio)
        skew = self._PORTFOLIO_RISK_K * (risk_after - risk_before)
        return min(max(skew, -self._SKEW_CAP), self._SKEW_CAP)

    def _quote_prices(self, option):
        fair = min(max(self._ensure_cached(option)["P"], 0.0), 1.0)
        skew_bid = self._skew_for_side(option, True)
        skew_ask = self._skew_for_side(option, False)
        bid = fair - self._H_BASE - skew_bid
        offer = fair + self._H_BASE + skew_ask
        return min(max(bid, 0.0), 1.0), min(max(offer, 0.0), 1.0)

    # --- solvency (unchanged: safety plumbing, not strategy) -------------------------

    def _net_position(self, option_id):
        return self.position.option_quantity_by_option_id.get(option_id, 0)

    def _margin_feasible_quantity(self, price, is_buy):
        unit_cost = price if is_buy else (1.0 - price)
        if unit_cost <= 1e-9:
            return self._Q_MAX
        headroom = min(
            self._MAX_UTILISATION * self._starting_cash - self._used_margin,
            self._feasible_cash() - self._reserve,
        )
        if headroom <= 0.0:
            return 0
        return max(0, int(headroom / unit_cost))

    def _size_for(self, option, price, is_buy):
        net = self._net_position(option.option_id)
        new_net = net + (1 if is_buy else -1)
        inventory_room = self._MAX_NET_PER_OPTION - abs(new_net) + 1
        if inventory_room <= 0:
            return 0
        margin_room = self._margin_feasible_quantity(price, is_buy)
        return max(0, min(self._Q_MAX, inventory_room, margin_room))

    def _worst_case_cash(self):
        short_exposure = sum(max(0, -q) for q in self.position.option_quantity_by_option_id.values())
        return self._cash - short_exposure

    def _feasible_cash(self):
        return min(self._worst_case_cash(), self._legacy_reserved)

    def _available_margin(self):
        return min(self._starting_cash - self._used_margin, self._feasible_cash())

    @staticmethod
    def _round_quote_prices(bid, offer):
        bid_price = math.floor(bid * 100.0) / 100.0
        offer_price = math.ceil(offer * 100.0) / 100.0
        if bid_price >= offer_price:
            offer_price = min(1.0, bid_price + 0.01)
            if bid_price >= offer_price:
                bid_price = max(0.0, offer_price - 0.01)
        bid_price, offer_price = round(bid_price, 2), round(offer_price, 2)
        if bid_price >= offer_price:
            return -1.0, -1.0
        return bid_price, offer_price

    @staticmethod
    def _risk_free_quote():
        """Buying N at 0.00 debits N*0=0; selling N at 1.00 debits N*(1-1)=0. Zero-margin,
        non-negative-PnL fallback, quoted at _Q_MAX since it costs no margin."""
        return Quote(bid_price=0.0, bid_quantity=MarketMaker._Q_MAX, offer_price=1.0, offer_quantity=MarketMaker._Q_MAX)

    def quote(self, option, counterparty_id):
        try:
            if self._available_margin() - self._reserve <= 0:
                return self._risk_free_quote()
            raw_bid, raw_offer = self._quote_prices(option)
            bid_price, offer_price = self._round_quote_prices(raw_bid, raw_offer)
            if bid_price < 0.0:
                return self._risk_free_quote()
            q_bid = self._size_for(option, bid_price, True)
            q_ask = self._size_for(option, offer_price, False)
            if q_bid <= 0:
                bid_price, q_bid = 0.0, self._Q_MAX
            if q_ask <= 0:
                offer_price, q_ask = 1.0, self._Q_MAX
            return Quote(bid_price=bid_price, bid_quantity=q_bid, offer_price=offer_price, offer_quantity=q_ask)
        except Exception:
            return self._risk_free_quote()

    def respond_to_fok(self, option, fok_order):
        try:
            raw_bid, raw_offer = self._quote_prices(option)
            is_buy_side = fok_order.order_type == OrderType.SELL  # counterparty sells -> we buy
            if is_buy_side:
                our_price = round(max(0.0, raw_bid), 2)
                if fok_order.price > our_price:
                    return False
                price = fok_order.price
            else:
                our_price = round(min(1.0, raw_offer), 2)
                if fok_order.price < our_price:
                    return False
                price = fok_order.price
            quantity = fok_order.quantity
            unit_cost = price if is_buy_side else (1.0 - price)
            margin_needed = quantity * unit_cost
            available = self._available_margin() - self._reserve
            return margin_needed <= available
        except Exception:
            return False