# Project Journey

A chronological account of this project for a new contributor to read before doing anything
else. It explains *why* the code and docs look the way they do, what's already been tried
(including dead ends), and where to look for detail instead of re-deriving it. Read this,
then `README.md` (the challenge spec), before touching `Bot.py`.

## The task

HackerRank challenge: implement `MarketMaker` in `Bot.py` (a market maker trading binary options
on FED/AJR/THR). Six methods to fill in: `price_option_from_parameters`, `warm_up`,
`price_option`, `quote`, `respond_to_fok`, plus state plumbing (`__init__`, `on_step_advance`,
`on_trade`). Scoring: 1 THEO test (pricing accuracy vs. true parameters), 3 VERBOSE tests
(pass if no error/bankruptcy), 16 SCORED tests (PnL-ranked, zero credit for bankruptcy or an
unhandled exception). Full spec in `README.md`.

## Phase 1 — Documentation pass (no logic yet)

Before writing any implementation, the entire supplied template was annotated: docstrings on
every class/field/method explaining what it is, why it's shaped that way, and how pieces
depend on each other. `docs/history/TODO.md` was written as an implementation plan (dependency order:
pricing math → parameter estimation → live pricing → quoting → FOK decisions). This mattered
later — the actual build order followed this plan closely, and it's still the right mental map
of the file.

**Lesson learned on comment style:** the project style is to write multi-line explanations as `"""..."""`
docstrings, not stacked `#` lines. Single-line asides stay as `#`. This was corrected multiple
times over the session — apply it consistently to new code.

## Phase 2 — `price_option_from_parameters` (the exact pricing engine)

Implemented as an exact finite-state DP over the FED rate's terminal distribution
(`tilted_rate_probabilities` recomputed at every visited level, not frozen at t=0), mixed with
the conditional (correlated, lognormal) distribution of AJR/THR at each terminal rate. Key
insight that makes this exact and cheap: daily rate changes telescope to `rate_T - rate_0`, so
the company dynamics only depend on the *terminal* rate, not the path — no Monte Carlo needed.

**Verified working**: matches a hand-derived reference table to ~3e-5 across FED-only,
single-company, and zero-strike-spread contract shapes. THEO test scores `max_error=0.0000`.
Full derivation is in `docs/history/LEGACY-MODEL.md` §3 if the math needs revisiting.

Later this single function was refactored into a `_BinaryOptionPricer` helper class (small
static/class methods) purely because HackerRank's autograder has a **cyclomatic-complexity
gate** (threshold 15) that the original single-function version tripped at 34. If you see a
"Cyclomatic complexity too high" error again, this is the pattern that fixed it last time:
split branching logic into small dispatcher + leaf functions, don't just add more `if`s.

## Phase 3 — Crash fixes (`price_option`, `quote`, `respond_to_fok`)

These were left as unimplemented stubs (`...`, i.e. `None`) for a while. This **crashed the
grader**, not just scored zero: the exchange calls `price_option`/`quote` to build log
messages on every RFQ/FOK *before* any trading logic runs, so `None.something` threw
`AttributeError`/`TypeError` and killed the whole session (all 20 tests, not just one).

**What worked:** implementing baseline versions of all three — simple, not sophisticated, but
total functions (never raise, never return `None`) fixed the crash immediately. Baseline
`warm_up`/`price_option` use independent-lognormal moment matching (no rate-beta, no
AJR/THR covariance) — deliberately simpler than the exact engine, see `docs/history/LEGACY-MODEL.md` §4-§5 for the
full gap list between this baseline and what `price_option_from_parameters` can do.

**Lesson learned:** every public method must be wrapped in `try/except` with a safe fallback,
matching the existing style. When adding new methods (e.g. `__init__` later), forgetting this
wrapper was a real bug — see Phase 5.

## Phase 4 — Quoting logic + risk ledger

