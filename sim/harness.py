"""
Offline replica of the HackerRank exchange loop, for local iteration without burning
submissions. Imports Bot.py (never the reverse -- Bot.py must stay stdlib-only and
submission-safe) and drives MarketMaker exactly the way the grader is understood to:
warm_up once, then per day advance state, settle expired options, issue RFQs/FOKs, and
call on_step_advance/on_trade for every fill.

Bankruptcy/settlement rule: replicated from MarketMaker._settle_expired_positions and the
README ("balance decreases by max loss on trade; settlement can only increase it; solvency
checked at end of day after payouts"), since that is the only documentation found in this
repo (see debug/CONVENTION.md). No independent grader source was available to verify
against, so this is flagged explicitly below rather than silently assumed correct.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

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
    OrderType,
    Underlying,
)

print("WARNING: bankruptcy rule unverified -- no grader source found in repo; "
      "replicated from README.md + MarketMaker._settle_expired_positions/on_trade "
      "(worst-case terminal cash: debit max loss on every trade immediately, credit payoffs "
      "only at expiry, bankrupt if cash < 0 after any day's settlement).", file=sys.stderr)


# ---------------------------------------------------------------------------
# A.1 -- sample_parameters
# ---------------------------------------------------------------------------

def sample_parameters(rng: np.random.Generator) -> MarketParameters:
    """
    Draws a plausible random MarketParameters, respecting every constraint enforced by
    MarketParameters.__post_init__ (positive rate_step, up/down probabilities in (0, 1)
    summing to <= 1, non-negative rate_target/std devs, reversion strength in [0, 1]).
    """
    rate_up = float(rng.uniform(0.05, 0.40))
    rate_down = float(rng.uniform(0.05, min(0.40, 0.95 - rate_up)))
    return MarketParameters(
        ajarai_drift=float(rng.uniform(-0.003, 0.003)),
        ajarai_idio_std_dev=float(rng.uniform(0.004, 0.030)),
        ajarai_rate_beta=float(rng.uniform(-0.4, 0.4)),
        ajarai_sector_beta=float(rng.uniform(0.1, 2.0) * rng.choice([-1, 1])),
        rate_down_probability=rate_down,
        rate_reversion_strength=float(rng.uniform(0.0, 0.5)),
        rate_up_probability=rate_up,
        sector_std_dev=float(rng.uniform(0.004, 0.030)),
        theriodic_drift=float(rng.uniform(-0.003, 0.003)),
        theriodic_idio_std_dev=float(rng.uniform(0.004, 0.030)),
        theriodic_rate_beta=float(rng.uniform(-0.4, 0.4)),
        theriodic_sector_beta=float(rng.uniform(0.1, 2.0) * rng.choice([-1, 1])),
        rate_step=0.25,
        rate_target=float(rng.uniform(1.0, 4.0)),
    )


def sample_parameters_wide(rng: np.random.Generator) -> MarketParameters:
    """
    Part G1's "wide" sampler: same shape as sample_parameters but with every range widened
    ~2.5x, to probe the edges of what hidden test cases might contain. Still respects
    MarketParameters.__post_init__'s constraints.
    """
    rate_up = float(rng.uniform(0.02, 0.55))
    rate_down = float(rng.uniform(0.02, min(0.55, 0.97 - rate_up)))
    return MarketParameters(
        ajarai_drift=float(rng.uniform(-0.0075, 0.0075)),
        ajarai_idio_std_dev=float(rng.uniform(0.001, 0.075)),
        ajarai_rate_beta=float(rng.uniform(-1.0, 1.0)),
        ajarai_sector_beta=float(rng.uniform(0.05, 5.0) * rng.choice([-1, 1])),
        rate_down_probability=rate_down,
        rate_reversion_strength=float(rng.uniform(0.0, 1.0)),
        rate_up_probability=rate_up,
        sector_std_dev=float(rng.uniform(0.001, 0.075)),
        theriodic_drift=float(rng.uniform(-0.0075, 0.0075)),
        theriodic_idio_std_dev=float(rng.uniform(0.001, 0.075)),
        theriodic_rate_beta=float(rng.uniform(-1.0, 1.0)),
        theriodic_sector_beta=float(rng.uniform(0.05, 5.0) * rng.choice([-1, 1])),
        rate_step=0.25,
        rate_target=float(rng.uniform(0.0, 8.0)),
    )


def sample_parameters_adversarial(rng: np.random.Generator) -> MarketParameters:
    """
    Part G1's adversarial sampler: hostile combinations -- rho_AT forced near +-1 (equal
    |sector_beta| with matching or opposite sign, idio near zero), a rate process that is
    either near-frozen (kappa~0, tiny up/down probs) or hyperactive (up/down probs near their
    ceiling), independent of what a burn-in sample would have suggested (a regime break).
    """
    same_sign = bool(rng.integers(0, 2))
    beta = float(rng.uniform(0.5, 2.0))
    frozen = bool(rng.integers(0, 2))
    if frozen:
        rate_up, rate_down, kappa = (1e-3, 1e-3, 0.0)
    else:
        rate_up, rate_down, kappa = (0.45, 0.45, float(rng.uniform(0.0, 1.0)))
    return MarketParameters(
        ajarai_drift=float(rng.uniform(-0.006, 0.006)) * rng.choice([-1, 1]),
        ajarai_idio_std_dev=float(rng.uniform(0.0005, 0.003)),
        ajarai_rate_beta=float(rng.uniform(-0.6, 0.6)),
        ajarai_sector_beta=beta,
        rate_down_probability=rate_down,
        rate_reversion_strength=kappa,
        rate_up_probability=rate_up,
        sector_std_dev=float(rng.uniform(0.01, 0.05)),
        theriodic_drift=float(rng.uniform(-0.006, 0.006)) * rng.choice([-1, 1]),
        theriodic_idio_std_dev=float(rng.uniform(0.0005, 0.003)),
        theriodic_rate_beta=float(rng.uniform(-0.6, 0.6)),
        theriodic_sector_beta=beta if same_sign else -beta,
        rate_step=0.25,
        rate_target=float(rng.uniform(0.0, 6.0)),
    )


def sample_initial_values(rng: np.random.Generator, params: MarketParameters) -> dict[int, float]:
    """A plausible starting state consistent with `params.rate_target`."""
    return {
        FED_FUNDS_RATE_UNDERLYING_ID: round(float(rng.uniform(0.0, 6.0)), 2),
        AJARAI_UNDERLYING_ID: round(float(rng.uniform(50.0, 800.0)), 2),
        THERIODIC_UNDERLYING_ID: round(float(rng.uniform(50.0, 800.0)), 2),
    }


# ---------------------------------------------------------------------------
# A.2 -- generate_history (drives MarketParameters.advance_step, the reference generator)
# ---------------------------------------------------------------------------

def generate_history(
    params: MarketParameters, n_days: int, rng: np.random.Generator, initial_values: Optional[dict[int, float]] = None,
) -> tuple[MarketHistory, dict[int, float]]:
    """
    Builds an n_days-long MarketHistory by repeatedly calling params.advance_step, which
    reads the stdlib `random` module internally -- seeded here from `rng` so the whole batch
    stays reproducible under run_batch's common-random-numbers scheme.

    Returns (history, final_values) so callers can continue live simulation from where the
    burn-in ended.
    """
    import random as _random

    seed = int(rng.integers(0, 2**31 - 1))
    state = _random.getstate()
    _random.seed(seed)
    try:
        values = dict(initial_values) if initial_values is not None else {
            FED_FUNDS_RATE_UNDERLYING_ID: params.rate_target,
            AJARAI_UNDERLYING_ID: 100.0,
            THERIODIC_UNDERLYING_ID: 100.0,
        }
        series: dict[int, list[float]] = {uid: [values[uid]] for uid in values}
        for _ in range(n_days):
            values = params.advance_step(values)
            for uid in values:
                series[uid].append(values[uid])
        history = MarketHistory(values_by_underlying_id={uid: tuple(v) for uid, v in series.items()})
        return history, values
    finally:
        _random.setstate(state)


def advance_step_reference(params: MarketParameters, values: dict[int, float], rng: np.random.Generator) -> dict[int, float]:
    """Single-day advance for live simulation, seeded from `rng` (not `generate_history`'s
    private seed) so day-by-day session simulation stays reproducible independently."""
    import random as _random

    seed = int(rng.integers(0, 2**31 - 1))
    state = _random.getstate()
    _random.seed(seed)
    try:
        return params.advance_step(values)
    finally:
        _random.setstate(state)


# ---------------------------------------------------------------------------
# A.3 -- generate_option_universe
# ---------------------------------------------------------------------------

_MONEYNESS_LEVELS = (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5)


def generate_option_universe(
    rng: np.random.Generator, values: dict[int, float], n_options: int = 40, next_id: int = 0,
) -> list[BinaryOption]:
    """
    Produces a mixed universe of BinaryOption contracts covering all three named shapes
    (single-leg, AJR/THR spreads, three-leg combinations), with steps_until_expiry spread
    across [0, 20] and strikes spread across the moneyness levels above (deep OTM to deep
    ITM relative to each leg's current observable value).
    """
    fed_v = values[FED_FUNDS_RATE_UNDERLYING_ID]
    a_v = values[AJARAI_UNDERLYING_ID]
    t_v = values[THERIODIC_UNDERLYING_ID]
    options: list[BinaryOption] = []
    option_id = next_id
    shapes = ["fed", "ajr", "thr", "spread", "sum", "three_leg"]
    for _ in range(n_options):
        shape = shapes[int(rng.integers(0, len(shapes)))]
        steps = int(rng.integers(0, 21))
        moneyness = float(rng.choice(_MONEYNESS_LEVELS))
        if shape == "fed":
            legs = (OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, 1.0),)
            base = fed_v if fed_v > 0 else 1.0
            strike = round(base * moneyness, 2)
        elif shape == "ajr":
            legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0),)
            strike = round(a_v * moneyness, 2)
        elif shape == "thr":
            legs = (OptionLeg(THERIODIC_UNDERLYING_ID, 1.0),)
            strike = round(t_v * moneyness, 2)
        elif shape == "spread":
            legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, -1.0))
            strike = round((a_v - t_v) * (moneyness - 1.0), 2)
        elif shape == "sum":
            legs = (OptionLeg(AJARAI_UNDERLYING_ID, 1.0), OptionLeg(THERIODIC_UNDERLYING_ID, 1.0))
            strike = round((a_v + t_v) * moneyness, 2)
        else:  # three_leg
            legs = (
                OptionLeg(FED_FUNDS_RATE_UNDERLYING_ID, float(rng.choice([1.0, -1.0, 0.5]))),
                OptionLeg(AJARAI_UNDERLYING_ID, float(rng.choice([1.0, -1.0, 1.5]))),
                OptionLeg(THERIODIC_UNDERLYING_ID, float(rng.choice([1.0, -1.0, 0.75]))),
            )
            strike = round((fed_v + a_v + t_v) * (moneyness - 1.0), 2)
        options.append(BinaryOption(legs=legs, option_id=option_id, steps_until_expiry=steps, strike=strike))
        option_id += 1
    return options


# ---------------------------------------------------------------------------
# A.5 -- synthetic counterparties (implementations live in sim/counterparties.py)
# ---------------------------------------------------------------------------

from sim.counterparties import Counterparty, InformedCounterparty, MixedCounterparty, NoiseCounterparty  # noqa: E402,F401


# ---------------------------------------------------------------------------
# A.6/A.7 -- config, scoring, session runner
# ---------------------------------------------------------------------------

@dataclass
class SessionConfig:
    n_burn_in_days: int = 30
    n_live_days: int = 20
    n_options_per_day: int = 6
    starting_cash: float = 10.0
    counterparty_factory: Callable[[np.random.Generator], Counterparty] = None  # type: ignore[assignment]
    rfq_fraction: float = 0.5  # fraction of daily interactions that are RFQs vs FOKs


@dataclass
class SessionResult:
    score: float
    bankrupt: bool
    bankruptcy_day: Optional[int]
    trade_count: int
    quote_count: int
    fok_count: int
    fill_rate: float
    final_cash: float
    trade_log: list[dict] = field(default_factory=list)


def _default_counterparty_factory(rng: np.random.Generator) -> Counterparty:
    return MixedCounterparty(rng, noise_sd=0.05, informed_fraction=0.5, informed_threshold=0.03)


def _underlyings(values: dict[int, float]) -> list[Underlying]:
    return [
        Underlying(name="FED", underlying_id=FED_FUNDS_RATE_UNDERLYING_ID, value=values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying(name="AJR", underlying_id=AJARAI_UNDERLYING_ID, value=values[AJARAI_UNDERLYING_ID]),
        Underlying(name="THR", underlying_id=THERIODIC_UNDERLYING_ID, value=values[THERIODIC_UNDERLYING_ID]),
    ]


def run_session(seed: int, config: SessionConfig, params: Optional[MarketParameters] = None, maker_factory=None) -> SessionResult:
    """
    Runs one full offline session: burn-in -> warm_up -> n_live_days of (advance, settle,
    quote/FOK, trade). Bankruptcy check matches _settle_expired_positions/on_trade
    (see module docstring for the caveat that this is a replica, not verified grader source).
    maker_factory, if given, replaces MarketMaker with any class exposing the same
    warm_up/on_step_advance/quote/respond_to_fok/on_trade/position interface (Part G2's
    synthetic reference baselines use this to run through the identical session loop).
    """
    rng = np.random.default_rng(seed)
    if params is None:
        params = sample_parameters(rng)
    initial_values = sample_initial_values(rng, params)
    history, values = generate_history(params, config.n_burn_in_days, rng, initial_values)

    counterparty_factory = config.counterparty_factory or _default_counterparty_factory
    counterparty = counterparty_factory(rng)

    maker_cls = maker_factory or MarketMaker
    mm = maker_cls(
        underlying_initial_state=_underlyings(values),
        option_initial_state=[],
        cash_balance=config.starting_cash,
    )
    mm.warm_up(history)

    true_cash = config.starting_cash
    active_options: list[BinaryOption] = []
    next_option_id = 10_000
    trade_log: list[dict] = []
    trade_count = quote_count = fok_count = fill_count = 0
    bankrupt = False
    bankruptcy_day: Optional[int] = None
    cp_id = 1

    for day in range(config.n_live_days):
        values = advance_step_reference(params, values, rng)

        aged_options = [o.advance_step() for o in active_options]
        still_active: list[BinaryOption] = []
        expired: list[BinaryOption] = []
        for original, aged in zip(active_options, aged_options):
            if original.steps_until_expiry == 0:
                expired.append(original)
            else:
                still_active.append(aged)

        for option in expired:
            payoff = option.expiry_valuation(values)
            qty = mm.position.option_quantity_by_option_id.get(option.option_id, 0)
            if qty > 0:
                true_cash += qty * payoff
            elif qty < 0:
                true_cash += (-qty) * (1.0 - payoff)

        new_options = generate_option_universe(rng, values, n_options=config.n_options_per_day, next_id=next_option_id)
        next_option_id += len(new_options)
        active_options = still_active + new_options

        mm.on_step_advance(_underlyings(values), list(active_options))

        if true_cash < 0:
            bankrupt = True
            bankruptcy_day = day
            break

        for option in active_options:
            if float(rng.uniform()) < config.rfq_fraction:
                quote_count += 1
                try:
                    quote = mm.quote(option, cp_id)
                except Exception:
                    cp_id += 1
                    continue
                fill = counterparty.respond_to_quote(params, values, option, quote)
                cp_id += 1
                if fill is None:
                    continue
                side, price, qty = fill
                fill_count += 1
                # side is the counterparty's side: SELL means they sell to us (we go long).
                mm_qty = qty if side == OrderType.SELL else -qty
                debit = mm_qty * price if mm_qty > 0 else (-mm_qty) * (1.0 - price)
                true_cash -= debit
                mm.on_trade(option, price, mm_qty, cp_id)
                trade_count += 1
                trade_log.append({
                    "day": day, "option_id": option.option_id, "kind": "rfq",
                    "side": str(side), "price": price, "quantity": mm_qty, "cash_after": true_cash,
                })
            else:
                fok_count += 1
                fok = counterparty.make_fok_order(params, values, option, cp_id)
                cp_id += 1
                if fok is None:
                    continue
                try:
                    accept = mm.respond_to_fok(option, fok)
                except Exception:
                    accept = False
                if not accept:
                    continue
                fill_count += 1
                mm_qty = fok.quantity if fok.order_type == OrderType.SELL else -fok.quantity
                debit = mm_qty * fok.price if mm_qty > 0 else (-mm_qty) * (1.0 - fok.price)
                true_cash -= debit
                mm.on_trade(option, fok.price, mm_qty, fok.counterparty_id)
                trade_count += 1
                trade_log.append({
                    "day": day, "option_id": option.option_id, "kind": "fok",
                    "side": str(fok.order_type), "price": fok.price, "quantity": mm_qty, "cash_after": true_cash,
                })

        if true_cash < 0:
            bankrupt = True
            bankruptcy_day = day
            break

    total_interactions = quote_count + fok_count
    fill_rate = fill_count / total_interactions if total_interactions else 0.0
    # No grader source was found to confirm the exact scoring formula (README only specifies
    # "full credit for #1 by PnL, zero for bankruptcy, partial for solvency" -- a ranking this
    # single-agent harness can't reproduce without a competitor-MM model). Per the fallback
    # rule (see startup WARNING), score = worst-case terminal cash: 0 on bankruptcy, else the
    # actual end-of-session cash balance.
    score = 0.0 if bankrupt else true_cash

    return SessionResult(
        score=score,
        bankrupt=bankrupt,
        bankruptcy_day=bankruptcy_day,
        trade_count=trade_count,
        quote_count=quote_count,
        fok_count=fok_count,
        fill_rate=fill_rate,
        final_cash=true_cash,
        trade_log=trade_log,
    )


# ---------------------------------------------------------------------------
# A.8 -- run_batch, with common random numbers across configs
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    n_sessions: int
    mean_score: float
    p5_score: float
    bankruptcy_rate: float
    mean_fill_rate: float
    results: list[SessionResult]


def run_batch(n_sessions: int, config: SessionConfig, base_seed: int = 0, maker_factory=None, params_sampler=None) -> BatchResult:
    """
    Runs n_sessions independent sessions. Seeds are `base_seed + i` for session i, so two
    calls to run_batch with different `config`s but the same `base_seed`/`n_sessions` see
    identical market paths and counterparty behaviour (common random numbers) -- every
    source of randomness inside run_session is derived from the per-session `np.random.
    default_rng(seed)`, so this holds regardless of what config.counterparty_factory does
    internally, as long as it only draws from the `rng` it's given. `params_sampler`, if
    given, replaces `sample_parameters` (Part G1's wide/adversarial pools).
    """
    if params_sampler is not None:
        results = []
        for i in range(n_sessions):
            seed = base_seed + i
            params = params_sampler(np.random.default_rng(seed))
            results.append(run_session(seed, config, params=params, maker_factory=maker_factory))
    else:
        results = [run_session(base_seed + i, config, maker_factory=maker_factory) for i in range(n_sessions)]
    scores = np.array([r.score for r in results])
    return BatchResult(
        n_sessions=n_sessions,
        mean_score=float(np.mean(scores)),
        p5_score=float(np.percentile(scores, 5)),
        bankruptcy_rate=float(np.mean([r.bankrupt for r in results])),
        mean_fill_rate=float(np.mean([r.fill_rate for r in results])),
        results=results,
    )


def write_csv(batch: BatchResult, path: str) -> None:
    """One line per session: seed order is implicit (row i == session base_seed + i)."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["session", "score", "bankrupt", "bankruptcy_day", "trade_count",
                          "quote_count", "fok_count", "fill_rate", "final_cash"])
        for i, r in enumerate(batch.results):
            writer.writerow([i, r.score, r.bankrupt, r.bankruptcy_day, r.trade_count,
                              r.quote_count, r.fok_count, round(r.fill_rate, 4), round(r.final_cash, 4)])


if __name__ == "__main__":
    cfg = SessionConfig()
    batch = run_batch(200, cfg, base_seed=1)
    print(f"n={batch.n_sessions} mean_score={batch.mean_score:.4f} "
          f"p5_score={batch.p5_score:.4f} bankruptcy_rate={batch.bankruptcy_rate:.4f} "
          f"mean_fill_rate={batch.mean_fill_rate:.4f}")
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline.csv")
    write_csv(batch, out_path)
    print(f"wrote {out_path}")
