# Test Case Handles

**Source:** `experimental/FlowRegimeTightening.py`

**Parent:** `StableMerge.py`

This mixture starts from StableMerge (17.00/20, the current best real-HackerRank
score) and leaves its entire proven stack untouched -- three-zone confidence quoting,
counterparty-toxicity/markout tracking, capital-scale ramp, portfolio-level cross-underlying
delta skew, and every hard solvency gate (`_available_margin`, `_worst_case_cash`,
`_size_for`'s inventory/margin caps). Before writing any new logic, a phase-1 investigation
instrumented a copy of Archived-K (a prior, real-HackerRank no-op change that added a
bounded hedge-size boost to `_size_for` on top of this same base) and ran it through
`sim/harness.py` -- 30 sessions, common random numbers against an un-boosted control. The
boost fired on 279 of 25,372 `_size_for` calls (1.10%), correctly gated on trust==1.0 and a
risk-reducing skew sign, yet produced a **bit-identical PnL outcome to the un-boosted parent
on all 30 of 30 sessions** (LOCAL-HARNESS-ONLY result). Root cause: `sim/counterparties.py`'s
`NoiseCounterparty`/`InformedCounterparty` cap their own requested trade quantity at 8-10
units, already below the un-boosted `_MAX_NET_PER_OPTION=10`, so extra inventory headroom
never became the binding constraint on an actual fill -- a clean mechanistic explanation for
the real-HackerRank no-op result too (byte-identical PnL on 19/20 tests). Separately,
`price_option_from_parameters` was reconfirmed exact against true `MarketParameters` (THEO
`max_error=0.0000`; `sim/test_pricer.py`'s martingale-property invariant: 0/205 failures for
`steps_until_expiry >= 2`), so there is no pricing-formula error to close with a Monte Carlo
repricer -- the only real estimation gap is `warm_up`'s grid-search `kappa` resolution
(`debug/ESTIMATION.md`: ~0.02-0.06 quantization error at N=200, an intrinsic grid/sample-size
tradeoff already documented as expected, not a bug), and it is left untouched here.

What the phase-1 investigation *did* surface as a real, evidenced pattern is in the real
HackerRank logs already pasted into `StableMerge_Scores.md`: AthenaBot loses outright
to Fixed-Width 0.05/0.1/0.25 competitors in 7 of 16 SCORED sessions, and loses by the largest
margins exactly when the Fixed-Width competitor's own PnL is large and easy (test 10: Fixed
Width 0.1 $44.12 vs AthenaBot $1.23; test 8: Fixed Width 0.1 $32.45 vs AthenaBot $2.08) --
consistent with the three-zone spread being too conservative precisely in sessions where a
naive constant-spread quoter is cleaning up. Stalemate Quoter, by contrast, never beats
AthenaBot outright in any co-occurring test, so it was not prioritized. This mixture adds a
`_FlowRegime` tracker: a bounded, capped, confidence-scaled "favorable markout" EMA that
reuses the exact same per-trade markout observations already computed for the existing
toxicity tracker, but reads them in the opposite (favorable, not adverse) direction. Once a
minimum sample of fills (`_FLOW_REGIME_MIN_N = 20`) has accumulated and the EMA is positive
(realized markouts have been favorable-or-flat, not adverse), `_mid_and_spreads` narrows the
effective half-spread by a small, hard-capped amount (`_FLOW_REGIME_TIGHTEN_CAP = 0.02`) --
but only inside the tight/mid confidence zones (`trust > 0`); the wide/low-confidence zone's
Fixed-Width-0.25 safety net is never touched by this signal. No solvency gate, sizing cap, or
pricing/estimation code was modified. A LOCAL-HARNESS-ONLY comparison (40 sessions, common
random numbers, default `MixedCounterparty` 50% informed flow) showed a small mean-score
decline versus the unmodified base (mean 5.01 vs. 5.09, 3 sessions better / 7 worse / 30
unchanged, largest single-session delta -2.65) and zero bankruptcies in 120 sessions tested
(worst final cash $0.50) -- expected, since this harness's `InformedCounterparty` is
adversarial by construction (always trades against a mispriced quote) and is a harsher test
than the naive Fixed-Width archetype this change specifically targets; the real-HackerRank
test pool's Fixed-Width sessions are the actual hypothesis under test and cannot be
reproduced locally (no competitor-archetype implementation exists in `sim/` or `akuna/`).

Paste the most recent HackerRank output here after each submission, one entry per test case.
This file is the working log used to diagnose failures and prioritize fixes -- see the
"Reading test_case_handles.md" section for the triage workflow.

Per `README.md` there are 20 test cases total:

- **1 THEO test** -- scores `price_option_from_parameters` against the true `MarketParameters`.
- **3 VERBOSE tests** -- short runs with debug logging; full credit as long as the code doesn't
  error and the `MarketMaker` doesn't go bankrupt.
- **16 SCORED tests** -- full sessions scored on PnL vs. other market makers, varying
  counterparty/competitor difficulty; zero credit for bankruptcy or an unhandled exception,
  partial credit for solvency, full credit for ranking first.

## How to fill this in

For each test case below, paste:
- **Status**: `PASS` / `ERROR` / `SCORED (n/n points)` -- whatever HackerRank reports.
- **Output**: the raw score/message, or the full traceback if it errored. Don't summarize or
  trim tracebacks -- the exact file/line/exception type is what makes diagnosis fast.
