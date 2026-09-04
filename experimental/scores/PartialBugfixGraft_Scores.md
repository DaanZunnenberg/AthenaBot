# Test Case Handles

**Source:** `experimental/PartialBugfixGraft.py`

**Parent:** `EpsilonSharpen.py`

PartialBugfixGraft starts from `EpsilonSharpen` (17.50/20, 10/16 outright #1 finishes) and applies 3 of
the 5 bug fixes developed for `experimental/FiveBugfixes.py`, deliberately omitting the other
2. Full per-fix detail is in the `MarketMaker` class docstring in `PartialBugfixGraft.py`. Summary:

**Context.** `FiveBugfixes` (all 5 fixes applied) scored 16.50/20 on real HackerRank, DOWN
from `EpsilonSharpen`'s 17.50/20 -- the regression was concentrated in sessions `EpsilonSharpen` had
previously been winning outright against Fixed-Width competitors (tests 7, 9, 13, 14, 16
all flipped from #1 to a loss; see `experimental/FiveBugfixes_Scores.md`). That was traced to
two specific fixes: FIX 1 (the mid-blend rewrite in `_mid_and_spreads`) traded away real
edge on a quote side that was never actually crossing fair value, and FIX 4 (margin
netting in `on_trade`) freed up margin that plausibly amplified variance on top of that.

**KEPT (no evidence of harm in the FiveBugfixes test-by-test):**
- **FIX 2** (`respond_to_fok`): routes through `_size_for`'s inventory cap (previously
  unenforced there -- verified 20x the stated cap reachable via repeated FOKs), and
  matches `quote()`'s floor/ceil rounding and utilisation-scaled margin budget instead of
  the wider `_available_margin()`.
- **FIX 3** (`_drawdown_severity`): measures mark-to-market PnL (cash plus the current
  fair value of open positions), not raw cash alone -- previously a flat, zero-EV buy and
  its symmetric zero-EV sell tripped drawdown severity 1.0 vs 0.0 purely from inventory
  sign, not actual loss.
- **FIX 5** (`_portfolio_risk_score` / `_skew_for_side` / `_numeric_delta`): underlying
  deltas are weighted by each underlying's own one-step volatility before being combined
  (raw FED delta was ~265x AJR's, making the portfolio skew effectively FED-only); the
  skew calculation drops a side-independent squared term that was widening both sides
  instead of skewing; the FED numeric-delta bump is a full `RATE_STRIKE_GRID` step.

**OMITTED (left as `EpsilonSharpen`'s original, unmodified behavior):**
- **FIX 1** (`_mid_and_spreads` mid-blend) and **FIX 4** (`on_trade` margin netting) --
  both close real bugs, but their net effect in the combined `FiveBugfixes` submission was
  negative or too entangled with the regression to trust without further isolation.
  `_mid_and_spreads` and `on_trade` in `PartialBugfixGraft.py` are byte-identical to `EpsilonSharpen.py`'s
  originals (verified directly).

## Local harness check (local-harness-only, does not represent Fixed-Width/Lattice/
Situational-Unawareness archetypes)

A self-contained comparator (own-classes-per-module, matching `sim/compare_prompt0.py`'s
pattern; `sim/harness.py`'s own built-in counterparties do not replicate the named
competitor bots this grader runs against) ran `PartialBugfixGraft` vs. unmodified `EpsilonSharpen`, 40
seeded sessions, common random numbers: `mean_score=2.6353` vs. `2.0530` baseline
(**+0.5822, ~28%**), 0/40 bankrupt both, **24 wins / 5 ties / 11 losses** -- notably
better locally than `FiveBugfixes`'s all-5-fixes result (`mean_score=2.0108`, -0.0423 vs.
baseline). This is a real, positive local signal for the selective (3-of-5) build, but it
still cannot represent the named HackerRank competitor archetypes, so the real payoff
could only be judged on submission -- see below.

`python3.11 -m py_compile` passes; THEO reconfirmed exact (`max_error=0.0000`); AST diff
against a pre-trim backup confirms the file-size trim needed to pass HackerRank's
submission-size ceiling changed zero executable logic (docstrings/comments only).

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
2. AthenaBot: $-0.56
AthenaBot bankrupt: False (cash balance: 9.44, starting capital: 10.0)
> FED: 5.75, AJR: 1391.0, THR: 2269.23
> FOK from counterparty 783057: buy 0.01 for 1 5498600 (2d THR >= 2419.00)
> AthenaBot ignored the FOK (theo=0.2174)

[Underlying state advanced by one step]
> FED: 5.5, AJR: 1327.04, THR: 2258.07
> RFQ from counterparty 689497: sell 6 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.32 for 10 / sell 10 @ 0.68 (theo=0.1065)
> AthenaBot bought 0.32 for 6 8734500 (1d THR >= 2371.00) (counterparty 689497)
> RFQ from counterparty 689497: buy 2 8734500 (1d THR >= 2371.00)
> AthenaBot quoted buy 0.32 for 4 / sell 6 @ 0.68 (theo=0.1065)
> AthenaBot sold 2 @ 0.68 8734500 (1d THR >= 2371.00) (counterparty 689497)

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
> AthenaBot quoted buy 0.32 for 10 / sell 10 @ 0.68 (theo=0.1666)

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
> AthenaBot quoted buy 0.32 for 10 / sell 10 @ 0.68 (theo=0.7104)
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
1. AthenaBot: $14.16
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 24.16, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 6 — SCORED 2

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $14.24
2. Stalemate Quoter: $1.0
3. AthenaBot: $-3.91
AthenaBot bankrupt: False (cash balance: 6.09, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 7 — SCORED 3

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.25: $10.27
2. AthenaBot: $5.31
AthenaBot bankrupt: False (cash balance: 15.31, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 8 — SCORED 4

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $32.74
2. Stalemate Quoter: $2.0
3. AthenaBot: $1.13
AthenaBot bankrupt: False (cash balance: 11.13, starting capital: 10.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 9 — SCORED 5

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $27.03
2. AthenaBot: $5.57
3. Fixed Width 0.25: $2.76
AthenaBot bankrupt: False (cash balance: 15.57, starting capital: 10.0)
Result: PASS (score=0.70)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $40.72
2. Stalemate Quoter: $5.0
3. AthenaBot: $3.26
AthenaBot bankrupt: False (cash balance: 23.26, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $10.89
2. Fixed Width 0.1: $1.03
3. Fixed Width 0.05: $-10.34
AthenaBot bankrupt: False (cash balance: 30.89, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 12 — SCORED 8

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $19.04
2. Fixed Width 0.05: $-19.14
AthenaBot bankrupt: False (cash balance: 39.04, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Lattice: $10.85
2. Fixed Width 0.1: $9.31
3. Situational Unawareness: $7.31
4. AthenaBot: $0.82
AthenaBot bankrupt: False (cash balance: 20.82, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $21.82
2. Lattice: $18.16
3. Fixed Width 0.05: $-2.47
AthenaBot bankrupt: False (cash balance: 41.82, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $47.5
2. Situational Unawareness: $13.91
3. Lattice: $-15.05
AthenaBot bankrupt: False (cash balance: 67.5, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $15.37
2. Lattice: $0.98
3. AthenaBot: $0.08
AthenaBot bankrupt: False (cash balance: 40.08, starting capital: 40.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.84
2. Situational Unawareness: $9.57
3. Lattice: $7.9
4. Mongoose: $-30.8
AthenaBot bankrupt: False (cash balance: 56.84, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $23.72
2. Fixed Width 0.05: $21.05
3. Lattice: $-6.07
4. Mongoose: $-29.7
AthenaBot bankrupt: False (cash balance: 63.72, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $27.21
2. Situational Unawareness: $16.35
3. Mongoose: $-28.95
4. Fixed Width 0.05: $-41.09
AthenaBot bankrupt: False (cash balance: 67.21, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-3.98
2. Lattice: $-11.8
3. Mongoose: $-33.51
4. Fixed Width 0.05: $-103.11
AthenaBot bankrupt: False (cash balance: 36.02, starting capital: 40.0)
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
| 7 | SCORED 3 | PASS | 0.40 | False | #2 of 2 |
| 8 | SCORED 4 | PASS | 0.40 | False | #3 of 3 |
| 9 | SCORED 5 | PASS | 0.70 | False | #2 of 3 |
| 10 | SCORED 6 | PASS | 0.40 | False | #3 of 3 |
| 11 | SCORED 7 | PASS | 1.00 | False | **#1 of 3** |
| 12 | SCORED 8 | PASS | 1.00 | False | **#1 of 2** |
| 13 | SCORED 9 | PASS | 0.40 | False | #4 of 4 |
| 14 | SCORED 10 | PASS | 1.00 | False | **#1 of 3** |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.40 | False | #3 of 3 |
| 17 | SCORED 13 | PASS | 1.00 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 1.00 | False | **#1 of 4** |
| 19 | SCORED 15 | PASS | 1.00 | False | **#1 of 4** |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 12.10/16 points (~76%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 9 of 16 SCORED sessions.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 12.10 | 16 |
| **Total** | **16.10** | **20** |

**16.10/20 (80.5%)** overall.
