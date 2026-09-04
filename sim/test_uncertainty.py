"""
Coverage study for U_P (parametric-bootstrap parameter uncertainty) and a sanity check on
sigma_P (finite-difference one-step proxy), per the task's acceptance criterion 1: over 200
harness sessions where the *true* MarketParameters are known, |P_hat - P_true| <= 2*U_P
should hold for at least 85% of priced options.

Run with: python3.11 sim/test_uncertainty.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import (  # noqa: E402
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    MarketMaker,
    Underlying,
    _BinaryOptionPricer,
)
from sim.harness import (  # noqa: E402
    advance_step_reference,
    generate_history,
    generate_option_universe,
    sample_initial_values,
    sample_parameters,
)

N_SESSIONS = 200
N_BURN_IN = 30
N_LIVE = 15
N_OPTIONS_PER_DAY = 6


def _underlyings(values: dict) -> list:
    return [
        Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
        Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID]),
    ]


def run_coverage_session(seed: int) -> list[dict]:
    """One session: returns a record per (day, option) with P_hat, P_true, sigma_P, U_P, and
    whether theta_cov was reliable that day."""
    rng = np.random.default_rng(seed)
    params = sample_parameters(rng)  # true parameters -- known to the test, never to MarketMaker
    values = sample_initial_values(rng, params)
    history, values = generate_history(params, N_BURN_IN, rng, values)

    mm = MarketMaker(_underlyings(values), [], 10.0)
    mm.warm_up(history)

    records: list[dict] = []
    active_options: list = []
    next_id = 1
    for _day in range(N_LIVE):
        values = advance_step_reference(params, values, rng)
        aged = [o.advance_step() for o in active_options]
        still_active = [a for o, a in zip(active_options, aged) if o.steps_until_expiry > 0]
        new_options = generate_option_universe(rng, values, n_options=N_OPTIONS_PER_DAY, next_id=next_id)
        next_id += len(new_options)
        active_options = still_active + new_options

        mm.on_step_advance(_underlyings(values), list(active_options))

        for option in active_options:
            p_hat = mm._get_cached_fair(option)
            sigma_p, u_p = mm._get_cached_uncertainty(option)
            p_true = _BinaryOptionPricer.price(params, values, option)
            records.append({
                "p_hat": p_hat, "p_true": p_true, "sigma_p": sigma_p, "u_p": u_p,
                "reliable": mm._theta_cov_reliable, "steps": option.steps_until_expiry,
            })
    return records


def run_coverage_study(n_sessions: int = N_SESSIONS, base_seed: int = 2000) -> dict:
    all_records: list[dict] = []
    for i in range(n_sessions):
        all_records.extend(run_coverage_session(base_seed + i))

    errors = np.array([abs(r["p_hat"] - r["p_true"]) for r in all_records])
    u_p = np.array([r["u_p"] for r in all_records])
    reliable = np.array([r["reliable"] for r in all_records])

    covered = errors <= 2.0 * u_p
    coverage = float(np.mean(covered))
    coverage_reliable = float(np.mean(covered[reliable])) if reliable.any() else float("nan")
    coverage_unreliable = float(np.mean(covered[~reliable])) if (~reliable).any() else float("nan")

    return {
        "n_records": len(all_records),
        "coverage": coverage,
        "coverage_reliable_days": coverage_reliable,
        "coverage_unreliable_days": coverage_unreliable,
        "fraction_reliable_days": float(np.mean(reliable)),
        "mean_error": float(np.mean(errors)),
        "mean_u_p": float(np.mean(u_p)),
        "mean_u_p_reliable": float(np.mean(u_p[reliable])) if reliable.any() else float("nan"),
        "mean_u_p_unreliable": float(np.mean(u_p[~reliable])) if (~reliable).any() else float("nan"),
    }


def main() -> int:
    result = run_coverage_study()
    print(f"n_records={result['n_records']}")
    print(f"coverage (all): {result['coverage']:.4f} (target >= 0.85)")
    print(f"  -- on theta_cov_reliable days ({result['fraction_reliable_days']:.2%} of records): "
          f"{result['coverage_reliable_days']:.4f}, mean U_P={result['mean_u_p_reliable']:.4f}")
    print(f"  -- on unreliable/floor days: {result['coverage_unreliable_days']:.4f}, "
          f"mean U_P={result['mean_u_p_unreliable']:.4f} (floor is 0.05)")
    print(f"mean |P_hat - P_true|: {result['mean_error']:.4f}, mean U_P: {result['mean_u_p']:.4f}")

    passed = result["coverage"] >= 0.85
    print(f"\n{'PASS' if passed else 'FAIL'}: coverage {'meets' if passed else 'is below'} the 85% target.")
    if not passed:
        # Diagnose which block is understated rather than inflating U_P by a fudge factor.
        if result["coverage_reliable_days"] < 0.85:
            print("  -> theta_cov IS marked reliable but coverage still fails there: Sigma_theta's "
                  "company/variance blocks are understated (the rate block only matters when reliable).")
        if result["fraction_reliable_days"] < 0.5:
            print("  -> theta_cov is reliable on a minority of days; the 0.05 floor is carrying most "
                  "of the coverage burden and may itself be too tight -- see debug/UNCERTAINTY.md.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
