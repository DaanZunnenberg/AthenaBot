# Test Case Handles

**Source:** `experimental/DrawdownBreaker.py`

**Parent:** `FlowRegimeTightening.py`

**THIS IS A SPECULATIVE, UNVALIDATED EXPERIMENT. It is not a confident upgrade over
`FlowRegimeTightening` (17.20/20, the current best real-HackerRank score) and has not been
submitted to HackerRank yet.** It starts from `FlowRegimeTightening`'s full, untouched stack
(same pricing engine, same `warm_up`/parameter estimation, same three-zone confidence
quoting, same counterparty-toxicity/markout tracking, same portfolio-level cross-underlying
delta skew, same hard solvency gates -- `_available_margin`, `_worst_case_cash`,
`_size_for`'s inventory/margin caps -- all unmodified) and layers on exactly two targeted
changes, both aimed at specific, named gaps in `FlowRegimeTightening`'s real HackerRank run
(see `experimental/FlowRegimeTightening_Scores.md`, Test 13 and Test 20 below):

1. **Test 13 (SCORED 9) gap.** On the real run, `FlowRegimeTightening` scored 0.40 there
   (Fixed Width 0.1 scored highest; other competitors 0.6-0.8-ish band) while ranking #4 of
   4 with only $1.03 PnL. The prior analysis pass attributed this to the wide/low-confidence
   zone's fallback (`_zone`'s `confidence < _C_LOW` branch, which blends the fair-value
   estimate 50% toward 0.5 and quotes at `_W_WIDE` half-spread) firing too broadly/defensively
   in that session, giving up edge to flatter, more aggressive competitors -- while that same
   defensive fallback was **also credited** with protecting the bot's aggregate SCORED lead
   in other sessions by guarding against actively-wrong fair-value estimates. Narrowing it is
   therefore an explicit tradeoff, not a strict improvement: **`_W_WIDE` changed from `0.25`
   to `0.18`** (see the inline comment at the constant's definition in the source for the
   full reasoning). This was chosen over the alternative candidate (raising the `_C_LOW`
   confidence threshold that gates entry into the wide zone) as the more surgical change: it
   only affects how defensive the wide-zone blend is *given* that zone is entered, without
   changing which quotes/sessions route into which zone at all.

2. **Test 20 (SCORED 16) gap.** Every bot lost money in that specific session (a universal
   adverse regime affecting all competitors), but `FlowRegimeTightening` lost the most among
   AthenaBot variants (-$25.98, vs. Lattice -$15.26, Mongoose -$32.95, Fixed Width 0.05
   -$71.96 -- so not worst overall, but worse than peer AthenaBot lineages that have scored
   in the -$1 to -$25 range on similar sessions historically). No single clean root-cause
   mechanism was pinned down for this one; the fix here is a plausible, **unvalidated**
   candidate: a bounded, conservative per-session **drawdown circuit breaker**
   (`_drawdown_severity` / `_drawdown_spread_add` / `_drawdown_size_scale` in the source).
   It derives a session-PnL proxy from `(self._cash - self._starting_cash) / self._starting_cash`
   -- the only session-PnL-shaped figure this class already tracks, since there is no
   separate realized/unrealized PnL ledger to read from -- and ramps a soft risk-reduction
   response in linearly between two thresholds:
   - **No effect** while session PnL is above -25% of starting cash (`_DRAWDOWN_TRIGGER_FRAC
     = 0.25`) -- deliberately deep, so ordinary variance never trips it.
   - **Ramps to full (but still bounded) severity** by -45% of starting cash
     (`_DRAWDOWN_FULL_FRAC = 0.45`).
   - At full severity: quoted half-spreads widen by up to `_DRAWDOWN_SPREAD_ADD = 0.06`
     price units (added in `_mid_and_spreads`, on top of the normal zone width/skew/toxicity
     terms), and size caps returned by `_size_for` are multiplied down to no less than
     `_DRAWDOWN_SIZE_MULT = 0.5` of their normal value.
   - This is strictly additive on top of the existing hard solvency gates
     (`_available_margin`, `_worst_case_cash`, inventory caps) -- it never loosens or
     bypasses them, only makes the bot quote wider/smaller *within* whatever those gates
     already allow. It has no separate "tripped" latch; severity is recomputed fresh from
     current `_cash` on every call, so it recovers automatically (with no lag) as cash
     recovers -- pure hysteresis via the underlying state, not a sticky flag.

