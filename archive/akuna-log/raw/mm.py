import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

from src.taqf.akuna.market_types import (  # noqa: E402
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    FokOrder,
    MarketHistory,
    MarketParameters,
    OrderType,
    Position,
    Quote,
    Underlying,
)

_SQRT_2PI = math.sqrt(2.0 * math.pi)
_QUAD_NODES = tuple(-8.0 + 0.125 * i for i in range(129))
_QUAD_STEP = 0.125


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _phi(u: float) -> float:
    return math.exp(-0.5 * u * u) / _SQRT_2PI


def _prob_ge(mean_log: float, sd: float, threshold: float) -> float:
    if sd < 1e-12:
        return 1.0 if math.exp(mean_log) >= threshold else 0.0
    if threshold <= 0:
        return 1.0
    return _norm_cdf((mean_log - math.log(threshold)) / sd)


def _prob_le(mean_log: float, sd: float, threshold: float) -> float:
    if sd < 1e-12:
        return 1.0 if math.exp(mean_log) <= threshold else 0.0
    if threshold <= 0:
        return 0.0
    return _norm_cdf((math.log(threshold) - mean_log) / sd)


def _single_leg_prob(mean_log: float, sd: float, weight: float, effective_strike: float) -> float:
    # condition: weight * V >= effective_strike, with cent-rounding correction applied by caller
    if weight > 0:
        return _prob_ge(mean_log, sd, effective_strike / weight)
    return _prob_le(mean_log, sd, effective_strike / weight)


def _two_leg_prob(mean_a, sd_a, mean_t, sd_t, cov, w_a, w_t, kp) -> float:
    var_a = sd_a * sd_a
    var_t = sd_t * sd_t
    if sd_a < 1e-12 and sd_t < 1e-12:
        a = math.exp(mean_a)
        t = math.exp(mean_t)
        return 1.0 if w_a * a + w_t * t >= kp else 0.0
    if sd_a < 1e-12:
        a = math.exp(mean_a)
        return _single_leg_prob(mean_t, sd_t, w_t, kp - w_a * a)
    if sd_t < 1e-12:
        t = math.exp(mean_t)
        return _single_leg_prob(mean_a, sd_a, w_a, kp - w_t * t)

    rho = cov / (sd_a * sd_t)
    rho = max(-0.999, min(0.999, rho))

    if abs(kp) < 1e-9 and w_a * w_t < 0:
        diff_var = max(var_a + var_t - 2.0 * cov, 0.0)
        sd_diff = math.sqrt(diff_var)
        if w_a > 0:
            diff_mean = mean_a - mean_t
            thr = math.log(-w_t / w_a)
        else:
            diff_mean = mean_t - mean_a
            thr = math.log(-w_a / w_t)
        if sd_diff < 1e-12:
            return 1.0 if diff_mean >= thr else 0.0
        return _norm_cdf((diff_mean - thr) / sd_diff)

    total = 0.0
    n = len(_QUAD_NODES)
    for i, u in enumerate(_QUAD_NODES):
        a = math.exp(mean_a + sd_a * u)
        kp2 = kp - w_a * a
        m2 = mean_t + rho * sd_t * u
        s2 = sd_t * math.sqrt(max(1.0 - rho * rho, 1e-12))
        if w_t > 0:
            g = _prob_ge(m2, s2, kp2 / w_t)
        else:
            g = _prob_le(m2, s2, kp2 / w_t)
        weight = _QUAD_STEP if 0 < i < n - 1 else _QUAD_STEP / 2.0
        total += weight * _phi(u) * g
    return min(max(total, 0.0), 1.0)


def _fed_lattice(r0, p_u, p_d, k, rate_step, rate_target, steps):
    dist = {r0: 1.0}
    for _ in range(steps):
        nxt = defaultdict(float)
        for r, p in dist.items():
            if p <= 0:
                continue
            tilt = k * (rate_target - r)
            up = min(max(p_u + tilt, 0.0), 1.0)
            down = min(max(p_d - tilt, 0.0), 1.0 - up)
            stay = 1.0 - up - down
            r_up = round(r + rate_step, 2)
            r_down = max(round(r - rate_step, 2), 0.0)
            nxt[r_up] += p * up
            nxt[r_down] += p * down
            nxt[r] += p * stay
        dist = dict(nxt)
    return dist


