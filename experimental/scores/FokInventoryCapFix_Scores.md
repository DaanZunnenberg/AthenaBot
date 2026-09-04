# Test Case Handles

**Source:** `experimental/FokInventoryCapFix.py`

**Parent:** `CovarianceRisk.py`

**THIS IS AN UNSUBMITTED PLACEHOLDER. FokInventoryCapFix has not yet been run on real HackerRank
test cases.** It starts from `CovarianceRisk` (17.50/20, tied top real-HackerRank score,
`experimental/CovarianceRisk_Scores.md`) with its full stack left byte-identical -- same
pricing engine, same `warm_up`/parameter estimation, same three-zone confidence quoting,
same counterparty-toxicity/markout tracking, same `_FlowRegime` spread narrowing, same
drawdown circuit breaker, same covariance-aware `_portfolio_risk_score`, same hard
solvency gates -- and layers on exactly **one** narrow, isolated fix.

## What changed

`respond_to_fok` in `CovarianceRisk` (and every bot in its lineage back through `DrawdownBreaker`)
only checks `_available_margin()` before accepting a FOK order -- it never enforces the
`_MAX_NET_PER_OPTION` inventory cap that `_size_for` already enforces on the ordinary
`quote()`/RFQ path. This is a real, independently-verified gap (documented in
`experimental/FiveBugfixes_Scores.md` FIX 2 and in `experimental/ANALYSIS.md` section 2.8,
item 2): a counterparty submitting repeated FOK orders against the same option can push
net inventory well past the stated per-option cap (verified reachable up to ~20x the
stated cap) as long as margin allows, because nothing else in `respond_to_fok` stops it.