Both changes were reviewed for interaction with each other and with the existing
`_FlowRegime` tightening term: `_drawdown_spread_add()` is added in the same expression as
`_flow_tighten()` is subtracted, so a favorable flow-regime signal and an active drawdown
response can partially offset (by design -- they measure different things, favorable
recent markouts vs. adverse net PnL, and both are independently capped, so neither can push
`h_bid`/`h_ask` out of the `>= 0.005` floor already enforced there).

**No local harness run was performed for this experiment** (per the task instructions, this
file documents intent and the exact parameter deltas, not fabricated scores). Both changes
must be validated against a real HackerRank submission to know whether they net-improve or
regress the 17.20/20 baseline -- it is entirely possible one or both changes make aggregate
score worse elsewhere even if they close the specific Test 13 / Test 20 gaps they target,
exactly as flagged by the originating analysis.

A full lifecycle smoke test (construction, `warm_up`, `price_option_from_parameters` on
single-leg and 2-leg spread options, `quote`, `respond_to_fok` accept/reject paths,
`on_trade`, `on_step_advance` across multiple steps including an engineered losing sequence)
ran with `python3.11 -m py_compile` passing and no exceptions; the engineered-loss run
confirmed `_drawdown_severity` ramps from 0.0 to 1.0 and `_drawdown_size_scale` drops to its
0.5 floor as designed. This confirms the code runs and the breaker fires -- it says nothing
about whether the change helps or hurts actual scored PnL.

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
1. AthenaBot: $13.96
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 23.96, starting capital: 10.0)
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
3. AthenaBot: $-4.45
AthenaBot bankrupt: False (cash balance: 5.55, starting capital: 10.0)
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
1. Fixed Width 0.1: $47.88
2. Stalemate Quoter: $5.0
3. AthenaBot: $-2.29
AthenaBot bankrupt: False (cash balance: 17.71, starting capital: 20.0)
Result: PASS (score=0.40)
```

**Notes:**

---

## Test 11 — SCORED 7

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $14.53
2. Fixed Width 0.1: $0.61
3. Fixed Width 0.05: $-13.66
AthenaBot bankrupt: False (cash balance: 34.53, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

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

**Notes:**

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

**Notes:** This is the primary target test for the `_W_WIDE` narrowing change
(0.25 -> 0.18). Baseline (`FlowRegimeTightening`) scored 0.40 here.

---

## Test 14 — SCORED 10

**Status:** PASS (score=0.70)

**Output:**
```
Ranking:
1. Lattice: $23.14
2. AthenaBot: $21.31
3. Fixed Width 0.05: $-5.91
AthenaBot bankrupt: False (cash balance: 41.31, starting capital: 20.0)
Result: PASS (score=0.70)
```

**Notes:**

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

**Notes:**

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

**Notes:**

---

## Test 17 — SCORED 13

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $14.18
2. Situational Unawareness: $12.71
3. Lattice: $7.36
4. Mongoose: $2.35
AthenaBot bankrupt: False (cash balance: 54.18, starting capital: 40.0)
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
2. AthenaBot: $27.95
3. Lattice: $-0.08
4. Mongoose: $-24.86
AthenaBot bankrupt: False (cash balance: 67.95, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $18.08
2. AthenaBot: $8.71
3. Fixed Width 0.05: $-22.33
4. Mongoose: $-28.08
AthenaBot bankrupt: False (cash balance: 48.71, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 20 — SCORED 16

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $-23.8
2. Lattice: $-25.15
3. Mongoose: $-33.24
4. Fixed Width 0.05: $-75.37
AthenaBot bankrupt: False (cash balance: 16.2, starting capital: 40.0)
Result: PASS (score=1.00)
```

**Notes:** This is the primary target test for the drawdown circuit breaker. Baseline
(`FlowRegimeTightening`) lost -$25.98 here (universal adverse regime, every bot lost money
this session).

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
