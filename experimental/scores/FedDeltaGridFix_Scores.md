# Test Case Handles

**Source:** `experimental/FedDeltaGridFix.py`

**Parent:** `AthenaBot/AthenaBot.py` (promoted submission)

`FedDeltaGridFix` is `AthenaBot/AthenaBot.py` (the promoted submission,
`AthenaBot/AthenaBotScores.md`:
17.70/20, $223.07 PnL, 11/16 outright #1s) with **one targeted fix only**: the
`_numeric_delta` finite-difference bump for the FED leg now uses a full
`RATE_STRIKE_GRID` step (0.25) instead of the same relative ~1% bump used for AJR/THR.
FED only ever moves in discrete grid steps and option price is a step function of it,
so a sub-grid bump either read ~0 (understating FED risk in the portfolio skew) or
spuriously huge (straddling a strike-crossing boundary) -- this fix measures the real
one-step sensitivity instead. Everything else, **including the separately-flagged
negative-EV quote-blending issue in `_mid_and_spreads`, is deliberately left
untouched** -- that fix was applied and reverted in a prior version after scoring
worse on this same test set; `AthenaBotV2` isolates the FED-delta fix on its own so its
effect can be judged independently. See `src/AthenaBotV2.py`'s `_numeric_delta`
docstring for the full reasoning.

## Local harness check

Not run. This is a single, narrow, mechanistically-justified fix to a component
(portfolio delta skew) that only affects FED-legged options -- the real per-test
numbers below come from an actual HackerRank submission of `AthenaBotV2.py` itself.

Paste the most recent HackerRank output here after each submission, one entry per test
case. This file is the working log used to diagnose failures and prioritize
fixes -- see the "Reading test_case_handles.md" section for the triage
workflow.

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
> AthenaBot quoted buy 0.28 for 10 / sell 10 @ 0.72 (theo=0.1666)

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
3. AthenaBot: $-0.02
AthenaBot bankrupt: False (cash balance: 39.98, starting capital: 40.0)
> FED: 2.25, AJR: 1309.3, THR: 635.29
> FOK from counterparty 123260: buy 0.94 for 26 6685933 (1d THR >= 624.00)
> AthenaBot ignored the FOK (theo=0.9549)
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
> AthenaBot ignored the FOK (theo=0.7104)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1347.82, THR: 648.13
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
1. AthenaBot: $14.31
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 24.31, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $13.68
2. Stalemate Quoter: $1.0
3. AthenaBot: $-3.74
AthenaBot bankrupt: False (cash balance: 6.26, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $14.05
2. Fixed Width 0.25: $10.67
AthenaBot bankrupt: False (cash balance: 24.05, starting capital: 10.0)
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
1. AthenaBot: $24.7
2. Fixed Width 0.1: $18.2
3. Fixed Width 0.25: $3.0
AthenaBot bankrupt: False (cash balance: 34.7, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $45.06
2. Stalemate Quoter: $5.0
3. AthenaBot: $0.74
AthenaBot bankrupt: False (cash balance: 20.74, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

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

**Notes:**

---

## Test 12 — SCORED 8

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $19.66
2. Fixed Width 0.05: $-28.27
AthenaBot bankrupt: False (cash balance: 39.66, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Lattice: $9.52
2. Situational Unawareness: $7.61
3. Fixed Width 0.1: $7.29
4. AthenaBot: $3.72
AthenaBot bankrupt: False (cash balance: 23.72, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $22.78
2. Lattice: $22.43
3. Fixed Width 0.05: $-8.23
AthenaBot bankrupt: False (cash balance: 42.78, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $51.61
2. Situational Unawareness: $8.78
3. Lattice: $-6.11
AthenaBot bankrupt: False (cash balance: 71.61, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $20.81
2. Lattice: $3.27
3. AthenaBot: $-4.15
AthenaBot bankrupt: False (cash balance: 35.85, starting capital: 40.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Lattice: $19.3
2. AthenaBot: $17.17
3. Situational Unawareness: $9.68
4. Mongoose: $-8.81
AthenaBot bankrupt: False (cash balance: 57.17, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $27.9
2. AthenaBot: $11.98
3. Lattice: $-2.11
4. Mongoose: $-24.36
AthenaBot bankrupt: False (cash balance: 51.98, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $20.33
2. Situational Unawareness: $18.39
3. Mongoose: $-28.84
4. Fixed Width 0.05: $-33.5
AthenaBot bankrupt: False (cash balance: 60.33, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-5.96
2. Lattice: $-16.62
3. Mongoose: $-33.5
4. Fixed Width 0.05: $-93.13
AthenaBot bankrupt: False (cash balance: 34.04, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

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
| 13 | SCORED 9 | PASS | 0.40 | False | #4 of 4 |
| 14 | SCORED 10 | PASS | 1.00 | False | **#1 of 3** |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.40 | False | #3 of 3 |
| 17 | SCORED 13 | PASS | 0.80 | False | #2 of 4 |
| 18 | SCORED 14 | PASS | 0.80 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 1.00 | False | **#1 of 4** |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 12.90/16 points (~81%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 9 of 16 SCORED sessions.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 12.90 | 16 |
| **Total** | **16.90** | **20** |

**16.90/20 (84.5%)** overall. Total SCORED P&L: **$203.91** (sum of the 16 SCORED
test P&Ls above), against **9/16** outright #1 finishes.
