# Test Case Handles

**Source:** `experimental/EpsilonSharpen.py`

**Parent:** `DrawdownBreaker.py`

**THIS IS A SPECULATIVE, UNVALIDATED EXPERIMENT and has NOT been submitted to
HackerRank.** It starts from `DrawdownBreaker` (17.50/20, current real-HackerRank leader,
see `experimental/DrawdownBreaker_Scores.md` and `experimental/Scores.md`) with its full stack
untouched -- same pricing engine, `warm_up`/parameter estimation, three-zone confidence
quoting, counterparty toxicity/markout tracking, portfolio-level cross-underlying delta
skew, hard solvency gates (`_available_margin`, `_worst_case_cash`, `_size_for`'s
inventory/margin caps), `_FlowRegime` spread narrowing, and drawdown circuit breaker --
and layers on exactly one small, bounded change.

## What this experiment was asked to test

The brief: design a strategy that specifically decreases competing market-makers' PnL
*without* increasing AthenaBot's own risk profile -- not "win more to make more," but
"target the mechanisms that let known-naive competitor archetypes (Fixed Width,
Stalemate Quoter, Lattice, Mongoose, Situational Unawareness) extract profit, and
neutralize them."

## Phase 1 finding: this is not mechanically available in this codebase

Before writing any code, `Bot.py`'s `MarketMaker` interface, `sim/harness.py`, and
`sim/counterparties.py` were read in full to check whether a real, distinct
"competitor-PnL-denial" lever exists.

- **`quote(option, counterparty_id)`** receives only the option and a flow-submitter id
  -- never a competing market maker's identity, quote, or fill outcome. RFQ routing
  ("goes to highest bid / lowest ask") happens entirely inside the exchange; we get back
  a fill or nothing, with no signal of who else quoted, by how much we won or lost, or
  whether a specific competitor was denied.
- **`respond_to_fok(option, fok_order)`** receives only the FOK terms. Nothing in
  `Bot.py`, `sim/harness.py`, or the FOK dataclass indicates or exposes a multi-MM
  pro-rata split; the local harness fills an accepted FOK at exactly the quantity we
  accept. "Capture more of the split share" is not something this codebase implements
  or can validate.
- **`sim/harness.py`'s own docstring says outright**: it is a "single-agent harness
  [that] can't reproduce [HackerRank's ranking] without a competitor-MM model," and its
  fallback scoring is literally our own terminal cash, not a rank. **There is no
  competitor-MM model anywhere in this repo.**
- **`sim/counterparties.py`** only implements `NoiseCounterparty` (uniformed,
  theo+noise reservation price), `InformedCounterparty` (adverse, trades only when our
  quote is mispriced past a threshold), and `MixedCounterparty` (a blend). None of these
  are "Fixed Width," "Stalemate Quoter," "Lattice," "Mongoose," or "Situational
  Unawareness" -- those names appear *only* in HackerRank's post-session ranking text
  pasted into this repo's `*_Scores.md` files, never as inspectable code. There is
  nothing to reverse-engineer a "static-width competitor" exploit against locally, and
  no way to confirm any hypothesis about *how* those archetypes lose against real
  HackerRank data, only pattern-match on the PnL numbers already logged.

**Conclusion:** winner-take-all RFQ routing does mean, tautologically, that any RFQ we
win is a fill some other bidder didn't win. But we cannot detect, target, verify, or
distinguish that outcome from any other ordinary win -- the interface gives us no
competitor-facing signal at all. So "decrease their PnL without changing our risk
profile" is **not mechanically distinct** from "win more RFQs, at our own existing
risk-adjusted threshold." This is the same conclusion the task brief itself anticipated
as a real possibility, and it is what Phase 1 actually found.

## What was built, and what it honestly is

Given no distinct lever exists, the most defensible, narrowly-scoped version of "be more
aggressive within our existing risk threshold" was implemented, restricted to the one
place it is genuinely free:

**`_EPSILON_SHARPEN = 0.01`**, applied in `_mid_and_spreads` only when `trust >= 1.0`
(the highest-confidence zone, where the fair-value estimate is already fully trusted,
never blended toward 0.5). After every other spread term (portfolio skew, toxicity,
flow-regime tightening, drawdown widening) is computed exactly as in `DrawdownBreaker`, one
additional minimum price increment is shaved off the resulting half-spread, still
floored at the existing `0.005` minimum-spread guard. It never fires in the mid or wide
confidence zones, so the fixed-width safety net for a less-trusted estimate
(`_W_WIDE`/`_W_MID`) is untouched. It never changes sizing, margin caps, toxicity
scoring, or drawdown throttling -- purely a price-only change gated to the zone we are
already most sure is right.