Replaced the fixed-spread/fixed-size `quote()`/`respond_to_fok()` with a reservation-price
market maker: inventory skews the quote center (not just spread width — an RFQ can hit either
side, so only moving the center actively manages inventory), skew scales *up* with remaining
time (per the classical `q·σ²·(T-t)` inventory-risk derivation — this was explicitly checked
against a wrong "spread ∝ 1/√steps" idea suggested earlier and rejected for having the sign
backwards). Added a self-tracked cash ledger (`_est_cash`) since `self.cash_balance` is only
ever set once and never updated live — the ledger mirrors the grader's own max-loss-at-trade
formula from trades (`on_trade`) and credits settlements (`on_step_advance`).

Full math and a list of known weaknesses (some real, found during a later audit) are in
`docs/history/LEGACY-MODEL.md` §6-§7 — notably: the risk caps are sized in contracts but derived from cash, so for
realistic starting capital they're effectively inert (G5); the ledger debits per-trade rather
than per-net-position, so round-tripping (which is a market maker's entire business) ratchets
cash down even on a flat book (G6). **These are known, documented, not yet fixed** — a good
starting point for the next round of improvement.

## Phase 5 — The "Server error while compiling" saga (the big one)

After the quoting rewrite, HackerRank started returning a **generic, traceback-free**
`"Server error while compiling. Try again."` on submission — distinct from every previous
error (which came with a real Python traceback). This took most of a session to resolve and
is fully written up in `debug/CHANGES.md`. Summary for future reference:

**What was tried and ruled out** (each individually verified, not assumed):
- Bad imports/packages — identical imports to the working template, nothing third-party.
- Encoding issues — pure ASCII, no BOM/CRLF/tabs/hidden characters.
- An extra top-level class (`_BinaryOptionPricer`) breaking some template-structure
  assumption — refuted once the working baseline was directly compared and found to *already*
  contain that class.
- A union type hint inside a string annotation
  (`-> "tuple[float, float] | tuple[None, None]"`) — unusual syntax, removed as a precaution,
  did not fix it alone.
- Unguarded computation in `__init__` (`float(cash_balance)` with no `try/except`, unlike
  every other method) — real inconsistency, fixed, did not fix the compile error alone.
- Private method/attribute typos — cross-checked every `self._x` reference against its
  definition; all resolved correctly, not the cause.

**How it was actually found:** systematic bisection. Built a sequence of files, each a strict
superset of the last (state-ledger plumbing only → + new `quote()` → + new `respond_to_fok()`
→ full rewrite), and had each one tested on HackerRank in turn. Every individual piece of the
rewrite compiled and ran fine in isolation; only the *full combined* file failed. That pointed
at something size-related rather than content-related.

**Root cause: file size.** Every file that passed was under 65,536 bytes (2¹⁶); the one that
failed was at 67,794 bytes. That's an extremely common hard limit (16-bit length-prefixed
field) somewhere in HackerRank's submission pipeline — nothing to do with Python semantics,
which is why it never produced a traceback.

**Fix:** trimmed the newest, most verbose docstrings (multi-paragraph derivations) down to
1-3 lines each, zero logic changes. Took `Bot.py` from 67,794 → 60,060 bytes. **Confirmed
fixed** — resubmitted, all checks passed.

**Takeaway for future work:** `Bot.py` has a real, hard ceiling somewhere above 60KB and
below 68KB (65,536 bytes is the leading theory, unconfirmed exact boundary). Keep new
docstrings terse. If "Server error while compiling" reappears, check file size *first* — see
`debug/CHANGES.md` for the full bisection file set (`debug/BotBaseline.py`,
`debug/BotBaseTest.py`, etc.) as reusable templates for redoing this bisection if needed, and
`debug/BotDefault.py` as the pristine original stub for comparison.

## Phase 6 — Code cleanup

Once things worked, `Bot.py` was cleaned up for readability without touching behavior:
removed a write-only dead attribute (`_est_krev`, set but never read), merged a duplicate
class docstring, deduplicated near-identical AJR/THR moment-calculation branches into one
shared helper, standardized docstring formatting. Every change was verified against a
regression suite (THEO reference table, `quote`/`respond_to_fok` outputs, settlement ledger
math) before and after. **This is the pattern to follow for any future cleanup**: read the
whole file first, make the change, re-run the same regression checks, don't trust "it still
compiles" alone as proof of no behavior change.

## Phase 7 — `docs/history/LEGACY-MODEL.md`

