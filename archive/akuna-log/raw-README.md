# `akuna/` — standalone pricing prototype + regression tests against `Bot.py`

Two unrelated things live in this folder — a self-contained prototype built *before* the
final `Bot.py` design settled, and a set of small regression scripts that test `Bot.py`
directly. See root `README.md`'s own section on `akuna/` for the original context.

## Standalone prototype (`mm.py`, `harness.py`)

An earlier `MarketMaker` implementation and a Monte Carlo ground-truth harness (`mc_price`,
`random_params`, `random_contract`, `init_states`), importing the shared interface types from
the private `src` submodule (`src.taqf.akuna.market_types`). Predates the pricing engine that
ended up in `Bot.py` and is kept as a reference sketch, not a drop-in final answer — useful
for cross-checking an idea in isolation before touching the graded file. Requires Python
3.11+ (`enum.StrEnum`). Not imported by `Bot.py` or anything under `experimental/`.

## Regression tests against `Bot.py` (`_world.py`, `test_*.py`)

Small, targeted scripts that `sys.path.insert` the repo root and import directly from
`Bot.py` (not from this folder's own prototype), each asserting one specific
previously-broken behavior stays fixed:

- `_world.py` — shared helper: builds a synthetic `MarketHistory` and steps a world forward
  using the THEO test's true `MarketParameters`. Imported by the other `test_*.py` scripts,
  not a test itself.
- `test_theo.py` — replicates the six THEO contracts from `TestCaseHandles.md` Test 1,
  asserts `price_option_from_parameters` matches the grader's reference values to `<1e-4`.
- `test_pricing_error.py` — reports mean absolute *live* pricing error (`price_option` vs.
  true parameters) bucketed by option type; asserts no bucket regresses past a tolerance.
- `test_rate_identification.py` — verifies the rate-reparameterization identity used by
  `warm_up`'s kappa estimation reduces correctly to the older model at the boundary case.
- `test_margin.py` — asserts the internal margin ledger matches the grader's own debit/credit
  rules line by line (buy debits `N*P`, sell debits `N*(1-P)`, a flat round trip does not
  permanently consume margin).
- `test_inventory_skew.py` — forces growing net inventory and asserts the quote stays live
  (never both sides withdrawn) with the mid moving monotonically against the position.
- `test_participation.py` — warms up at several starting-capital levels and asserts the
  degenerate `0.00`/`1.00` fallback quote fires rarely (<5%), not as the default behavior.

Run any of them directly, e.g. `python3.11 akuna/test_margin.py`, from the repo root or from
inside `akuna/` (each script fixes up `sys.path` itself). These are regression guards for
specific historical bugs, not a full test suite — see `sim/` for broader multi-session
comparison harnesses.
