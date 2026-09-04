"""
Part G: adversarial/wide-pool validation, synthetic reference baselines, and a reduced-scale
re-sweep including Prompt 7's new free constants. See debug/HARNESS_V2.md and
debug/ROBUSTNESS_RESULTS.md for the full writeup and the documented scale-down (this task's
literal 300x200 sweep over three pools is well beyond this session's compute budget; see
debug/CALIBRATION.md Section-note for the same measured per-session cost this reduction is
based on). Run with: python3.11 sim/test_robustness.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import FokOrder, MarketMaker, OrderType, Position, Quote  # noqa: E402
from sim.harness import SessionConfig, run_batch, sample_parameters, sample_parameters_adversarial, sample_parameters_wide  # noqa: E402


class NaiveInventoryQuoter:
    """G2 stand-in for a simple inventory-only competitor: fixed half-spread centered at 0.5
    (no pricing model at all -- deliberately not even reading the underlying state), linear
    inventory skew. NOT the actual "Situational Unawareness"/"Mongoose" competitor (internals
    unknown); only shares the qualitative property of being simple and unmodeled."""
    _HALF_SPREAD = 0.1
    _SKEW = 0.03
    _CAP = 20

    def __init__(self, underlying_initial_state, option_initial_state, cash_balance):
        self.position = Position()
        self._cash = cash_balance

    def warm_up(self, market_history):
        pass

    def on_step_advance(self, new_underlying_state, new_option_state):
        pass

    def on_trade(self, option, price, quantity, counterparty_id):
        self._cash -= quantity * price
        self.position.add_option_quantity(option.option_id, quantity)

    def quote(self, option, counterparty_id):
        q = self.position.option_quantity_by_option_id.get(option.option_id, 0)
        center = 0.5 - self._SKEW * max(-1.0, min(1.0, q / self._CAP))
        bid = max(0.0, round(center - self._HALF_SPREAD, 2))
        ask = min(1.0, round(center + self._HALF_SPREAD, 2))
        if bid >= ask:
            return Quote(bid_price=0.0, bid_quantity=1, offer_price=1.0, offer_quantity=1)
        return Quote(bid_price=bid, bid_quantity=2, offer_price=ask, offer_quantity=2)

    def respond_to_fok(self, option, fok_order):
        return False


def _fixed_width_factory():
    """G2's second stand-in: the existing Part B fixed-width fallback (w=0 forced), i.e. the
    AthenaBot pricing engine with zero blend weight toward the sophisticated side -- constant
    spread, centered on the model fair value, no inventory skew from the utility layer."""
    class FixedWidthMaker(MarketMaker):
        def _blend_weight(self, u_p):
            return 0.0
    return FixedWidthMaker


def lexicographic_criterion(batch):
    frac_profitable = float(np.mean([r.score > 0 for r in batch.results]))
    return (batch.p5_score, frac_profitable, batch.mean_score)


def compare(name, cfg, n_sessions, base_seed, params_sampler=None):
    athena = run_batch(n_sessions, cfg, base_seed=base_seed, params_sampler=params_sampler)
    fixed = run_batch(n_sessions, cfg, base_seed=base_seed, maker_factory=_fixed_width_factory(), params_sampler=params_sampler)
    naive = run_batch(n_sessions, cfg, base_seed=base_seed, maker_factory=NaiveInventoryQuoter, params_sampler=params_sampler)
    c_a, c_f, c_n = (lexicographic_criterion(athena), lexicographic_criterion(fixed), lexicographic_criterion(naive))
    beats_both = c_a >= c_f and c_a >= c_n
    print(f"[{name}] AthenaBot p5={c_a[0]:.3f} frac_profit={c_a[1]:.3f} mean={c_a[2]:.3f}")
    print(f"[{name}] FixedWidth p5={c_f[0]:.3f} frac_profit={c_f[1]:.3f} mean={c_f[2]:.3f}")
    print(f"[{name}] NaiveInv   p5={c_n[0]:.3f} frac_profit={c_n[1]:.3f} mean={c_n[2]:.3f}")
    print(f"[{name}] AthenaBot beats both on G3 lexicographic criterion: {beats_both}")
    return athena, fixed, naive, beats_both


def main():
    n = int(os.environ.get("ROBUSTNESS_N_SESSIONS", "12"))
    cfg = SessionConfig()
    results = {}
    results['plausible'] = compare('plausible', cfg, n, base_seed=20000, params_sampler=sample_parameters)
    results['wide'] = compare('wide', cfg, n, base_seed=21000, params_sampler=sample_parameters_wide)
    results['adversarial'] = compare('adversarial', cfg, n, base_seed=22000, params_sampler=sample_parameters_adversarial)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
