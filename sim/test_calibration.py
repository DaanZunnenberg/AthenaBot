"""
Random-search calibration sweep over MarketMaker's free constants, evaluated with common
random numbers on the mixed-counterparty harness config. See debug/CALIBRATION.md for the
scale-down from the task's literal 300 configs x 200 sessions (infeasible in-session; see
that file for the runtime measurement that justifies the reduction) and the full results
table. Run with: python3.11 sim/test_calibration.py
"""
from __future__ import annotations

import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import MarketMaker  # noqa: E402
from sim.harness import SessionConfig, run_batch  # noqa: E402

# (attr, low, high, kind) -- kind in {"float", "int", "choice"}; ranges documented in
# debug/CALIBRATION.md alongside the rationale (gamma centered near the Prompt 4 provisional
# value per debug/OBJECTIVE.md; S/B kept modest to bound sweep runtime).
FREE_CONSTANTS = [
    ("_GAMMA", 0.01, 0.15, "float"),
    ("_M0", 0.0, 0.03, "float"),
    ("_C_U", 0.3, 2.0, "float"),
    ("_C_T", 0.3, 2.0, "float"),
    ("_TAU", 10.0, 60.0, "float"),
    ("_S", [512, 1024, 2048], None, "choice"),
    ("_BOOTSTRAP_B", [16, 32, 48], None, "choice"),
    ("_RESERVE_FRACTION", 0.05, 0.35, "float"),
    ("_POSITION_CAP_FRACTION", 0.08, 0.25, "float"),
    ("_B_MIN", 0.0, 0.05, "float"),
    # Prompt 7 additions:
    ("_U_REF", 0.03, 0.3, "float"),
    ("_N_MIN", [3, 10, 25], None, "choice"),
    ("_KAPPA_K", 0.1, 1.0, "float"),
    ("_LAMBDA_MIN", 0.1, 0.6, "float"),
    ("_T_MAX", 0.03, 0.25, "float"),
    ("_S_FIXED", 0.02, 0.1, "float"),
    ("_N0_CORR", 15.0, 100.0, "float"),
]

INCUMBENT = {
    "_GAMMA": 0.05, "_M0": 0.01, "_C_U": 1.0, "_C_T": 1.0, "_TAU": 30.0, "_S": 2048,
    "_BOOTSTRAP_B": 32, "_RESERVE_FRACTION": 0.2, "_POSITION_CAP_FRACTION": 0.15, "_B_MIN": 0.0,
    "_U_REF": 0.1, "_N_MIN": 10, "_KAPPA_K": 0.3, "_LAMBDA_MIN": 0.3, "_T_MAX": 0.1,
    "_S_FIXED": 0.05, "_N0_CORR": 50.0,
}


def sample_config(rng: random.Random) -> dict:
    cfg = {}
    for name, low, high, kind in FREE_CONSTANTS:
        if kind == "choice":
            cfg[name] = rng.choice(low)
        elif kind == "int":
            cfg[name] = rng.randint(int(low), int(high))
        else:
            cfg[name] = round(rng.uniform(low, high), 5)
    return cfg


def apply_config(cfg: dict) -> dict:
    original = {name: getattr(MarketMaker, name) for name in cfg}
    for name, value in cfg.items():
        setattr(MarketMaker, name, value)
    return original


def restore_config(original: dict) -> None:
    for name, value in original.items():
        setattr(MarketMaker, name, value)


def evaluate(cfg: dict, n_sessions: int, base_seed: int, combined_pool: bool = False) -> dict:
    original = apply_config(cfg)
    try:
        if combined_pool:
            from sim.harness import sample_parameters, sample_parameters_adversarial, sample_parameters_wide
            import numpy as np
            per_pool = max(1, n_sessions // 3)
            scores, p5s, bankrupts, fills = ([], [], [], [])
            for sampler, seed_off in ((sample_parameters, 0), (sample_parameters_wide, 100000), (sample_parameters_adversarial, 200000)):
                b = run_batch(per_pool, SessionConfig(), base_seed=base_seed + seed_off, params_sampler=sampler)
                scores.extend([r.score for r in b.results])
                bankrupts.extend([r.bankrupt for r in b.results])
                fills.append(b.mean_fill_rate)
            return {"mean_score": float(np.mean(scores)), "p5_score": float(np.percentile(scores, 5)),
                    "bankruptcy_rate": float(np.mean(bankrupts)), "mean_fill_rate": float(np.mean(fills))}
        batch = run_batch(n_sessions, SessionConfig(), base_seed=base_seed)
    finally:
        restore_config(original)
    return {
        "mean_score": batch.mean_score, "p5_score": batch.p5_score,
        "bankruptcy_rate": batch.bankruptcy_rate, "mean_fill_rate": batch.mean_fill_rate,
    }


def main() -> int:
    n_configs = int(os.environ.get("CALIBRATION_N_CONFIGS", "20"))
    n_sessions = int(os.environ.get("CALIBRATION_N_SESSIONS", "25"))
    base_seed = int(os.environ.get("CALIBRATION_BASE_SEED", "42000"))
    combined_pool = os.environ.get("CALIBRATION_COMBINED_POOL", "0") == "1"
    rng = random.Random(1)

    incumbent_result = evaluate(INCUMBENT, n_sessions, base_seed, combined_pool)
    print(f"[incumbent] {INCUMBENT}")
    print(f"  -> mean={incumbent_result['mean_score']:.4f} p5={incumbent_result['p5_score']:.4f} "
          f"bankrupt={incumbent_result['bankruptcy_rate']:.4f} fill={incumbent_result['mean_fill_rate']:.4f}")

    best_cfg, best_result = dict(INCUMBENT), incumbent_result
    rows = [{"config": INCUMBENT, "result": incumbent_result, "accepted": True, "role": "incumbent"}]

    for i in range(n_configs):
        cfg = sample_config(rng)
        result = evaluate(cfg, n_sessions, base_seed, combined_pool)
        improves_mean = result["mean_score"] >= best_result["mean_score"] * 1.05
        no_worse_bankruptcy = result["bankruptcy_rate"] <= best_result["bankruptcy_rate"]
        no_worse_p5 = result["p5_score"] >= best_result["p5_score"]
        accept = improves_mean and no_worse_bankruptcy and no_worse_p5
        rows.append({"config": cfg, "result": result, "accepted": accept, "role": "candidate"})
        print(f"[{i}] mean={result['mean_score']:.4f} p5={result['p5_score']:.4f} "
              f"bankrupt={result['bankruptcy_rate']:.4f} fill={result['mean_fill_rate']:.4f} "
              f"{'ACCEPTED' if accept else 'rejected'}")
        if accept:
            best_cfg, best_result = cfg, result

    print(f"\nFinal chosen config: {best_cfg}")
    print(f"  -> mean={best_result['mean_score']:.4f} p5={best_result['p5_score']:.4f} "
          f"bankrupt={best_result['bankruptcy_rate']:.4f} fill={best_result['mean_fill_rate']:.4f}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration_sweep.json")
    with open(out_path, "w") as f:
        json.dump({"incumbent": INCUMBENT, "chosen": best_cfg, "rows": rows}, f, indent=2)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
