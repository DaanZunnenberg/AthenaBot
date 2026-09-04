# Test Case Handles

**Source:** `experimental/FlowCapTune03.py`

**Parent:** `DrawdownBreaker.py`

**THIS IS A SPECULATIVE, UNVALIDATED EXPERIMENT. It is not a confident upgrade over
`DrawdownBreaker` (17.50/20, the current best real-HackerRank score) and has not been
submitted to HackerRank yet.** It starts from `DrawdownBreaker`'s full, untouched stack (same
pricing engine, same `warm_up`/parameter estimation, same three-zone confidence quoting
with `_W_WIDE=0.18`, same counterparty-toxicity/markout tracking, same portfolio-level
cross-underlying delta skew, same hard solvency gates, same bounded per-session drawdown
circuit breaker -- all unmodified) and makes exactly **one** targeted parameter change,
aimed at one specific, named near-miss on `DrawdownBreaker`'s real HackerRank run (see
`experimental/DrawdownBreaker_Scores.md`, Test 18 below). A second near-miss (Test 8) was
investigated and deliberately **not** touched -- see the reasoning below.

## What was investigated

This experiment followed up on 5 near-miss SCORED tests where `DrawdownBreaker` placed #2
(narrowly losing) instead of #1: Tests 8, 14, 16, 18, 19. The exact real-HackerRank
numbers for each, pulled from `DrawdownBreaker_Scores.md`:

- **Test 8 (SCORED 4)**: score=0.70. 1. Fixed Width 0.1: $32.45 / 2. AthenaBot: $2.08 /
  3. Stalemate Quoter: $2.0. A wide gap (~$30), not a near-tie.
- **Test 14 (SCORED 10)**: score=0.70. 1. Lattice: $23.14 / 2. AthenaBot: $21.31 /
  3. Fixed Width 0.05: $-5.91. Narrow gap (~$1.83), but the winner is Lattice, not a
  Fixed-Width archetype -- no mechanistic story tying it to `_FlowRegime`.
- **Test 16 (SCORED 12)**: score=0.70. 1. Fixed Width 0.05: $23.0 / 2. AthenaBot: $18.76 /
  3. Lattice: $1.74. Moderate gap (~$4.24).
- **Test 18 (SCORED 14)**: score=0.80. 1. Fixed Width 0.05: $28.33 / 2. AthenaBot: $27.95 /
  3. Lattice: $-0.08 / 4. Mongoose: $-24.86. Extremely narrow gap (~$0.38), nearly a tie.
- **Test 19 (SCORED 15)**: score=0.80. 1. Situational Unawareness: $18.08 /
  2. AthenaBot: $8.71 / 3. Fixed Width 0.05: $-22.33 / 4. Mongoose: $-28.08. Moderate gap
  (~$9.37), winner is not a Fixed-Width archetype.

## What changed and why

**Test 18 diagnosis (the change made here).** This is the cleanest signal: a $0.38 gap
against Fixed Width 0.05, whose own half-spread is 0.025 (spread 0.05, split evenly).
`DrawdownBreaker`'s tight-confidence-zone half-spread is `_W_TIGHT=0.05`, and the existing
`_FlowRegime` mechanism (`_flow_tighten()`, gated to `trust > 0.0`, i.e. tight/mid zones
only) narrows this by up to `_FLOW_REGIME_TIGHTEN_CAP=0.02` once >= 20 fills have shown a
favorable-or-flat markout EMA. Even at full narrowing, `DrawdownBreaker`'s best-case tight-zone
half-spread was `0.05 - 0.02 = 0.03` -- still 0.005 wider than Fixed Width 0.05's own
0.025 half-spread. Given the gap is only $0.38 in realized session PnL, this narrow,
mechanistic story (our tightest quote was structurally never able to fully match this
specific competitor's width, even in the best case) plausibly explains all or most of the
gap. The change: **`_FLOW_REGIME_TIGHTEN_CAP` raised from `0.02` to `0.03`** (see the
inline comment at the constant's definition in `FlowCapTune03.py` for the full reasoning).
This lets the tight zone narrow to within 0.005 of Fixed Width 0.05's own half-spread at
full flow-regime saturation, while leaving unchanged: the `_FLOW_REGIME_MIN_N=20` fill
gate, the `_FLOW_REGIME_ALPHA=0.03` EMA speed, the `trust > 0.0` restriction that keeps
this signal from ever touching the wide/low-confidence-zone `_W_WIDE=0.18` safety net,
and every solvency gate and the drawdown breaker. The cap was raised only to parity with
the tightest named competitor archetype observed (Fixed Width 0.05) -- going further
would not be justified by any observed number and would just be guessing.

**Test 8 diagnosis (deliberately left unchanged).** This gap ($32.45 vs $2.08, a ~15x
difference) is structurally different from Test 18's near-tie and is **not** attributed
to spread width. A gap this large cannot plausibly be closed by a bounded ~0.01-0.02
price-unit spread adjustment -- the ceiling on what `_flow_tighten()` can contribute is
tiny relative to the realized PnL delta. The competitor mix (Fixed Width 0.1 and
Stalemate Quoter, both flat/naive quoters) combined with the sheer size of Fixed Width
0.1's PnL ($32.45) is more consistent with a session where trade flow was abundant and/or
directionally favorable, and a constant-width, always-quoting competitor captured far
more volume/edge than a confidence-gated bot restricts itself to, independent of exact
spread width. Narrowing the flow-regime cap further would not plausibly close a gap this
size, and risks bleeding edge or absorbing more of a losing trend in other, unrelated
sessions where the mechanism fires. No fix is proposed for Test 8 in this experiment --
per the project's explicit caution (informed by `Archived-K`'s unjustified, no-op size-cap
change), a narrow parameter tweak was not applied without a mechanistic story tying it to
the actual numbers.

Tests 14, 16, and 19 were reviewed but not targeted: 14 and 19 have winners outside the
Fixed-Width archetype this mechanism was built for, and 16's ~$4.24 gap is large enough
relative to the `_FlowRegime` cap's total possible contribution (a few cents of
half-spread) that a cap increase alone is unlikely to be the dominant factor, similar to
Test 8's reasoning though the gap is smaller. No changes were made for any of these three.

