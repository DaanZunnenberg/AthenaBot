# AthenaBot

This repo contains only my own submission for this challenge. No code, data, or text from the
actual HackerRank challenge itself is included here (the shared interface types the challenge
provides live in a separate private submodule, `src/`, not published in this repo). It's shared
purely so other participants can compare their own method against mine.

An automated market-making bot for a binary-options (event-contract) exchange simulation, built
around a `MarketMaker` class with six methods to implement: `price_option_from_parameters`,
`warm_up`, `price_option`, `quote`, `respond_to_fok`, and state-update hooks
(`on_step_advance`/`on_trade`). The surrounding data model (`BinaryOption`, `MarketParameters`,
`MarketHistory`, `Quote`, `FokOrder`, etc.) is fixed infrastructure supplied by the grading
harness: it can be read and constructed freely, but the grader always uses its own copies, so
edits to those classes have no effect on scoring.

## What's being traded

Three correlated underlyings evolve day over day: a short-term policy interest rate, and the
valuations of two hypothetical companies (referred to here by their in-repo tickers, FED/AJR/THR).
A binary option settles to $1 if a weighted combination of one or more of these underlyings
clears a strike threshold by a given expiry, and $0 otherwise (e.g. "does the rate exceed some
level in N days," or "does one company's valuation exceed the other's by expiry"). Multi-leg
combinations are supported by the data model in general, but in practice the option book only
ever contains single-underlying options and two-way relative-value spreads between the two
company valuations.

Two order types reach the bot: two-sided RFQs, where the exchange takes the best bid/offer across
all participating market makers and the direction (buy or sell) isn't known in advance, and
fill-or-kill orders, which are fully specified up front and can be accepted or declined outright
(splitting the fill with other market makers who also accept).

## Scoring shape

A first pass checks pure pricing accuracy against ground-truth parameters (no estimation
involved). A handful of short, log-heavy runs follow, meant for debugging rather than scoring;
they pass as long as the bot runs without error and doesn't go bankrupt. The bulk of the grading
comes from a larger set of full trading sessions of varying difficulty and competitive makeup,
ranked by realized PnL, with a bankruptcy or an unhandled exception zeroing out that session's
score outright.

## Solvency mechanics

The grader tracks a cash balance independent of anything the bot keeps internally. Trading debits
the position's maximum possible loss immediately (buying reserves the price paid; shorting
reserves the complement), and that reservation is only ever released or improved when a position
actually settles at end of day: settlement can raise the balance but a fresh debit is taken the
moment a trade happens. If the balance is negative once a day's settlements have posted, the bot
is marked bankrupt and the run ends early with no further scoring.

## Implementation status

All six `MarketMaker` methods are implemented (`price_option_from_parameters`, `warm_up`,
`price_option`, `quote`, `respond_to_fok`, plus `__init__`/`on_step_advance`/`on_trade` state
plumbing). `price_option_from_parameters` prices every leg shape (FED-only, single-company,
AJR/THR spreads, non-unit weights, three-leg combinations) via an exact finite-state DP over
the fed funds rate's possible terminal values, mixed with the conditional (correlated,
lognormal) distribution of AJR/THR at each one (no Monte Carlo, deterministic and
reproducible). See `docs/history/LEGACY-MODEL.md` for the full math spec and `docs/history/JOURNEY.md` for how each method
reached its current form.

## Mathematical logic summary (`AthenaBot/AthenaBot.py`)

Full derivations and every tunable constant are in `AthenaBot/MODEL.md`; this is the short
version.

**Generative model.** Each day the fed funds rate steps up, down, or holds with
mean-reversion-tilted probabilities toward a target rate. AJR and THR evolve as correlated
lognormals driven by that rate change plus a shared sector shock and idiosyncratic noise:
$$\log\frac{V_{t+1}}{V_t} = \mu + \beta_r \Delta r_t + \beta_s S_t + \varepsilon_t$$
Because daily rate changes telescope ($\sum \Delta r_i = r_n - r_0$), an option's payoff only
depends on the *terminal* rate, not the path, which is what makes exact, non-Monte-Carlo
pricing possible.

**Pricing (`price_option_from_parameters` / `price_option`).** An exact finite-state DP
(`_BinaryOptionPricer`) enumerates every reachable terminal rate value and its probability,
then for each one prices the option's conditional payoff probability by leg shape: a direct
threshold check for FED-only legs, a closed-form lognormal tail probability for single-company
legs, a closed-form normal-difference spread for AJR-vs-THR options, and 129-point quadrature
for the general two-leg case. Summing over terminal rates gives the fair value, deterministic
and reproducible.

**Parameter estimation (`warm_up`).** Fits `MarketParameters` from `MarketHistory`: OLS of each
company's log-return on the rate change (drift, rate-beta), Fisher-z-shrunk residual
correlation to reconstruct sector loadings, and a grid search over the mean-reversion strength
that maximizes a per-rate-level multinomial log-likelihood. Re-fit after every step so
estimates keep adapting through the session.

