# `debug/` — the modeling/debugging/optimizing log

A numbered, chronological log of investigations, tuning passes, and dead ends encountered
while building `Bot.py`, kept because the next time a similar symptom appears, these are the
fastest way to recognize it and reuse the fix instead of re-deriving it from scratch. Each
file opens with a **"What this improved / established"** line summarizing the outcome before
the full writeup.

Read in numeric order for a rough chronological narrative, or jump to whichever topic is
relevant:

| # | File | What it covers |
|---|---|---|
| 00 | `00-SCORING-OBJECTIVE.md` | What the grader actually pays out on (rank, not raw PnL) — read before tuning any constant. |
| 01 | `01-SETTLEMENT-CONVENTION.md` | Resolved an ambiguity in what `steps_until_expiry == 0` means for settlement timing. |
| 02 | `02-COMPILE-ERROR-FILE-SIZE-FIX.md` | The "Server error while compiling" saga — root cause was a ~65,536-byte submission-size ceiling, not a code defect. |
| 03 | `03-PARAMETER-ESTIMATION-ACCURACY.md` | Validated `warm_up`'s estimation layer against the task's own recovery-accuracy criteria. |
| 04 | `04-CALIBRATION-SWEEP-COST-BUDGET.md` | Real compute-cost budget for calibration sweeps, to keep later sweep designs tractable. |
| 05 | `05-HARNESS-WIDER-ADVERSARIAL-SAMPLING.md` | Wider/adversarial parameter samplers added to the local harness for harder robustness testing. |
| 06 | `06-QUOTING-REWRITE-PHASE1-RESULTS.md` | An early quoting-rewrite candidate that **failed** its own kill criterion — a real, documented dead end. |
| 07 | `07-INDIFFERENCE-QUOTING-PHASE2.md` | Replaced heuristic fixed-spread quoting with exponential-utility indifference pricing. |
| 08 | `08-MARKOUT-ADVERSE-SELECTION-INSTRUMENTATION.md` | Markout/toxicity instrumentation — later reused (inverted) by `experimental/`'s `_FlowRegime` bots. |
| 09 | `09-MODEL-UNCERTAINTY-SIZE-CUTS.md` | Model-uncertainty design, plus the **second** occurrence of the file-size compile bug from #02. |
| 10 | `10-PORTFOLIO-TAIL-RISK-SCOPE-CUTS.md` | What shipped vs. was cut from portfolio-level tail-risk work, due to the size ceiling again. |
| 11 | `11-ROBUSTNESS-BEFORE-AFTER-RESULTS.md` | Before/after robustness results for a defined scope (some parts shipped, some cut). |
| 12 | `12-REGIME-SWITCHING-AUDIT.md` | Confirmed no regime-switching/HMM logic exists — a negative result ruling out a hypothesis. |

## `BotDefault.py`

The pristine, unimplemented HackerRank stub template (all six `MarketMaker` methods as
`TODO`/`...`) — kept as the starting-point reference to diff any later version against.

## Where the rest went

The raw bisection/reference `.py` snapshots that these writeups describe (`BotBaseline.py`,
`BotFault.py`, `BotFinal.py`, etc.) are archived in `archive/debug-snapshots/`, not kept
alongside the writeups — they're historical code, not documentation. See that folder's own
`README.md` for what each snapshot was.
