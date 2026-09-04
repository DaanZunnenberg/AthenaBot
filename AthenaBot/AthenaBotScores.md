# Test Case Handles

**Source:** `experimental/AuditedRestructure.py`

AuditedRestructure is an **audited, restructured copy of `FokInventoryCapFix`** (17.70/20, current top
real-HackerRank score) -- not a new strategy variant. Two changes only:

1. **Compliance audit** of `FokInventoryCapFix.py`: checked for AI-tool attribution comments,
   copy-pasted external code, and any `print`/logging output. All clear -- no changes
   needed as a result of the audit itself.
2. **Structural reformat to match `debug/BotDefault.py`**: the four module-level helper
   classes (`_BinaryOptionPricer`, `_SufficientStats`, `_FitResult`,
   `_ParameterEstimator`) and the one helper function (`_default_market_parameters`)
   were folded into nested members of `MarketMaker`, so the file now contains exactly
   one class beyond the given scaffold (`MarketMaker`), matching `BotDefault.py`'s
   format. The nine given interface classes (`BinaryOption`, `FokOrder`,
   `MarketHistory`, `MarketParameters`, `OptionLeg`, `OrderType`, `Position`, `Quote`,
   `Underlying`) were also reformatted to `BotDefault.py`'s exact (typed, multi-line)
   style, replacing `FokInventoryCapFix`'s minified single-line scaffold formatting.

**No logic changed.** Verified directly (not just by inspection): a side-by-side
interpreter test against `FokInventoryCapFix.py` with identical RNG seeds, identical warm-up
history, and identical option/quote/FOK inputs produced byte-identical
`price_option_from_parameters`, `price_option`, `quote`, and `respond_to_fok` output --
including confirming the `respond_to_fok` inventory-cap fix still declines an
oversized FOK the same way in both files. `python3 -m py_compile` passes; file size is
60,010 bytes, under HackerRank's ~65,536-byte submission ceiling.

## Local harness check

Not applicable / not re-run. Since this is a structural reformat with zero logic
change from `FokInventoryCapFix` (verified above), a fresh `sim/harness.py` comparison would be
expected to reproduce `FokInventoryCapFix`'s local numbers exactly and adds no new signal --
see `experimental/FokInventoryCapFix_Scores.md` for that bot's local-harness history. The real
per-test numbers below come from an actual HackerRank submission of `AuditedRestructure.py`
itself, not a projection from `FokInventoryCapFix`.

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
1. AthenaBot: $14.35
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 24.35, starting capital: 10.0)
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
1. AthenaBot: $14.34
2. Fixed Width 0.25: $10.67
AthenaBot bankrupt: False (cash balance: 24.34, starting capital: 10.0)
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
1. AthenaBot: $25.3
2. Fixed Width 0.1: $18.2
3. Fixed Width 0.25: $3.0
AthenaBot bankrupt: False (cash balance: 35.3, starting capital: 10.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 10 — SCORED 6

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.1: $48.39
2. Stalemate Quoter: $5.0
3. AthenaBot: $-2.68
AthenaBot bankrupt: False (cash balance: 17.32, starting capital: 20.0)
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
1. AthenaBot: $19.53
2. Fixed Width 0.05: $-27.21
AthenaBot bankrupt: False (cash balance: 39.53, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 13 — SCORED 9

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $16.06
2. Fixed Width 0.1: $6.46
3. Lattice: $6.42
4. Situational Unawareness: $3.06
AthenaBot bankrupt: False (cash balance: 36.06, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 14 — SCORED 10

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $23.12
2. Lattice: $22.05
3. Fixed Width 0.05: $-8.23
AthenaBot bankrupt: False (cash balance: 43.12, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $60.5
2. Situational Unawareness: $8.8
3. Lattice: $-6.8
AthenaBot bankrupt: False (cash balance: 80.5, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=0.40)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $20.75
2. Lattice: $2.68
3. AthenaBot: $-3.06
AthenaBot bankrupt: False (cash balance: 36.94, starting capital: 40.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $15.71
2. Situational Unawareness: $13.08
3. Lattice: $7.81
4. Mongoose: $2.11
AthenaBot bankrupt: False (cash balance: 55.71, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 18 — SCORED 14

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Fixed Width 0.05: $39.63
2. AthenaBot: $10.04
3. Lattice: $-0.51
4. Mongoose: $-31.55
AthenaBot bankrupt: False (cash balance: 50.04, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $23.88
2. Situational Unawareness: $18.15
3. Mongoose: $-28.76
4. Fixed Width 0.05: $-32.44
AthenaBot bankrupt: False (cash balance: 63.88, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-6.99
2. Lattice: $-16.14
3. Mongoose: $-32.84
4. Fixed Width 0.05: $-93.03
AthenaBot bankrupt: False (cash balance: 33.01, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Running summary

| # | Test | Status | Score | P&L ($) | Bankrupt? | AthenaBot rank |
|---|------|--------|-------|---------|-----------|-----------|
| 1 | THEO | PASS | max_error=0.0000 | n/a | n/a | n/a |
| 2 | VERBOSE 1 | PASS | 1.00 | -0.48 | False | #2 of 2 |
| 3 | VERBOSE 2 | PASS | 1.00 | -0.66 | False | #3 of 3 |
| 4 | VERBOSE 3 | PASS | 1.00 | -0.02 | False | #3 of 3 |
| 5 | SCORED 1 | PASS | 1.00 | 14.35 | False | **#1 of 2** |
| 6 | SCORED 2 | PASS | 0.40 | -3.74 | False | #3 of 3 |
| 7 | SCORED 3 | PASS | 1.00 | 14.34 | False | **#1 of 2** |
| 8 | SCORED 4 | PASS | 0.70 | 2.08 | False | #2 of 3 |
| 9 | SCORED 5 | PASS | 1.00 | 25.30 | False | **#1 of 3** |
| 10 | SCORED 6 | PASS | 0.40 | -2.68 | False | #3 of 3 |
| 11 | SCORED 7 | PASS | 1.00 | 14.63 | False | **#1 of 3** |
| 12 | SCORED 8 | PASS | 1.00 | 19.53 | False | **#1 of 2** |
| 13 | SCORED 9 | PASS | 1.00 | 16.06 | False | **#1 of 4** |
| 14 | SCORED 10 | PASS | 1.00 | 23.12 | False | **#1 of 3** |
| 15 | SCORED 11 | PASS | 1.00 | 60.50 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.40 | -3.06 | False | #3 of 3 |
| 17 | SCORED 13 | PASS | 1.00 | 15.71 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 0.80 | 10.04 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 1.00 | 23.88 | False | **#1 of 4** |
| 20 | SCORED 16 | PASS | 1.00 | -6.99 | False | **#1 of 4** |

**SCORED subtotal: 13.70/16 points (~86%).** No bankruptcies and no errors across all 20 test cases. AthenaBot ranks #1 outright in 11 of 16 SCORED sessions.

**Total P&L (Tests 5-20, SCORED): $223.07.** (VERBOSE Tests 2-4 add a further -$1.16, for
-$1.16 + $223.07 = **$221.91** across every dollar-denominated test; SCORED-only is the
number used elsewhere in this repo for cross-bot P&L comparisons, e.g. `experimental/Scores.md`.)

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 13.70 | 16 |
| **Total** | **17.70** | **20** |

**17.70/20 (88.5%)** overall -- matches `FokInventoryCapFix`'s real HackerRank score exactly, as
expected given the interpreter-level verification (see intro) that `AuditedRestructure` is a
behaviorally byte-identical restructuring, not a strategy change.
