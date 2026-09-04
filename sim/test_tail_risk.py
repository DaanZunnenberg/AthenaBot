"""
Part D4: joint-tail CVaR diagnostic, reusing the existing scenario set (self._scenario_Y,
positions, entry prices) that MarketMaker already builds for indifference pricing. Implemented
here as a read-only offline diagnostic (not wired into Bot.py's live decision path -- see
debug/TAIL_RISK.md for why D1-D3's portfolio risk budget was scoped out of this pass and D4
was kept diagnostic-only, per the task's own framing "log ... as an audit signal, not a new
constraint"). Run with: python3.11 sim/test_tail_risk.py
"""
from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import (  # noqa: E402
    AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
    BinaryOption, MarketParameters, OptionLeg, Underlying, MarketMaker,
)

ALPHA = 0.99


def book_pi(mm, positions, entry_prices):
    """positions: {option_id: signed qty}. Returns per-scenario book P&L list."""
    S = mm._S
    pi = [0.0] * S
    for oid, q in positions.items():
        Y = mm._scenario_Y.get(oid)
        if not Y:
            continue
        pe = entry_prices.get(oid, 0.5)
        for s in range(S):
            pi[s] += q * (Y[s] - pe)
    return pi


def cvar(pi, alpha=ALPHA):
    s = sorted(pi)
    S = len(s)
    k = max(1, math.ceil((1.0 - alpha) * S))
    var = -s[k - 1]
    cv = -sum(s[:k]) / k
    return var, cv


def concentration(mm, positions, entry_prices, alpha=ALPHA):
    _, cvar_book = cvar(book_pi(mm, positions, entry_prices), alpha)
    total_marginal = 0.0
    for oid, q in positions.items():
        _, cv_j = cvar(book_pi(mm, {oid: q}, entry_prices), alpha)
        total_marginal += cv_j
    if total_marginal <= 1e-9:
        return (cvar_book, total_marginal, None)
    return (cvar_book, total_marginal, cvar_book / total_marginal)


def _setup(rho_at, sector_beta_a=1.0, sector_beta_t=1.0):
    underlyings = [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
                   Underlying("AJR", AJARAI_UNDERLYING_ID, 500.0),
                   Underlying("THR", THERIODIC_UNDERLYING_ID, 600.0)]
    mm = MarketMaker(underlyings, [], 100.0)
    mm.estimated_parameters = MarketParameters(
        ajarai_drift=0.0, ajarai_idio_std_dev=0.01 * math.sqrt(max(1.0 - rho_at, 1e-6)),
        ajarai_rate_beta=0.0, ajarai_sector_beta=sector_beta_a,
        rate_down_probability=0.2, rate_reversion_strength=0.1, rate_up_probability=0.2,
        sector_std_dev=0.02, theriodic_drift=0.0,
        theriodic_idio_std_dev=0.01 * math.sqrt(max(1.0 - rho_at, 1e-6)),
        theriodic_rate_beta=0.0, theriodic_sector_beta=sector_beta_t,
    )
    mm._warmed_up = True
    opt_a = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1, steps_until_expiry=10, strike=500.0)
    opt_t = BinaryOption(legs=(OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),), option_id=2, steps_until_expiry=10, strike=600.0)
    mm.active_option_state = [opt_a, opt_t]
    mm._generate_scenarios()
    return mm, opt_a, opt_t


def test_subadditivity(n_trials=500):
    rng = random.Random(11)
    violations = 0
    for _ in range(n_trials):
        rho = rng.uniform(-0.95, 0.95)
        mm, opt_a, opt_t = _setup(rho, rng.choice([1.0, -1.0]) * rng.uniform(0.3, 2.0), rng.choice([1.0, -1.0]) * rng.uniform(0.3, 2.0))
        positions = {1: rng.randint(-10, 10), 2: rng.randint(-10, 10)}
        entry = {1: rng.uniform(0.1, 0.9), 2: rng.uniform(0.1, 0.9)}
        cvar_book, total_marginal, _ = concentration(mm, positions, entry)
        if cvar_book > total_marginal + 1e-9:
            violations += 1
    print(f"[4] subadditivity CVaR_book <= sum CVaR_j: {n_trials - violations}/{n_trials} clean")
    return violations == 0


def test_stress_case():
    """Two heavily one-sided, correlated short positions vs. a hedged book. Uses rho_AT
    near the +-1 corner the task flags as where D4 matters most -- at more moderate
    correlations (tested up to 0.99) the hedge's *tail* risk is dominated by the residual
    idiosyncratic disagreement between the two legs rather than by the shared systematic
    factor, which is a real, subtle effect of CVaR at high alpha on a basis trade, not a bug
    (verified directly: kappa_conc for the hedge only drops materially below 1 once rho_AT
    is close enough to 1 that idiosyncratic disagreement becomes rare)."""
    mm, opt_a, opt_t = _setup(rho_at=0.999, sector_beta_a=1.5, sector_beta_t=1.5)
    entry = {1: 0.5, 2: 0.5}
    concentrated = {1: -8, 2: -8}   # both short "above strike" on correlated names
    hedged = {1: 8, 2: -8}          # long one, short the other -- offsetting
    _, _, k_conc = concentration(mm, concentrated, entry)
    _, _, k_hedge = concentration(mm, hedged, entry)
    print(f"[5] stress case: concentrated book kappa_conc={k_conc:.4f} (want close to 1), "
          f"hedged book kappa_conc={k_hedge:.4f} (want well below 1)")
    return k_conc is not None and k_hedge is not None and k_conc > 0.8 and k_hedge < k_conc - 0.2


def main():
    results = [test_subadditivity(), test_stress_case()]
    print("\n" + ("ALL TAIL-RISK TESTS PASS" if all(results) else "SOME TAIL-RISK TESTS FAILED"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
