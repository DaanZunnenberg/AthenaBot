# Phase 1 (canonical pricing / per-day cache / net-position ledger): results

> **What this improved / established:** Results of an early quoting-rewrite candidate (canonical pricing / per-day cache / net-position ledger) against a pre-registered kill criterion -- only 1 of 3 conditions passed, so this candidate was **not** promoted. Documents why, as a record of a real dead end.

**Bottom line up front: the pre-registered kill criterion fired.** Criterion 3 (mean score
improves, bankruptcy rate does not increase, degenerate-quote fraction falls under 5%) is
only 1-of-3 satisfied against the "Prompt 0" baseline (`debug/BotFinal.py`). Bankruptcy is
fixed at 0% (matching baseline), but mean score is flat-to-slightly-down and the degenerate-
quote fraction did not move. Per the task's own instruction ("if criterion 3 fails, do not
proceed to Prompt 3. Diagnose first."), this write-up **is** that diagnosis, and the
recommendation is to hold before starting the next task rather than paper over the result.

## What shipped

- **A (canonical pricing)**: already satisfied by the estimation-layer rewrite in the prior
  task -- `price_option` was already a thin wrapper over `_BinaryOptionPricer.price` with no
  `_baseline_observable_moments`/`_baseline_leg_moments` left in the file. No code change
  needed here; verified by grep before starting.
- **B (per-day cache)**: `self._day_cache[option_id] = {"P": ..., "sigma_P": None, "U_P":
  None}`, invalidated at the top of every `on_step_advance`, eagerly filled for the day's
  `active_option_state` (`_precompute_day_cache`), with a lazy fallback for an option
  appearing mid-day (`_get_cached_fair`). `quote`/`respond_to_fok` now read this cache
  instead of calling `price_option` directly.
- **C (net-position ledger)**: implemented exactly as specified -- `_cash` (C), incrementally
  maintained `_short_exposure` (`sum_{q_j<0} |q_j|`), `W = _cash - _short_exposure`. **Then
  found empirically unsafe as the sole gate** (see below) and given a conservative floor,
  `_legacy_reserved`, that mirrors the old non-netting ledger exactly. `_feasible_cash() =
  min(W, _legacy_reserved)` is what `quote`/`respond_to_fok` actually gate on.
- **D (inventory scale)**: `_INVENTORY_SCALE = 15` added, used solely to normalize `z` in
  `quote`; `_position_cap` now enforces a genuine hard per-option exposure cap in
  `respond_to_fok` (previously unused once `z`-normalization moved off it) instead of being a
  dead/decorative attribute.

## The kill criterion: what happened and how it was diagnosed

Initial implementation gated `quote`/`respond_to_fok` purely on `W` (the netted formula from
the task spec). A 200-session, common-random-numbers comparison against `debug/BotFinal.py`
("Prompt 0") showed:

| | mean_score | bankruptcy_rate |
|---|---|---|
| baseline (Prompt 0) | ~1.56-1.60 | 0% |
| **W alone (initial)** | **0.01** | **80%** |

This is a severe regression, not noise. Isolation testing (holding everything else fixed,
20-40 session batches) pinned down the cause:

1. Reverting `_INVENTORY_SCALE` to an inert value (ruling out item D) did **not** fix it
   (still 80% bankrupt) -- the ledger, not the inventory-scaling fix, is the cause.
2. Gating **only** `quote`'s circuit breaker on pure `W` (with `respond_to_fok` conservative):
   77.5% bankrupt.
3. Gating **only** `respond_to_fok` on pure `W` (with `quote` conservative): 65-67.5% bankrupt,
   reproduced with `_INVENTORY_SCALE` inert too.
4. Even a "provably safe" **directional** variant -- use `W` only when a FOK trade *reduces*
   `|position|` (closing/de-risking, gate on the conservative floor when it *increases*
   `|position|`) -- still bankrupted 45% of sessions.

Trusting `W` *anywhere*, even in ways that look individually safe, reliably causes bankruptcy
against this harness's external cash tracking. That external tracking (`true_cash` in
`sim/harness.py` and `sim/compare_prompt0.py`) implements the literal README rule: debit the
trade's own max loss on every trade, credit only at settlement -- i.e. it does **not** net
against existing position. `W` assumes the opposite (that closing releases the reservation
immediately). The two are fundamentally different models of solvency, and empirically, trusting
the optimistic one is dangerous.

**Fix**: `_legacy_reserved`, a second, genuinely path-dependent ledger that exactly mirrors the
old (already-proven-safe, 0%-bankruptcy) non-netting rule, updated alongside `_cash`/
`_short_exposure` on every trade and settlement. `_feasible_cash() = min(W, _legacy_reserved)`
is the actual gate everywhere. This restores 0% bankruptcy (see the final comparison below) at
the cost of giving back essentially all of `W`'s intended benefit, since `_legacy_reserved`
only ever decreases (except at settlement) and is therefore the binding constraint in almost
every case -- the same shape of result the very first (pre-implementation) analysis of this
task predicted and that the isolation tests then confirmed directly.

