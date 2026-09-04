"""
Tests for the exponential-utility scenario/indifference-pricing quoting layer.
Run with: python3.11 sim/test_utility.py
"""
from __future__ import annotations

import math
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import (  # noqa: E402
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    MarketHistory,
    MarketMaker,
    MarketParameters,
    OptionLeg,
    Underlying,
)
from sim.harness import (  # noqa: E402
    SessionConfig,
    advance_step_reference,
    generate_history,
    generate_option_universe,
    run_batch,
    sample_initial_values,
    sample_parameters,
)


def _underlyings(values: dict) -> list:
    return [
        Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
        Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID]),
    ]


def _fresh_mm(seed: int, n_burn_in: int = 30, cash: float = 20.0):
    rng = np.random.default_rng(seed)
    params = sample_parameters(rng)
    values = sample_initial_values(rng, params)
    history, values = generate_history(params, n_burn_in, rng, values)
    mm = MarketMaker(_underlyings(values), [], cash)
    mm.warm_up(history)
    return mm, params, values, rng


# ---------------------------------------------------------------------------
# 1. Scenario-vs-pricer consistency
# ---------------------------------------------------------------------------

def test_scenario_pricer_consistency(n_sessions: int = 20, n_days: int = 8, n_options: int = 6) -> bool:
    failures = 0
    checked = 0
    for i in range(n_sessions):
        mm, params, values, rng = _fresh_mm(3000 + i)
        active_options: list = []
        next_id = 1
        for _day in range(n_days):
            values = advance_step_reference(params, values, rng)
            aged = [o.advance_step() for o in active_options]
            still_active = [a for o, a in zip(active_options, aged) if o.steps_until_expiry > 0]
            new_options = generate_option_universe(rng, values, n_options=n_options, next_id=next_id)
            next_id += len(new_options)
            active_options = still_active + new_options
            mm.on_step_advance(_underlyings(values), list(active_options))
            for option in active_options:
                Y = mm._scenario_Y.get(option.option_id)
                if not Y:
                    continue
                checked += 1
                p_hat = mm._get_cached_fair(option)
                mean_y = sum(Y) / len(Y)
                tol = 4.0 * math.sqrt(max(p_hat * (1.0 - p_hat), 0.0) / len(Y))
                if abs(mean_y - p_hat) > tol:
                    failures += 1
    print(f"[1] scenario-vs-pricer consistency: {checked - failures}/{checked} within 4*sqrt(P(1-P)/S)")
    return failures == 0


# ---------------------------------------------------------------------------
# 2. Closed-form analytic check, flat book
# ---------------------------------------------------------------------------

def test_analytic_flat_book(n_cases: int = 50) -> bool:
    rng = random.Random(42)
    worst = 0.0
    for _ in range(n_cases):
        underlyings = [
            Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
            Underlying("AJR", AJARAI_UNDERLYING_ID, 500.0),
            Underlying("THR", THERIODIC_UNDERLYING_ID, 600.0),
        ]
        mm = MarketMaker(underlyings, [], 20.0)
        mm.estimated_parameters = MarketParameters(
            ajarai_drift=rng.uniform(-0.002, 0.002), ajarai_idio_std_dev=rng.uniform(0.005, 0.02),
            ajarai_rate_beta=0.0, ajarai_sector_beta=rng.uniform(-1.0, 1.0),
            rate_down_probability=0.2, rate_reversion_strength=0.1, rate_up_probability=0.2,
            sector_std_dev=rng.uniform(0.005, 0.02), theriodic_drift=0.0,
            theriodic_idio_std_dev=0.01, theriodic_rate_beta=0.0, theriodic_sector_beta=0.0,
        )
        mm._warmed_up = True
        strike = 500.0 * rng.uniform(0.9, 1.1)
        steps = rng.randint(1, 15)
        option = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1,
                               steps_until_expiry=steps, strike=strike)
        mm.active_option_state = [option]
        mm._generate_scenarios()
        mm._recompute_u_s()
        Y = mm._scenario_Y[1]
        S = len(Y)
        P = sum(Y) / S
        for Q in (1, 3, 7):
            b = mm._indifference_bid(1, Q)
            gQ = mm._GAMMA * Q
            analytic = -(1.0 / gQ) * math.log(1.0 - P + P * math.exp(-gQ))
            worst = max(worst, abs(b - analytic))
    print(f"[2] analytic flat-book check: max |b_j(Q) - analytic| = {worst:.2e} (tol 1e-10)")
    return worst <= 1e-10


# ---------------------------------------------------------------------------
# 3. Quote ordering invariants
# ---------------------------------------------------------------------------

