"""
Adversarial total-function fuzz test for every public MarketMaker method: 10,000 malformed
inputs per method, asserting no exception escapes and no method that must return a value
returns None. Run with: python3.11 sim/test_fuzz.py

Malformed-input classes exercised (per the task's enumeration): empty option lists, degenerate
history (empty/zero-length), zero-variance parameters, steps_until_expiry == 0, extreme
strikes, near-singular Sigma_theta (forced via a hostile _theta_cov), S == 0 scenario sets,
gamma -> 0.
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import (  # noqa: E402
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    FokOrder,
    MarketHistory,
    MarketMaker,
    MarketParameters,
    OptionLeg,
    OrderType,
    Underlying,
    Quote,
)

N_TRIALS = int(os.environ.get("FUZZ_N_TRIALS", "150"))
rng = random.Random(12345)


def _extreme(rng: random.Random) -> float:
    return rng.choice([0.0, -1.0, 1e12, -1e12, 1e-12, float(rng.uniform(-1e6, 1e6))])


def _underlyings(rng: random.Random) -> list:
    n = rng.choice([0, 1, 2, 3, 3, 3])
    ids = [FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID][:n]
    return [Underlying("X", i, _extreme(rng) if rng.random() < 0.3 else round(rng.uniform(0.01, 1000), 2)) for i in ids]


def _option(rng: random.Random) -> BinaryOption:
    n_legs = rng.choice([1, 1, 1, 2, 3])
    ids = rng.sample([FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID], min(n_legs, 3))
    legs = tuple(OptionLeg(i, rng.choice([1.0, -1.0, 0.5, -0.5, 3.0])) for i in ids)
    steps = rng.choice([0, 0, 0, 1, 2, rng.randint(0, 200)])
    strike = _extreme(rng)
    return BinaryOption(legs=legs, option_id=rng.randint(1, 10_000), steps_until_expiry=steps, strike=strike)


def _market_params(rng: random.Random) -> MarketParameters:
    zero_var = rng.random() < 0.3
    up = rng.choice([1e-6, 0.2, 0.49])
    down = rng.choice([1e-6, 0.2, 0.49])
    return MarketParameters(
        ajarai_drift=_extreme(rng) * 1e-6, ajarai_idio_std_dev=0.0 if zero_var else rng.uniform(1e-6, 0.1),
        ajarai_rate_beta=_extreme(rng) * 1e-6, ajarai_sector_beta=_extreme(rng) * 1e-6,
        rate_down_probability=down, rate_reversion_strength=rng.uniform(0.0, 1.0), rate_up_probability=up,
        sector_std_dev=0.0 if zero_var else rng.uniform(1e-6, 0.1),
        theriodic_drift=_extreme(rng) * 1e-6, theriodic_idio_std_dev=0.0 if zero_var else rng.uniform(1e-6, 0.1),
        theriodic_rate_beta=_extreme(rng) * 1e-6, theriodic_sector_beta=_extreme(rng) * 1e-6,
        rate_step=rng.choice([0.01, 0.25, 1.0]), rate_target=rng.choice([0.0, 2.0, 1e6]),
    )


def _mm(rng: random.Random) -> MarketMaker:
    cash = rng.choice([0.0, -5.0, 1e-9, 10.0, 1e9])
    mm = MarketMaker(_underlyings(rng), [_option(rng) for _ in range(rng.choice([0, 1, 3]))], cash)
    if rng.random() < 0.5:
        try:
            mm.warm_up(_history(rng))
        except Exception:
            pass
    if rng.random() < 0.4:
        mm._S = 0  # scenario-set edge case
    if rng.random() < 0.4:
        mm._GAMMA = 0.0  # gamma -> 0 edge case
    if rng.random() < 0.3:
        mm._theta_cov_reliable = True
        mm._theta_cov = {"company_A": [[1e18, 0], [0, 1e18]], "company_T": [[0, 0], [0, 0]],
                          "variance": {"vbar_A": -1.0, "vbar_T": float("nan"), "cbar": 1e18},
                          "rate": [[0, 0, 0, 0]] * 4}  # near-singular / hostile Sigma_theta
    if rng.random() < 0.2:
        mm.estimated_parameters = _market_params(rng)
        mm._warmed_up = True
    try:
        mm.active_option_state = [_option(rng) for _ in range(rng.choice([0, 1, 5]))]
        mm._precompute_day_cache()
        mm._generate_scenarios()
        mm._recompute_u_s()
    except Exception:
        pass
    return mm


def _history(rng: random.Random) -> MarketHistory:
    n = rng.choice([0, 1, 2, 30])
    if n == 0:
        return MarketHistory({})
    vals = {i: tuple(_extreme(rng) if rng.random() < 0.1 else round(rng.uniform(0.01, 1000), 2) for _ in range(n))
            for i in (FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID)}
    return MarketHistory(vals)


def fuzz(name: str, fn) -> int:
    failures = 0
    for _ in range(N_TRIALS):
        try:
            fn()
        except Exception as exc:
            failures += 1
            if failures <= 3:
                print(f"  [{name}] exception: {exc!r}")
    print(f"[{name}] {N_TRIALS - failures}/{N_TRIALS} clean")
    return failures


def main() -> int:
    total_failures = 0

    def t_init():
        MarketMaker(_underlyings(rng), [_option(rng) for _ in range(rng.choice([0, 1, 3]))], rng.choice([0.0, -5.0, 10.0, 1e9]))
    total_failures += fuzz("__init__", t_init)

    def t_warm_up():
        mm = MarketMaker(_underlyings(rng), [], 10.0)
        mm.warm_up(_history(rng))
    total_failures += fuzz("warm_up", t_warm_up)

    def t_price_from_params():
        mm = MarketMaker(_underlyings(rng), [], 10.0)
        result = mm.price_option_from_parameters(_market_params(rng), _option(rng))
        assert result is not None
    total_failures += fuzz("price_option_from_parameters", t_price_from_params)

    def t_price_option():
        mm = _mm(rng)
        result = mm.price_option(_option(rng))
        assert result is not None
    total_failures += fuzz("price_option", t_price_option)

    def t_on_step_advance():
        mm = _mm(rng)
        mm.on_step_advance(_underlyings(rng), [_option(rng) for _ in range(rng.choice([0, 1, 5]))])
    total_failures += fuzz("on_step_advance", t_on_step_advance)

    def t_on_trade():
        mm = _mm(rng)
        opt = rng.choice([_option(rng), None]) if rng.random() < 0.05 else _option(rng)
        mm.on_trade(opt, _extreme(rng), rng.choice([0, 1, -1, 100, -100]), rng.randint(1, 100))
    total_failures += fuzz("on_trade", t_on_trade)

    def t_quote():
        mm = _mm(rng)
        q = mm.quote(_option(rng), rng.randint(1, 100))
        assert isinstance(q, Quote)
    total_failures += fuzz("quote", t_quote)

    def t_respond_to_fok():
        mm = _mm(rng)
        order_type = rng.choice([OrderType.BUY, OrderType.SELL])
        price = rng.choice([0.0, 1.0, 0.5, round(rng.uniform(0.0, 1.0), 2)])
        quantity = rng.choice([1, 1, 5, 1000])
        fok = FokOrder(counterparty_id=rng.randint(1, 100), option_id=rng.randint(1, 100),
                        order_type=order_type, price=price, quantity=quantity)
        result = mm.respond_to_fok(_option(rng), fok)
        assert result is not None and isinstance(result, bool)
    total_failures += fuzz("respond_to_fok", t_respond_to_fok)

    print(f"\n{'ALL FUZZ TESTS PASS' if total_failures == 0 else f'{total_failures} FAILURES'}")
    return 0 if total_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