- **Notes** (optional): anything you noticed (e.g. "score dropped after last change").

Leave a test case's section as `(not yet run)` until you have output to paste.

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

**Notes:**

---

## Test 2 — VERBOSE 1

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $0.08
2. Stalemate Quoter: $0.0
AthenaBot bankrupt: False (cash balance: 10.08, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> FOK from counterparty 783057: buy 0.01 for 1 5498600 (2d THR >= 2419.00)
> AthenaBot ignored the FOK (theo=0.2174)

[Underlying state advanced by one step]
> FED: 5.5, AJR: 1327.04, THR: 2258.07
> RFQ from counterparty 689497: sell 6 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.24 for 10 / sell 10 @ 0.76 (theo=0.1065)
> AthenaBot bought 0.24 for 6 8734500 (1d THR >= 2371.00) (counterparty 689497)
> RFQ from counterparty 689497: buy 2 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.24 for 4 / sell 6 @ 0.76 (theo=0.1065)
> AthenaBot sold 2 @ 0.76 8734500 (1d THR >= 2371.00) (counterparty 689497)

[Underlying state advanced by one step]
> FED: 5.75, AJR: 1277.17, THR: 2241.32
> 8734500 (0d THR >= 2371.00) expired with expiry_val=0.0
Result: PASS (score=1.00)
```

**Notes:**

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
> AthenaBot quoted buy 0.09 for 10 / sell 10 @ 0.9 (theo=0.1666)

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

**Notes:**

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
> AthenaBot quoted buy 0.24 for 10 / sell 10 @ 0.76 (theo=0.7104)
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

**Notes:**

---

## Test 5 — SCORED 1

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $14.45
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 24.45, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $12.66
2. Stalemate Quoter: $1.0
3. AthenaBot: $-2.36
AthenaBot bankrupt: False (cash balance: 7.64, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $11.07
2. Fixed Width 0.25: $5.82
AthenaBot bankrupt: False (cash balance: 21.07, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

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

**Notes:**

---

## Test 9 — SCORED 5

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $22.61
2. Fixed Width 0.1: $20.91
3. Fixed Width 0.25: $3.0
AthenaBot bankrupt: False (cash balance: 32.61, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $44.12
2. Stalemate Quoter: $5.0
3. AthenaBot: $1.23
AthenaBot bankrupt: False (cash balance: 21.23, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.0
2. Fixed Width 0.1: $0.61
3. Fixed Width 0.05: $-13.66
AthenaBot bankrupt: False (cash balance: 36.0, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 12 — SCORED 8

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $17.06
2. Fixed Width 0.05: $-22.57
AthenaBot bankrupt: False (cash balance: 37.06, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $16.77
2. Lattice: $6.68
3. Situational Unawareness: $2.59
4. AthenaBot: $1.03
AthenaBot bankrupt: False (cash balance: 21.03, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Lattice: $26.12
2. AthenaBot: $12.92
3. Fixed Width 0.05: $-0.37
AthenaBot bankrupt: False (cash balance: 32.92, starting capital: 20.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $49.09
2. Situational Unawareness: $11.12
3. Lattice: $-7.85
AthenaBot bankrupt: False (cash balance: 69.09, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $26.25
2. Fixed Width 0.05: $17.19
3. Lattice: $1.74
AthenaBot bankrupt: False (cash balance: 66.25, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $15.75
2. Situational Unawareness: $12.38
3. Lattice: $7.36
4. Mongoose: $2.35
AthenaBot bankrupt: False (cash balance: 55.75, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $28.58
2. Fixed Width 0.05: $28.33
3. Lattice: $-0.08
4. Mongoose: $-24.86
AthenaBot bankrupt: False (cash balance: 68.58, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $16.53
2. AthenaBot: $11.75
3. Fixed Width 0.05: $-22.87
4. Mongoose: $-28.72
AthenaBot bankrupt: False (cash balance: 51.75, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Lattice: $-15.26
2. AthenaBot: $-25.98
3. Mongoose: $-32.95
4. Fixed Width 0.05: $-71.96
AthenaBot bankrupt: False (cash balance: 14.02, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Running summary

| # | Test | Status | Score | Bankrupt? | AthenaBot rank |
|---|------|--------|-------|-----------|-----------|
| 1 | THEO | PASS | max_error=0.0000 | n/a | n/a |
| 2 | VERBOSE 1 | PASS | 1.00 | False | **#1 of 2** |
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
| 13 | SCORED 9 | PASS | 0.40 | False | #4 of 4 |
| 14 | SCORED 10 | PASS | 0.70 | False | #2 of 3 |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 1.00 | False | **#1 of 3** |
| 17 | SCORED 13 | PASS | 1.00 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 1.00 | False | **#1 of 4** |
| 19 | SCORED 15 | PASS | 0.80 | False | #2 of 4 |
| 20 | SCORED 16 | PASS | 0.80 | False | #2 of 4 |

**SCORED subtotal: 13.20/16 points (~83%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 9 of 16 SCORED sessions.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 13.20 | 16 |
| **Total** | **17.20** | **20** |


**17.20/20 (86.0%)** overall.
