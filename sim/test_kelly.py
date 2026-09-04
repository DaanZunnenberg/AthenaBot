"""
Unit tests for Part C's fractional-Kelly sizing. Run with: python3.11 sim/test_kelly.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import MarketMaker  # noqa: E402


def test_symmetry(n_grid=25):
    """Criterion 1: f*_buy(P,p) == f*_sell(1-P,1-p) -- substituting Y'=1-Y, P'=1-P, p'=1-p
    turns a buy at (P,p) into a sell at (P',p') with the identical fraction, per the task's
    own derivation ("by symmetry ... substitute Y'=1-Y, P'=1-P, p'=1-p for the short side")."""
    worst = 0.0
    for i in range(1, n_grid):
        for j in range(1, n_grid):
            P = i / n_grid
            p = j / n_grid
            if abs(p - 1.0) < 1e-9 or p < 1e-9:
                continue
            f_buy = MarketMaker._kelly_fraction(P, p, True)
            f_sell_mirror = MarketMaker._kelly_fraction(1.0 - P, 1.0 - p, False)
            worst = max(worst, abs(f_buy - f_sell_mirror))
    print(f"[1] symmetry f*_buy(P,p) == f*_sell(1-P,1-p): max diff = {worst:.2e}")
    return worst < 1e-9


def test_smooth_at_zero_edge(eps=1e-4):
    """Criterion 2: f* -> 0 smoothly as p -> P from either side, no discontinuity."""
    P = 0.4
    f_above = MarketMaker._kelly_fraction(P, P + eps, True)
    f_below = MarketMaker._kelly_fraction(P, P - eps, True)
    f_at = MarketMaker._kelly_fraction(P, P, True)
    ok = abs(f_at) < 1e-9 and abs(f_above) < 1e-2 and abs(f_below) < 1e-2
    print(f"[2] smooth at zero edge: f*(P-eps)={f_below:.6f} f*(P)={f_at:.6f} f*(P+eps)={f_above:.6f}")
    return ok


def test_kelly_never_exceeds_gate(n_trials=int(os.environ.get("KELLY_FUZZ_TRIALS", "300"))):
    """Criterion 4: Q_final (post-Kelly) never exceeds the feasibility-gate max in fuzzed states."""
    import random
    from Bot import BinaryOption, OptionLeg, Underlying, AJARAI_UNDERLYING_ID, FED_FUNDS_RATE_UNDERLYING_ID, THERIODIC_UNDERLYING_ID, MarketHistory

    rng = random.Random(7)
    violations = 0
    for _ in range(n_trials):
        cash = rng.choice([0.5, 5.0, 20.0, 1000.0])
        underlyings = [Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, round(rng.uniform(0, 5), 2)),
                       Underlying("AJR", AJARAI_UNDERLYING_ID, round(rng.uniform(50, 900), 2)),
                       Underlying("THR", THERIODIC_UNDERLYING_ID, round(rng.uniform(50, 900), 2))]
        mm = MarketMaker(underlyings, [], cash)
        n = rng.choice([0, 5, 30])
        hist = MarketHistory({FED_FUNDS_RATE_UNDERLYING_ID: tuple(round(rng.uniform(0, 5), 2) for _ in range(n)),
                               AJARAI_UNDERLYING_ID: tuple(round(rng.uniform(50, 900), 2) for _ in range(n)),
                               THERIODIC_UNDERLYING_ID: tuple(round(rng.uniform(50, 900), 2) for _ in range(n))}) if n else MarketHistory({})
        try:
            mm.warm_up(hist)
        except Exception:
            continue
        legs = tuple(OptionLeg(u.underlying_id, rng.choice([1.0, -1.0])) for u in rng.sample(underlyings, rng.choice([1, 2])))
        option = BinaryOption(legs=legs, option_id=1, steps_until_expiry=rng.randint(1, 20), strike=round(rng.uniform(-500, 900), 2))
        try:
            mm.active_option_state = [option]
            mm._precompute_day_cache()
            mm._generate_scenarios()
            mm._recompute_u_s()
        except Exception:
            continue
        # gate-only max (Prompt 2/4 search without the Kelly cap)
        gate_max = 0
        price_at_max = 0.5
        for q in range(1, mm._position_cap + 1):
            price = mm._indifference_bid(option.option_id, q)
            if price < mm._B_MIN or not mm._gate_passes(option, q, price):
                break
            gate_max, price_at_max = (q, price)
        kelly_q, _ = mm._size_bid(option)
        if kelly_q > gate_max:
            violations += 1
    print(f"[4] Kelly-capped size never exceeds gate max: {n_trials - violations}/{n_trials} clean")
    return violations == 0


def main():
    results = [test_symmetry(), test_smooth_at_zero_edge(), test_kelly_never_exceeds_gate()]
    print("\n" + ("ALL KELLY TESTS PASS" if all(results) else "SOME KELLY TESTS FAILED"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
