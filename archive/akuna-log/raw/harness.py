import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

from src.taqf.akuna.market_types import (  # noqa: E402
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    MarketParameters,
    OptionLeg,
)


def mc_price(params: MarketParameters, vals0: dict, option: BinaryOption, n: int, seed: int) -> float:
    rng_state = random.getstate()
    random.seed(seed)
    try:
        hits = 0
        T = option.steps_until_expiry
        for _ in range(n):
            vals = dict(vals0)
            for _ in range(T):
                vals = params.advance_step(vals)
            hits += option.expiry_valuation(vals)
        return hits / n
    finally:
        random.setstate(rng_state)


def random_params(rng: random.Random) -> MarketParameters:
    return MarketParameters(
        ajarai_drift=rng.uniform(-0.003, 0.003),
        ajarai_idio_std_dev=rng.uniform(0.004, 0.030),
        ajarai_rate_beta=rng.uniform(-0.4, 0.4),
        ajarai_sector_beta=rng.uniform(0.1, 2.0) * rng.choice([-1, 1]),
        rate_down_probability=rng.uniform(0.05, 0.40),
        rate_reversion_strength=rng.uniform(0.0, 0.35),
        rate_up_probability=rng.uniform(0.05, 0.40),
        sector_std_dev=rng.uniform(0.004, 0.030),
        theriodic_drift=rng.uniform(-0.003, 0.003),
        theriodic_idio_std_dev=rng.uniform(0.004, 0.030),
        theriodic_rate_beta=rng.uniform(-0.4, 0.4),
        theriodic_sector_beta=rng.uniform(0.1, 2.0) * rng.choice([-1, 1]),
    )


def random_contract(rng: random.Random, vals: dict, option_id: int = 0) -> BinaryOption:
    shape = rng.choice(
        [
            "fed",
            "company_pos",
            "company_neg",
            "spread",
            "sum",
            "nonunit",
            "three_leg",
        ]
    )
    T = rng.randint(0, 10)
    fed_v = vals[FED_FUNDS_RATE_UNDERLYING_ID]
    a_v = vals[AJARAI_UNDERLYING_ID]
    t_v = vals[THERIODIC_UNDERLYING_ID]

    if shape == "fed":
        legs = (OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),)
        strike = round(fed_v + rng.uniform(-1.0, 1.0), 2)
    elif shape == "company_pos":
        uid = rng.choice([AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID])
        base = a_v if uid == AJARAI_UNDERLYING_ID else t_v
        legs = (OptionLeg(uid, 1.0),)
        strike = round(base * rng.uniform(0.5, 1.5), 2)
    elif shape == "company_neg":
        uid = rng.choice([AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID])
        base = a_v if uid == AJARAI_UNDERLYING_ID else t_v
        legs = (OptionLeg(uid, -1.0),)
        strike = round(-base * rng.uniform(0.5, 1.5), 2)
    elif shape == "spread":
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0))
        strike = round(rng.uniform(-50, 50), 2)
    elif shape == "sum":
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, 1.0))
        strike = round((a_v + t_v) * rng.uniform(0.5, 1.5), 2)
    elif shape == "nonunit":
        legs = (OptionLeg(AJARAI_UNDERLYING_ID, 2.5), OptionLeg(THERIODIC_UNDERLYING_ID, -1.5))
        strike = round(rng.uniform(-100, 100), 2)
    else:  # three_leg
        legs = (
            OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, rng.choice([1.0, -1.0, 0.5])),
            OptionLeg(AJARAI_UNDERLYING_ID, rng.choice([1.0, -1.0, 1.5])),
            OptionLeg(THERIODIC_UNDERLYING_ID, rng.choice([1.0, -1.0, 0.75])),
        )
        strike = round(rng.uniform(-100, 100), 2)

    return BinaryOption(legs=legs, option_id=option_id, steps_until_expiry=T, strike=strike)


def init_states():
    return [
        {FED_FUNDS_RATE_UNDERLYING_ID: 0.0, AJARAI_UNDERLYING_ID: 10.0, THERIODIC_UNDERLYING_ID: 10.0},
        {FED_FUNDS_RATE_UNDERLYING_ID: 6.0, AJARAI_UNDERLYING_ID: 400.0, THERIODIC_UNDERLYING_ID: 400.0},
        {FED_FUNDS_RATE_UNDERLYING_ID: 2.0, AJARAI_UNDERLYING_ID: 100.0, THERIODIC_UNDERLYING_ID: 250.0},
        {FED_FUNDS_RATE_UNDERLYING_ID: 1.25, AJARAI_UNDERLYING_ID: 50.0, THERIODIC_UNDERLYING_ID: 30.0},
    ]