## Local harness check (local-harness-only, does not represent Fixed-Width/Lattice/
Situational-Unawareness archetypes)

`sim/harness.py`'s built-in counterparties (`NoiseCounterparty`, `InformedCounterparty`,
`MixedCounterparty`) do **not** replicate the named competitor bots (Fixed Width 0.05/0.1/
0.25, Lattice, Situational Unawareness, Stalemate Quoter, Mongoose) that the real
HackerRank grader runs against -- the harness only exercises `FlowCapTune03`'s own
`MarketMaker` against synthetic RFQ/FOK flow, with no other market maker competing for the
same trades. A full lifecycle smoke run (seed=42, default `SessionConfig`, Python 3.11)
completed with **no exceptions, no bankruptcy** (129 trades executed, 463 quotes, 410 FOKs
seen, final cash positive). This confirms the code runs correctly end-to-end and that the
raised `_FLOW_REGIME_TIGHTEN_CAP` does not break anything locally -- it says **nothing**
about whether the change actually closes the Test 18 gap or affects PnL against the real
named competitors, since the harness cannot represent them.

**This change must be validated against a real HackerRank submission.** It may close the
Test 18 gap as diagnosed, have no effect (if `_flow_favorable_ema` in that session's actual
run never saturated the old cap in the first place, in which case this is a no-op exactly
like `Archived-K`'s change was), or regress other tests where `_FlowRegime` fires and a
larger cap turns out to be too aggressive.

A full lifecycle smoke test (construction, `warm_up`, `price_option_from_parameters` on
single-leg and 2-leg spread options, `quote`, `respond_to_fok`, `on_trade`,
`on_step_advance` across multiple simulated days) ran with `python3.11 -m py_compile`
passing and no exceptions, via `sim/harness.py`'s `run_session` with `maker_factory`
pointed at `FlowCapTune03.MarketMaker`.

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

**Notes:** Investigated but deliberately NOT targeted by this experiment -- see "What
changed and why" above. Baseline (`DrawdownBreaker`) scored 0.70 here (Fixed Width 0.1 $32.45
vs AthenaBot $2.08).

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

**Notes:**

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

**Notes:** Investigated but not targeted (winner is Lattice, not a Fixed-Width
archetype -- no mechanistic tie to `_FlowRegime`). Baseline (`DrawdownBreaker`) scored 0.70
here.

---

## Test 15 — SCORED 11

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $57.47
2. Situational Unawareness: $9.03
3. Lattice: $-7.67
AthenaBot bankrupt: False (cash balance: 77.47, starting capital: 20.0)
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
2. AthenaBot: $18.35
3. Lattice: $1.74
AthenaBot bankrupt: False (cash balance: 58.35, starting capital: 40.0)
Result: PASS (score=0.70)
```

**Notes:** Investigated but not targeted (gap ~$4.24, likely too large relative to the
`_FlowRegime` cap's total possible contribution). Baseline (`DrawdownBreaker`) scored 0.70 here.

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

**Notes:** This is the primary target test for the `_FLOW_REGIME_TIGHTEN_CAP` change
(0.02 -> 0.03). Baseline (`DrawdownBreaker`) scored 0.80 here (Fixed Width 0.05 $28.33 vs
AthenaBot $27.95, a ~$0.38 gap -- nearly a tie).

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $18.1
2. AthenaBot: $8.3
3. Fixed Width 0.05: $-22.05
4. Mongoose: $-28.16
AthenaBot bankrupt: False (cash balance: 48.3, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:** Investigated but not targeted (winner is Situational Unawareness, not a
Fixed-Width archetype). Baseline (`DrawdownBreaker`) scored 0.80 here.

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
