# Test Case Handles

**Source:** `experimental/FlowCapTune04.py`

**Parent:** `DrawdownBreaker.py`

FlowCapTune04 starts from `EpsilonSharpen` (17.50/20, prior real-HackerRank leader) with its full
stack untouched, and widens two constants inside the existing `_FlowRegime` mechanism:
`_FLOW_REGIME_MIN_N` (20 -> 12) and `_FLOW_REGIME_TIGHTEN_CAP` (0.02 -> 0.04). Rationale
(full detail in the `MarketMaker` class docstring and the comments above
`_ENABLE_FLOW_REGIME` in `FlowCapTune04.py`): `EpsilonSharpen_Scores.md`'s real HackerRank logs
showed AthenaBot losing outright to naive Fixed-Width competitors specifically in calm,
low-toxicity sessions (Tests 6, 8, 10 -- Fixed-Width earned $13-47 while AthenaBot sat
flat/negative in the *same* sessions), consistent with our spreads being too wide once a
sustained favorable-markout signal should already be trusted. `_FlowRegime` already
detects this condition but was tuned conservatively relative to how few fills a short
SCORED session produces; widening its trust threshold and cap is additive-only, stays
inside the existing `_W_TIGHT=0.05` ceiling (half-spread still floored at 0.005), only
fires in the tight/mid confidence zones, and never touches sizing/margin/solvency logic.

A LOCAL-HARNESS-ONLY comparison (`sim/harness.py`, 40 seeded sessions, common random
numbers, EpsilonSharpen vs. FlowCapTune04) came back bit-identical: `mean_score=2.252` for both,
0 wins / 40 ties / 0 losses, 0 bankruptcies. The widened cap is mechanically reachable
(observed tighten values up to 0.0257, above the old 0.02 ceiling) but never flipped a
fill/no-fill decision in that batch -- plausibly because `sim/counterparties.py`'s
Noise/Informed/Mixed archetypes aren't the Fixed-Width/Lattice archetypes the hypothesis
targets (no competitor-MM model exists locally, per `EpsilonSharpen_Scores.md`'s own Phase 1
finding), so the real payoff of this change could only be judged on a real submission.

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

**Notes:**

---

## Test 5 — SCORED 1

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $13.88
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 23.88, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $13.76
2. Stalemate Quoter: $1.0
3. AthenaBot: $-4.53
AthenaBot bankrupt: False (cash balance: 5.47, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $10.65
2. Fixed Width 0.25: $5.82
AthenaBot bankrupt: False (cash balance: 20.65, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 8 — SCORED 4

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $32.88
2. Stalemate Quoter: $2.0
3. AthenaBot: $1.13
AthenaBot bankrupt: False (cash balance: 11.13, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 9 — SCORED 5

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $26.85
2. Fixed Width 0.1: $15.76
3. Fixed Width 0.25: $3.0
AthenaBot bankrupt: False (cash balance: 36.85, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $47.75
2. Stalemate Quoter: $5.0
3. AthenaBot: $-2.57
AthenaBot bankrupt: False (cash balance: 17.43, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $14.82
2. Fixed Width 0.1: $0.61
3. Fixed Width 0.05: $-14.18
AthenaBot bankrupt: False (cash balance: 34.82, starting capital: 20.0)
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
2. Fixed Width 0.05: $-19.15
AthenaBot bankrupt: False (cash balance: 39.05, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $12.7
2. Fixed Width 0.1: $8.17
3. Lattice: $7.69
4. Situational Unawareness: $3.15
AthenaBot bankrupt: False (cash balance: 32.7, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Lattice: $24.04
2. AthenaBot: $11.22
3. Fixed Width 0.05: $2.3
AthenaBot bankrupt: False (cash balance: 31.22, starting capital: 20.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $39.19
2. Situational Unawareness: $17.25
3. Lattice: $-13.28
AthenaBot bankrupt: False (cash balance: 59.19, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $42.45
2. Fixed Width 0.05: $20.82
3. Lattice: $1.3
AthenaBot bankrupt: False (cash balance: 82.45, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $12.14
2. Situational Unawareness: $11.09
3. Lattice: $8.71
4. Mongoose: $-31.88
AthenaBot bankrupt: False (cash balance: 52.14, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $29.05
2. AthenaBot: $4.44
3. Lattice: $2.08
4. Mongoose: $-31.48
AthenaBot bankrupt: False (cash balance: 44.44, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $17.98
2. AthenaBot: $12.02
3. Mongoose: $-23.23
4. Fixed Width 0.05: $-28.98
AthenaBot bankrupt: False (cash balance: 52.02, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-18.96
2. Lattice: $-19.83
3. Mongoose: $-31.86
4. Fixed Width 0.05: $-83.98
AthenaBot bankrupt: False (cash balance: 21.04, starting capital: 40.0)
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
| 8 | SCORED 4 | PASS | 0.40 | False | #3 of 3 |
| 9 | SCORED 5 | PASS | 1.00 | False | **#1 of 3** |
| 10 | SCORED 6 | PASS | 0.40 | False | #3 of 3 |
| 11 | SCORED 7 | PASS | 1.00 | False | **#1 of 3** |
| 12 | SCORED 8 | PASS | 1.00 | False | **#1 of 2** |
| 13 | SCORED 9 | PASS | 1.00 | False | **#1 of 4** |
| 14 | SCORED 10 | PASS | 0.70 | False | #2 of 3 |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 1.00 | False | **#1 of 3** |
| 17 | SCORED 13 | PASS | 1.00 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 0.80 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 0.80 | False | #2 of 4 |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 13.50/16 points (~84%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 10 of 16 SCORED sessions.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 13.50 | 16 |
| **Total** | **17.50** | **20** |


**17.50/20 (87.5%)** overall.
