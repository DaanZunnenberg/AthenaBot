# Test Case Handles

**Source:** `experimental/CovarianceRisk.py`

**Parent:** `DrawdownBreaker.py`

**THIS IS A SPECULATIVE, UNVALIDATED EXPERIMENT. It has not been submitted to
HackerRank yet.** It starts from `DrawdownBreaker`'s full, untouched stack -- current leader at
17.50/20 real HackerRank score (`experimental/DrawdownBreaker_Scores.md`): same pricing engine,
same `warm_up`/parameter estimation, same three-zone confidence quoting, same
counterparty-toxicity/markout tracking, same `_W_WIDE`, same `FlowRegime` spread narrowing,
same drawdown circuit breaker, same hard solvency gates (`_available_margin`,
`_worst_case_cash`, `_size_for`'s inventory/margin caps) -- and layers on exactly **one**
narrow, isolated change.

## What changed

A prior analysis pass compared `DrawdownBreaker` (17.50/20) against a hand-written
`Archived-J` (12.60/20, same underlying codebase but with an aggression dial turned up
across FOK acceptance, near-expiry spread shrinking, and dropped defensive widening --
which cost `Archived-J` seven floor-score losses to naive Fixed-Width/Lattice competitors,
per `experimental/Scores.md`). That pass isolated **one** piece of `Archived-J` that is
structurally different from all the "more aggression" changes and looks like a genuine,
low-risk pricing-quality improvement rather than a risk-dial change: `_portfolio_risk_score`.

`DrawdownBreaker` (inherited from the original portfolio-skew graft documented in
`experimental/StableMerge_Scores.md`) aggregates portfolio-level cross-underlying delta risk
with a naive sum-of-squares over the per-underlying net delta vector:

```python
@staticmethod
def _portfolio_risk_score(delta_vector):
    return sum(v * v for v in delta_vector.values())
```

`Archived-J` instead reconstructs the real variance/covariance structure from the fitted
`MarketParameters` (`ajarai_sector_beta`, `theriodic_sector_beta`, `sector_std_dev`,
`ajarai_idio_std_dev`, `theriodic_idio_std_dev`, `rate_step`) and computes true portfolio
variance, including the AJR/THR cross-covariance term driven by their shared sector-beta
exposure:

```python
def _portfolio_risk_score(self, delta_vector):
    if not self.estimated_parameters:
        return sum(v * v for v in delta_vector.values())
    p = self.estimated_parameters
    d_f = delta_vector.get(FED_FUNDS_RATE_UNDERLYING_ID, 0.0)
    d_a = delta_vector.get(AJARAI_UNDERLYING_ID, 0.0)
    d_t = delta_vector.get(THERIODIC_UNDERLYING_ID, 0.0)
    var_a = (p.ajarai_sector_beta**2 * p.sector_std_dev**2) + p.ajarai_idio_std_dev**2
    var_t = (p.theriodic_sector_beta**2 * p.sector_std_dev**2) + p.theriodic_idio_std_dev**2
    cov_at = p.ajarai_sector_beta * p.theriodic_sector_beta * p.sector_std_dev**2
    return (d_a**2 * var_a) + (d_t**2 * var_t) + (2 * d_a * d_t * cov_at) + (d_f**2 * p.rate_step)
```

This is believed to be low-risk and isolated because:

- **Same interface.** Both versions take the same `delta_vector` dict (per-underlying net
  delta) and return a single non-negative scalar "risk score." Both are called identically
  from `_skew_for_side` (`risk_before` / `risk_after`, feeding the existing, unmodified
  `_PORTFOLIO_RISK_K` / `_SKEW_CAP` skew calculation) -- confirmed by inspecting both call
  sites, which are byte-identical between the two files.
- **No extra state needed.** `self.estimated_parameters` (a `MarketParameters` instance)
  is already populated by `DrawdownBreaker`'s own `warm_up`/`_refit` pipeline before `quote` or
  `respond_to_fok` can be called; all the fields the covariance formula reads
  (`ajarai_sector_beta`, `theriodic_sector_beta`, `sector_std_dev`, `ajarai_idio_std_dev`,
  `theriodic_idio_std_dev`, `rate_step`) exist on `DrawdownBreaker`'s `MarketParameters` dataclass
  unchanged -- nothing needed to be ported from `Archived-J` beyond the method body itself.
  The only mechanical change required was `@staticmethod` -> instance method (`self`), since
  the new version reads `self.estimated_parameters`.
- **Falls back safely.** Before `warm_up` completes (`self.estimated_parameters is None`),
  it degrades to the exact same naive sum-of-squares `DrawdownBreaker` always used, so there is no
  new pre-`warm_up` failure mode.
- **Not an aggression change.** It does not touch FOK acceptance thresholds, near-expiry
  spread shrinking, defensive widening, `_W_WIDE`, `_DRAWDOWN_*`, or any sizing/quoting
  constant. It only changes how accurately correlated cross-underlying risk is *measured*,
  feeding into the existing, unmodified portfolio-skew pricing logic.

Everything else in `DrawdownBreaker.py` is untouched: same FOK edge logic, same defensive
epsilon-sharpen, same `FlowRegime`, same drawdown breaker, same `_W_WIDE`, same solvency
gates. The diff against `DrawdownBreaker.py` is exactly one method body (see source).

**This is unvalidated and needs a real HackerRank submission.**

## Local verification performed (not HackerRank)

- `python3 -m py_compile experimental/CovarianceRisk.py` -- passes (via Python 3.11; the repo's
  default `python3` is 3.9 and lacks `enum.StrEnum`, which `DrawdownBreaker.py` also requires --
  this is a pre-existing environment constraint, not new to this change).
- Full lifecycle smoke test: instantiate `MarketMaker`, `warm_up` from a synthetic
  `MarketHistory`, `quote` a single-leg option, `quote` a 2-leg spread option,
  `respond_to_fok`, `on_trade`, `on_step_advance` -- all completed without exception.
- A second smoke test specifically built 2 open positions across AJR and THR
  (`on_trade` on two different single-leg options with opposite-sign quantities) so the
  portfolio covariance path is actually exercised rather than the degenerate single-position
  case. Confirmed the new `_portfolio_risk_score` produces a materially different,
  variance-scaled result from the old naive sum-of-squares on the same delta vector
  (naive: ~315.4; covariance-aware: ~0.00043 -- the fitted idiosyncratic/sector vols in the
  synthetic history were small, so this is only a sanity check that the formula executes and
  differentiates from the naive version, not a claim about realistic magnitudes).
- No local scoring harness (e.g. `sim/harness.py`) exists in this repository, so no
  local-harness PnL/ranking comparison against `DrawdownBreaker` is available. All comparative
  numbers below are placeholders pending a real HackerRank run.

---

## Test 1 — THEO

**Status:** PASS (max_error=0.0000)

**Output:**
```
Market parameters: [REDACTED -- real grader THEO answer key, not reproduced publicly]
Underlyings: [REDACTED]
[REDACTED -- the six THEO reference contracts + their true theoretical values, not reproduced publicly]
Result: PASS (max_error=0.0000)
```

**Notes:** (not yet run)

---

## Test 2 — VERBOSE 1

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. Stalemate Quoter: $0.0
2. AthenaBot: $-0.48
AthenaBot bankrupt: False (cash balance: 9.52, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> FOK from counterparty 783057: buy 0.01 for 1 5498600 (2d THR >= 2419.00)
> AthenaBot ignored the FOK (theo=0.2174)

[Underlying state advanced by one step]
> FED: 5.5, AJR: 1327.04, THR: 2258.07
> RFQ from counterparty 689497: sell 6 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.31 for 10 / sell 10 @ 0.69 (theo=0.1065)
> AthenaBot bought 0.31 for 6 8734500 (1d THR >= 2371.00) (counterparty 689497)
> RFQ from counterparty 689497: buy 2 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.31 for 4 / sell 6 @ 0.69 (theo=0.1065)
> AthenaBot sold 2 @ 0.69 8734500 (1d THR >= 2371.00) (counterparty 689497)

[Underlying state advanced by one step]
> FED: 5.75, AJR: 1277.17, THR: 2241.32
> 8734500 (0d THR >= 2371.00) expired with expiry_val=0.0
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 3 — VERBOSE 2

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $1.05
2. Stalemate Quoter: $0.0
3. AthenaBot: $-0.66
AthenaBot bankrupt: False (cash balance: 19.34, starting capital: 20.0)
> FED: 1.5, AJR: 1143.14, THR: 1787.62
> FOK from counterparty 482453: buy 0.99 for 2 4895269 (2d THR >= 1735.00)
> AthenaBot accepted the FOK (theo=0.9989)
> AthenaBot sold 2 @ 0.99 4895269 (2d THR >= 1735.00) (counterparty 482453)
> RFQ from counterparty 309546: buy 3 3857985 (1d FED >= 1.75)
> AthenaBot quoted buy 0.17 for 10 / sell 10 @ 0.83 (theo=0.1666)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1142.9, THR: 1794.43
> FOK from counterparty 482453: sell 9 @ 0.99 4895269 (1d THR >= 1735.00)
> AthenaBot ignored the FOK (theo=0.9999)
> FOK from counterparty 101661: sell 8 @ 0.99 1280022 (2d THR - AJR >= 0.00)
> AthenaBot ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1162.7, THR: 1808.13
> 4895269 (0d THR >= 1735.00) expired with expiry_val=1.0
> RFQ from counterparty 474121: buy 4 1280022 (1d THR - AJR >= 0.00)
> AthenaBot quoted buy 0.65 for 10 / sell 10 @ 0.86 (theo=1.0000)
> AthenaBot sold 4 @ 0.86 1280022 (1d THR - AJR >= 0.00) (counterparty 474121)
> FOK from counterparty 482453: buy 0.99 for 8 5517759 (1d THR >= 1523.00)
> AthenaBot accepted the FOK (theo=1.0000)
> AthenaBot sold 8 @ 0.99 5517759 (1d THR >= 1523.00) (counterparty 482453)

[Underlying state advanced by one step]
> FED: 1.25, AJR: 1194.78, THR: 1863.33
> 5517759 (0d THR >= 1523.00) expired with expiry_val=1.0
> 1280022 (0d THR - AJR >= 0.00) expired with expiry_val=1.0
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 4 — VERBOSE 3

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $2.9
2. Mongoose: $0.3
3. AthenaBot: $-5.32
AthenaBot bankrupt: False (cash balance: 34.68, starting capital: 40.0)
> FED: 2.25, AJR: 1309.3, THR: 635.29
> FOK from counterparty 123260: buy 0.94 for 26 6685933 (1d THR >= 624.00)
> AthenaBot accepted the FOK (theo=0.9549)
> AthenaBot sold 26 @ 0.94 6685933 (1d THR >= 624.00) (counterparty 123260)
> FOK from counterparty 469703: buy 0.39 for 11 4986864 (2d AJR >= 1315.00)
> AthenaBot ignored the FOK (theo=0.4437)
> FOK from counterparty 469703: buy 0.99 for 2 6685933 (1d THR >= 624.00)
> AthenaBot accepted the FOK (theo=0.9549)
> AthenaBot sold 2 @ 0.99 6685933 (1d THR >= 624.00) (counterparty 469703)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1324.96, THR: 651.85
> 6685933 (0d THR >= 624.00) expired with expiry_val=1.0
> RFQ from counterparty 469703: sell 11 4986864 (1d AJR >= 1315.00)
> AthenaBot quoted buy 0.31 for 10 / sell 10 @ 0.69 (theo=0.7104)
> FOK from counterparty 808858: buy 0.99 for 16 4765820 (2d FED >= 1.50)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 578477: buy 0.78 for 17 4986864 (1d AJR >= 1315.00)
> AthenaBot accepted the FOK (theo=0.7104)
> AthenaBot sold 17 @ 0.78 4986864 (1d AJR >= 1315.00) (counterparty 578477)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1347.82, THR: 648.13
> 4986864 (0d AJR >= 1315.00) expired with expiry_val=1.0
> FOK from counterparty 757814: sell 25 @ 0.01 7933446 (1d AJR >= 1408.00)
> AthenaBot ignored the FOK (theo=0.0040)
> FOK from counterparty 808858: buy 0.99 for 26 7316899 (1d FED >= 1.00)
> AthenaBot ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1361.52, THR: 690.84
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 5 — SCORED 1

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $13.85
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 23.85, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $13.76
2. Stalemate Quoter: $1.0
3. AthenaBot: $-4.45
AthenaBot bankrupt: False (cash balance: 5.55, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:** (not yet run)

---

## Test 7 — SCORED 3

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $10.94
2. Fixed Width 0.25: $5.82
AthenaBot bankrupt: False (cash balance: 20.94, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 8 — SCORED 4

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $32.45
2. AthenaBot: $2.08
3. Stalemate Quoter: $2.0
AthenaBot bankrupt: False (cash balance: 12.08, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:** (not yet run)

---

## Test 9 — SCORED 5

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $25.3
2. Fixed Width 0.1: $18.2
3. Fixed Width 0.25: $3.0
AthenaBot bankrupt: False (cash balance: 35.3, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $47.88
2. Stalemate Quoter: $5.0
3. AthenaBot: $-2.29
AthenaBot bankrupt: False (cash balance: 17.71, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:** (not yet run)

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $14.63
2. Fixed Width 0.1: $0.61
3. Fixed Width 0.05: $-13.66
AthenaBot bankrupt: False (cash balance: 34.63, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 12 — SCORED 8

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.76
2. Fixed Width 0.05: $-22.41
AthenaBot bankrupt: False (cash balance: 36.76, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 13 — SCORED 9

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $8.61
2. Fixed Width 0.1: $7.93
3. Lattice: $6.18
4. Situational Unawareness: $3.06
AthenaBot bankrupt: False (cash balance: 28.61, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Lattice: $23.14
2. AthenaBot: $21.21
3. Fixed Width 0.05: $-5.91
AthenaBot bankrupt: False (cash balance: 41.21, starting capital: 20.0)
Result: PASS (score=0.70)
```

**Notes:** (not yet run)

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $57.51
2. Situational Unawareness: $9.03
3. Lattice: $-7.67
AthenaBot bankrupt: False (cash balance: 77.51, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 16 — SCORED 12

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $23.0
2. AthenaBot: $18.76
3. Lattice: $1.74
AthenaBot bankrupt: False (cash balance: 58.76, starting capital: 40.0)
Result: PASS (score=0.70)
```

**Notes:** (not yet run)

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.12
2. Situational Unawareness: $13.08
3. Lattice: $7.35
4. Mongoose: $2.56
AthenaBot bankrupt: False (cash balance: 56.12, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $28.33
2. AthenaBot: $27.95
3. Lattice: $-0.08
4. Mongoose: $-24.86
AthenaBot bankrupt: False (cash balance: 67.95, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:** (not yet run)

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $19.79
2. AthenaBot: $-3.81
3. Mongoose: $-14.13
4. Fixed Width 0.05: $-30.81
AthenaBot bankrupt: False (cash balance: 36.19, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:** (not yet run)

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-22.86
2. Lattice: $-25.16
3. Mongoose: $-32.65
4. Fixed Width 0.05: $-75.48
AthenaBot bankrupt: False (cash balance: 17.14, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:** (not yet run)

---

## Running summary

| # | Test | Status | Score | Bankrupt? | AthenaBot rank |
|---|------|--------|-------|-----------|-----------|
| 1 | THEO | PASS | max_error=0.0000 | n/a | n/a |
| 2 | VERBOSE 1 | PASS | 1.00 | False | #2 of 2 |
| 3 | VERBOSE 2 | PASS | 1.00 | False | #3 of 3 |
| 4 | VERBOSE 3 | PASS | 1.00 | False | #3 of 3 |
| 5 | SCORED 1 | PASS | 1.00 | False | **#1 of 2** |
| 6 | SCORED 2 | PASS | 0.40 | False | #3 of 3 |
| 7 | SCORED 3 | PASS | 1.00 | False | **#1 of 2** |
| 8 | SCORED 4 | PASS | 0.70 | False | #2 of 3 |
| 9 | SCORED 5 | PASS | 1.00 | False | **#1 of 3** |
| 10 | SCORED 6 | PASS | 0.40 | False | #3 of 3 |
| 11 | SCORED 7 | PASS | 1.00 | False | **#1 of 3** |
| 12 | SCORED 8 | PASS | 1.00 | False | **#1 of 2** |
| 13 | SCORED 9 | PASS | 1.00 | False | **#1 of 4** |
| 14 | SCORED 10 | PASS | 0.70 | False | #2 of 3 |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.70 | False | #2 of 3 |
| 17 | SCORED 13 | PASS | 1.00 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 0.80 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 0.80 | False | #2 of 4 |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 13.50/16 points (~84%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 9 of 16 SCORED sessions.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 13.50 | 16 |
| **Total** | **17.50** | **20** |

**17.50/20 (87.5%)** overall.