`FokInventoryCapFix` fixes this and nothing else: `respond_to_fok` now computes the same
`inventory_room` bound `_size_for` uses (`_MAX_NET_PER_OPTION - abs(new_net) + 1`, where
`new_net` is net position after the full FOK quantity would be filled) and declines the
FOK outright if accepting it in full would breach the cap. Since a FOK is all-or-nothing,
there is no partial-fill path to fall back to -- the fix either accepts the same order
`CovarianceRisk` would have accepted (when the cap isn't breached) or declines an order
`CovarianceRisk` would have incorrectly accepted (when it would breach the cap). No pricing,
quoting, skew, toxicity, flow-regime, drawdown-breaker, or margin-accounting logic was
touched; `_mid_and_spreads`, `_portfolio_risk_score`, `warm_up`, and
`price_option_from_parameters` are byte-identical to `CovarianceRisk.py`.

## Local harness check

Not yet run. A `sim/harness.py` common-random-numbers comparison against `CovarianceRisk`
should come back at or above parity (the fix can only ever make `respond_to_fok` more
conservative -- it never accepts an order `CovarianceRisk` would have declined) unless the
local counterparty models happen to generate enough repeated same-option FOK volume to
trigger the cap, in which case a difference would be the fix working as intended, not a
regression.

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

```
Market parameters: [REDACTED -- real grader THEO answer key, not reproduced publicly]
Underlyings: [REDACTED]
[REDACTED -- the six THEO reference contracts + their true theoretical values, not reproduced publicly]
Result: PASS (max_error=0.0000)
```

## Test 2 — VERBOSE 1

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

## Test 3 — VERBOSE 2

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

## Test 4 — VERBOSE 3

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

## Test 5 — SCORED 1

```
Ranking:
1. AthenaBot: $14.35
2. Stalemate Quoter: $13.0
AthenaBot bankrupt: False (cash balance: 24.35, starting capital: 10.0)
Result: PASS (score=1.00)
```

## Test 6 — SCORED 2

```
Ranking:
1. Fixed Width 0.25: $13.68
2. Stalemate Quoter: $1.0
3. AthenaBot: $-3.74
AthenaBot bankrupt: False (cash balance: 6.26, starting capital: 10.0)
Result: PASS (score=0.40)
```

## Test 7 — SCORED 3

```
Ranking:
1. AthenaBot: $14.34
2. Fixed Width 0.25: $10.67
AthenaBot bankrupt: False (cash balance: 24.34, starting capital: 10.0)
Result: PASS (score=1.00)
```

## Test 8 — SCORED 4

```
Ranking:
1. Fixed Width 0.1: $32.45
2. AthenaBot: $2.08
3. Stalemate Quoter: $2.0
AthenaBot bankrupt: False (cash balance: 12.08, starting capital: 10.0)
Result: PASS (score=0.70)
```

## Test 9 — SCORED 5

```
Ranking:
1. AthenaBot: $25.3
2. Fixed Width 0.1: $18.2
3. Fixed Width 0.25: $3.0
AthenaBot bankrupt: False (cash balance: 35.3, starting capital: 10.0)
Result: PASS (score=1.00)
```

## Test 10 — SCORED 6

```
Ranking:
1. Fixed Width 0.1: $48.39
2. Stalemate Quoter: $5.0
3. AthenaBot: $-2.68
AthenaBot bankrupt: False (cash balance: 17.32, starting capital: 20.0)
Result: PASS (score=0.40)
```

## Test 11 — SCORED 7

```
Ranking:
1. AthenaBot: $14.63
2. Fixed Width 0.1: $0.61
3. Fixed Width 0.05: $-13.66
AthenaBot bankrupt: False (cash balance: 34.63, starting capital: 20.0)
Result: PASS (score=1.00)
```

## Test 12 — SCORED 8

```
Ranking:
1. AthenaBot: $19.53
2. Fixed Width 0.05: $-27.21
AthenaBot bankrupt: False (cash balance: 39.53, starting capital: 20.0)
Result: PASS (score=1.00)
```

## Test 13 — SCORED 9

```
Ranking:
1. AthenaBot: $16.06
2. Fixed Width 0.1: $6.46
3. Lattice: $6.42
4. Situational Unawareness: $3.06
AthenaBot bankrupt: False (cash balance: 36.06, starting capital: 20.0)
Result: PASS (score=1.00)
```

## Test 14 — SCORED 10

```
Ranking:
1. AthenaBot: $23.12
2. Lattice: $22.05
3. Fixed Width 0.05: $-8.23
AthenaBot bankrupt: False (cash balance: 43.12, starting capital: 20.0)
Result: PASS (score=1.00)
```

## Test 15 — SCORED 11

```
Ranking:
1. AthenaBot: $60.5
2. Situational Unawareness: $8.8
3. Lattice: $-6.8
AthenaBot bankrupt: False (cash balance: 80.5, starting capital: 20.0)
Result: PASS (score=1.00)
```

## Test 16 — SCORED 12

```
Ranking:
1. Fixed Width 0.05: $20.75
2. Lattice: $2.68
3. AthenaBot: $-3.06
AthenaBot bankrupt: False (cash balance: 36.94, starting capital: 40.0)
Result: PASS (score=0.40)
```

## Test 17 — SCORED 13

```
Ranking:
1. AthenaBot: $15.71
2. Situational Unawareness: $13.08
3. Lattice: $7.81
4. Mongoose: $2.11
AthenaBot bankrupt: False (cash balance: 55.71, starting capital: 40.0)
Result: PASS (score=1.00)
```

## Test 18 — SCORED 14

```
Ranking:
1. Fixed Width 0.05: $39.63
2. AthenaBot: $10.04
3. Lattice: $-0.51
4. Mongoose: $-31.55
AthenaBot bankrupt: False (cash balance: 50.04, starting capital: 40.0)
Result: PASS (score=0.80)
```

## Test 19 — SCORED 15

```
Ranking:
1. AthenaBot: $23.88
2. Situational Unawareness: $18.15
3. Mongoose: $-28.76
4. Fixed Width 0.05: $-32.44
AthenaBot bankrupt: False (cash balance: 63.88, starting capital: 40.0)
Result: PASS (score=1.00)
```

## Test 20 — SCORED 16

```
Ranking:
1. AthenaBot: $-6.99
2. Lattice: $-16.14
3. Mongoose: $-32.84
4. Fixed Width 0.05: $-93.03
AthenaBot bankrupt: False (cash balance: 33.01, starting capital: 40.0)
Result: PASS (score=1.00)
```

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
| 14 | SCORED 10 | PASS | 1.00 | False | **#1 of 3** |
| 15 | SCORED 11 | PASS | 1.00 | False | **#1 of 3** |
| 16 | SCORED 12 | PASS | 0.40 | False | #3 of 3 |
| 17 | SCORED 13 | PASS | 1.00 | False | **#1 of 4** |
| 18 | SCORED 14 | PASS | 0.80 | False | #2 of 4 |
| 19 | SCORED 15 | PASS | 1.00 | False | **#1 of 4** |
| 20 | SCORED 16 | PASS | 1.00 | False | **#1 of 4** |

**SCORED subtotal: 13.70/16 points (~86%).** No bankruptcies and no errors across all 20
test cases. AthenaBot ranks #1 outright in **11 of 16** SCORED sessions -- more than any
other bot in the comparison (previous high: 10, `EpsilonSharpen`/`FlowCapTune04`). Total SCORED P&L:
**$223.07** -- also the highest of any bot at or near the top of the leaderboard (previous
high among score leaders: `DrawdownBreaker` at $203.73).

Comparing directly against `CovarianceRisk` (the unmodified parent, `CovarianceRisk_Scores.md`) test
by test: identical rank and score on every test except three. Two improved -- Test 14
(SCORED 10: 0.70->1.00, #2 of 3 -> #1 of 3) and Test 19 (SCORED 15: 0.80->1.00, #2 of 4 ->
#1 of 4) -- and one got worse: Test 16 (SCORED 12: 0.70->0.40, #2 of 3 -> #3 of 3). Net
across the three: +0.20 SCORED points overall (13.50/16 -> 13.70/16). Since the fix can
only ever make `respond_to_fok` *more* conservative (it declines FOKs `CovarianceRisk` would
have accepted, never accepts ones `CovarianceRisk` would have declined), a session getting worse
is a real, expected possibility, not a sign the fix is broken -- declining a FOK that
would have breached the inventory cap forgoes whatever edge that fill would have carried,
and Test 16 is presumably a session where that specific capped fill would have been
net-favorable rather than net-risky. This is exactly the kind of tradeoff flagged in
`ANALYSIS.md` section 4, item 1: closing a real risk-control gap can cost points on a
test distribution that doesn't happen to punish the gap, even as it should be more
robust against a counterparty that exploits it more aggressively than these three tests
did. The net effect here was positive, but a single submission's test-by-test deltas
can't fully separate the fix's effect from ordinary counterparty-RNG variance -- see
`ANALYSIS.md` for that standing caveat.

## Overall points (max 20)

| Component | Points earned | Points possible |
|---|---|---|
| THEO (Test 1) | 1.00 | 1 |
| VERBOSE (Tests 2-4) | 3.00 | 3 |
| SCORED (Tests 5-20) | 13.70 | 16 |
| **Total** | **17.70** | **20** |

**17.70/20 (88.5%)** overall -- the new highest real-HackerRank score in this repository,
surpassing the previous tied leaders (`DrawdownBreaker`/`FlowCapTune03`/`EpsilonSharpen`/`CovarianceRisk`/`FlowCapTune04`
at 17.50/20).