class MarketMaker:
    def __init__(self, underlying_initial_state, option_initial_state, cash_balance) -> None:
        self.underlying_state = underlying_initial_state
        self.active_option_state = option_initial_state
        self.cash_balance = cash_balance
        self.position = Position()

        self._realized_cash = float(cash_balance)
        self._reserve_buffer = 0.15 * float(cash_balance)
        self._engine = self._default_engine()
        self._n_obs = 0
        self._se_var_rel = 1.0
        self._se_mu_a = 0.01
        self._se_mu_t = 0.01
        self._se_pu = 0.1
        self._se_pd = 0.1
        self._se_k = 0.1
        self._param_version = 0
        self._unc_cache = {}

    # ---------------------------------------------------------------- state

    def on_step_advance(self, new_underlying_state, new_option_state) -> None:
        try:
            new_ids = {o.option_id for o in new_option_state}
            value_by_id = {u.underlying_id: u.value for u in new_underlying_state}
            for opt in self.active_option_state:
                if opt.option_id in new_ids:
                    continue
                qty = self.position.option_quantity_by_option_id.get(opt.option_id, 0)
                if qty == 0:
                    continue
                payoff = opt.expiry_valuation(value_by_id)
                if qty >= 0:
                    self._realized_cash += qty * payoff
                else:
                    self._realized_cash += (-qty) * (1.0 - payoff)
                self.position.option_quantity_by_option_id[opt.option_id] = 0
        except Exception:
            pass
        self.underlying_state = new_underlying_state
        self.active_option_state = new_option_state
        self._param_version += 1
        self._unc_cache.clear()

    def on_trade(self, option, price, quantity, counterparty_id) -> None:
        try:
            debit = quantity * price if quantity > 0 else (-quantity) * (1.0 - price)
            self._realized_cash -= debit
        except Exception:
            pass
        self.position.add_option_quantity(option.option_id, quantity)

    @property
    def name(self) -> str:
        return "AthenaBot"

    # -------------------------------------------------------------- pricing

    def _default_engine(self):
        return {
            "mu_a": 0.0, "beta_r_a": 0.0, "var_a": 0.0004,
            "mu_t": 0.0, "beta_r_t": 0.0, "var_t": 0.0004,
            "cov": 0.0,
            "p_u": 0.2, "p_d": 0.2, "k": 0.1,
            "rate_step": 0.25, "rate_target": 2.0,
        }

    def _engine_from_parameters(self, mp: MarketParameters):
        return {
            "mu_a": mp.ajarai_drift,
            "beta_r_a": mp.ajarai_rate_beta,
            "var_a": mp.ajarai_sector_beta ** 2 * mp.sector_std_dev ** 2 + mp.ajarai_idio_std_dev ** 2,
            "mu_t": mp.theriodic_drift,
            "beta_r_t": mp.theriodic_rate_beta,
            "var_t": mp.theriodic_sector_beta ** 2 * mp.sector_std_dev ** 2 + mp.theriodic_idio_std_dev ** 2,
            "cov": mp.ajarai_sector_beta * mp.theriodic_sector_beta * mp.sector_std_dev ** 2,
            "p_u": mp.rate_up_probability,
            "p_d": mp.rate_down_probability,
            "k": mp.rate_reversion_strength,
            "rate_step": mp.rate_step,
            "rate_target": mp.rate_target,
        }

    def _underlying_values(self):
        return {u.underlying_id: u.value for u in self.underlying_state}

    def _price_with_engine(self, engine, values, option: BinaryOption) -> float:
        T = option.steps_until_expiry
        if T <= 0:
            return option.expiry_valuation(values)

        w_f = w_a = w_t = 0.0
        for leg in option.legs:
            if leg.underlying_id == FED_FUNDS_RATE_UNDERLYING_ID:
                w_f = leg.weight
            elif leg.underlying_id == AJARAI_UNDERLYING_ID:
                w_a = leg.weight
            elif leg.underlying_id == THERIODIC_UNDERLYING_ID:
                w_t = leg.weight

        r0 = values.get(FED_FUNDS_RATE_UNDERLYING_ID, engine["rate_target"])
        a0 = values.get(AJARAI_UNDERLYING_ID, 1.0)
        t0 = values.get(THERIODIC_UNDERLYING_ID, 1.0)
        a0 = a0 if a0 > 0 else 1e-9
        t0 = t0 if t0 > 0 else 1e-9

        lattice = _fed_lattice(r0, engine["p_u"], engine["p_d"], engine["k"], engine["rate_step"], engine["rate_target"], T)

        total_var_a = max(T * engine["var_a"], 0.0)
        total_var_t = max(T * engine["var_t"], 0.0)
        total_cov = T * engine["cov"]
        sd_a = math.sqrt(total_var_a)
        sd_t = math.sqrt(total_var_t)
        log_a0 = math.log(a0)
        log_t0 = math.log(t0)

        prob = 0.0
        for x, px in lattice.items():
            if px <= 0:
                continue
            dr = x - r0
            kp = option.strike - w_f * x

            if w_a == 0.0 and w_t == 0.0:
                prob += px * (1.0 if w_f * x >= option.strike else 0.0)
                continue

            mean_a = log_a0 + T * engine["mu_a"] + engine["beta_r_a"] * dr
            mean_t = log_t0 + T * engine["mu_t"] + engine["beta_r_t"] * dr

            if w_t == 0.0:
                thr = kp / w_a
                thr = thr - 0.005 if w_a > 0 else thr + 0.005
                c = _single_leg_prob(mean_a, sd_a, w_a, thr * w_a)
            elif w_a == 0.0:
                thr = kp / w_t
                thr = thr - 0.005 if w_t > 0 else thr + 0.005
                c = _single_leg_prob(mean_t, sd_t, w_t, thr * w_t)
            else:
                c = _two_leg_prob(mean_a, sd_a, mean_t, sd_t, total_cov, w_a, w_t, kp)

            prob += px * c

        return min(max(prob, 0.0), 1.0)

    def price_option_from_parameters(self, market_parameters: MarketParameters, option: BinaryOption) -> float:
        try:
            engine = self._engine_from_parameters(market_parameters)
            return self._price_with_engine(engine, self._underlying_values(), option)
        except Exception:
            return 0.5

    def warm_up(self, market_history: MarketHistory) -> None:
        try:
            self._fit(market_history)
        except Exception:
            self._engine = self._default_engine()
        finally:
            self._param_version += 1
            self._unc_cache.clear()

    def price_option(self, option: BinaryOption) -> float:
        try:
            return self._price_with_engine(self._engine, self._underlying_values(), option)
        except Exception:
            return 0.5

    # ----------------------------------------------------------- estimation

    def _fit(self, market_history: MarketHistory) -> None:
        hist = market_history.values_by_underlying_id
        fed = hist.get(FED_FUNDS_RATE_UNDERLYING_ID, ())
        ajr = hist.get(AJARAI_UNDERLYING_ID, ())
        thr = hist.get(THERIODIC_UNDERLYING_ID, ())
        n_days = min(len(fed), len(ajr), len(thr))
        if n_days < 3:
            self._engine = self._default_engine()
            self._n_obs = 0
            return

        n_obs = n_days - 1

        # --- rate_step inference
        deltas = [round(fed[i + 1] - fed[i], 2) for i in range(n_obs)]
        nonzero = [abs(d) for d in deltas if abs(d) > 1e-9]
        rate_step = min(nonzero) if nonzero else 0.25

        # --- rate MLE grid search bucketed by level
        by_level = defaultdict(lambda: [0.0, 0.0, 0.0])  # up, down, stay (pseudo-counted)
        for i in range(n_obs):
            r = fed[i]
            d = deltas[i]
            counts = by_level[r]
            if d > 1e-9:
                counts[0] += 1.0
            elif d < -1e-9:
                counts[1] += 1.0
            else:
                counts[2] += 1.0

        levels = sorted(by_level.keys())
        targets = sorted(set(levels)) or [2.0]
        if len(targets) > 6:
            step = len(targets) / 6.0
            targets = [targets[int(i * step)] for i in range(6)]
        mean_r = sum(fed[:n_obs]) / n_obs
        if mean_r not in targets:
            targets.append(mean_r)

        def log_lik(p_u, p_d, k, target):
            ll = 0.0
            for r in levels:
                up_c, down_c, stay_c = by_level[r]
                tilt = k * (target - r)
                up = min(max(p_u + tilt, 0.0), 1.0)
                down = min(max(p_d - tilt, 0.0), 1.0 - up)
                stay = 1.0 - up - down
                if r <= 1e-9:
                    # a down draw at the floor is indistinguishable from a stay
                    no_change = stay + down
                    ll += (up_c + 0.1) * math.log(max(up, 1e-9))
                    ll += (down_c + stay_c + 0.1) * math.log(max(no_change, 1e-9))
                else:
                    ll += (up_c + 0.1) * math.log(max(up, 1e-9))
                    ll += (down_c + 0.1) * math.log(max(down, 1e-9))
                    ll += (stay_c + 0.1) * math.log(max(stay, 1e-9))
            return ll

        best = (None, None, None, None, -1e18)
        coarse = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
        k_grid = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]
        for target in targets:
            for p_u in coarse:
                for p_d in coarse:
                    if p_u + p_d > 1.0:
                        continue
                    for k in k_grid:
                        ll = log_lik(p_u, p_d, k, target)
                        if ll > best[4]:
                            best = (p_u, p_d, k, target, ll)

        p_u, p_d, k, target, best_ll = best
        for _ in range(2):
            span_p = 0.05
            span_k = 0.05
            for cand_pu in (p_u - span_p, p_u, p_u + span_p):
                for cand_pd in (p_d - span_p, p_d, p_d + span_p):
                    if cand_pu <= 0 or cand_pd <= 0 or cand_pu + cand_pd > 1.0:
                        continue
                    for cand_k in (max(0.0, k - span_k), k, min(1.0, k + span_k)):
                        ll = log_lik(cand_pu, cand_pd, cand_k, target)
                        if ll > best_ll:
                            best_ll = ll
                            p_u, p_d, k = cand_pu, cand_pd, cand_k

        # --- company regressions
        n_rate = min(n_obs, len(ajr) - 1)
        la = [math.log(ajr[i + 1] / ajr[i]) for i in range(n_rate) if ajr[i] > 0 and ajr[i + 1] > 0]
        lt = [math.log(thr[i + 1] / thr[i]) for i in range(n_rate) if thr[i] > 0 and thr[i + 1] > 0]
        m = min(len(la), len(lt), n_rate)
        la = la[:m]
        lt = lt[:m]
        dr = deltas[:m]

        if m < 2:
            mu_a = mu_t = 0.0
            beta_r_a = beta_r_t = 0.0
            var_a = var_t = 0.0004
            cov = 0.0
            se_mu_a = se_mu_t = 0.01
        else:
            mean_dr = sum(dr) / m
            var_dr = sum((d - mean_dr) ** 2 for d in dr) / m
            mean_la = sum(la) / m
            mean_lt = sum(lt) / m
            cov_la_dr = sum((la[i] - mean_la) * (dr[i] - mean_dr) for i in range(m)) / m
            cov_lt_dr = sum((lt[i] - mean_lt) * (dr[i] - mean_dr) for i in range(m)) / m

            beta_r_a_raw = cov_la_dr / var_dr if var_dr > 1e-10 else 0.0
            beta_r_t_raw = cov_lt_dr / var_dr if var_dr > 1e-10 else 0.0
            alpha_a_raw = mean_la - beta_r_a_raw * mean_dr
            alpha_t_raw = mean_lt - beta_r_t_raw * mean_dr

            shrink_drift = m / (m + 25.0)
            shrink_beta = m / (m + 15.0)
            mu_a = alpha_a_raw * shrink_drift
            mu_t = alpha_t_raw * shrink_drift
            beta_r_a = beta_r_a_raw * shrink_beta
            beta_r_t = beta_r_t_raw * shrink_beta

            res_a = [la[i] - mu_a - beta_r_a * dr[i] for i in range(m)]
            res_t = [lt[i] - mu_t - beta_r_t * dr[i] for i in range(m)]
            mean_res_a = sum(res_a) / m
            mean_res_t = sum(res_t) / m
            var_a_raw = sum((r - mean_res_a) ** 2 for r in res_a) / m
            var_t_raw = sum((r - mean_res_t) ** 2 for r in res_t) / m
            cov_raw = sum((res_a[i] - mean_res_a) * (res_t[i] - mean_res_t) for i in range(m)) / m

            var_a = min(max(var_a_raw, 1e-8), 1.0)
            var_t = min(max(var_t_raw, 1e-8), 1.0)
            if var_a_raw > 1e-12 and var_t_raw > 1e-12:
                corr = cov_raw / math.sqrt(var_a_raw * var_t_raw)
            else:
                corr = 0.0
            corr *= m / (m + 20.0)
            corr = max(-0.999, min(0.999, corr))
            cov = corr * math.sqrt(var_a * var_t)

            se_mu_a = math.sqrt(var_a / m)
            se_mu_t = math.sqrt(var_t / m)

        self._engine = {
            "mu_a": mu_a, "beta_r_a": beta_r_a, "var_a": var_a,
            "mu_t": mu_t, "beta_r_t": beta_r_t, "var_t": var_t,
            "cov": cov,
            "p_u": p_u, "p_d": p_d, "k": k,
            "rate_step": rate_step, "rate_target": target,
        }
        self._n_obs = m
        self._se_var_rel = 1.0 / math.sqrt(max(2 * m, 1))
        self._se_mu_a = se_mu_a
        self._se_mu_t = se_mu_t
        self._se_pu = math.sqrt(max(p_u * (1 - p_u), 1e-6) / max(n_obs, 1))
        self._se_pd = math.sqrt(max(p_d * (1 - p_d), 1e-6) / max(n_obs, 1))
        self._se_k = 0.1

    # --------------------------------------------------------- uncertainty

    def _get_uncertainty(self, option: BinaryOption) -> float:
        try:
            r0 = round(self._underlying_values().get(FED_FUNDS_RATE_UNDERLYING_ID, 0.0), 2)
            a0 = round(self._underlying_values().get(AJARAI_UNDERLYING_ID, 0.0), 2)
            t0 = round(self._underlying_values().get(THERIODIC_UNDERLYING_ID, 0.0), 2)
            key = (option.option_id, option.steps_until_expiry, r0, a0, t0, self._param_version)
            cached = self._unc_cache.get(key)
            if cached is not None:
                return cached
            sigma = self._compute_uncertainty(option)
            self._unc_cache[key] = sigma
            return sigma
        except Exception:
            return 0.05

    def _compute_uncertainty(self, option: BinaryOption) -> float:
        values = self._underlying_values()
        base = self._engine
        fair = self._price_with_engine(base, values, option)

        def dev(engine2):
            return abs(self._price_with_engine(engine2, values, option) - fair)

        rel = self._se_var_rel
        vol_dev = 0.0
        for factor in (1.0 + rel, max(1.0 - rel, 0.0)):
            e2 = dict(base)
            e2["var_a"] *= factor
            e2["var_t"] *= factor
            e2["cov"] *= factor
            vol_dev = max(vol_dev, dev(e2))

        drift_dev = 0.0
        for s_a in (1, -1):
            for s_t in (1, -1):
                e2 = dict(base)
                e2["mu_a"] += s_a * self._se_mu_a
                e2["mu_t"] += s_t * self._se_mu_t
                drift_dev = max(drift_dev, dev(e2))

        rate_dev = 0.0
        for s_u in (1, -1):
            for s_d in (1, -1):
                e2 = dict(base)
                e2["p_u"] = min(max(base["p_u"] + s_u * self._se_pu, 0.0), 1.0)
                e2["p_d"] = min(max(base["p_d"] + s_d * self._se_pd, 0.0), 1.0 - e2["p_u"])
                rate_dev = max(rate_dev, dev(e2))

        k_dev = 0.0
        for s_k in (1, -1):
            e2 = dict(base)
            e2["k"] = min(max(base["k"] + s_k * self._se_k, 0.0), 1.0)
            k_dev = max(k_dev, dev(e2))

        return math.sqrt(vol_dev ** 2 + drift_dev ** 2 + rate_dev ** 2 + k_dev ** 2)

    # --------------------------------------------------------------- risk

    def _max_qty(self, cost_per_contract: float, cap: int = 25) -> int:
        headroom = self._realized_cash - self._reserve_buffer
        if headroom <= 0 or cost_per_contract <= 1e-9:
            return 0
        qty = int(headroom / cost_per_contract)
        return max(0, min(cap, qty))

    def _fok_allowed(self, debit: float) -> bool:
        return (self._realized_cash - debit) >= self._reserve_buffer

    # ------------------------------------------------------------- quoting

    _DEGENERATE = None  # set lazily to avoid constructing Quote at class body time

    def quote(self, option: BinaryOption, counterparty_id: int) -> Quote:
        try:
            fair = self.price_option(option)
            p = min(max(fair, 0.0), 1.0)
            sigma = self._get_uncertainty(option)

            half_spread = 0.01 + 1.5 * sigma + 0.15 * math.sqrt(max(p * (1.0 - p), 0.0))
            position = self.position.option_quantity_by_option_id.get(option.option_id, 0)
            skew = -0.02 * position * max(p * (1.0 - p), 0.0)
            skew = max(-0.2, min(0.2, skew))
            reservation = min(max(p + skew, 0.0), 1.0)

            bid = max(0.0, reservation - half_spread)
            offer = min(1.0, reservation + half_spread)
            bid_c = math.floor(bid * 100.0) / 100.0
            offer_c = math.ceil(offer * 100.0) / 100.0
            if bid_c >= offer_c:
                offer_c = min(1.0, bid_c + 0.01)
                if bid_c >= offer_c:
                    bid_c = max(0.0, offer_c - 0.01)
            bid_c = round(bid_c, 2)
            offer_c = round(offer_c, 2)

            bid_qty = self._max_qty(bid_c) if bid_c > 0 else 25
            offer_qty = self._max_qty(1.0 - offer_c) if offer_c < 1.0 else 25
            bid_qty = max(1, bid_qty) if bid_c == 0.0 else bid_qty
            offer_qty = max(1, offer_qty) if offer_c == 1.0 else offer_qty

            if bid_qty <= 0 and offer_qty <= 0:
                return Quote(bid_price=0.0, bid_quantity=1, offer_price=1.0, offer_quantity=1)
            if bid_qty <= 0:
                bid_c, bid_qty = 0.0, 1
            if offer_qty <= 0:
                offer_c, offer_qty = 1.0, 1
            if bid_c >= offer_c:
                return Quote(bid_price=0.0, bid_quantity=1, offer_price=1.0, offer_quantity=1)

            return Quote(bid_price=bid_c, bid_quantity=bid_qty, offer_price=offer_c, offer_quantity=offer_qty)
        except Exception:
            return Quote(bid_price=0.0, bid_quantity=1, offer_price=1.0, offer_quantity=1)

    def respond_to_fok(self, option: BinaryOption, fok_order: FokOrder) -> bool:
        try:
            fair = self.price_option(option)
            sigma = self._get_uncertainty(option)
            margin = min(0.3, 2.5 * sigma + 0.002 * fok_order.quantity)

            if fok_order.order_type == OrderType.BUY:
                # counterparty buys from us -> we sell
                edge_ok = fok_order.price >= fair + margin
                debit = fok_order.quantity * (1.0 - fok_order.price)
            else:
                edge_ok = fok_order.price <= fair - margin
                debit = fok_order.quantity * fok_order.price

            if not edge_ok:
                return False
            return self._fok_allowed(debit)
        except Exception:
            return False