A full mathematical specification of everything implemented in `Bot.py` — notation, the
generative model, the exact pricing derivation (including the telescoping lemma that makes it
tractable), the estimation layer, the quoting model, and the risk ledger — plus a "Summary of
modelling gaps" table (§7) listing known weaknesses with severity, most of which are still
open. Verified to render correctly on GitHub (correct `$`/`$$` delimiter usage, no blank
lines inside display-math blocks, no literal `|` characters inside inline math within table
cells — the specific things that actually break GitHub's math renderer). **Read `docs/history/LEGACY-MODEL.md`
before making any change to the pricing or quoting math** — it's the source of truth for what
the code is *supposed* to compute, including the parts that are known-simplified rather than
buggy.

## Phase 8 — `experimental/`: a bot lineage, not a single `Bot.py`

Once `Bot.py` was solvent and scoring well, further tuning moved to `experimental/` instead
of iterating on the graded file directly — each idea became its own numbered `Bot_[4-digit].py`
(e.g. `EpsilonSharpen.py`) with a paired `Bot_[4-digit]_Scores.md`. Both were later renamed to
describe what each bot actually added, with its parent noted in a header comment/`**Parent:**`
line (e.g. `EpsilonSharpen.py` → `EpsilonSharpen.py`) — see `experimental/README.md` for the current
naming convention and `experimental/ANALYSIS.md` for the full diff-verified lineage graph.
Each `_Scores.md` records the hypothesis, the exact bounded change from its parent bot, a
LOCAL-HARNESS-ONLY comparison via
`sim/harness.py`, and (once submitted) the real HackerRank per-test breakdown. This keeps every
tuning attempt independently reproducible and comparable, and — critically — means a
regression never overwrites a working baseline; `Bot.py` itself is only touched to promote a
proven winner.

`experimental/Scores.md` is the cross-bot leaderboard (score, SCORED-only subtotal, total
P&L, #1-outright finish count, bankruptcies) built from those real submissions. As of this
writing, five bots tie for the top score (17.50/20): `DrawdownBreaker`,
`FlowCapTune03`, `EpsilonSharpen`,
`CovarianceRisk`, `FlowCapTune04` —
`DrawdownBreaker` currently leads on P&L among the tied group.
`experimental/` itself now holds a **curated 10**, not every variant ever tried: those five
tied leaders, plus five chosen to show the journey rather than just the winners (strong
intermediate ancestors, the highest-raw-P&L outlier despite a lower score, the originator of
the portfolio-delta-skew technique the winners inherited, and the single worst-performing bot
in the lineage). Every other real, scored variant — 11 bots in total, plus an earlier,
non-curated top-10 selection superseded by this one — is preserved unmodified in
`archive/experiment-archive/`, not deleted; see `experimental/README.md` and
`archive/experiment-archive/README.md` for the full breakdown and reasoning.

**`FlowCapTune04`** is the most recent entry and reprises two lessons from earlier phases in a new
context:
- It widens two `_FlowRegime` constants inherited from `EpsilonSharpen` (`_FLOW_REGIME_MIN_N`
  20→12, `_FLOW_REGIME_TIGHTEN_CAP` 0.02→0.04) to test whether AthenaBot's worst real losses
  (sessions where a naive Fixed-Width competitor earns large PnL while AthenaBot sits
  flat/negative — see `EpsilonSharpen_Scores.md` Tests 6/8/10) are a too-wide-spread problem in
  calm regimes. The local harness came back bit-identical to `EpsilonSharpen` (mechanism verified
  live-firing but never flipped a fill decision — `sim/`'s counterparty archetypes aren't
  the Fixed-Width/Lattice ones the hypothesis targets), and the real HackerRank result
  landed at the same 17.50/20 with the same 10/16 outright-#1 count as `EpsilonSharpen`, just a
  few dollars lower P&L — a genuine, honestly-reported no-op, not an improvement.
- Its first submission hit **the exact same "Server error while compiling" failure from
  Phase 5**, because the docstring/comment additions pushed the file to 66,492 bytes, over
  the ~65,536-byte ceiling. Same diagnosis, same fix: trim prose only, verify
  AST-identical to the pre-trim version aside from docstrings (confirms zero logic change),
  resubmit. **This ceiling applies to every file in `experimental/`, not just `Bot.py`** —
  check `wc -c` before submitting a new variant if its docstring grew.

Separately, every bot's `name` property (in `Bot.py` and every `experimental/`/`debug/`
variant) returns the plain string `"AthenaBot"` — cosmetic display text only, verified not
to affect scoring or quoting/pricing logic.

## Phase 9 — repo reorganized into a public/`archive/` split

Once the bot lineage in `experimental/` grew past ~19 variants, plus a full `debug/`
bisection history, an early standalone `akuna/` pricing prototype, and raw `prompts/`
drafts, the top level stopped reading like a project a first-time visitor could follow. The
repo was reorganized (moves only — nothing deleted) into a clearer public/archive split:

- **`debug/`** kept only its numbered investigation writeups (renamed, each annotated with a
  "what this improved" summary) plus `BotDefault.py` (the starting-point stub). The raw
  bisection/reference `.py` snapshots those writeups describe moved to
  `archive/debug-snapshots/`.
- **`experimental/`** was pruned from ~19 bots down to a curated 10 (see Phase 8 above); the
  rest moved to `archive/experiment-archive/`, along with a superseded earlier top-10 selection.
- **`akuna/`** (the early standalone prototype + regression tests against `Bot.py`) moved to
  `archive/akuna-log/` wholesale, with an explainer of what worked and what didn't added on
  top of the preserved originals. The standalone prototype's own independent copy of the
  challenge's starter types was later removed as a redundant duplicate ahead of making the
  repo public; `mm.py`/`harness.py` now import those types from the private `src` submodule
  instead, same as everywhere else in the repo.
- **`prompts/`** (raw prompt drafts) moved to `archive/prompt-drafts/`, later removed entirely
  ahead of making the repo public (working-session scratch, not part of the project itself).

Every folder — old and new — has its own `README.md`. See `archive/README.md` for the index of
what moved where and why.

## Where things stand now

- `price_option_from_parameters`: exact, verified, essentially done.
- `warm_up` / `price_option`: intentionally simple baseline (independent lognormals, no
  rate-beta, no AJR/THR covariance). `docs/history/LEGACY-MODEL.md` §7.1 has a worked-out identification argument
  for how to close this gap relatively cheaply if it becomes the priority.
- `quote` / `respond_to_fok`: real reservation-price logic with a self-tracked risk ledger.
  The original G5/G6 structural defects noted in `docs/history/LEGACY-MODEL.md` §7 and the bankruptcy-sizing gap
  in `docs/history/NOTES.md` were subsequently addressed (see the bankruptcy-fix / capital-aggression-scale
  commit lineage documented in `docs/history/NOTES.md`); current tuning work happens on top of that fixed
  base, in `experimental/`, not by reopening those root causes.
- Compile/submission issues: resolved twice now, same root cause both times (file size over
  ~65,536 bytes) — see Phase 5 and Phase 8. `Bot.py` currently 48,424 bytes, comfortably
  under the ceiling.
- Latest full HackerRank run (`archive/debug-snapshots/TestCaseHandles.md`): all tests reporting `PASS`, no
  bankruptcies, no errors.
- `experimental/Scores.md` is the current source of truth for "which bot is best" — five
  bots tie at 17.50/20; see Phase 8 above.

## Phase 10 — `AthenaBot/AthenaBot.py`: the promoted final submission, math spec + code scan

`EpsilonSharpen.py` was copied verbatim into `AthenaBot/AthenaBot.py` as the designated final-submission
copy — it ties for the top real-HackerRank score and has the most outright #1 finishes (10/16)
of any bot in the lineage, so it was chosen over the other four tied-at-17.50 bots (including
its own descendant `FlowCapTune04`, whose one tuning change was a real-HackerRank no-op — see
Phase 8) as the simpler, original, equally-strong option.

Before documenting it, the file was scanned directly for correctness issues rather than
assumed correct because it scores well — a high score doesn't rule out latent bugs that just
haven't been exercised by the counterparty mix seen so far. Three real, verified issues came
out of that scan (full detail with reproduction in `AthenaBot/MODEL.md` §7):

1. **`Underlying.__eq__` breaks Python's hash/eq contract.** It's overridden to compare only
   `underlying_id`, but the frozen dataclass's auto-generated `__hash__` still hashes all
   fields — verified directly: two `Underlying` instances with the same id but different
   `value` compare equal (`==` is `True`) yet hash differently. Doesn't currently bite this
   file (which only ever converts underlying state to a plain dict, never uses `Underlying`
   objects themselves as dict/set keys), but is a real, latent contract violation.
2. **`_size_for`'s inventory-room formula is wrong for risk-*reducing* trades.** Verified by
   direct comparison at every net-position level: the formula is exactly correct for trades
   that grow an existing same-signed position, but badly underestimates room for trades that
   *cover* an opposite-signed position — e.g. at max short (`net = -10`), buying to cover
   should have room for `20` more contracts; the code allows only `2`. This throttles exactly
   the trades that reduce risk, backwards from the intent everywhere else in this file (e.g.
   the drawdown breaker exists specifically to make risk reduction easier under stress).
3. **`respond_to_fok` never enforces the per-option inventory cap.** `quote()` sizes through
   `_size_for`, which checks both margin and `_MAX_NET_PER_OPTION`; `respond_to_fok` only
   checks margin before accepting a FOK order in full. Not a solvency risk on its own (margin
   is still checked), but it means the inventory-concentration protection is only half-applied
   across the two entry points into the same book.

None of these currently crash or bankrupt the bot — all sit behind existing defensive
wrapping or independent hard caps — but all three are genuine defects worth fixing before
further tuning builds on top of this file. Not fixed in this pass (documentation and scanning
only, per the task); `AthenaBot/AthenaBot.py` is left exactly as promoted.

`AthenaBot/MODEL.md` is the full math specification for this file: it shares its pricing/estimation
engine exactly with `docs/history/LEGACY-MODEL.md`'s (verified by diff — only a docstring differs) and summarizes
that shared core briefly, then documents in full the parts unique to this quoting/risk system
that don't exist in root `Bot.py` — three-zone confidence quoting, counterparty toxicity and
its mirror-image "flow regime" signal, portfolio-level delta skew via numeric deltas, the
drawdown circuit breaker, and the solvency/margin ledger — introducing every state variable
and tunable constant, the math behind each mechanism, and the design choices made (including
which ones are genuine approximations/identification choices rather than bugs, e.g. the
sector-loading split in parameter estimation).

## Where to look for what

| Question | File |
|---|---|
| What does the challenge actually require? | `README.md` |
| Step-by-step build plan (still broadly accurate) | `docs/history/TODO.md` |
| Full math spec + known gaps for `Bot.py` | `docs/history/LEGACY-MODEL.md` |
| The promoted final-submission bot + its own math spec/code-scan findings | `AthenaBot/AthenaBot.py`, `AthenaBot/MODEL.md` |
| Latest real HackerRank results for `Bot.py` | `archive/debug-snapshots/TestCaseHandles.md` |
| The bankruptcy/risk-sizing root-cause writeup (historical, since fixed) | `docs/history/NOTES.md` |
| The modeling/debugging/optimizing log (numbered, chronological) | `debug/`, `debug/README.md` |
| The full "Server error while compiling" investigation | `debug/02-COMPILE-ERROR-FILE-SIZE-FIX.md` |
| Curated 10 tuning variants + their scorecards | `experimental/`, `experimental/README.md` |
| Cross-bot leaderboard (score/P&L/#1-finishes, all bots) | `experimental/Scores.md` |
| Local multi-session comparison harness (not HackerRank-accurate, see its own docstring) | `sim/`, `sim/README.md` |
| Everything archived out of the folders above (index) | `archive/`, `archive/README.md` |
| Raw bisection `.py` snapshots (referenced by `debug/`'s writeups) | `archive/debug-snapshots/` |
| Non-curated bot variants (11 more, real scores, not deleted) | `archive/experiment-archive/` |
| Early standalone pricing prototype + regression tests vs. `Bot.py` | `archive/akuna-log/` |
