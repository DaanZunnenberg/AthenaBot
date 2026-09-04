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
# Adds: Stein-shrinkage fair-value blending toward 0.5 plus a live multiplicative-weights spread bandit.
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

@dataclass
class _SufficientStats:
    n: int = 0
    sum_d: float = 0.0
    sum_d2: float = 0.0
    sum_lA: float = 0.0
    sum_lA2: float = 0.0
    sum_dlA: float = 0.0
    sum_lT: float = 0.0
    sum_lT2: float = 0.0
    sum_dlT: float = 0.0
    sum_lAlT: float = 0.0
    rate_level_counts: dict[float, list[int]] = None

    def __post_init__(self):
        if self.rate_level_counts is None:
            self.rate_level_counts = {}

    def add_transition(self, prev_rate, prev_ajr, prev_thr, rate, ajr, thr, rate_step):
        d = rate - prev_rate
        if prev_ajr > 0.0 and ajr > 0.0 and (prev_thr > 0.0) and (thr > 0.0):
            log_ajr = math.log(ajr / prev_ajr)
            log_thr = math.log(thr / prev_thr)
            self.n += 1
            self.sum_d += d
            self.sum_d2 += d * d
            self.sum_lA += log_ajr
            self.sum_lA2 += log_ajr * log_ajr
            self.sum_dlA += d * log_ajr
            self.sum_lT += log_thr
            self.sum_lT2 += log_thr * log_thr
            self.sum_dlT += d * log_thr
            self.sum_lAlT += log_ajr * log_thr
        if rate_step > 0:
            grid_steps = round(d / rate_step)
        else:
            grid_steps = 0.0
        counts = self.rate_level_counts.setdefault(prev_rate, [0, 0, 0])
        if grid_steps > 0:
            counts[0] += 1
        elif grid_steps < 0:
            counts[1] += 1
        else:
            counts[2] += 1

_DEFAULT_SES = {
    "se_mu_A": 0.05, "se_beta_A": 0.05,
    "se_mu_T": 0.05, "se_beta_T": 0.05,
    "se_rate_up": 0.15, "se_rate_down": 0.15,
}

@dataclass
class _FitResult:
    parameters: MarketParameters
    ses: dict = None

    def __post_init__(self):
        if self.ses is None:
            self.ses = dict(_DEFAULT_SES)

