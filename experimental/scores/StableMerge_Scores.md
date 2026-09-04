# Test Case Handles

**Source:** `experimental/StableMerge.py`

**Parent:** `PortfolioDeltaSkew.py`

This mixture combines Archived-A's (16.60/20, the highest-scoring source bot) three-zone
confidence quoting, counterparty-toxicity/markout tracking, and small-book capital-scale
utilisation boost -- all left untouched, since that stack has zero recorded bankruptcies and
ranks #1 in 8 of 16 SCORED sessions across its own real HackerRank runs -- with PortfolioDeltaSkew's
portfolio-level cross-underlying delta skew (numeric Greeks aggregated across every open
position into a single portfolio risk score, clamped and converted into a price skew) swapped
in for the simpler single-option net-position skew the top scorer otherwise uses. The bet is
that a more informed skew signal (aware that two different options can both be secretly long the
same AJR-vs-THR risk) improves on the top scorer's PnL without touching any of its proven hard
solvency gates.

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
1. AthenaBot: $17.0
2. Fixed Width 0.05: $-22.47
AthenaBot bankrupt: False (cash balance: 37.0, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $17.17
2. Lattice: $6.38
3. Situational Unawareness: $2.59
4. AthenaBot: $0.82
AthenaBot bankrupt: False (cash balance: 20.82, starting capital: 20.0)
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
3. Fixed Width 0.05: $-0.22
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
1. AthenaBot: $30.06
2. Situational Unawareness: $9.45
3. Lattice: $-4.96
AthenaBot bankrupt: False (cash balance: 50.06, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $23.16
2. Fixed Width 0.05: $17.02
3. Lattice: $4.52
AthenaBot bankrupt: False (cash balance: 63.16, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.19
2. Situational Unawareness: $12.38
3. Lattice: $7.61
4. Mongoose: $2.11
AthenaBot bankrupt: False (cash balance: 56.19, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $28.93
2. AthenaBot: $28.06
3. Lattice: $-0.08
4. Mongoose: $-24.86
AthenaBot bankrupt: False (cash balance: 68.06, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $19.77
2. AthenaBot: $-4.59
3. Mongoose: $-12.92
4. Fixed Width 0.05: $-28.52
AthenaBot bankrupt: False (cash balance: 35.41, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Lattice: $-23.68
2. AthenaBot: $-24.97
3. Mongoose: $-32.02
4. Fixed Width 0.05: $-71.12
AthenaBot bankrupt: False (cash balance: 15.03, starting capital: 40.0)
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
| 18 | SCORED 14 | PASS | 0.80 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 0.80 | False | #2 of 4 |
| 20 | SCORED 16 | PASS | 0.80 | False | #2 of 4 |

**SCORED subtotal: 13.00/16 points (~81%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 8 of 16 SCORED sessions.

## Overall points (max 20)

Each test case is worth 1 point at full credit: THEO and the 3 VERBOSE tests are pass/fail (1
point each), and the 16 SCORED tests each contribute their fractional `score` (0.00-1.00)
directly as points, per `README.md`'s "full credit for #1 by PnL, zero for bankruptcy, partial
for solvency" rule.

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 13.00 | 16 |
| **Total** | **17.00** | **20** |

**17.00/20 (85.0%)** overall.
