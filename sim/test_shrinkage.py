"""
Unit tests for Part A's shrinkage estimators (James-Stein bundle, Fisher-z correlation
pooling), tested directly against the internal _ParameterEstimator machinery with simulated
data (not the full harness) so the statistical claims can be checked in isolation.
Run with: python3.11 sim/test_shrinkage.py
"""
from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import _ParameterEstimator, _SufficientStats  # noqa: E402


def _simulate_stats(rng, n, mu_A, beta_A, mu_T, beta_T, rho, sd_A=0.02, sd_T=0.02, rate_step=0.25):
    stats = _SufficientStats()
    fed, ajr, thr = (2.0, 500.0, 600.0)
    for _ in range(n):
        d = rng.choice([-rate_step, 0.0, rate_step])
        z1, z2 = (rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0))
        eA = sd_A * z1
        eT = sd_T * (rho * z1 + math.sqrt(max(1.0 - rho * rho, 0.0)) * z2)
        log_ajr = mu_A + beta_A * d + eA
        log_thr = mu_T + beta_T * d + eT
        new_fed = max(0.0, fed + d)
        new_ajr = ajr * math.exp(log_ajr)
        new_thr = thr * math.exp(log_thr)
        stats.add_transition(fed, ajr, thr, new_fed, new_ajr, new_thr, rate_step)
        fed, ajr, thr = (new_fed, new_ajr, new_thr)
    return stats


def test_fisher_z_rmse(n_reps=500, n=200):
    """Criterion 1: at true rho=0, shrunk rho has lower RMSE than raw rho."""
    rng = random.Random(1)
    raw_sq, shrunk_sq = (0.0, 0.0)
    for _ in range(n_reps):
        stats = _simulate_stats(rng, n, 0.0, 0.0, 0.0, 0.0, rho=0.0)
        fit = _ParameterEstimator._fit_company(stats)
        rho_raw = fit['cbar'] / math.sqrt(fit['vbar_A'] * fit['vbar_T']) if fit['vbar_A'] > 0 and fit['vbar_T'] > 0 else 0.0
        rho_shrunk = _ParameterEstimator._fisher_z_shrink_rho(rho_raw, stats.n, 50.0)
        raw_sq += rho_raw ** 2
        shrunk_sq += rho_shrunk ** 2
    raw_rmse = math.sqrt(raw_sq / n_reps)
    shrunk_rmse = math.sqrt(shrunk_sq / n_reps)
    print(f"[1] Fisher-z RMSE at true rho=0: raw={raw_rmse:.4f} shrunk={shrunk_rmse:.4f}")
    return shrunk_rmse < raw_rmse


def test_js_bundle_rmse(n_reps=500, n=200):
    """Criterion 2: at true mu=beta=0, JS-shrunk bundle has lower MSE than raw OLS."""
    rng = random.Random(2)
    raw_mse, js_mse = (0.0, 0.0)
    for _ in range(n_reps):
        stats = _simulate_stats(rng, n, 0.0, 0.0, 0.0, 0.0, rho=0.0)
        fit = _ParameterEstimator._fit_company(stats)
        cov_A = _ParameterEstimator._company_covariance(fit, 'vbar_A', 'mu_A', 'beta_A')
        cov_T = _ParameterEstimator._company_covariance(fit, 'vbar_T', 'mu_T', 'beta_T')
        raw = {'mu_A': fit['mu_A'], 'mu_T': fit['mu_T'], 'beta_A': fit['beta_A'], 'beta_T': fit['beta_T'], 'b_r': 0.0}
        se = {'mu_A': math.sqrt(max(cov_A[0][0], 0.0)), 'mu_T': math.sqrt(max(cov_T[0][0], 0.0)),
              'beta_A': math.sqrt(max(cov_A[1][1], 0.0)), 'beta_T': math.sqrt(max(cov_T[1][1], 0.0)), 'b_r': 0.01}
        shrunk, _, _ = _ParameterEstimator._james_stein_bundle(raw, se)
        for k in ('mu_A', 'mu_T', 'beta_A', 'beta_T'):
            raw_mse += raw[k] ** 2
            js_mse += shrunk[k] ** 2
    raw_mse /= (n_reps * 4)
    js_mse /= (n_reps * 4)
    print(f"[2] JS bundle MSE at true theta=0: raw={raw_mse:.6f} js={js_mse:.6f}")
    return js_mse < raw_mse


def test_strong_signal_not_distorted(n=200):
    """Criterion 3: with a strong true signal, shrinkage stays close to unshrunk (c near 1,
    rho_shrunk within a few percent of raw rho)."""
    rng = random.Random(3)
    stats = _simulate_stats(rng, n, mu_A=0.02, beta_A=0.5, mu_T=0.015, beta_T=0.4, rho=0.8, sd_A=0.01, sd_T=0.01)
    fit = _ParameterEstimator._fit_company(stats)
    cov_A = _ParameterEstimator._company_covariance(fit, 'vbar_A', 'mu_A', 'beta_A')
    cov_T = _ParameterEstimator._company_covariance(fit, 'vbar_T', 'mu_T', 'beta_T')
    raw = {'mu_A': fit['mu_A'], 'mu_T': fit['mu_T'], 'beta_A': fit['beta_A'], 'beta_T': fit['beta_T'], 'b_r': 0.0}
    se = {'mu_A': math.sqrt(max(cov_A[0][0], 0.0)), 'mu_T': math.sqrt(max(cov_T[0][0], 0.0)),
          'beta_A': math.sqrt(max(cov_A[1][1], 0.0)), 'beta_T': math.sqrt(max(cov_T[1][1], 0.0)), 'b_r': 0.01}
    shrunk, c, _ = _ParameterEstimator._james_stein_bundle(raw, se)
    rho_raw = fit['cbar'] / math.sqrt(fit['vbar_A'] * fit['vbar_T']) if fit['vbar_A'] > 0 and fit['vbar_T'] > 0 else 0.0
    rho_shrunk = _ParameterEstimator._fisher_z_shrink_rho(rho_raw, stats.n, 50.0)
    rel_err = abs(rho_shrunk - rho_raw) / abs(rho_raw) if rho_raw != 0 else 0.0
    print(f"[3] strong signal: JS c={c:.4f} (want close to 1), rho_raw={rho_raw:.4f} "
          f"rho_shrunk={rho_shrunk:.4f} rel_err={rel_err:.4f}")
    return c > 0.7 and rel_err < 0.15


def main():
    results = [test_fisher_z_rmse(), test_js_bundle_rmse(), test_strong_signal_not_distorted()]
    print("\n" + ("ALL SHRINKAGE TESTS PASS" if all(results) else "SOME SHRINKAGE TESTS FAILED"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