class _ParameterEstimator:
    _MIN_VAR = 1e-12
    _KAPPA_MAX = 0.5
    _KAPPA_SEARCH_STEPS = 101

    @classmethod
    def _fit_company(cls, stats):
        n = stats.n
        if n < 3:
            return {'beta_A': 0.0, 'beta_T': 0.0, 'mu_A': 0.0, 'mu_T': 0.0, 'vbar_A': 0.0001, 'vbar_T': 0.0001, 'cbar': 0.0, 'Sdd': 0.0, 'dof': max(n - 2, 1), 'dbar': 0.0, 'n': n, 'degenerate': True}
        dbar = stats.sum_d / n
        Sdd = stats.sum_d2 - n * dbar * dbar
        lAbar = stats.sum_lA / n
        lTbar = stats.sum_lT / n
        SdlA = stats.sum_dlA - n * dbar * lAbar
        SdlT = stats.sum_dlT - n * dbar * lTbar
        SlAlA = stats.sum_lA2 - n * lAbar * lAbar
        SlTlT = stats.sum_lT2 - n * lTbar * lTbar
        SlAlT = stats.sum_lAlT - n * lAbar * lTbar
        if Sdd < 1e-12:
            beta_A = beta_T = 0.0
            mu_A, mu_T = (lAbar, lTbar)
        else:
            beta_A = SdlA / Sdd
            beta_T = SdlT / Sdd
            mu_A = lAbar - beta_A * dbar
            mu_T = lTbar - beta_T * dbar
        dof = max(n - 2, 1)
        ssr_A = max(SlAlA - beta_A * SdlA, 0.0)
        ssr_T = max(SlTlT - beta_T * SdlT, 0.0)
        vbar_A = ssr_A / dof
        vbar_T = ssr_T / dof
        sum_eAeT = SlAlT - beta_A * SdlT
        cbar = sum_eAeT / dof
        return {'beta_A': beta_A, 'beta_T': beta_T, 'mu_A': mu_A, 'mu_T': mu_T, 'vbar_A': vbar_A, 'vbar_T': vbar_T, 'cbar': cbar, 'Sdd': Sdd, 'dof': dof, 'dbar': dbar, 'n': n, 'degenerate': False}

    @classmethod
    def _fisher_z_shrink_rho(cls, rho_raw, n, n0):
        if n <= 3:
            return 0.0
        rho_raw = cls._clip(rho_raw, -0.999, 0.999)
        z_hat = math.atanh(rho_raw)
        z_shrunk = (n - 3) * z_hat / ((n - 3) + n0)
        return math.tanh(z_shrunk)

    @classmethod
    def _reconstruct_sector_loadings(cls, vbar_A, vbar_T, cbar):
        if vbar_A <= cls._MIN_VAR or vbar_T <= cls._MIN_VAR:
            return (0.0, 0.0, max(vbar_A, 0.0), max(vbar_T, 0.0))
        gamma_A = math.sqrt(abs(cbar) * math.sqrt(vbar_A / vbar_T))
        gamma_T = math.copysign(math.sqrt(abs(cbar) * math.sqrt(vbar_T / vbar_A)), cbar) if cbar != 0.0 else 0.0
        if not (math.isfinite(gamma_A) and math.isfinite(gamma_T)):
            return (0.0, 0.0, max(vbar_A, 0.0), max(vbar_T, 0.0))
        sigma_A2 = max(vbar_A - gamma_A * gamma_A, 0.0)
        sigma_T2 = max(vbar_T - gamma_T * gamma_T, 0.0)
        return (gamma_A, gamma_T, sigma_A2, sigma_T2)

    @staticmethod
    def _clip(x, lo, hi):
        return min(max(x, lo), hi)

    @classmethod
    def _rate_loglik_reparam(cls, level_counts, a_up, a_down, kappa):
        ll = 0.0
        for level, (nu, nd, ns) in level_counts.items():
            up = cls._clip(a_up - kappa * level, 0.0, 1.0)
            down = cls._clip(a_down + kappa * level, 0.0, 1.0 - up)
            stay = max(1.0 - up - down, 0.0)
            if nu:
                ll += nu * math.log(max(up, 1e-12))
            if nd:
                ll += nd * math.log(max(down, 1e-12))
            if ns:
                ll += ns * math.log(max(stay, 1e-12))
        return ll

    @classmethod
    def _fit_up_down_given_kappa(cls, level_counts, kappa):
        n = sum_up = sum_down = 0
        for level, (nu, nd, ns) in level_counts.items():
            n += nu + nd + ns
            sum_up += nu + kappa * level * (nu + nd + ns)
            sum_down += nd - kappa * level * (nu + nd + ns)
        if n == 0:
            return (0.2, 0.2)
        a_up = cls._clip(sum_up / n, 1e-06, 1.0 - 1e-06)
        a_down = cls._clip(sum_down / n, 1e-06, 1.0 - a_up - 1e-06)
        return (a_up, a_down)

    @classmethod
    def _fit_rate(cls, level_counts):
        """Direct fit of the three identified parameters: up(level) = a_up - kappa*level,
        down(level) = a_down + kappa*level. Searches kappa on a 1-D grid; a_up/a_down are
        the closed-form weighted means at each kappa. Equivalent to the old 4-parameter
        model with rate_target fixed at 0 (see identity in test_rate_identification.py)."""
        total_obs = sum((sum(c) for c in level_counts.values()))
        if total_obs < 5:
            return (0.2, 0.2, 0.1)
        best = None
        for ki in range(cls._KAPPA_SEARCH_STEPS):
            kappa = cls._KAPPA_MAX * ki / (cls._KAPPA_SEARCH_STEPS - 1)
            a_up, a_down = cls._fit_up_down_given_kappa(level_counts, kappa)
            ll = cls._rate_loglik_reparam(level_counts, a_up, a_down, kappa)
            if math.isfinite(ll) and (best is None or ll > best[0]):
                best = (ll, a_up, a_down, kappa)
        if best is None:
            return (0.2, 0.2, 0.1)
        _, a_up, a_down, kappa = best
        return (a_up, a_down, kappa)

    @classmethod
    def _directional_ses(cls, company_fit):
        """Standard errors of the parameters that determine *which side of 0.5* the fair
        value should sit on (drift, rate-beta, rate up/down probabilities). Deliberately
        does not cover the volatility/correlation parameters -- those drive genuine
        payoff variance (handled separately, see MarketMaker._half_spread), whereas these
        drive epistemic (estimation) uncertainty about direction, which is what the
        confidence-gated aggression in MarketMaker is meant to measure."""
        n, Sdd, dbar = company_fit['n'], company_fit['Sdd'], company_fit['dbar']
        vbar_A, vbar_T = company_fit['vbar_A'], company_fit['vbar_T']
        if company_fit['degenerate'] or Sdd < 1e-9 or n <= 2:
            return dict(se_mu_A=0.05, se_beta_A=0.05, se_mu_T=0.05, se_beta_T=0.05)
        se_beta_A = math.sqrt(max(vbar_A, 0.0) / Sdd)
        se_beta_T = math.sqrt(max(vbar_T, 0.0) / Sdd)
        se_mu_A = math.sqrt(max(vbar_A, 0.0) * (1.0 / n + (dbar * dbar) / Sdd))
        se_mu_T = math.sqrt(max(vbar_T, 0.0) * (1.0 / n + (dbar * dbar) / Sdd))
        return dict(se_mu_A=se_mu_A, se_beta_A=se_beta_A, se_mu_T=se_mu_T, se_beta_T=se_beta_T)

    @classmethod
    def _rate_ses(cls, level_counts, a_up, a_down):
        total_obs = sum(sum(c) for c in level_counts.values())
        if total_obs < 5:
            return dict(se_rate_up=0.15, se_rate_down=0.15)
        se_up = math.sqrt(max(a_up * (1.0 - a_up), 1e-6) / total_obs)
        se_down = math.sqrt(max(a_down * (1.0 - a_down), 1e-6) / total_obs)
        return dict(se_rate_up=se_up, se_rate_down=se_down)

    @classmethod
    def fit(cls, stats):
        try:
            company_fit = cls._fit_company(stats)
            mu_A, mu_T, beta_A, beta_T = (company_fit['mu_A'], company_fit['mu_T'], company_fit['beta_A'], company_fit['beta_T'])
            vbar_A, vbar_T, cbar = (company_fit['vbar_A'], company_fit['vbar_T'], company_fit['cbar'])
            ses = cls._directional_ses(company_fit)
            if not company_fit['degenerate'] and company_fit['Sdd'] >= 1e-09 and vbar_A > 0 and (vbar_T > 0):
                rho_raw = cbar / math.sqrt(vbar_A * vbar_T)
                rho_shrunk = cls._fisher_z_shrink_rho(rho_raw, stats.n, 50.0)
                v_pool = (vbar_A + vbar_T) / 2.0
                vbar_A = 0.8 * vbar_A + 0.2 * v_pool
                vbar_T = 0.8 * vbar_T + 0.2 * v_pool
                cbar = rho_shrunk * math.sqrt(max(vbar_A, 0.0) * max(vbar_T, 0.0))
            gamma_A, gamma_T, sigma_A2, sigma_T2 = cls._reconstruct_sector_loadings(vbar_A, vbar_T, cbar)
            a_up, a_down, kappa = cls._fit_rate(stats.rate_level_counts)
            a_up = cls._clip(a_up, 1e-06, 1.0 - 1e-06)
            a_down = cls._clip(a_down, 1e-06, 1.0 - a_up - 1e-06)
            kappa = cls._clip(kappa, 0.0, 1.0)
            ses.update(cls._rate_ses(stats.rate_level_counts, a_up, a_down))
            parameters = MarketParameters(ajarai_drift=mu_A, ajarai_idio_std_dev=math.sqrt(sigma_A2), ajarai_rate_beta=beta_A, ajarai_sector_beta=gamma_A, rate_down_probability=a_down, rate_reversion_strength=kappa, rate_up_probability=a_up, sector_std_dev=1.0, theriodic_drift=mu_T, theriodic_idio_std_dev=math.sqrt(sigma_T2), theriodic_rate_beta=beta_T, theriodic_sector_beta=gamma_T, rate_step=RATE_STRIKE_GRID, rate_target=0.0)
            numeric_fields = (parameters.ajarai_drift, parameters.ajarai_idio_std_dev, parameters.ajarai_rate_beta, parameters.ajarai_sector_beta, parameters.rate_down_probability, parameters.rate_reversion_strength, parameters.rate_up_probability, parameters.sector_std_dev, parameters.theriodic_drift, parameters.theriodic_idio_std_dev, parameters.theriodic_rate_beta, parameters.theriodic_sector_beta, parameters.rate_step, parameters.rate_target)
            if not all((math.isfinite(v) for v in numeric_fields)):
                raise ValueError('fitted MarketParameters has a non-finite field')
            return _FitResult(parameters, ses)
        except Exception:
            return _FitResult(_default_market_parameters(), dict(_DEFAULT_SES))



