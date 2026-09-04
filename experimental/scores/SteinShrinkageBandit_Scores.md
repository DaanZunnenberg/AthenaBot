# Test Case Handles

**Source:** `experimental/SteinShrinkageBandit.py`

**Parent:** `Archived-A (archived, not renamed)`

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
1. Stalemate Quoter: $0.0
2. AthenaBot: $-3.03
AthenaBot bankrupt: False (cash balance: 6.97, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> RFQ from counterparty 675208: sell 7 8734500 (2d THR >= 2371.00)
> AthenaBot quoted buy 0.25 for 10 / sell 10 @ 0.75 (theo=0.3925)
> AthenaBot bought 0.25 for 7 8734500 (2d THR >= 2371.00) (counterparty 675208)

[Underlying state advanced by one step]
> FED: 6.0, AJR: 1413.82, THR: 2314.94
> FOK from counterparty 957581: sell 4 @ 0.32 8734500 (1d THR >= 2371.00)
> AthenaBot accepted the FOK (theo=0.4004)
> AthenaBot bought 0.32 for 4 8734500 (1d THR >= 2371.00) (counterparty 957581)

[Underlying state advanced by one step]
> FED: 6.0, AJR: 1386.78, THR: 2314.99
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
1. Fixed Width 0.1: $2.6
2. Stalemate Quoter: $0.0
3. AthenaBot: $-1.64
AthenaBot bankrupt: False (cash balance: 18.36, starting capital: 20.0)
> FED: 1.5, AJR: 1143.14, THR: 1787.62
> RFQ from counterparty 843780: sell 9 5517759 (3d THR >= 1523.00)
> AthenaBot quoted buy 0.45 for 10 / sell 10 @ 0.56 (theo=1.0000)
> RFQ from counterparty 431422: sell 3 4895269 (2d THR >= 1735.00)
> AthenaBot quoted buy 0.45 for 10 / sell 10 @ 0.56 (theo=0.9989)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1158.04, THR: 1796.58
> RFQ from counterparty 431422: sell 4 5517759 (2d THR >= 1523.00)
> AthenaBot quoted buy 0.4 for 10 / sell 10 @ 0.6 (theo=1.0000)
> FOK from counterparty 316783: sell 24 @ 0.99 5517759 (2d THR >= 1523.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 435317: buy 0.87 for 12 5517759 (2d THR >= 1523.00)
> AthenaBot accepted the FOK (theo=1.0000)
> AthenaBot sold 12 @ 0.87 5517759 (2d THR >= 1523.00) (counterparty 435317)

[Underlying state advanced by one step]
> FED: 1.25, AJR: 1186.26, THR: 1831.48
> RFQ from counterparty 731130: sell 10 2124055 (1d THR - AJR >= 0.00)
> AthenaBot quoted buy 0.4 for 10 / sell 10 @ 0.6 (theo=1.0000)
> FOK from counterparty 843780: sell 9 @ 0.99 2124055 (1d THR - AJR >= 0.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 857730: buy 0.99 for 8 2124055 (1d THR - AJR >= 0.00)
> AthenaBot accepted the FOK (theo=1.0000)
> AthenaBot sold 8 @ 0.99 2124055 (1d THR - AJR >= 0.00) (counterparty 857730)

[Underlying state advanced by one step]
> FED: 1.0, AJR: 1186.92, THR: 1873.46
> 5517759 (0d THR >= 1523.00) expired with expiry_val=1.0
> 2124055 (0d THR - AJR >= 0.00) expired with expiry_val=1.0
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 4 — VERBOSE 3

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $0.0
2. Mongoose: $0.0
3. Fixed Width 0.05: $-0.6
AthenaBot bankrupt: False (cash balance: 40.0, starting capital: 40.0)
> FED: 2.25, AJR: 1309.3, THR: 635.29
> FOK from counterparty 613784: sell 29 @ 0.48 4986864 (2d AJR >= 1315.00)
> AthenaBot ignored the FOK (theo=0.4437)
> FOK from counterparty 713527: sell 11 @ 0.99 7338251 (2d THR >= 621.00)
> AthenaBot ignored the FOK (theo=0.9796)
> FOK from counterparty 388108: sell 1 @ 0.99 7316899 (3d FED >= 1.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 557411: sell 11 @ 0.98 2720886 (3d THR >= 592.00)
> AthenaBot ignored the FOK (theo=0.9996)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1304.95, THR: 635.88
> FOK from counterparty 808320: buy 0.98 for 16 7316899 (2d FED >= 1.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 670799: buy 0.37 for 22 4986864 (1d AJR >= 1315.00)
> AthenaBot ignored the FOK (theo=0.3205)
> FOK from counterparty 713527: buy 0.33 for 11 4986864 (1d AJR >= 1315.00)
> AthenaBot ignored the FOK (theo=0.3205)
> RFQ from counterparty 713527: buy 1 4986864 (1d AJR >= 1315.00)
> AthenaBot quoted buy 0.2 for 10 / sell 10 @ 0.65 (theo=0.3205)

[Underlying state advanced by one step]
> FED: 2.0, AJR: 1330.18, THR: 648.75
> FOK from counterparty 808320: sell 15 @ 0.99 7316899 (1d FED >= 1.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 557411: sell 9 @ 0.9 8048737 (1d AJR >= 1300.00)
> AthenaBot ignored the FOK (theo=0.9338)
> FOK from counterparty 613784: sell 22 @ 0.98 2720886 (1d THR >= 592.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 557411: sell 30 @ 0.98 7919363 (1d AJR >= 1266.00)
> AthenaBot ignored the FOK (theo=0.9994)

[Underlying state advanced by one step]
> FED: 2.0, AJR: 1351.98, THR: 651.68
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 5 — SCORED 1

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $12.71
2. Stalemate Quoter: $11.0
AthenaBot bankrupt: False (cash balance: 22.71, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $16.37
2. Stalemate Quoter: $1.0
3. AthenaBot: $-1.49
AthenaBot bankrupt: False (cash balance: 8.51, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $18.15
2. AthenaBot: $-6.47
AthenaBot bankrupt: False (cash balance: 3.53, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 8 — SCORED 4

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $27.78
2. Stalemate Quoter: $0.0
3. AthenaBot: $-5.48
AthenaBot bankrupt: False (cash balance: 4.52, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 9 — SCORED 5

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $45.93
2. Fixed Width 0.25: $1.15
3. AthenaBot: $-4.49
AthenaBot bankrupt: False (cash balance: 5.51, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Stalemate Quoter: $0.0
2. Fixed Width 0.1: $-4.35
3. AthenaBot: $-14.99
AthenaBot bankrupt: False (cash balance: 5.01, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $23.55
2. Fixed Width 0.1: $2.79
3. AthenaBot: $-13.81
AthenaBot bankrupt: False (cash balance: 6.19, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 12 — SCORED 8

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $37.53
2. AthenaBot: $-7.0
AthenaBot bankrupt: False (cash balance: 13.0, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.60)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $7.04
2. Lattice: $2.53
3. AthenaBot: $-3.0
4. Situational Unawareness: $-4.08
AthenaBot bankrupt: False (cash balance: 17.0, starting capital: 20.0)
Result: PASS (score=0.60)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $17.57
2. Lattice: $0.39
3. AthenaBot: $-10.96
AthenaBot bankrupt: False (cash balance: 9.04, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $50.31
2. Situational Unawareness: $8.5
3. Lattice: $-6.25
AthenaBot bankrupt: False (cash balance: 70.31, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $28.18
2. Lattice: $-7.05
3. AthenaBot: $-28.97
AthenaBot bankrupt: False (cash balance: 11.03, starting capital: 40.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Situational Unawareness: $14.5
2. Mongoose: $6.02
3. Lattice: $-9.8
4. AthenaBot: $-12.75
AthenaBot bankrupt: False (cash balance: 27.25, starting capital: 40.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Mongoose: $30.97
2. Fixed Width 0.05: $12.24
3. Lattice: $-22.66
4. AthenaBot: $-28.0
AthenaBot bankrupt: False (cash balance: 12.0, starting capital: 40.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $1.68
2. AthenaBot: $-18.99
3. Mongoose: $-30.53
4. Fixed Width 0.05: $-111.88
AthenaBot bankrupt: False (cash balance: 21.01, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Lattice: $52.64
2. AthenaBot: $-21.99
3. Mongoose: $-22.07
4. Fixed Width 0.05: $-55.7
AthenaBot bankrupt: False (cash balance: 18.01, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Running summary

| # | Test | Status | Score | Bankrupt? | AthenaBot rank |
|---|------|--------|-------|-----------|-----------|
| 1 | THEO | PASS | max_error=0.0000 | n/a | n/a |
| 2 | VERBOSE 1 | PASS | 1.00 | False | #2 of 2 |
| 3 | VERBOSE 2 | PASS | 1.00 | False | #3 of 3 |
| 4 | VERBOSE 3 | PASS | 1.00 | False | **#1 of 3** |
| 5 | SCORED 1 | PASS | 1.00 | False | **#1 of 2** |
| 6 | SCORED 2 | PASS | 0.40 | False | #3 of 3 |
| 7 | SCORED 3 | PASS | 0.40 | False | #2 of 2 |
| 8 | SCORED 4 | PASS | 0.40 | False | #3 of 3 |
| 9 | SCORED 5 | PASS | 0.40 | False | #3 of 3 |
| 10 | SCORED 6 | PASS | 0.40 | False | #3 of 3 |
| 11 | SCORED 7 | PASS | 0.40 | False | #3 of 3 |
| 12 | SCORED 8 | PASS | 0.40 | False | #2 of 2 |
| 13 | SCORED 9 | PASS | 0.60 | False | #3 of 4 |
| 14 | SCORED 10 | PASS | 0.40 | False | #3 of 3 |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.40 | False | #3 of 3 |
| 17 | SCORED 13 | PASS | 0.40 | False | #4 of 4 |
| 18 | SCORED 14 | PASS | 0.40 | False | #4 of 4 |
| 19 | SCORED 15 | PASS | 0.80 | False | #2 of 4 |
| 20 | SCORED 16 | PASS | 0.80 | False | #2 of 4 |

**SCORED subtotal: 8.60/16 points (~54%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 2 of 16 SCORED sessions.

## Overall points (max 20)

Each test case is worth 1 point at full credit: THEO and the 3 VERBOSE tests are pass/fail (1
point each, awarded in full since they passed), and the 16 SCORED tests each contribute their
fractional `score` (0.00-1.00) directly as points, per `README.md`'s "full credit for #1 by
PnL, zero for bankruptcy, partial for solvency" rule.

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 8.60 | 16 |
| **Total** | **12.60** | **20** |

**12.60/20 (63.0%)** overall.
