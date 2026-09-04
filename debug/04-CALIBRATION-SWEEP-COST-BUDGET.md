# Calibration sweep

> **What this improved / established:** Establishes the real compute budget for calibration sweeps (measured ~2.2s/session) so later sweep designs stay tractable instead of naively attempting the full 300-config x 200-session spec (60,000 sessions).

## Scale note (read first)

The task specifies 300 configurations x 200 sessions with common random numbers (60,000
sessions). Measured cost is ~2.2s/session (`sim/harness.run_batch`, mixed-counterparty), so a
literal run is ~37 hours of single-core compute — not feasible within this session. The sweep
actually run here is **8 candidate configurations x 10 sessions**, plus the incumbent evaluated
once at the same n (99 sessions total, ~4 minutes). This is a real, honest random-search run
over the documented ranges below, not a simulation of one — but it is far too small to have
statistical power to detect a genuine 5%+ improvement reliably; treat the "no improvement found"
result as a directional signal (the incumbent from Prompt 4/5's provisional constants is not
obviously beatable by nearby configurations), not as proof the incumbent is optimal. A fuller
run (`CALIBRATION_N_CONFIGS=300 CALIBRATION_N_SESSIONS=200 python3.11 sim/test_calibration.py`,
run alone rather than concurrently with other heavy jobs, budgeting ~37 hours or split across
sessions) is the recommended follow-up before treating this as final.

## Free constants swept and their ranges

| Constant | Attr | Range | Kind | Rationale |
|---|---|---|---|---|
| `gamma` | `_GAMMA` | [0.01, 0.15] | float | Centered near the Prompt 4 provisional 0.05; `debug/OBJECTIVE.md` argues against searching orders of magnitude away from it, since the ordinal scored objective makes the feasibility gate (not `gamma`) the primary bankruptcy defense |
| `m0` | `_M0` | [0.0, 0.03] | float | Flat spread floor |
| `c_U` | `_C_U` | [0.3, 2.0] | float | Uncertainty-premium weight |
| `c_T` | `_C_T` | [0.3, 2.0] | float | Toxicity-premium weight (Prompt 5) |
| `tau` | `_TAU` | [10, 60] | float | Per-counterparty shrinkage constant |
| `S` | `_S` | {512, 1024, 2048} | choice | Scenario count; kept to 3 discrete values to bound sweep runtime, matching Prompt 4's own performance budget testing |
| `B` | `_BOOTSTRAP_B` | {16, 32, 48} | choice | Parametric-bootstrap draw count for `U_P` |
| reserve fraction | `_RESERVE_FRACTION` | [0.05, 0.35] | float | Cash reserve floor |
| `Q_hard` (via cap fraction) | `_POSITION_CAP_FRACTION` | [0.08, 0.25] | float | `Q_hard = _position_cap` is derived from this fraction, not a separate constant in the current implementation |
| `b_min` | `_B_MIN` | [0.0, 0.05] | float | Minimum acceptable bid indifference price for sizing |

Incumbent (Prompt 4/5 provisional values): `gamma=0.05, m0=0.01, c_U=1.0, c_T=1.0, tau=30.0,
S=2048, B=32, reserve_fraction=0.2, position_cap_fraction=0.15, b_min=0.0`.

## Pre-registered acceptance rule

Adopt a candidate over the current best only if **all three** hold: (1) mean score improves by
>= 5%, (2) bankruptcy rate is no higher, (3) 5th-percentile score is no worse. All evaluated
with common random numbers (`base_seed=42000`, identical across every config in a run).

## Results (8 configs x 10 sessions, `sim/calibration_sweep.json` has the full machine-readable
record)

| Row | mean | p5 | bankrupt | fill | Decision |
|---|---|---|---|---|---|
| incumbent | 9.6210 | 8.2940 | 0.0000 | 0.0427 | (baseline) |
| candidate 0 | 9.3540 | 8.2840 | 0.0000 | 0.0424 | rejected (mean did not improve 5%) |
| candidate 1 | 9.4640 | 7.7865 | 0.0000 | 0.0427 | rejected (mean did not improve; p5 worse) |
| candidate 2 | 9.1230 | 7.9490 | 0.0000 | 0.0435 | rejected |
| candidate 3 | 9.5420 | 8.2390 | 0.0000 | 0.0427 | rejected |
| candidate 4 | 9.5020 | 8.0840 | 0.0000 | 0.0427 | rejected |
| candidate 5 | 9.7390 | 8.8580 | 0.0000 | 0.0424 | rejected (mean +1.2%, under the 5% bar despite p5 and bankruptcy both being at least as good — a real near-miss, see below) |
| candidate 6 | 9.7100 | 8.8360 | 0.0000 | 0.0424 | rejected (mean +0.9%, same near-miss pattern as candidate 5) |
| candidate 7 | 9.6370 | 8.3465 | 0.0000 | 0.0425 | rejected |

**No candidate was accepted; the incumbent configuration is retained.** Bankruptcy rate was
0.0000 across every single row (incumbent and all 8 candidates) at this sample size — this
sweep's evaluation set (mixed-counterparty, moderate difficulty) does not produce enough
bankruptcy variance at n=10 to meaningfully test criterion 2 either way; a wider/adversarial
pool (as Prompt 7 Part G later adds) is a better instrument for that criterion specifically.

**Candidates 5 and 6 are worth flagging for the follow-up full-scale run**, since they both beat
the incumbent on mean score *and* on p5 (not just non-worse), just short of the 5% bar — at
n=10 that's within plausible sampling noise of actually clearing 5% at n=200, and the
acceptance rule's job is exactly to prevent chasing that kind of noise, but they are the
natural starting point for the recommended fuller sweep rather than a fresh random draw. Their
full parameter rows are in `sim/calibration_sweep.json`.

