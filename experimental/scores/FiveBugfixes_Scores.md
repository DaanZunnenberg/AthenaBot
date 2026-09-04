# Test Case Handles

**Source:** `experimental/FiveBugfixes.py`

**Parent:** `EpsilonSharpen.py` (originally developed as `experimental/Debug.py`)

FiveBugfixes starts from `EpsilonSharpen` (17.50/20, prior real-HackerRank leader, 10/16 outright
#1 finishes) with 5 targeted bug fixes applied on top, each isolated and verified with a
repro script plus a 40-seed local harness comparison before moving to the next. Full
per-fix detail is in the `MarketMaker` class docstring and inline `FIX N:` comments in
`FiveBugfixes.py`. Summary:

- **FIX 1** (`_mid_and_spreads`): the trust-weighted midpoint blend toward 0.5 used to
  price one side of the quote through fair value itself (negative edge by the bot's own
  model, not just a thin spread). Now always quotes around `fair`; uncertainty widens
  the spread symmetrically instead of shifting the midpoint.
- **FIX 2** (`respond_to_fok`): now routes through the same `_size_for` inventory cap
  `quote()` uses (previously unenforced there -- verified 20x the stated cap, 200 vs 10,
  reachable via repeated FOKs), and matches `quote()`'s floor/ceil rounding and
  utilisation-scaled margin budget instead of the wider `_available_margin()`.
- **FIX 3** (`_drawdown_severity`): now measures mark-to-market PnL (cash plus the
  current fair value of open positions), not raw cash alone -- previously a flat,
  zero-EV buy and its symmetric zero-EV sell tripped severity 1.0 vs 0.0 purely from
  inventory sign, not actual loss.
- **FIX 4** (`on_trade`): margin is now recomputed from net position and a
  volume-weighted average entry price, instead of accumulating every trade's gross
  debit forever -- previously a buy-then-sell back to flat left `_used_margin` stuck
  nonzero (verified: net=0 but used_margin=5.00 after a round trip that should cost 0).
- **FIX 5** (`_portfolio_risk_score` / `_skew_for_side` / `_numeric_delta`): underlying
  deltas are now weighted by each underlying's own one-step volatility before being
  combined (raw FED delta was ~265x AJR's on comparable options, making the portfolio
  skew effectively FED-only and saturating the skew cap at a single FED contract); the
  skew calculation drops a side-independent squared term that was widening both sides
  equally instead of skewing; and the FED numeric-delta bump is now a full
  `RATE_STRIKE_GRID` step instead of a sub-grid relative bump that finite-differenced a
  step function inside one lattice cell.

A LOCAL-HARNESS-ONLY comparison (`sim/harness.py`-style self-contained comparator, 40
seeded sessions, common random numbers, `EpsilonSharpen` vs. `Debug.py`/`FiveBugfixes`) after all
5 fixes: `mean_score=2.0108` vs. `2.0530` baseline (-0.0423, ~2%), 0/40 bankrupt both,
19 wins / 4 ties / 17 losses -- near parity locally despite fixing 5 real,
independently-verified bugs. Each fix was also checked individually against a targeted
repro script confirming the specific bug closed (no negative-edge quotes, FOK inventory
respected, symmetric drawdown severity, margin returns to ~0 on a flat round trip,
AJR/THR positions now produce nonzero skew). THEO stayed `max_error=0.0000` throughout
every fix. Real-HackerRank payoff could only be judged on submission -- see below.

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
1. AthenaBot: $0.84
2. Stalemate Quoter: $0.0
AthenaBot bankrupt: False (cash balance: 10.84, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> FOK from counterparty 783057: buy 0.01 for 1 5498600 (2d THR >= 2419.00)
> AthenaBot ignored the FOK (theo=0.2174)

[Underlying state advanced by one step]
> FED: 5.5, AJR: 1327.04, THR: 2258.07
> RFQ from counterparty 689497: sell 6 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.0 for 10 / sell 10 @ 0.42 (theo=0.1065)
> AthenaBot bought 0.0 for 3 8734500 (1d THR >= 2371.00) (counterparty 689497)
> RFQ from counterparty 689497: buy 2 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.0 for 7 / sell 9 @ 0.42 (theo=0.1065)
> AthenaBot sold 2 @ 0.42 8734500 (1d THR >= 2371.00) (counterparty 689497)

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
> AthenaBot ignored the FOK (theo=0.9989)
> RFQ from counterparty 309546: buy 3 3857985 (1d FED >= 1.75)
> AthenaBot quoted buy 0.0 for 10 / sell 10 @ 0.48 (theo=0.1666)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1142.9, THR: 1794.43
> FOK from counterparty 482453: sell 9 @ 0.99 4895269 (1d THR >= 1735.00)
> AthenaBot ignored the FOK (theo=0.9999)
> FOK from counterparty 101661: sell 8 @ 0.99 1280022 (2d THR - AJR >= 0.00)
> AthenaBot ignored the FOK (theo=1.0000)

[Underlying state advanced by one step]
> FED: 1.5, AJR: 1162.7, THR: 1808.13
> RFQ from counterparty 474121: buy 4 1280022 (1d THR - AJR >= 0.00)
> AthenaBot quoted buy 0.83 for 10 / sell 10 @ 1.0 (theo=1.0000)
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
3. AthenaBot: $0.0
AthenaBot bankrupt: False (cash balance: 40.0, starting capital: 40.0)
> FED: 2.25, AJR: 1309.3, THR: 635.29
> FOK from counterparty 123260: buy 0.94 for 26 6685933 (1d THR >= 624.00)
> AthenaBot ignored the FOK (theo=0.9549)
> FOK from counterparty 469703: buy 0.39 for 11 4986864 (2d AJR >= 1315.00)
> AthenaBot ignored the FOK (theo=0.4437)
> FOK from counterparty 469703: buy 0.99 for 2 6685933 (1d THR >= 624.00)
> AthenaBot ignored the FOK (theo=0.9549)

[Underlying state advanced by one step]
> FED: 2.25, AJR: 1324.96, THR: 651.85
> RFQ from counterparty 469703: sell 11 4986864 (1d AJR >= 1315.00)
> AthenaBot quoted buy 0.4 for 10 / sell 10 @ 1.0 (theo=0.7104)
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
1. AthenaBot: $13.79
2. Stalemate Quoter: $12.0
AthenaBot bankrupt: False (cash balance: 23.79, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $9.21
2. AthenaBot: $2.71
3. Stalemate Quoter: $0.0
AthenaBot bankrupt: False (cash balance: 12.71, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $24.79
2. AthenaBot: $-2.46
AthenaBot bankrupt: False (cash balance: 7.54, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 8 — SCORED 4

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $31.29
2. AthenaBot: $4.04
3. Stalemate Quoter: $1.0
AthenaBot bankrupt: False (cash balance: 14.04, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 9 — SCORED 5

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $20.58
2. AthenaBot: $19.54
3. Fixed Width 0.25: $0.76
AthenaBot bankrupt: False (cash balance: 29.54, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $37.8
2. AthenaBot: $9.4
3. Stalemate Quoter: $5.0
AthenaBot bankrupt: False (cash balance: 29.4, starting capital: 20.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $4.68
2. Fixed Width 0.1: $1.35
3. Fixed Width 0.05: $-0.06
AthenaBot bankrupt: False (cash balance: 24.68, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 12 — SCORED 8

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $19.05
2. Fixed Width 0.05: $-19.77
AthenaBot bankrupt: False (cash balance: 39.05, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $16.43
2. Lattice: $9.89
3. Situational Unawareness: $5.3
4. AthenaBot: $-0.93
AthenaBot bankrupt: False (cash balance: 19.07, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Lattice: $22.87
2. Fixed Width 0.05: $10.67
3. AthenaBot: $6.04
AthenaBot bankrupt: False (cash balance: 26.04, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $19.8
2. Situational Unawareness: $10.62
3. Lattice: $9.84
AthenaBot bankrupt: False (cash balance: 39.8, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $12.86
2. AthenaBot: $9.3
3. Lattice: $3.0
AthenaBot bankrupt: False (cash balance: 49.3, starting capital: 40.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $15.86
2. Situational Unawareness: $12.79
3. Lattice: $8.3
4. Mongoose: $-31.88
AthenaBot bankrupt: False (cash balance: 55.86, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $28.33
2. AthenaBot: $19.03
3. Lattice: $-1.26
4. Mongoose: $-31.02
AthenaBot bankrupt: False (cash balance: 59.03, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $28.9
2. Situational Unawareness: $19.96
3. Mongoose: $-30.19
4. Fixed Width 0.05: $-39.99
AthenaBot bankrupt: False (cash balance: 68.9, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $23.22
2. Lattice: $-13.88
3. Mongoose: $-32.79
4. Fixed Width 0.05: $-110.48
AthenaBot bankrupt: False (cash balance: 63.22, starting capital: 40.0)
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
| 5 | SCORED 1 | PASS | 1.00 | False | **#1 of 2** |
| 6 | SCORED 2 | PASS | 0.70 | False | #2 of 3 |
| 7 | SCORED 3 | PASS | 0.40 | False | #2 of 2 |
| 8 | SCORED 4 | PASS | 0.70 | False | #2 of 3 |
| 9 | SCORED 5 | PASS | 0.70 | False | #2 of 3 |
| 10 | SCORED 6 | PASS | 0.70 | False | #2 of 3 |
| 11 | SCORED 7 | PASS | 1.00 | False | **#1 of 3** |
| 12 | SCORED 8 | PASS | 1.00 | False | **#1 of 2** |
| 13 | SCORED 9 | PASS | 0.40 | False | #4 of 4 |
| 14 | SCORED 10 | PASS | 0.40 | False | #3 of 3 |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.70 | False | #2 of 3 |
| 17 | SCORED 13 | PASS | 1.00 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 0.80 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 1.00 | False | **#1 of 4** |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 12.50/16 points (~78%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 7 of 16 SCORED sessions.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 12.50 | 16 |
| **Total** | **16.50** | **20** |


**16.50/20 (82.5%)** overall.
