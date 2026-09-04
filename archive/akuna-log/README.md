# `archive/akuna-log/` — the `akuna/` scratch workspace, archived

This was originally a top-level `akuna/` folder — a standalone scratch environment used
alongside `Bot.py`, not a public-facing part of the submission. It's archived here (folded
into `archive/`, the same as the `debug/` bisection snapshots) rather than kept as its own
top-level folder, because it's working scratch material, not final-submission documentation.

## What it was and why

Two unrelated things lived in the original `akuna/` folder:

1. **A standalone pricing prototype** (`raw/mm.py`, `raw/harness.py`) — a more elaborate
   `MarketMaker` prototype (including early `warm_up`/`quote`/`respond_to_fok`/risk logic)
   built *before* the pricing/quoting design in `Bot.py` settled. `harness.py` provided a
   Monte Carlo ground truth (`mc_price`) to accuracy-test the prototype pricer against
   simulation across randomly generated parameter regimes and contract shapes. Both import
   the shared interface types from the private `src` submodule (`src.taqf.akuna.market_types`),
   same as everything else in this repo — an earlier standalone copy of that starter template
   used to live here too and was removed as a redundant duplicate.
2. **Regression tests against the real `Bot.py`** (`raw/_world.py` + `raw/test_*.py`) — six
   small scripts, written later, that import directly from the root `Bot.py` (not from this
   folder's own prototype) and assert specific previously-broken behaviors stay fixed.

## What worked

- The prototype's pricing approach was validated against `harness.py`'s Monte Carlo ground
  truth across many regimes/contract shapes, and that validation informed the exact,
  deterministic finite-state-DP pricer that ended up in `Bot.py`'s
  `price_option_from_parameters` — no Monte Carlo needed there, see `docs/history/JOURNEY.md` Phase 2 for
  why that's possible (rate changes telescope to a terminal-only dependency).
- Every regression test recorded a real pre-fix baseline failure it was written to catch, and
  all were passing as of the last run against `Bot.py`:
  - `test_theo.py` — matches the six THEO reference contracts to `<1e-4`.
  - `test_margin.py` — internal margin ledger matches the grader's own debit/credit rules
    exactly (a flat round trip does not permanently consume margin).
  - `test_inventory_skew.py` — quote stays live and the mid moves monotonically against a
    growing position (baseline/pre-fix code collapsed bid/offer to `0.00`/`1.00` at net long 1).
  - `test_participation.py` — the degenerate `0.00`/`1.00` fallback quote fires on <5% of
    quotes across three capital levels (baseline/pre-fix: 100% / 100% / 17%).
  - `test_pricing_error.py` — live pricing error (`price_option`, the estimated-parameter
    path) tracked against a recorded pre-fix baseline (0.0789 / 0.0506 / 0.0139 mean absolute
    error by option type), asserting no regression past a small tolerance.
  - `test_rate_identification.py` — confirms the rate-reparameterisation identity used by
    `warm_up`'s kappa estimation reduces correctly to an earlier model at the boundary case.

## What didn't (or was superseded)

- The prototype `MarketMaker` in `mm.py` was **not** promoted into `Bot.py` as-is — it's a
  more elaborate, earlier design explored before the final, narrower quoting/risk design
  (three-zone confidence quoting, capital-scale ramp, hard solvency gates — see `docs/history/LEGACY-MODEL.md`
  and `docs/history/JOURNEY.md` Phase 4) was settled on. Kept only as a reference sketch of an alternative
  approach, not a dead end exactly, but a road not taken.
- `harness.py`'s Monte Carlo ground truth was a *verification* tool for the prototype, not a
  production dependency — `Bot.py`'s actual `price_option_from_parameters` is exact and
  deterministic, so it doesn't need or use Monte Carlo at runtime. `sim/harness.py` (a
  different, unrelated file despite the similar name) is the *current* local multi-session
  comparison tool used by `experimental/`'s bot lineage — see `sim/README.md`.

## Files here

- `raw/` — every original file, runnable independently as before, now importing shared types
  from the private `src` submodule instead of a local copy (the test scripts import from the
  repo-root `Bot.py`; the prototype files import `src.taqf.akuna.market_types`).