**What this costs:** nothing beyond what `DrawdownBreaker` already spends in that zone --
the sharpened price is still strictly on the profitable side of the already-trusted fair
value (it can only move the bid up / offer down toward, never past, `fair`), so it can
only convert a marginal near-miss loss into a fill we'd already judge favorable. It does
not lower the acceptance bar, widen risk, or touch the solvency gates.

**Honesty check, as required:** this is **not a new mechanism**. It is a smaller,
more conservative version of "quote tighter when confidence is highest," a strategy
class already present in this lineage (`DrawdownBreaker`'s own `_W_WIDE` narrowing, the
`_W_TIGHT`/`_C_HIGH` zone design itself). Framing it as "denies a competitor a fill" is
literally true in the winner-take-all sense, but that framing applies equally to every
prior bot's ordinary edge-capture logic -- it does not add a distinguishable
competitor-targeting capability, because Phase 1 found the interface provides none to
add. If this change helps, it will help for the same reason `DrawdownBreaker`'s zone design
already helps: slightly better fill capture in the zone we're most confident in, nothing
more.

## Local harness signal (LOCAL-HARNESS-ONLY, not HackerRank data)

`sim/harness.py`'s `run_batch`, 40 seeded sessions (seeds 1000-1039, common random
numbers so `DrawdownBreaker` and `EpsilonSharpen` face identical simulated market paths/order flow),
default `SessionConfig`, comparing `DrawdownBreaker.MarketMaker` vs `EpsilonSharpen.MarketMaker`:

```
DrawdownBreaker: mean_score=2.154 bankrupt=0/40
EpsilonSharpen: mean_score=2.252 bankrupt=0/40
mean diff (4913 - 8488): +0.0975 per session
per-session wins/ties/losses (4913 vs 8488): 15 / 7 / 18
```

Zero bankruptcies for either bot across all 40 sessions. The per-session win/tie/loss
split (15/7/18) is close to even, consistent with a marginal, low-risk price-only tweak
rather than a decisive edge -- exactly what the "honesty check" above predicts, since
this is a small refinement of existing logic, not a new mechanism. This local harness
does not model competing MMs (see Phase 1 finding above), so it cannot show anything
about competitor PnL, only our own terminal cash; it is included as the only rough
signal available, clearly labeled as such.

A full lifecycle smoke test (construction, `warm_up` from a synthetic `MarketHistory`,
`quote` on a single-leg FED option and a 2-leg AJR-THR spread, `respond_to_fok`,
`on_trade` on both option ids, `on_step_advance` across 5 steps with re-quoting each
step) ran cleanly under `python3.11` with no exceptions. `python3.11 -m py_compile`
passes.

**This is entirely unvalidated against real HackerRank data and needs a real submission
run to know whether it helps, hurts, or is a no-op against the 17.50/20 baseline.**

---

Paste the most recent HackerRank output here after each submission, one entry per test
case. This file is the working log used to diagnose failures and prioritize
fixes -- see the "Reading TestCaseHandles.md" section for the triage
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
2. Fixed Width 0.05: $-19.03
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
1. AthenaBot: $44.05
2. Situational Unawareness: $14.74
3. Lattice: $-14.18
AthenaBot bankrupt: False (cash balance: 64.05, starting capital: 20.0)
Result: PASS (score=1.00)
```

**Notes:**

---

## Test 16 — SCORED 12

**Status:** PASS (score=1.00)

**Output:**
```
Ranking:
1. AthenaBot: $43.21
2. Fixed Width 0.05: $20.42
3. Lattice: $1.3
AthenaBot bankrupt: False (cash balance: 83.21, starting capital: 40.0)
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
1. Fixed Width 0.05: $27.14
2. AthenaBot: $7.4
3. Lattice: $2.09
4. Mongoose: $-31.44
AthenaBot bankrupt: False (cash balance: 47.4, starting capital: 40.0)
Result: PASS (score=0.80)
```

**Notes:**

---

## Test 19 — SCORED 15

**Status:** PASS (score=0.80)

**Output:**
```
Ranking:
1. Situational Unawareness: $17.36
2. AthenaBot: $14.59
3. Mongoose: $-25.84
4. Fixed Width 0.05: $-29.81
AthenaBot bankrupt: False (cash balance: 54.59, starting capital: 40.0)
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
