"""
Stage 1: markout instrumentation and the pre-registered kill criterion for Stage 2
(per-counterparty adverse-selection shrinkage). Run with: python3.11 sim/test_markouts.py
"""
from __future__ import annotations

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import MarketMaker, OrderType  # noqa: E402
from sim.counterparties import InformedCounterparty, MixedCounterparty, NoiseCounterparty  # noqa: E402
from sim.harness import (  # noqa: E402
    SessionConfig,
    advance_step_reference,
    generate_history,
    generate_option_universe,
    run_batch,
    sample_initial_values,
    sample_parameters,
)
from sim.harness import _underlyings  # noqa: E402

_NO_TOXICITY = lambda self, counterparty_id: (0.0, 0.0)  # noqa: E731


def _score_with_and_without_toxicity(counterparty_factory, n_sessions: int, base_seed: int) -> dict:
    cfg = SessionConfig(counterparty_factory=counterparty_factory)
    with_tox = run_batch(n_sessions, cfg, base_seed=base_seed)
    original = MarketMaker._toxicity
    MarketMaker._toxicity = _NO_TOXICITY
    try:
        without_tox = run_batch(n_sessions, cfg, base_seed=base_seed)
    finally:
        MarketMaker._toxicity = original
    return {
        'mean_score_with': with_tox.mean_score, 'mean_score_without': without_tox.mean_score,
        'bankruptcy_with': with_tox.bankruptcy_rate, 'bankruptcy_without': without_tox.bankruptcy_rate,
    }


def _run_session(seed: int, counterparty_factory, n_burn_in: int = 30, n_live: int = 20, n_options: int = 6, cash: float = 20.0):
    rng = np.random.default_rng(seed)
    params = sample_parameters(rng)
    values = sample_initial_values(rng, params)
    history, values = generate_history(params, n_burn_in, rng, values)
    counterparty = counterparty_factory(rng)

    mm = MarketMaker(_underlyings(values), [], cash)
    mm.warm_up(history)

    active_options: list = []
    next_id = 1
    cp_id = 1
    day_times: list[float] = []
    markout_times: list[float] = []
    _orig_update_markouts = mm._update_markouts

    def _timed_update_markouts():
        t0 = time.time()
        _orig_update_markouts()
        markout_times.append(time.time() - t0)
    mm._update_markouts = _timed_update_markouts

    for _day in range(n_live):
        values = advance_step_reference(params, values, rng)
        aged = [o.advance_step() for o in active_options]
        still_active = [a for o, a in zip(active_options, aged) if o.steps_until_expiry > 0]
        new_options = generate_option_universe(rng, values, n_options=n_options, next_id=next_id)
        next_id += len(new_options)
        active_options = still_active + new_options

        t0 = time.time()
        mm.on_step_advance(_underlyings(values), list(active_options))
        day_times.append(time.time() - t0)

        for option in active_options:
            if float(rng.uniform()) < 0.5:
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
                mm_qty = qty if side == OrderType.SELL else -qty
                mm.on_trade(option, price, mm_qty, cp_id)
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
                mm_qty = fok.quantity if fok.order_type == OrderType.SELL else -fok.quantity
                mm.on_trade(option, fok.price, mm_qty, fok.counterparty_id)
    return mm, day_times, markout_times


def _toxicity_distribution(counterparty_factory, n_sessions: int, base_seed: int) -> dict:
    buy_obs: list[float] = []
    sell_obs: list[float] = []
    all_day_times: list[float] = []
    all_markout_times: list[float] = []
    for i in range(n_sessions):
        mm, day_times, markout_times = _run_session(base_seed + i, counterparty_factory)
        all_day_times.extend(day_times)
        all_markout_times.extend(markout_times)
        for entry in mm._markout_log:
            values = [v for v in entry['M'].values() if v is not None]
            if not values:
                continue
            m = sum(values) / len(values)
            if entry['side'] == 'buy':
                buy_obs.append(-m)
            else:
                sell_obs.append(m)
    T_b = float(np.mean(buy_obs)) if buy_obs else float('nan')
    se_b = float(np.std(buy_obs, ddof=1) / math.sqrt(len(buy_obs))) if len(buy_obs) > 1 else float('nan')
    T_a = float(np.mean(sell_obs)) if sell_obs else float('nan')
    se_a = float(np.std(sell_obs, ddof=1) / math.sqrt(len(sell_obs))) if len(sell_obs) > 1 else float('nan')
    return {
        'T_b': T_b, 'se_b': se_b, 'n_b': len(buy_obs),
        'T_a': T_a, 'se_a': se_a, 'n_a': len(sell_obs),
        'median_day_ms': 1000.0 * float(np.median(all_day_times)) if all_day_times else float('nan'),
        'median_markout_ms': 1000.0 * float(np.median(all_markout_times)) if all_markout_times else float('nan'),
    }


def main() -> int:
    n_sessions = int(os.environ.get('MARKOUT_TEST_SESSIONS', '200'))
    configs = {
        'NoiseCounterparty': lambda rng: NoiseCounterparty(rng, noise_sd=0.05),
        'InformedCounterparty': lambda rng: InformedCounterparty(rng, threshold=0.03),
        'MixedCounterparty': lambda rng: MixedCounterparty(rng, noise_sd=0.05, informed_fraction=0.5, informed_threshold=0.03),
    }
    results = {}
    for name, factory in configs.items():
        r = _toxicity_distribution(factory, n_sessions, base_seed=7000 if name == 'NoiseCounterparty' else (8000 if name == 'InformedCounterparty' else 9000))
        results[name] = r
        print(f"[{name}] n={n_sessions} T_b={r['T_b']:.5f}+-{r['se_b']:.5f} (n_b={r['n_b']}) "
              f"T_a={r['T_a']:.5f}+-{r['se_a']:.5f} (n_a={r['n_a']}) median_day={r['median_day_ms']:.2f}ms "
              f"median_markout_overhead={r['median_markout_ms']:.4f}ms")

    kill = True
    for name, r in results.items():
        for key_T, key_se in (('T_b', 'se_b'), ('T_a', 'se_a')):
            T, se = r[key_T], r[key_se]
            if math.isnan(T) or math.isnan(se):
                continue
            ci_lo, ci_hi = T - 1.96 * se, T + 1.96 * se
            covers_zero = ci_lo <= 0.0 <= ci_hi
            if abs(T) >= 0.005 or not covers_zero:
                kill = False
    print(f"\nKill criterion (|T_b|,|T_a| < 0.005 AND CI covers zero, for every counterparty model): "
          f"{'MET -- do not build Stage 2' if kill else 'NOT MET -- Stage 2 is warranted'}")
    if kill:
        return 0

    ab_sessions = int(os.environ.get('MARKOUT_AB_SESSIONS', '60'))
    ab_configs = {
        'InformedCounterparty': lambda rng: InformedCounterparty(rng, threshold=0.03),
        'NoiseCounterparty': lambda rng: NoiseCounterparty(rng, noise_sd=0.05),
        'MixedCounterparty (default)': None,
    }
    print(f"\n--- A/B: score with vs. without toxicity margin (n={ab_sessions}/config) ---")
    for name, factory in ab_configs.items():
        r = _score_with_and_without_toxicity(factory, ab_sessions, base_seed=11000)
        delta = r['mean_score_with'] - r['mean_score_without']
        print(f"[{name}] with={r['mean_score_with']:.4f} without={r['mean_score_without']:.4f} "
              f"delta={delta:+.4f} bankrupt_with={r['bankruptcy_with']:.3f} bankrupt_without={r['bankruptcy_without']:.3f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
