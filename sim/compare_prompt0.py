"""
200-session, common-random-numbers comparison between the current `Bot.py` (this task's
changes: canonical pricing already wired in Prompt 1, plus this task's per-day cache and
net-position ledger) and `debug/BotFinal.py` (the "Prompt 0" baseline -- the last file
before the estimation-layer rewrite, 60,060 bytes, matching JOURNEY.md's last-confirmed-
working snapshot).

Each candidate module is loaded in isolation (importlib, distinct module names) since both
define top-level names like `MarketMaker`/`BinaryOption` that would otherwise collide. A
self-contained day loop (deliberately independent of sim/harness.py, which is wired to one
specific `Bot` module) drives each candidate through identical market paths and identical
counterparty behaviour per session, using per-session `np.random.default_rng(seed)` for
common random numbers -- so a score delta reflects the candidate change, not sampling noise.

Run with: python3.11 sim/compare_prompt0.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from sim.counterparties import MixedCounterparty  # noqa: E402


def _load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CURRENT = _load_module(os.path.join(_ROOT, "Bot.py"), "bot_current")
BASELINE = _load_module(os.path.join(_ROOT, "debug", "BotFinal.py"), "bot_prompt0")


@dataclass
class CompareResult:
    score: float
    bankrupt: bool
    trade_count: int
    ended_degenerate: bool


def _underlyings(mod, values: dict) -> list:
    return [
        mod.Underlying("FED", mod.FED_FUNDS_RATE_UNDERLYING_ID, values[mod.FED_FUNDS_RATE_UNDERLYING_ID]),
        mod.Underlying("AJR", mod.AJARAI_UNDERLYING_ID, values[mod.AJARAI_UNDERLYING_ID]),
        mod.Underlying("THR", mod.THERIODIC_UNDERLYING_ID, values[mod.THERIODIC_UNDERLYING_ID]),
    ]


def _option_universe(mod, rng: np.random.Generator, values: dict, n_options: int, next_id: int) -> list:
    fed_v, a_v, t_v = values[mod.FED_FUNDS_RATE_UNDERLYING_ID], values[mod.AJARAI_UNDERLYING_ID], values[mod.THERIODIC_UNDERLYING_ID]
    moneyness_levels = (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5)
    shapes = ["fed", "ajr", "thr", "spread", "sum", "three_leg"]
    options = []
    option_id = next_id
    for _ in range(n_options):
        shape = shapes[int(rng.integers(0, len(shapes)))]
        steps = int(rng.integers(0, 21))
        m = float(rng.choice(moneyness_levels))
        if shape == "fed":
            legs = (mod.OptionLeg(mod.FED_FUNDS_RATE_UNDERLYING_ID, 1.0),)
            strike = round((fed_v if fed_v > 0 else 1.0) * m, 2)
        elif shape == "ajr":
            legs = (mod.OptionLeg(mod.AJARAI_UNDERLYING_ID, 1.0),)
            strike = round(a_v * m, 2)
        elif shape == "thr":
            legs = (mod.OptionLeg(mod.THERIODIC_UNDERLYING_ID, 1.0),)
            strike = round(t_v * m, 2)
        elif shape == "spread":
            legs = (mod.OptionLeg(mod.AJARAI_UNDERLYING_ID, 1.0), mod.OptionLeg(mod.THERIODIC_UNDERLYING_ID, -1.0))
            strike = round((a_v - t_v) * (m - 1.0), 2)
        elif shape == "sum":
            legs = (mod.OptionLeg(mod.AJARAI_UNDERLYING_ID, 1.0), mod.OptionLeg(mod.THERIODIC_UNDERLYING_ID, 1.0))
            strike = round((a_v + t_v) * m, 2)
        else:
            legs = (
                mod.OptionLeg(mod.FED_FUNDS_RATE_UNDERLYING_ID, float(rng.choice([1.0, -1.0, 0.5]))),
                mod.OptionLeg(mod.AJARAI_UNDERLYING_ID, float(rng.choice([1.0, -1.0, 1.5]))),
                mod.OptionLeg(mod.THERIODIC_UNDERLYING_ID, float(rng.choice([1.0, -1.0, 0.75]))),
            )
            strike = round((fed_v + a_v + t_v) * (m - 1.0), 2)
        options.append(mod.BinaryOption(legs=legs, option_id=option_id, steps_until_expiry=steps, strike=strike))
        option_id += 1
    return options


_DEGENERATE = (0.0, 1, 1.0, 1)  # (bid_price, bid_quantity, offer_price, offer_quantity)


def run_one(mod, seed: int, n_burn_in: int = 30, n_live: int = 20, n_options_per_day: int = 6, starting_cash: float = 10.0) -> CompareResult:
    rng = np.random.default_rng(seed)
    params = mod.MarketParameters(
        ajarai_drift=float(rng.uniform(-0.003, 0.003)), ajarai_idio_std_dev=float(rng.uniform(0.004, 0.030)),
        ajarai_rate_beta=float(rng.uniform(-0.4, 0.4)), ajarai_sector_beta=float(rng.uniform(0.1, 2.0) * rng.choice([-1, 1])),
        rate_down_probability=float(rng.uniform(0.05, 0.40)), rate_reversion_strength=float(rng.uniform(0.0, 0.5)),
        rate_up_probability=float(rng.uniform(0.05, 0.40)), sector_std_dev=float(rng.uniform(0.004, 0.030)),
        theriodic_drift=float(rng.uniform(-0.003, 0.003)), theriodic_idio_std_dev=float(rng.uniform(0.004, 0.030)),
        theriodic_rate_beta=float(rng.uniform(-0.4, 0.4)), theriodic_sector_beta=float(rng.uniform(0.1, 2.0) * rng.choice([-1, 1])),
        rate_step=0.25, rate_target=float(rng.uniform(1.0, 4.0)),
    )
    values = {
        mod.FED_FUNDS_RATE_UNDERLYING_ID: round(float(rng.uniform(0.0, 6.0)), 2),
        mod.AJARAI_UNDERLYING_ID: round(float(rng.uniform(50.0, 800.0)), 2),
        mod.THERIODIC_UNDERLYING_ID: round(float(rng.uniform(50.0, 800.0)), 2),
    }

    import random as _random
    burn_seed = int(rng.integers(0, 2**31 - 1))
    state = _random.getstate()
    _random.seed(burn_seed)
    try:
        series = {uid: [values[uid]] for uid in values}
        for _ in range(n_burn_in):
            values = params.advance_step(values)
            for uid in values:
                series[uid].append(values[uid])
        history = mod.MarketHistory(values_by_underlying_id={uid: tuple(v) for uid, v in series.items()})
    finally:
        _random.setstate(state)

    counterparty = MixedCounterparty(rng, noise_sd=0.05, informed_fraction=0.5, informed_threshold=0.03)

    mm = mod.MarketMaker(_underlyings(mod, values), [], starting_cash)
    mm.warm_up(history)

    true_cash = starting_cash
    active_options: list = []
    next_option_id = 10_000
    trade_count = 0
    bankrupt = False
    cp_id = 1
    last_quote_degenerate = False

    for day in range(n_live):
        day_seed = int(rng.integers(0, 2**31 - 1))
        state = _random.getstate()
        _random.seed(day_seed)
        try:
            values = params.advance_step(values)
        finally:
            _random.setstate(state)

        aged = [o.advance_step() for o in active_options]
        still_active, expired = [], []
        for original, agedopt in zip(active_options, aged):
            if original.steps_until_expiry == 0:
                expired.append(original)
            else:
                still_active.append(agedopt)

        for option in expired:
            payoff = option.expiry_valuation(values)
            qty = mm.position.option_quantity_by_option_id.get(option.option_id, 0)
            if qty > 0:
                true_cash += qty * payoff
            elif qty < 0:
                true_cash += (-qty) * (1.0 - payoff)

        new_options = _option_universe(mod, rng, values, n_options_per_day, next_option_id)
        next_option_id += len(new_options)
        active_options = still_active + new_options

        mm.on_step_advance(_underlyings(mod, values), list(active_options))

        if true_cash < 0:
            bankrupt = True
            break

        for option in active_options:
            if float(rng.uniform()) < 0.5:
                try:
                    quote = mm.quote(option, cp_id)
                except Exception:
                    cp_id += 1
                    continue
                last_quote_degenerate = (
                    quote.bid_price, quote.bid_quantity, quote.offer_price, quote.offer_quantity
                ) == _DEGENERATE
                fill = counterparty.respond_to_quote(params, values, option, quote)
                cp_id += 1
                if fill is None:
                    continue
                side, price, qty = fill
                mm_qty = qty if side == mod.OrderType.SELL else -qty
                debit = mm_qty * price if mm_qty > 0 else (-mm_qty) * (1.0 - price)
                true_cash -= debit
                mm.on_trade(option, price, mm_qty, cp_id)
                trade_count += 1
            else:
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
                mm_qty = fok.quantity if fok.order_type == mod.OrderType.SELL else -fok.quantity
                debit = mm_qty * fok.price if mm_qty > 0 else (-mm_qty) * (1.0 - fok.price)
                true_cash -= debit
                mm.on_trade(option, fok.price, mm_qty, fok.counterparty_id)
                trade_count += 1

        if true_cash < 0:
            bankrupt = True
            break

    score = 0.0 if bankrupt else true_cash
    return CompareResult(score=score, bankrupt=bankrupt, trade_count=trade_count, ended_degenerate=last_quote_degenerate)


def run_comparison(n_sessions: int = 200, base_seed: int = 1) -> dict:
    current_results = [run_one(CURRENT, base_seed + i) for i in range(n_sessions)]
    baseline_results = [run_one(BASELINE, base_seed + i) for i in range(n_sessions)]

    def summarize(results):
        scores = np.array([r.score for r in results])
        return {
            "mean_score": float(np.mean(scores)),
            "p5_score": float(np.percentile(scores, 5)),
            "bankruptcy_rate": float(np.mean([r.bankrupt for r in results])),
            "degenerate_fraction": float(np.mean([r.ended_degenerate for r in results])),
            "mean_trades": float(np.mean([r.trade_count for r in results])),
        }

    return {"current": summarize(current_results), "baseline": summarize(baseline_results)}


if __name__ == "__main__":
    result = run_comparison()
    for label in ("baseline", "current"):
        s = result[label]
        print(f"{label:10s}: mean_score={s['mean_score']:.4f} p5_score={s['p5_score']:.4f} "
              f"bankruptcy_rate={s['bankruptcy_rate']:.4f} degenerate_fraction={s['degenerate_fraction']:.4f} "
              f"mean_trades={s['mean_trades']:.1f}")
