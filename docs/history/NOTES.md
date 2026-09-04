# Notes

> **Status: resolved.** The bankruptcy-from-unsized-quoting problem documented below was the
> real diagnosis at the time this file was written, and the fix priority list at the bottom
> was followed — `Bot.py` now tracks realized/at-risk cash, sizes `quote`/`respond_to_fok` off
> a real risk budget, and keeps a reserve buffer (see the bankruptcy-fix / capital-aggression
> -scale commit lineage, and `docs/history/JOURNEY.md` Phase 4 onward). Kept here
> unedited as the original root-cause writeup — still useful context for *why* the risk-ledger
> code in `Bot.py` looks the way it does, and as a template for diagnosing any future
> bankruptcy regression the same way (rank-at-death pattern, not-a-pricing-problem check,
> ruled-out list). For current status see `docs/history/JOURNEY.md`'s "Where things stand now".

## Main problem: `quote` and `respond_to_fok` are unsized/unrisked, not "unimplemented"

The bot is not crashing and it is not mispriced -- THEO passes with `max_error=0.0000`, all 3
VERBOSE tests pass, and no test case shows a traceback. The main problem is narrower and more
specific than "pricing is wrong": **`quote` and `respond_to_fok` never check cash or position
before trading, so they can size a correctly-priced trade larger than the account can survive.**
That is what's producing bankruptcy in 8 of 16 SCORED tests (50%), including four cases where
AthenaBot was ranked **#1 by PnL at the moment it went bankrupt** (tests 7, 9, 13, 15) and one
where it was still showing **positive** PnL (test 8). Being right about the price and still going
broke is the signature of a sizing/risk problem, not a pricing problem.

### What's actually implemented today

| Method | Status | Behavior |
|---|---|---|
| `price_option_from_parameters` | Fully implemented | Exact FED-lattice DP + conditional lognormal/quadrature pricing. Verified to 3e-5 against a reference table. This is the real engine. |
| `warm_up` | Baseline only | Simple regularized rate-transition frequencies + shrunk/floored per-company log-return moments. No rate-beta/sector-beta decomposition, no AJR-THR covariance estimate. |
| `price_option` | Baseline only | Independent-normal moment matching using `warm_up`'s estimates. Never raises, always returns a valid probability -- but it's a cruder model than `price_option_from_parameters`. |
| `quote` | **Placeholder, not real logic** | Fixed 5¢ half-spread around the fair price, fixed size of 5 contracts on both sides, **no reference to `self.cash_balance`, `self.position`, or any risk budget at all.** |
| `respond_to_fok` | **Placeholder, not real logic** | Accepts if price clears fair value by a fixed 5¢ edge. **No check against remaining cash before accepting**, and FOK orders can arrive with large quantities (26 contracts seen in one VERBOSE log) that get accepted in full if the edge condition alone is met. |

So the honest framing is: `quote` and `respond_to_fok` exist and return legal values (which was
the previous fix -- they used to crash the session by returning `None`), but their *decision
logic* was never built past "does this trade look profitable in isolation." Neither one asks "can
I afford the worst case of this trade given what I already hold and how much cash is left."

### Why this produces exactly the failure pattern seen

The grader reserves `quantity * max_loss_per_contract` from cash **at trade time**, not net
expected PnL (see `README.md`'s bankruptcy note). A sequence of individually well-priced trades
can still exhaust a starting balance as small as $10-$40 if:

- `quote` always offers the same fixed size (5) regardless of how much cash is already
  committed to other open positions, so open risk can stack up across multiple concurrent
  quotes/fills.
- `respond_to_fok` accepts large FOK quantities (whatever the counterparty offers, no cap) as
  long as the edge condition is met, with no check of whether that single trade's max loss fits
  in remaining cash.
- Neither method reduces size or refuses to trade as `self.cash_balance`/realized cash gets
  low -- there's no reserve buffer, no shrinking size near a risk floor, no degenerate
  "riskless" fallback quote (e.g. `bid=0.00`/`offer=1.00`) once the risk budget is exhausted.

This matches the observed pattern precisely: bankruptcies happen mid-session (partway through a
20-150 day run), often while the *displayed* PnL still looks good, because the realized-loss
accounting the grader uses is stricter and faster than anything the bot currently defends
against.

### What is not the problem (ruled out)

- **Not a crash/exception issue.** Zero tracebacks across all 20 test cases.
- **Not a raw pricing-accuracy issue for THEO.** `price_option_from_parameters` matches the
  true parameters essentially exactly.
- **Probably not the main driver even where `warm_up`/`price_option`'s baseline model is
  weaker than the true-parameter engine.** A noisier fair-value estimate would show up as worse
  edge/PnL, not as bankruptcy while ranked #1 -- the bankruptcies are a sizing failure sitting on
  top of pricing that was, at least directionally, good enough to be winning.

### Fix priority (per the project's triage order: errors first, then optimize)

No errors remain, so this -- risk-aware sizing in `quote` and `respond_to_fok` -- is the top
optimization priority, ahead of upgrading `warm_up`/`price_option`'s pricing model, because a
single bankruptcy zeroes out an otherwise-winning test case regardless of pricing quality:

1. Track realized/at-risk cash properly (mirror the grader's max-loss-at-trade-time accounting
   internally, since `self.cash_balance` is only set once at `__init__` and goes stale -- see
   `Bot.py`'s docstrings on this).
2. Size `quote`'s bid/offer quantities from remaining risk budget, not a fixed constant.
3. Cap what `respond_to_fok` will accept by the same risk budget, independent of how large the
   FOK order's quantity is.
4. Keep a reserve buffer (e.g. a fraction of starting cash) so a losing streak can't fully
   exhaust capital, and fall back to a riskless degenerate quote once that buffer is breached
   rather than refusing to quote at all.
5. Only after that: revisit `warm_up`/`price_option`'s baseline model (rate-beta/sector-beta
   decomposition, AJR-THR covariance) to close the gap with `price_option_from_parameters`'s
   accuracy -- this improves edge quality, which matters once bankruptcy is no longer wiping out
   otherwise-good sessions.
