# Test Case Handles

**Source:** `experimental/PortfolioDeltaSkew.py`

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
1. AthenaBot: $0.18
2. Stalemate Quoter: $0.0
AthenaBot bankrupt: False (cash balance: 10.18, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> FOK from counterparty 783057: buy 0.01 for 1 5498600 (2d THR >= 2419.00)
> AthenaBot ignored the FOK (theo=0.1989)

[Underlying state advanced by one step]
> FED: 5.5, AJR: 1327.04, THR: 2258.07
> RFQ from counterparty 689497: sell 6 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.02 for 10 / sell 7 @ 0.15 (theo=0.0853)
> AthenaBot bought 0.02 for 6 8734500 (1d THR >= 2371.00) (counterparty 689497)
> RFQ from counterparty 689497: buy 2 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.02 for 4 / sell 6 @ 0.15 (theo=0.0853)
> AthenaBot sold 2 @ 0.15 8734500 (1d THR >= 2371.00) (counterparty 689497)

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
2. AthenaBot: $0.0
3. Stalemate Quoter: $0.0
AthenaBot bankrupt: False (cash balance: 20.0, starting capital: 20.0)
> FED: 1.5, AJR: 1143.14, THR: 1787.62
> FOK from counterparty 482453: buy 0.99 for 2 4895269 (2d THR >= 1735.00)
> AthenaBot ignored the FOK (theo=0.9995)
> RFQ from counterparty 309546: buy 3 3857985 (1d FED >= 1.75)
> AthenaBot quoted buy 0.0 for 10 / sell 10 @ 0.36 (theo=0.1429)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1142.9, THR: 1794.43
> FOK from counterparty 482453: sell 9 @ 0.99 4895269 (1d THR >= 1735.00)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 101661: sell 8 @ 0.99 1280022 (2d THR - AJR >= 0.00)
> AthenaBot ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1162.7, THR: 1808.13
> RFQ from counterparty 474121: buy 4 1280022 (1d THR - AJR >= 0.00)
> AthenaBot quoted buy 0.94 for 10 / sell 10 @ 1.0 (theo=1.0000)
> AthenaBot sold 2 @ 1.0 1280022 (1d THR - AJR >= 0.00) (counterparty 474121)
> FOK from counterparty 482453: buy 0.99 for 8 5517759 (1d THR >= 1523.00)
> AthenaBot ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 1.25, AJR: 1194.78, THR: 1863.33
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
3. AthenaBot: $-3.74
AthenaBot bankrupt: False (cash balance: 36.26, starting capital: 40.0)
> FED: 2.25, AJR: 1309.3, THR: 635.29
> FOK from counterparty 123260: buy 0.94 for 26 6685933 (1d THR >= 624.00)
> AthenaBot ignored the FOK (theo=0.9497)
> FOK from counterparty 469703: buy 0.39 for 11 4986864 (2d AJR >= 1315.00)
> AthenaBot ignored the FOK (theo=0.4141)
> FOK from counterparty 469703: buy 0.99 for 2 6685933 (1d THR >= 624.00)
> AthenaBot ignored the FOK (theo=0.9497)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1324.96, THR: 651.85
> RFQ from counterparty 469703: sell 11 4986864 (1d AJR >= 1315.00)
> AthenaBot quoted buy 0.65 for 10 / sell 10 @ 0.78 (theo=0.7181)
> FOK from counterparty 808858: buy 0.99 for 16 4765820 (2d FED >= 1.50)
> AthenaBot ignored the FOK (theo=1.0000)
> FOK from counterparty 578477: buy 0.78 for 17 4986864 (1d AJR >= 1315.00)
> AthenaBot accepted the FOK (theo=0.7181)
> AthenaBot sold 17 @ 0.78 4986864 (1d AJR >= 1315.00) (counterparty 578477)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1347.82, THR: 648.13
> 4986864 (0d AJR >= 1315.00) expired with expiry_val=1.0
> FOK from counterparty 757814: sell 25 @ 0.01 7933446 (1d AJR >= 1408.00)
> AthenaBot ignored the FOK (theo=0.0014)
> FOK from counterparty 808858: buy 0.99 for 26 7316899 (1d FED >= 1.00)
> AthenaBot ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1361.52, THR: 690.84
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 5 — SCORED 1

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Stalemate Quoter: $23.0
2. AthenaBot: $4.03
AthenaBot bankrupt: False (cash balance: 14.03, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $13.58
2. Stalemate Quoter: $1.0
3. AthenaBot: $-5.39
AthenaBot bankrupt: False (cash balance: 4.61, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $27.39
2. AthenaBot: $-4.36
AthenaBot bankrupt: False (cash balance: 5.64, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 8 — SCORED 4

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $33.27
2. AthenaBot: $2.02
3. Stalemate Quoter: $2.0
AthenaBot bankrupt: False (cash balance: 12.02, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 9 — SCORED 5

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $29.42
2. AthenaBot: $5.54
3. Fixed Width 0.25: $2.76
AthenaBot bankrupt: False (cash balance: 15.54, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $46.19
2. Stalemate Quoter: $5.0
3. AthenaBot: $1.11
AthenaBot bankrupt: False (cash balance: 21.11, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $23.15
2. Fixed Width 0.1: $0.61
3. Fixed Width 0.05: $-24.86
AthenaBot bankrupt: False (cash balance: 43.15, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 12 — SCORED 8

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $11.34
2. Fixed Width 0.05: $-24.02
AthenaBot bankrupt: False (cash balance: 31.34, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Lattice: $16.92
2. AthenaBot: $13.9
3. Situational Unawareness: $3.8
4. Fixed Width 0.1: $0.76
AthenaBot bankrupt: False (cash balance: 33.9, starting capital: 20.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Lattice: $24.03
2. Fixed Width 0.05: $9.51
3. AthenaBot: $-1.72
AthenaBot bankrupt: False (cash balance: 18.28, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $53.76
2. Situational Unawareness: $6.08
3. Lattice: $4.39
AthenaBot bankrupt: False (cash balance: 73.76, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.56
2. Fixed Width 0.05: $14.5
3. Lattice: $5.14
AthenaBot bankrupt: False (cash balance: 56.56, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=0.60)

**Output:**
```
Ranking:
1. Situational Unawareness: $15.92
2. Lattice: $4.19
3. AthenaBot: $3.52
4. Mongoose: $1.23
AthenaBot bankrupt: False (cash balance: 43.52, starting capital: 40.0)
Result: PASS (score=0.60)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.60)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $33.61
2. Lattice: $3.91
3. AthenaBot: $-7.0
4. Mongoose: $-28.97
AthenaBot bankrupt: False (cash balance: 33.0, starting capital: 40.0)
Result: PASS (score=0.60)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $18.63
2. AthenaBot: $-9.8
3. Mongoose: $-23.51
4. Fixed Width 0.05: $-30.21
AthenaBot bankrupt: False (cash balance: 30.2, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-21.0
2. Lattice: $-24.67
3. Mongoose: $-32.94
4. Fixed Width 0.05: $-86.45
AthenaBot bankrupt: False (cash balance: 19.0, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Running summary

| # | Test | Status | Score | Bankrupt? | AthenaBot rank |
|---|------|--------|-------|-----------|-----------|
| 1 | THEO | PASS | max_error=0.0000 | n/a | n/a |
| 2 | VERBOSE 1 | PASS | 1.00 | False | **#1 of 2** |
| 3 | VERBOSE 2 | PASS | 1.00 | False | #2 of 3 |
| 4 | VERBOSE 3 | PASS | 1.00 | False | #3 of 3 |
| 5 | SCORED 1 | PASS | 0.40 | False | #2 of 2 |
| 6 | SCORED 2 | PASS | 0.40 | False | #3 of 3 |
| 7 | SCORED 3 | PASS | 0.40 | False | #2 of 2 |
| 8 | SCORED 4 | PASS | 0.70 | False | #2 of 3 |
| 9 | SCORED 5 | PASS | 0.70 | False | #2 of 3 |
| 10 | SCORED 6 | PASS | 0.40 | False | #3 of 3 |
| 11 | SCORED 7 | PASS | 1.00 | False | **#1 of 3** |
| 12 | SCORED 8 | PASS | 1.00 | False | **#1 of 2** |
| 13 | SCORED 9 | PASS | 0.80 | False | #2 of 4 |
| 14 | SCORED 10 | PASS | 0.40 | False | #3 of 3 |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 1.00 | False | **#1 of 3** |
| 17 | SCORED 13 | PASS | 0.60 | False | #3 of 4 |
| 18 | SCORED 14 | PASS | 0.60 | False | #3 of 4 |
| 19 | SCORED 15 | PASS | 0.80 | False | #2 of 4 |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 11.20/16 points (~70%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 5 of 16 SCORED sessions.

## Overall points (max 20)

Each test case is worth 1 point at full credit: THEO and the 3 VERBOSE tests are pass/fail (1
point each, awarded in full since they passed), and the 16 SCORED tests each contribute their
fractional `score` (0.00-1.00) directly as points, per `README.md`'s "full credit for #1 by
PnL, zero for bankruptcy, partial for solvency" rule.

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 11.20 | 16 |
| **Total** | **15.20** | **20** |

**15.20/20 (76.0%)** overall.