class MarketMaker:
    """Fourth overhaul: shrink toward the naive prior, and literally learn from the
    competition instead of just trying to out-math it.

    Three overhauls in, the working theory was always "our probabilistic fair value,
    priced and spread more carefully, should beat a dumb static spread." The brief for
    this round says that theory is wrong often enough to matter: Fixed Width quoters at
    flat 0.05/0.10/0.25 half-spreads apparently do *well*. Rather than treat that as
    an inconvenience to out-clever, this version takes it as data and builds it directly
    into the pricing logic, via two ideas neither of which appeared in the last three
    versions:

    1. **Shrinkage toward 0.5 (Stein-style).** A raw fair-value estimate from a fitted
       model is a maximum-likelihood-ish point estimate; when the underlying signal is
       weak or the fit is noisy, an MLE is provably *not* the estimator with lowest
       expected error -- shrinking it toward a fixed, data-independent anchor typically
       is (this is the substance of Stein's paradox / James-Stein estimation). 0.5 is
       exactly the anchor a Fixed Width quoter implicitly assumes. So instead of either
       "trust the model" or "ignore the model," the bot blends:
       `p_shrunk = 0.5 + confidence * (p_raw - 0.5)`
       using the same ensemble-based epistemic confidence from the last overhaul as the
       shrinkage weight. At low confidence this *is* Fixed Width's assumption; at high
       confidence it converges to the model's own view. This is a candidate explanation
       for why the naive quoters are competitive: much of the time, the model's raw
       point estimate isn't actually more accurate than 0.5, and shrinkage is what
       protects against trusting it anyway.

    2. **A live bandit over quoting strategies, run daily.** The bot now maintains four
       named "arms" -- flat half-spreads of 0.05, 0.10, and 0.25 (literal replicas of
       the Fixed Width competitors), plus an "adaptive" arm using the confidence-gated,
       shrinkage-adjusted spread from before. Once per day, it picks an arm via a
       softmax-with-exploration rule (a simplified Hedge/EXP3-style multiplicative-
       weights scheme) over each arm's running realized per-contract P&L, and quotes
       every option that day using only that arm. When a position settles, the realized
       edge is credited back to whichever arm was active when the trade was made. This
       is genuinely new behavior for this bot: rather than compute one formula and trust
       it, it runs a live experiment across strategies including its competitors' own
       playbook, and lets realized money -- not a prior belief about which approach is
       smarter -- decide which one governs quoting. It can and will spend some days
       being deliberately as "dumb" as Fixed Width, if that is what the data says wins.

    What's unchanged, deliberately: the hard solvency gates (`_worst_case_cash` /
    `_feasible_cash` / `_available_margin`), inventory skew, and the bounded/capped
    counterparty toxicity term from the last two overhauls. All four arms flow through
    the same sizing and solvency logic -- the bandit can only change price and width, on
    a bounded schedule (once per day), never bypass a risk gate. Losing money on a
    Fixed Width day just means the reward signal nudges the bandit away from it
    tomorrow, exactly as it should.
    """

    _RESERVE_FRACTION = 0.05
    _MAX_UTILISATION = 0.6
    _MAX_NET_PER_OPTION = 10
    _Q_MAX = 50

    _SKEW_K = 0.01

    # --- epistemic-uncertainty ensemble (unchanged from the last overhaul) ----------
    _ENSEMBLE_K = 10          # ensemble draws per option per day
    _ENSEMBLE_FAST = True     # use the coarse (9-node) quadrature for ensemble reprices

    # --- adaptive-arm spread: interpolate between a tight "snipe" floor and a wide
    # "concede" band based on epistemic confidence, plus the irreducible payoff-variance
    # term -- used only when the bandit has selected the "adaptive" arm --------------
    _H_MIN = 0.01
    _H_CONCEDE = 0.20
    _H_VAR_K = 0.10
    _SIGMA_REF = 0.05         # ensemble std-dev at which confidence = 0.5

    # --- Fixed Width arms: literal replicas of the .05/.10/.25 competitors ----------
    _ARM_NAMES = ("fixed_005", "fixed_010", "fixed_025", "adaptive")
    _ARM_WIDTHS = {"fixed_005": 0.05, "fixed_010": 0.10, "fixed_025": 0.25}

    # --- daily bandit over the four arms, on realized per-contract P&L --------------
    _BANDIT_ETA = 12.0             # softmax temperature: higher = more exploitative
    _BANDIT_EPS = 0.10             # exploration floor: min per-arm selection probability
    _BANDIT_REWARD_ALPHA = 0.2     # EWMA rate for each arm's running realized P&L

    # --- small-book aggression: sizing/utilisation only, never spread ---------------
    _ENABLE_CAPITAL_SCALE = True
    _CAPITAL_SCALE_THRESHOLD = 20.0
    _CAPITAL_SCALE_FULL = 10.0
    _CAPITAL_UTIL_BOOST = 0.15

    # --- confidence-weighted sizing, applied only while the adaptive arm is active --
    _CONFIDENCE_UTIL_BOOST = 0.10

    # --- counterparty toxicity: bounded, slow, capped (unchanged) -------------------
    _ENABLE_TOXICITY = True
    _TOXICITY_TAU = 50.0
    _TOXICITY_MIN_N = 15
    _TOXICITY_CAP = 0.02
    _MARKOUT_ALPHA = 0.05
    _MARKOUT_HORIZON = 3

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
        if self._ENABLE_CAPITAL_SCALE:
            span = self._CAPITAL_SCALE_THRESHOLD - self._CAPITAL_SCALE_FULL
            self._capital_scale = min(1.0, max(0.0, (self._CAPITAL_SCALE_THRESHOLD - starting_cash) / span))
        else:
            self._capital_scale = 0.0
        self._reserve = self._RESERVE_FRACTION * starting_cash
        self._used_margin = 0.0
        self._margin_by_option = {}
        self._cash = starting_cash
        self._legacy_reserved = starting_cash
        self._day_cache = {}
        self._day_index = 0
        self.estimated_parameters = None
        self._parameter_ses = dict(_DEFAULT_SES)
        self._stats = _SufficientStats()
        self._warmed_up = False

        # toxicity/markout state
        self._markout_pending = []
        self._T_b_global = 0.0
        self._T_a_global = 0.0
        self._cp_b_sum = {}
        self._cp_b_n = {}
        self._cp_a_sum = {}
        self._cp_a_n = {}

        # bandit-over-arms state
        self._arm_reward = {name: 0.0 for name in self._ARM_NAMES}
        self._arm_pending = []
        self._active_arm = "adaptive"

    # --- lifecycle -----------------------------------------------------------------

    def on_step_advance(self, new_underlying_state, new_option_state):
        self._day_cache = {}
        self._day_index += 1
        try:
            self._settle_expired_positions(new_underlying_state, new_option_state)
        except Exception:
            pass
        try:
            if self._warmed_up:
                self._ingest_live_transition(new_underlying_state)
                self._refit()
        except Exception:
            pass
        self.underlying_state = new_underlying_state
        self.active_option_state = new_option_state
        try:
            self._precompute_day_cache()
        except Exception:
            pass
        if self._ENABLE_TOXICITY:
            try:
                self._update_markouts()
            except Exception:
                pass
        try:
            self._active_arm = self._select_arm()
        except Exception:
            self._active_arm = "adaptive"

    def on_trade(self, option, price, quantity, counterparty_id):
        try:
            debit = quantity * price if quantity > 0 else -quantity * (1.0 - price)
            self._cash -= quantity * price
            self._used_margin += debit
            self._legacy_reserved -= debit
            self._margin_by_option[option.option_id] = self._margin_by_option.get(option.option_id, 0.0) + debit
        except Exception:
            pass
        if self._ENABLE_TOXICITY:
            try:
                self._record_markout(option.option_id, quantity, price, counterparty_id)
            except Exception:
                pass
        try:
            self._record_arm_trade(option.option_id, quantity, price)
        except Exception:
            pass
        try:
            self.position.add_option_quantity(option.option_id, quantity)
        except Exception:
            pass

    def warm_up(self, market_history):
        try:
            self._ingest_history(market_history)
            self._refit()
        except Exception:
            self.estimated_parameters = _default_market_parameters()
            self._parameter_ses = dict(_DEFAULT_SES)
        self._warmed_up = True
        try:
            self._precompute_day_cache()
        except Exception:
            pass
        try:
            self._active_arm = self._select_arm()
        except Exception:
            self._active_arm = "adaptive"

    def _ingest_history(self, market_history):
        history = market_history.values_by_underlying_id
        fed = history.get(FED_FUNDS_RATE_UNDERLYING_ID, ())
        ajr = history.get(AJARAI_UNDERLYING_ID, ())
        thr = history.get(THERIODIC_UNDERLYING_ID, ())
        n = min(len(fed), len(ajr), len(thr))
        for i in range(1, n):
            if fed[i - 1] < 0 or fed[i] < 0:
                continue
            self._stats.add_transition(fed[i - 1], ajr[i - 1], thr[i - 1], fed[i], ajr[i], thr[i], RATE_STRIKE_GRID)

    def _ingest_live_transition(self, new_underlying_state):
        prev = {u.underlying_id: u.value for u in self.underlying_state}
        new = {u.underlying_id: u.value for u in new_underlying_state}
        self._stats.add_transition(
            prev[FED_FUNDS_RATE_UNDERLYING_ID], prev[AJARAI_UNDERLYING_ID], prev[THERIODIC_UNDERLYING_ID],
            new[FED_FUNDS_RATE_UNDERLYING_ID], new[AJARAI_UNDERLYING_ID], new[THERIODIC_UNDERLYING_ID],
            RATE_STRIKE_GRID,
        )

    def _refit(self):
        result = _ParameterEstimator.fit(self._stats)
        self.estimated_parameters = result.parameters
        self._parameter_ses = result.ses

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
            if self._ENABLE_TOXICITY:
                for entry in self._markout_pending:
                    if entry["option_id"] == option.option_id and entry["Y"] is None:
                        entry["Y"] = payoff
            self._resolve_arm_trades(option.option_id, payoff)
            reserved = self._margin_by_option.pop(option.option_id, 0.0)
            self._used_margin = max(0.0, self._used_margin - reserved)
            if quantity == 0:
                continue
            self._cash += quantity * payoff
            self._legacy_reserved += quantity * payoff if quantity > 0 else -quantity * (1.0 - payoff)
            self.position.option_quantity_by_option_id[option.option_id] = 0

    # --- pricing (unchanged interface, same analytic pricer) ------------------------

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
            if not getattr(self, "_warmed_up", False) or self.estimated_parameters is None:
                return 0.5
            values = {u.underlying_id: u.value for u in self.underlying_state}
            result = _BinaryOptionPricer.price(self.estimated_parameters, values, option)
            return result if math.isfinite(result) else 0.5
        except Exception:
            return 0.5

    # --- epistemic-uncertainty ensemble ----------------------------------------------

    def _epistemic_sigma(self, option):
        """Std-dev of the fair-value estimate across a small ensemble of the fitted model,
        perturbing only the *directional* parameters within their estimated standard
        errors. High disagreement across the ensemble means the point estimate of fair
        value could easily be on the wrong side of where we think it is; low disagreement
        means the ensemble is converged and we can trust the point estimate."""
        if not self._warmed_up or self.estimated_parameters is None:
            return self._SIGMA_REF * 3.0
        base = self.estimated_parameters
        ses = self._parameter_ses or _DEFAULT_SES
        values = {u.underlying_id: u.value for u in self.underlying_state}
        draws = []
        for _ in range(self._ENSEMBLE_K):
            try:
                up = min(max(random.gauss(base.rate_up_probability, ses.get("se_rate_up", 0.15)), 1e-4), 0.98)
                down = min(max(random.gauss(base.rate_down_probability, ses.get("se_rate_down", 0.15)), 1e-4), 0.98 - up)
                perturbed = replace(
                    base,
                    ajarai_drift=random.gauss(base.ajarai_drift, ses.get("se_mu_A", 0.05)),
                    ajarai_rate_beta=random.gauss(base.ajarai_rate_beta, ses.get("se_beta_A", 0.05)),
                    theriodic_drift=random.gauss(base.theriodic_drift, ses.get("se_mu_T", 0.05)),
                    theriodic_rate_beta=random.gauss(base.theriodic_rate_beta, ses.get("se_beta_T", 0.05)),
                    rate_up_probability=up,
                    rate_down_probability=down,
                )
                p = _BinaryOptionPricer.price(perturbed, values, option, fast=self._ENSEMBLE_FAST)
                if math.isfinite(p):
                    draws.append(p)
            except Exception:
                continue
        if len(draws) < 3:
            return self._SIGMA_REF * 3.0
        mean = sum(draws) / len(draws)
        var = sum((d - mean) ** 2 for d in draws) / len(draws)
        return math.sqrt(var)

    def _confidence(self, sigma):
        """Maps epistemic sigma to a [0, 1] confidence score; 1.0 at sigma=0 (ensemble
        fully agrees), asymptotically 0 as sigma grows (ensemble disagrees wildly).
        `_SIGMA_REF` is the sigma at which confidence == 0.5, and is the one constant
        worth recalibrating against observed ensemble spread if this is deployed live."""
        return 1.0 / (1.0 + (sigma / self._SIGMA_REF) ** 2)

    def _precompute_day_cache(self):
        for option in self.active_option_state:
            self._ensure_cached(option)

    def _ensure_cached(self, option):
        entry = self._day_cache.get(option.option_id)
        if entry is not None:
            return entry
        fair = self.price_option(option)
        sigma = self._epistemic_sigma(option)
        entry = {"P": fair, "sigma": sigma}
        self._day_cache[option.option_id] = entry
        return entry

    # --- solvency (unchanged: this is what stopped bankruptcies) --------------------

    def _net_position(self, option_id):
        return self.position.option_quantity_by_option_id.get(option_id, 0)

    def _utilisation_cap(self, confidence):
        """Margin willing to be used scales with the small-book boost (unchanged from
        the previous overhaul) always, and with confidence only while the *adaptive*
        arm is active -- confidence is a claim about our own model's directional view,
        which isn't what's being quoted when a Fixed Width arm is active. Neither ever
        relaxes the hard solvency gates below, only how much of the *available* margin
        we choose to use."""
        cap = self._MAX_UTILISATION
        if self._ENABLE_CAPITAL_SCALE:
            cap += self._CAPITAL_UTIL_BOOST * self._capital_scale
        if self._active_arm == "adaptive":
            cap += self._CONFIDENCE_UTIL_BOOST * confidence
        return min(0.95, max(0.05, cap))

    def _margin_feasible_quantity(self, price, is_buy, confidence):
        unit_cost = price if is_buy else (1.0 - price)
        if unit_cost <= 1e-9:
            return self._Q_MAX
        headroom = min(
            self._utilisation_cap(confidence) * self._starting_cash - self._used_margin,
            self._feasible_cash() - self._reserve,
        )
        if headroom <= 0.0:
            return 0
        return max(0, int(headroom / unit_cost))

    def _size_for(self, option, price, is_buy, confidence):
        net = self._net_position(option.option_id)
        new_net = net + (1 if is_buy else -1)
        inventory_room = self._MAX_NET_PER_OPTION - abs(new_net) + 1
        if inventory_room <= 0:
            return 0
        margin_room = self._margin_feasible_quantity(price, is_buy, confidence)
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

    # --- bandit over quoting arms: pick your strategy, not just your price -----------

    def _half_spread(self, fair, confidence):
        """Adaptive-arm spread only: interpolates between the wide concede band and the
        tight snipe floor based on epistemic confidence, then adds the irreducible
        payoff-variance term (real Bernoulli risk, present even with a perfectly known
        model). Fixed Width arms bypass this entirely in favor of their literal width."""
        base = self._H_CONCEDE - (self._H_CONCEDE - self._H_MIN) * confidence
        payoff_variance_term = self._H_VAR_K * 4.0 * fair * (1.0 - fair)
        return base + payoff_variance_term

    def _toxicity(self, counterparty_id, confidence):
        """Bounded, slow counterparty adverse-selection estimate, hard-capped and scaled
        by epistemic confidence -- applied as a small, safety-motivated addition on top
        of whichever arm is quoting, including the literal Fixed Width arms."""
        if not self._ENABLE_TOXICITY:
            return 0.0, 0.0
        n_b = self._cp_b_n.get(counterparty_id, 0)
        n_a = self._cp_a_n.get(counterparty_id, 0)
        w_b = n_b / (n_b + self._TOXICITY_TAU) if n_b >= self._TOXICITY_MIN_N else 0.0
        w_a = n_a / (n_a + self._TOXICITY_TAU) if n_a >= self._TOXICITY_MIN_N else 0.0
        local_b = self._cp_b_sum.get(counterparty_id, 0.0) / n_b if n_b else 0.0
        local_a = self._cp_a_sum.get(counterparty_id, 0.0) / n_a if n_a else 0.0
        raw_b = w_b * local_b + (1.0 - w_b) * self._T_b_global
        raw_a = w_a * local_a + (1.0 - w_a) * self._T_a_global
        t_b = min(max(raw_b, 0.0), self._TOXICITY_CAP) * confidence
        t_a = min(max(raw_a, 0.0), self._TOXICITY_CAP) * confidence
        return t_b, t_a

    def _select_arm(self):
        """Softmax-with-exploration selection over the four arms' running realized
        per-contract P&L (a simplified Hedge/EXP3-style multiplicative-weights rule).
        `_BANDIT_EPS` guarantees every arm, including the ones currently losing, keeps
        getting sampled occasionally -- a regime that favored Fixed Width yesterday can
        stop favoring it tomorrow, and the bandit needs live data on all four to notice."""
        rewards = self._arm_reward
        max_r = max(rewards.values())
        exp_weights = {name: math.exp(self._BANDIT_ETA * (r - max_r)) for name, r in rewards.items()}
        total = sum(exp_weights.values())
        n = len(self._ARM_NAMES)
        if total <= 0.0 or not math.isfinite(total):
            probs = {name: 1.0 / n for name in self._ARM_NAMES}
        else:
            probs = {
                name: (1.0 - self._BANDIT_EPS) * (exp_weights[name] / total) + self._BANDIT_EPS / n
                for name in self._ARM_NAMES
            }
        draw = random.random()
        cumulative = 0.0
        for name in self._ARM_NAMES:
            cumulative += probs[name]
            if draw <= cumulative:
                return name
        return self._ARM_NAMES[-1]

    def _mid_and_spreads(self, option, counterparty_id):
        """Prices `option` using whichever arm the daily bandit currently has active.
        Fixed Width arms are literal replicas of the .05/.10/.25 competitors: flat
        half-spread around 0.5, adjusted only by our own inventory skew (a safety
        feature kept active regardless of pricing philosophy). The adaptive arm applies
        Stein-style shrinkage of the raw fair value toward 0.5 by the epistemic
        confidence -- at low confidence this converges to exactly what the Fixed Width
        arms assume; at high confidence it converges to the model's own view."""
        cached = self._ensure_cached(option)
        fair = min(max(cached["P"], 0.0), 1.0)
        confidence = self._confidence(cached["sigma"])
        net = self._net_position(option.option_id)
        skew = self._SKEW_K * net
        if self._active_arm == "adaptive":
            shrunk = 0.5 + confidence * (fair - 0.5)
            mid = min(max(shrunk - skew, 0.0), 1.0)
            base_h = self._half_spread(shrunk, confidence)
        else:
            mid = min(max(0.5 - skew, 0.0), 1.0)
            base_h = self._ARM_WIDTHS[self._active_arm]
        t_b, t_a = self._toxicity(counterparty_id, confidence)
        return mid, base_h + t_b, base_h + t_a, confidence

    def quote(self, option, counterparty_id):
        try:
            if self._available_margin() - self._reserve <= 0:
                return self._risk_free_quote()
            mid, h_bid, h_ask, confidence = self._mid_and_spreads(option, counterparty_id)
            bid_price, offer_price = self._round_quote_prices(max(0.0, mid - h_bid), min(1.0, mid + h_ask))
            if bid_price < 0.0:
                return self._risk_free_quote()
            q_bid = self._size_for(option, bid_price, True, confidence)
            q_ask = self._size_for(option, offer_price, False, confidence)
            if q_bid <= 0:
                bid_price, q_bid = 0.0, self._Q_MAX
            if q_ask <= 0:
                offer_price, q_ask = 1.0, self._Q_MAX
            return Quote(bid_price=bid_price, bid_quantity=q_bid, offer_price=offer_price, offer_quantity=q_ask)
        except Exception:
            return self._risk_free_quote()

    def respond_to_fok(self, option, fok_order):
        """Uses the exact same confidence-gated mid/half-spread as `quote`, so a FOK is
        accepted iff its price is at least as good as the price we would have quoted
        ourselves -- including the same "pick your battles" gating: a low-confidence
        option effectively can't be FOK'd into at a price we'd regret, since our own
        reference price has already widened to the concede band."""
        try:
            mid, h_bid, h_ask, confidence = self._mid_and_spreads(option, fok_order.counterparty_id)
            is_buy_side = fok_order.order_type == OrderType.SELL  # counterparty sells -> we buy
            if is_buy_side:
                our_price = round(max(0.0, mid - h_bid), 2)
                if fok_order.price > our_price:
                    return False
                price = fok_order.price
            else:
                our_price = round(min(1.0, mid + h_ask), 2)
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

    # --- toxicity bookkeeping --------------------------------------------------------

    def _record_markout(self, option_id, quantity, price, counterparty_id):
        p_t = self._day_cache.get(option_id, {}).get("P")
        self._markout_pending.append({
            "option_id": option_id,
            "side": "buy" if quantity > 0 else "sell",
            "price": price,
            "quantity": abs(quantity),
            "counterparty_id": counterparty_id,
            "day": self._day_index,
            "P_t": p_t,
            "M": {},
            "Y": None,
        })

    def _update_markouts(self):
        still_pending = []
        for entry in self._markout_pending:
            elapsed = self._day_index - entry["day"]
            if 1 <= elapsed <= self._MARKOUT_HORIZON and elapsed not in entry["M"]:
                cached = self._day_cache.get(entry["option_id"])
                if cached is not None and entry["P_t"] is not None:
                    entry["M"][elapsed] = cached["P"] - entry["P_t"]
            if elapsed >= self._MARKOUT_HORIZON or entry["Y"] is not None:
                self._finalize_markout(entry)
                continue
            still_pending.append(entry)
        self._markout_pending = still_pending

    def _finalize_markout(self, entry):
        values = [v for v in entry["M"].values() if v is not None]
        if not values:
            return
        m = sum(values) / len(values)
        cid = entry["counterparty_id"]
        alpha = self._MARKOUT_ALPHA
        if entry["side"] == "buy":
            obs = -m
            self._T_b_global = alpha * obs + (1.0 - alpha) * self._T_b_global
            self._cp_b_sum[cid] = self._cp_b_sum.get(cid, 0.0) + obs
            self._cp_b_n[cid] = self._cp_b_n.get(cid, 0) + 1
        else:
            obs = m
            self._T_a_global = alpha * obs + (1.0 - alpha) * self._T_a_global
            self._cp_a_sum[cid] = self._cp_a_sum.get(cid, 0.0) + obs
            self._cp_a_n[cid] = self._cp_a_n.get(cid, 0) + 1

    # --- bandit reward bookkeeping ----------------------------------------------------

    def _record_arm_trade(self, option_id, quantity, price):
        """Tags every fill with the arm that was active when it was made. Multiple
        trades on the same option_id across its life can carry different arm tags, since
        the bandit can switch arms daily while an option is still alive."""
        self._arm_pending.append({
            "option_id": option_id,
            "quantity": quantity,
            "price": price,
            "arm": self._active_arm,
        })

    def _resolve_arm_trades(self, option_id, payoff):
        """Credits each pending trade on `option_id` to its tagged arm's running
        realized per-contract P&L, using the option's true settlement payoff -- the
        bandit's reward signal is always actual realized money, never a hypothetical."""
        remaining = []
        for entry in self._arm_pending:
            if entry["option_id"] != option_id:
                remaining.append(entry)
                continue
            price, quantity, arm = entry["price"], entry["quantity"], entry["arm"]
            pnl = (payoff - price) if quantity > 0 else (price - payoff)
            prev = self._arm_reward.get(arm, 0.0)
            self._arm_reward[arm] = self._BANDIT_REWARD_ALPHA * pnl + (1.0 - self._BANDIT_REWARD_ALPHA) * prev
        self._arm_pending = remaining