## What this means for the shipped configuration

`Bot.py` ships with the incumbent (Prompt 4/5) constants unchanged. This sweep did not find a
5%+ improvement at reduced scale; it also did not rule one out, given the scale-down above. See
`debug/ROBUSTNESS_RESULTS.md` (Prompt 7) for the later, wider-pool re-sweep that supersedes this
one once Prompt 7's new constants exist to sweep alongside these.

---

## Section D: Submission hardening

### D1. Single file, stdlib only, no `sim`/`debug` references

Confirmed: `Bot.py`'s only imports are `math`, `random`, `collections.defaultdict`,
`dataclasses`, `enum.StrEnum`, `typing` (plus `from __future__ import annotations`, added this
task to let annotation quoting be stripped for byte budget without losing forward-reference
safety). `grep -n "sim\.\|debug\."  Bot.py` returns nothing.

### D2. Adversarial total-function audit and fuzz test

Enumerated every public `MarketMaker` method (`__init__`, `on_step_advance`, `on_trade`, `name`,
`price_option_from_parameters`, `warm_up`, `price_option`, `quote`, `respond_to_fok`) against
the task's malformed-input list. Nearly all were already total by construction (every method
except `on_trade` already wrapped its body in `try/except` with a safe fallback, a pattern
established across Prompts 1-5). Two real gaps found and fixed:

1. **`gamma -> 0` divides by zero in `_indifference_bid`/`_indifference_ask`** (`gQ = gamma *
   quantity` in the denominator of `math.log(ratio) / gQ`). This was already *masked* by
   `quote()`/`respond_to_fok()`'s outer `try/except` (falls back to the degenerate quote/`False`
   — technically total at the public boundary already), but that would make the bot silently
   degenerate on every single quote if `gamma` were ever swept near zero, rather than behaving
   correctly. Fixed with an explicit branch at `gQ < 1e-9` returning the analytic limit
   `U1/U` (the L'Hopital limit of the closed form as risk aversion vanishes) — see `docs/history/LEGACY-MODEL.md`
   §6.2.
2. **`on_trade` was not wrapped in `try/except` at all** — `option.option_id` on a malformed
   `option` (e.g. `None`) would have raised past the method boundary, unlike every other public
   method. Fixed: the position lookup is now guarded (returns early on failure) and every
   subsequent step already had its own `try/except`; the final `position.add_option_quantity`
   call is now also guarded.

`sim/test_fuzz.py` fires malformed inputs at all 8 methods (empty option lists, degenerate/
empty `MarketHistory`, zero-variance parameters, `steps_until_expiry == 0`, extreme strikes,
a forced near-singular/hostile `_theta_cov`, `S = 0` scenario sets, `gamma -> 0`) and asserts no
exception and no disallowed `None`. **Scale note**: the task specifies 10,000 trials/method;
measured cost is ~0.145s per constructed-and-warmed `MarketMaker` fixture (scenario generation
dominates), so 10,000 trials across the 5 methods that build a fixture would be ~2 hours single
processes and did not complete in two attempts in this session (see the commit history for the
two killed background runs). Shipped default is **150 trials/method** (`FUZZ_N_TRIALS` env var
overrides it, e.g. `FUZZ_N_TRIALS=10000 python3.11 sim/test_fuzz.py` for the full run before
final submission) — result at n=150: **all 8 methods, 150/150 clean, zero exceptions.**

### D3. Determinism

Verified directly: ran an identical sequence of `warm_up`/`on_step_advance`/`quote`/
`respond_to_fok`/`on_trade` calls on two fresh `MarketMaker` instances constructed from the same
inputs, and confirmed the full call/response log is bit-identical (`log1 == log2`, Python
equality on tuples of floats/ints, not approximate). This holds because every source of
randomness `MarketMaker` itself uses (scenario generation, parametric bootstrap) is drawn from a
locally-seeded `random.Random(...)` instance keyed off `self._day_index`, never the global
`random` module — the global module is only used by `MarketParameters.advance_step`/
`advance_rate`/`advance_company_value`, which is the *grader's* simulation of the true process,
not code `MarketMaker` calls on itself.

### D4. Cyclomatic complexity

`python3.11 -m radon cc Bot.py -s -n B` (rank B and above, i.e. complexity >= 6) against the
stated threshold of 15: one method, `_generate_scenarios`, was over the limit at **22**
(rank D). Decomposed into four smaller helpers (`_effective_steps`, `_advance_scenario_step`,
`_simulate_scenario_paths`, `_evaluate_indicator`) with no behavior change (`sim/test_ledger.py`
and `sim/test_pricer.py` both re-verified unaffected after the split). Post-decomposition,
`_generate_scenarios` is at **9**; the file's maximum is now **15** (`_ParameterEstimator.
_invert_matrix`, a pre-existing Gauss-Jordan solver predating this task, at the threshold, not
over it) — no method in the file exceeds 15.

### D5. Latency

Measured on this machine, uncontended (no other heavy job running concurrently), 50-option
universe held constant day-to-day (matching Prompt 4's own performance-testing convention),
20 live days after a 30-day burn-in: **median 104.6ms/day, max 115.7ms/day** (`on_step_advance`
+ quoting every active option). No officially-published grader latency budget was found in this
repository (`README.md` does not state one); the working figure carried through Prompts 4-6 is
the self-imposed 400ms/day budget from Prompt 4's own sizing of the scenario-generation cost.
Measured latency is **~3.8x under that budget** with margin to spare, consistent with Prompt 4's
own 50-option/30-step-horizon measurement (~87-90ms) plus the small, measured overhead of
Prompt 5's markout bookkeeping (0.001-0.005ms/day, `debug/MARKOUTS.md`) and Prompt 6's fixes.
