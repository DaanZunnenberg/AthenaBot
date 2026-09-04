"""Shared helper: builds a synthetic MarketHistory and steps a world forward using an
illustrative MarketParameters, for use by the akuna/ standalone test scripts.
Note: history length is a test-harness choice, not a production assumption (resolved
question 2) -- production code (Bot.py) must not assume any particular length.

TRUE_PARAMS below is a made-up example, not the real grader's answer key -- it exists so
these scripts have some valid, self-consistent parameters to exercise, not to reproduce any
actual test case."""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import (
    MarketParameters, MarketHistory, Underlying, BinaryOption, OptionLeg,
    FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID,
)

TRUE_PARAMS = MarketParameters(
    ajarai_drift=0.0008, ajarai_idio_std_dev=0.015, ajarai_rate_beta=-0.01, ajarai_sector_beta=0.9,
    rate_down_probability=0.15, rate_reversion_strength=0.2, rate_up_probability=0.2,
    sector_std_dev=0.025, theriodic_drift=0.0012, theriodic_idio_std_dev=0.014,
    theriodic_rate_beta=-0.02, theriodic_sector_beta=1.1, rate_step=0.25, rate_target=2.5,
)


def make_history(num_days, seed=0, params=TRUE_PARAMS, start=None):
    rng_state = random.getstate()
    random.seed(seed)
    try:
        values = dict(start or {FED_FUNDS_RATE_UNDERLYING_ID: 2.5, AJARAI_UNDERLYING_ID: 450.0, THERIODIC_UNDERLYING_ID: 550.0})
        fed, ajr, thr = [values[FED_FUNDS_RATE_UNDERLYING_ID]], [values[AJARAI_UNDERLYING_ID]], [values[THERIODIC_UNDERLYING_ID]]
        for _ in range(num_days - 1):
            values = params.advance_step(values)
            fed.append(values[FED_FUNDS_RATE_UNDERLYING_ID])
            ajr.append(values[AJARAI_UNDERLYING_ID])
            thr.append(values[THERIODIC_UNDERLYING_ID])
        history = MarketHistory(values_by_underlying_id={
            FED_FUNDS_RATE_UNDERLYING_ID: tuple(fed),
            AJARAI_UNDERLYING_ID: tuple(ajr),
            THERIODIC_UNDERLYING_ID: tuple(thr),
        })
        return history, values
    finally:
        random.setstate(rng_state)


def underlyings_from_values(values):
    return [
        Underlying(name="FED", underlying_id=FED_FUNDS_RATE_UNDERLYING_ID, value=values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying(name="AJR", underlying_id=AJARAI_UNDERLYING_ID, value=values[AJARAI_UNDERLYING_ID]),
        Underlying(name="THR", underlying_id=THERIODIC_UNDERLYING_ID, value=values[THERIODIC_UNDERLYING_ID]),
    ]


def advance_values(values, params=TRUE_PARAMS):
    return params.advance_step(values)


def make_option(option_id, values, steps=3, kind="fed"):
    if kind == "fed":
        legs = (OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),)
        strike = round(values[FED_FUNDS_RATE_UNDERLYING_ID], 2)
    elif kind == "ajr":
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0),)
        strike = round(values[AJARAI_UNDERLYING_ID], 2)
    elif kind == "thr":
        legs = (OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),)
        strike = round(values[THERIODIC_UNDERLYING_ID], 2)
    else:  # spread
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0))
        strike = round(values[AJARAI_UNDERLYING_ID] - values[THERIODIC_UNDERLYING_ID], 2)
    return BinaryOption(legs=legs, option_id=option_id, steps_until_expiry=steps, strike=strike)