def test_ordering_invariants(n_sessions: int = 10, n_days: int = 6, n_options: int = 6) -> bool:
    ok = True
    for i in range(n_sessions):
        mm, params, values, rng = _fresh_mm(4000 + i)
        active_options: list = []
        next_id = 1
        for _day in range(n_days):
            values = advance_step_reference(params, values, rng)
            aged = [o.advance_step() for o in active_options]
            still_active = [a for o, a in zip(active_options, aged) if o.steps_until_expiry > 0]
            new_options = generate_option_universe(rng, values, n_options=n_options, next_id=next_id)
            next_id += len(new_options)
            active_options = still_active + new_options
            mm.on_step_advance(_underlyings(values), list(active_options))
            for option in active_options:
                if option.option_id not in mm._scenario_Y:
                    continue
                q = mm.quote(option, 1)
                if not (q.bid_price < q.offer_price):
                    ok = False
                b1 = mm._indifference_bid(option.option_id, 1)
                b3 = mm._indifference_bid(option.option_id, 3)
                a1 = mm._indifference_ask(option.option_id, 1)
                a3 = mm._indifference_ask(option.option_id, 3)
                if b3 > b1 + 1e-9 or a3 < a1 - 1e-9:
                    ok = False
    print(f"[3a] bid < offer and weakly worse with size: {'PASS' if ok else 'FAIL'}")

    # Hedging pair: two options that move together; a position in one should get a strictly
    # better price on a trade that reduces correlated exposure than the same trade taken naked.
    underlyings = [
        Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
        Underlying("AJR", AJARAI_UNDERLYING_ID, 500.0),
        Underlying("THR", THERIODIC_UNDERLYING_ID, 600.0),
    ]
    params = MarketParameters(
        ajarai_drift=0.0, ajarai_idio_std_dev=0.02, ajarai_rate_beta=0.0, ajarai_sector_beta=1.0,
        rate_down_probability=0.2, rate_reversion_strength=0.1, rate_up_probability=0.2,
        sector_std_dev=0.02, theriodic_drift=0.0, theriodic_idio_std_dev=0.02,
        theriodic_rate_beta=0.0, theriodic_sector_beta=-1.0,
    )
    opt_a = BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=1, steps_until_expiry=10, strike=500.0)
    opt_t = BinaryOption(legs=(OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),), option_id=2, steps_until_expiry=10, strike=600.0)

    mm_naked = MarketMaker(underlyings, [], 40.0)
    mm_naked.estimated_parameters = params
    mm_naked._warmed_up = True
    mm_naked.active_option_state = [opt_a, opt_t]
    mm_naked._generate_scenarios()
    mm_naked._recompute_u_s()
    naked_bid = mm_naked._indifference_bid(2, 3)

    mm_hedge = MarketMaker(underlyings, [], 40.0)
    mm_hedge.estimated_parameters = params
    mm_hedge._warmed_up = True
    mm_hedge.active_option_state = [opt_a, opt_t]
    mm_hedge._generate_scenarios()
    mm_hedge._entry_price[1] = 0.5
    mm_hedge.position.add_option_quantity(1, 5)  # long AJR>=500, sector_beta=+1
    mm_hedge._recompute_u_s()
    hedge_bid = mm_hedge._indifference_bid(2, 3)  # buying THR>=600 (sector_beta=-1) hedges it

    hedge_better = hedge_bid > naked_bid + 1e-9
    print(f"[3b] hedging trade priced better than naked: naked_bid={naked_bid:.6f} "
          f"hedge_bid={hedge_bid:.6f} ({'PASS' if hedge_better else 'FAIL'})")
    return ok and hedge_better


# ---------------------------------------------------------------------------
# 4. Performance
# ---------------------------------------------------------------------------

def test_performance(n_days: int = 15, universe_size: int = 50) -> bool:
    mm, params, values, rng = _fresh_mm(5000, cash=40.0)
    active_options: list = []
    next_id = 1
    day_times = []
    for _day in range(n_days):
        values = advance_step_reference(params, values, rng)
        aged = [o.advance_step() for o in active_options]
        still_active = [a for o, a in zip(active_options, aged) if o.steps_until_expiry > 0]
        n_new = max(0, universe_size - len(still_active))
        new_options = generate_option_universe(rng, values, n_options=n_new, next_id=next_id)
        next_id += len(new_options)
        active_options = (still_active + new_options)[:universe_size]
        t0 = time.time()
        mm.on_step_advance(_underlyings(values), list(active_options))
        for option in active_options:
            mm.quote(option, 1)
        day_times.append(time.time() - t0)
    median = sorted(day_times)[len(day_times) // 2]
    print(f"[4] median day (50-option universe): {median * 1000:.1f}ms (budget 400ms)")
    return median < 0.4


# ---------------------------------------------------------------------------
# 5. Score / bankruptcy vs. baseline (uses the existing harness batch runner)
# ---------------------------------------------------------------------------

def test_score_vs_baseline(n_sessions: int = 200) -> bool:
    cfg = SessionConfig()
    batch = run_batch(n_sessions, cfg, base_seed=1)
    print(f"[5] n={batch.n_sessions} mean_score={batch.mean_score:.4f} "
          f"bankruptcy_rate={batch.bankruptcy_rate:.4f} mean_fill_rate={batch.mean_fill_rate:.4f}")
    return True


def main() -> int:
    results = [
        test_scenario_pricer_consistency(),
        test_analytic_flat_book(),
        test_ordering_invariants(),
        test_performance(),
    ]
    test_score_vs_baseline(n_sessions=int(os.environ.get("UTILITY_TEST_SESSIONS", "200")))
    passed = all(results)
    print("\n" + ("ALL UTILITY TESTS PASS." if passed else "SOME UTILITY TESTS FAILED."))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
