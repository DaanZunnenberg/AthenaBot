"""Verifies the reparameterisation identity: up(level) = a_up - kappa*level and
down(level) = a_down + kappa*level exactly reproduce the old p_up + kappa*(target-level)
model when target=0 (a_up=p_up+kappa*target, a_down=p_down-kappa*target with target=0
means a_up=p_up, a_down=p_down -- the identity is checked directly here for a nonzero
target to show it's the general algebraic identity, not a coincidence of target=0).

Also verifies fitted kappa dispersion across 12 synthetic worlds is lower than the old
4-parameter model's reported range of 0.100-0.500 (D5 in the task spec)."""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _world import make_history

from Bot import _ParameterEstimator, MarketParameters, RATE_STRIKE_GRID


def old_tilted_probs(p_up, p_down, kappa, target, level):
    tilt = kappa * (target - level)
    up = min(max(p_up + tilt, 0.0), 1.0)
    down = min(max(p_down - tilt, 0.0), 1.0 - up)
    return up, down


def new_tilted_probs(a_up, a_down, kappa, level):
    up = min(max(a_up - kappa * level, 0.0), 1.0)
    down = min(max(a_down + kappa * level, 0.0), 1.0 - up)
    return up, down


def test_identity():
    p_up, p_down, kappa, target = 0.22, 0.18, 0.15, 2.0
    a_up = p_up + kappa * target
    a_down = p_down - kappa * target
    for level in (0.0, 1.0, 2.0, 3.0, 5.0):
        old_up, old_down = old_tilted_probs(p_up, p_down, kappa, target, level)
        new_up, new_down = new_tilted_probs(a_up, a_down, kappa, level)
        assert abs(old_up - new_up) < 1e-12, f"up mismatch at level={level}: {old_up} vs {new_up}"
        assert abs(old_down - new_down) < 1e-12, f"down mismatch at level={level}: {old_down} vs {new_down}"
    print("reparameterisation identity holds exactly: OK")


def test_kappa_dispersion():
    kappas = []
    for seed in range(12):
        history, _ = make_history(80, seed=1000 + seed)
        stats = _build_stats_from_history(history)
        a_up, a_down, kappa = _ParameterEstimator._fit_rate(stats)
        kappas.append(kappa)
    lo, hi = min(kappas), max(kappas)
    spread = hi - lo
    old_spread = 0.500 - 0.100  # reported baseline dispersion (D5)
    print(f"fitted kappa range: [{lo:.3f}, {hi:.3f}] (spread {spread:.3f}); old baseline spread {old_spread:.3f}")
    assert spread <= old_spread, f"kappa dispersion {spread:.3f} did not improve on old baseline {old_spread:.3f}"
    print("kappa dispersion improved vs baseline: OK")


def _build_stats_from_history(history):
    from Bot import _SufficientStats, FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID
    h = history.values_by_underlying_id
    fed, ajr, thr = h[FED_FUNDS_RATE_UNDERLYING_ID], h[AJARAI_UNDERLYING_ID], h[THERIODIC_UNDERLYING_ID]
    stats = _SufficientStats()
    for i in range(1, len(fed)):
        stats.add_transition(fed[i - 1], ajr[i - 1], thr[i - 1], fed[i], ajr[i], thr[i], RATE_STRIKE_GRID)
    return stats.rate_level_counts


def main():
    test_identity()
    test_kappa_dispersion()
    print("PASS")


if __name__ == "__main__":
    main()