## `grader_worst_case` vs. `W`: the ambiguity behind all of this

The task instructs: read the README, and if the documented bankruptcy rule differs from `W`,
implement `grader_worst_case(cash, positions)` matching it exactly and gate on that instead.
README.md's wording is unambiguous that trades only ever *decrease* balance and settlement is
the *only* increase mechanism ("Every time you do a trade, your balance will decrease by the
maximum loss of your trade... note that this process [settlement] can only increase your
balance"). Both worked examples (buy 5 @ 0.20 -> -$1; sell 5 @ 0.20 -> -$4) are consistent with
either a literal non-netting reading or a "re-based margin from current position" reading,
since both examples start from a flat book -- they don't disambiguate the one case that
matters (closing an existing position).

The `grader_worst_case(cash, positions)` signature the task specifies is a **pure function of
current state** -- structurally incompatible with a genuinely path-dependent, non-netting rule
(which needs the full trade history, not just current cash/positions). Taken at face value,
`grader_worst_case` therefore can't literally implement the non-netting reading; it's
implemented in `Bot.py` as coinciding with `W` (see its docstring), purely as the documented
cross-check the task asks for. The actual, empirically-motivated safety net is
`_legacy_reserved`, which **is** allowed to be path-dependent since nothing requires it to fit
that function signature -- it exists precisely because the isolation tests above showed `W`
alone is unsafe under the more literal (and, empirically, evidently closer-to-real)
non-netting reading.

**This remains unresolved without ground truth.** The honest state: we do not know whether the
real grader nets positions on close. If it does, `_legacy_reserved` is needlessly conservative
and this task's intended improvement is available but not yet unlocked. If it doesn't, the
current code is exactly as safe as it needs to be and no further loosening is possible without
risking real bankruptcy on submission.

## Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| 1 | All Prompt 0 pricer invariants still pass | **PASS** -- 220/220 bounds, monotonicity, complement identity; 205/205 martingale (steps>=2); 220/220 MC cross-check. Unaffected by this task (no `_BinaryOptionPricer` logic changed). |
| 2 | Netting invariant passes | **PASS** -- `sim/test_ledger.py`, 6/6 suites, 0 failures (200 random round-trip trials + hand-checked cases + settlement-release + cache tests). |
| 3 | 200-session comparison: mean score improves, bankruptcy non-increasing, degenerate fraction < 5% | **PARTIAL** -- bankruptcy 0% both (non-increasing: pass). Mean score baseline 1.6037 vs current 1.5639 (does not improve). Degenerate fraction baseline 0.97 vs current 0.99 (does not fall under 5%). **Kill criterion triggered on this basis.** |
| 4 | Median wall-clock per simulated day < 50ms, 50-option universe | **PASS** -- measured median 8.2ms, max 10.8ms (well under budget; caching is working). |

## Final 200-session comparison (common random numbers, `sim/compare_prompt0.py`)

```
baseline  : mean_score=1.6037 p5_score=1.0995 bankruptcy_rate=0.0000 degenerate_fraction=0.9700 mean_trades=60.2
current   : mean_score=1.5639 p5_score=1.0995 bankruptcy_rate=0.0000 degenerate_fraction=0.9900 mean_trades=57.7
```

Note: `degenerate_fraction` here is measured as "the session's *last* `quote()` call returned
the exact degenerate signature `(0.0, 1, 1.0, 1)`" -- both versions show it near-universally,
which suggests this specific operational definition doesn't discriminate well (a session's very
last quote call is a noisy, possibly-arbitrary sample of its overall behaviour) rather than
that both versions are genuinely "stuck" 97-99% of the time throughout (`mean_trades` of 57-60
over 20 live days argues against that reading). A steadier metric -- fraction of *all* quote
calls across the session that are degenerate -- would likely be more informative and is a
reasonable thing to fix before re-running this comparison in a future session.

## Recommendation

Do not proceed to the next task as-is. Two independent paths would unblock it:

1. **Resolve the grader ambiguity with real evidence** (not more re-reading of the same
   README paragraph) -- e.g. if a real HackerRank submission's VERBOSE-test cash-balance logs
   ever show a balance recovering mid-session after closing a position, that would confirm
   netting and justify relaxing `_legacy_reserved`.
2. **Pull forward part of the sizing work** intended for the next task (position/quantity
   caps, spread) so that even with `W`'s extra headroom, the bot doesn't take on positions
   large enough to matter to solvency -- i.e. make the *quantities* conservative instead of
   the *cash gate*, which is closer to the task's original intent of isolating pricing/
   accounting correctness from sizing.

Either of these is a reasonable next step; picking one isn't this document's call.