**Quoting (`quote`).** A confidence score (distance of the fair value from 0.5, scaled by how
much history backs it) selects one of three fixed spread widths, then the quote is skewed by
counterparty toxicity (an EMA of adverse post-trade price movement), a "flow regime" signal
(the same EMA, favorable side), and portfolio-level delta skew (whether filling this side would
concentrate or hedge the book's existing correlated risk across FED/AJR/THR).

**Risk (`respond_to_fok`, sizing, solvency).** A self-tracked cash/margin ledger mirrors the
grader's own debit-at-trade-time rule, sizing every quote and FOK acceptance to the smaller of
a hard per-option inventory cap and remaining margin headroom. A drawdown circuit breaker
widens spreads and shrinks size (never to zero) once session PnL crosses a loss threshold,
recovering automatically as PnL recovers.

---

## Project status (this repo, not part of the original challenge template)

Everything from the top of this file down through "Solvency mechanics" is an original
paraphrase of the challenge rules (not the original spec text). Everything from
"Implementation status" onward (including this section) is added by the working repo to
orient a new reader:

- `Bot.py` is the graded submission: solvent, no crashes, currently scoring well on
  real HackerRank runs (see `archive/debug-snapshots/TestCaseHandles.md`). It lives outside
  this repo (the local working copy actually pasted into HackerRank's editor), not tracked
  here; `AthenaBot/AthenaBot.py` below is the promoted, in-repo copy of the winning variant.
- `docs/history/JOURNEY.md` is the chronological account of how it got there (start here for context).
  `docs/history/` also holds `NOTES.md`, `TODO.md`, and `LEGACY-MODEL.md` (all resolved/historical,
  each says so at the top). `docs/DEFICIENCIES.md` is a standalone research note on binary-option
  market-making risk modes not yet evaluated against this bot; read separately, not part of the
  build history.
- `AthenaBot/AthenaBot.py` is the promoted final-submission copy: a byte-for-byte copy of
  `experimental/src/EpsilonSharpen.py`, one of five bots tied for the top real-HackerRank score
  (17.50/20) and the one with the most outright #1 finishes (10/16 SCORED sessions). It
  shares its pricing/estimation engine exactly with `Bot.py` but layers a materially
  different quoting/risk system on top (three-zone confidence quoting, counterparty
  toxicity, a "flow regime" favorable-markout signal, portfolio-level delta skew, a
  drawdown circuit breaker). Fully documented, including three real bugs found by a
  code-scan pass, in `AthenaBot/MODEL.md`.
- `src/` holds the shared interface classes (`BinaryOption`, `MarketHistory`,
  `MarketParameters`, `Quote`, etc., everything except `MarketMaker` itself) factored out of
  `AthenaBot/AthenaBot.py`. `experimental/` and `archive/debug-snapshots/` bots `import` these
  from `src` instead of redefining them, so each one only contains its `MarketMaker` and its
  own helper classes. `AthenaBot/AthenaBot.py` itself is untouched and stays a single
  self-contained file, since that's the only one that has to work as a standalone HackerRank
  submission.
- `experimental/` holds a curated set of tuning variants beyond `Bot.py`, each with its own
  scorecard, ranked in `experimental/Scores.md`.
- `debug/` is the modeling/debugging/optimizing log: numbered writeups of investigations,
  what they improved, and what didn't work.
- `sim/` is the local multi-session comparison harness used to iterate on `experimental/`'s
  bots without burning a real submission (not HackerRank-accurate; see its own README).
- `archive/` holds everything archived out of the folders above (raw bisection snapshots, the
  full set of non-curated bot variants, an earlier standalone prototype, and prompt drafts):
  real history, kept in full, just not what a first-time reader needs to see first.
- Every folder in this repo (`debug/`, `experimental/`, `archive/` and its subfolders, `sim/`)
  has its own `README.md` explaining what's in it.

## Dependency graph

```
src/ (private submodule)
  └─ taqf/akuna/market_types.py   -- BinaryOption, MarketParameters, MarketHistory,
                                      Quote, FokOrder, OptionLeg, OrderType, Position,
                                      Underlying, and the FED/AJR/THR id constants
       │
       ├─ AthenaBot/AthenaBot.py        (imports nothing -- fully self-contained,
       │                                 must work as a standalone HackerRank submission)
       ├─ experimental/src/*.py         (10 curated tuning-variant bots)
       ├─ debug/BotDefault.py
       ├─ archive/debug-snapshots/*.py
       ├─ archive/experiment-archive/**/*.py
       └─ archive/akuna-log/raw/{mm,harness}.py

Bot.py (external, untracked -- lives outside this repo, the local working copy
        actually pasted into the HackerRank editor before a variant is promoted)
  └─ sim/harness.py, archive/akuna-log/raw/test_*.py, _world.py
       (sys.path-insert the repo root and import Bot.py directly; not runnable
       here unless a Bot.py is placed at the repo root locally)
```

Everything under `src/` is supplied by the challenge itself, not written by us; everything
that imports from it is our own `MarketMaker` implementation and helper code.

## Why `src/` is a private submodule

`src/` holds the interface code the challenge hands every participant (the classes above) --
not code we wrote, and not ours to publish. It's kept in a separate private repository and
pulled in here as a git submodule so this repo can be public without republishing someone
else's starter material: anyone without access to that private repo can still read and run
everything in this repo except `src/`'s contents itself.

---

_Last reviewed: 2026-08-31._
