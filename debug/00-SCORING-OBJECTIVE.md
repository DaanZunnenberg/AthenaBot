# The scored objective (read before touching any constant)

> **What this improved / established:** Reference doc, not a change log -- defines what the grader actually pays out on (rank, not raw PnL). Read before tuning any quoting/sizing constant so effort targets the right thing.

## What the grader actually pays out on

Per `README.md`: each SCORED session ranks every participating market maker by end-of-session
PnL. **Full credit for ranking #1, partial credit for merely staying solvent, zero credit for
bankruptcy or an unhandled exception -- regardless of how good the PnL was at the moment of
bankruptcy** (see `docs/history/JOURNEY.md`/`docs/history/NOTES.md`: four of the historical bankruptcies happened while
`AthenaBot` was ranked #1 by PnL at the time). This is an **ordinal, competitor-relative**
objective with a hard floor, not a raw expected-cash objective:

- Being #1 by a lot and #1 by a little score the same (full credit either way).
- Being #2 instead of #1 loses most of the value of the session even if the PnL gap is tiny.
- Bankruptcy is catastrophic and non-negotiable: it zeroes the session regardless of unrealized
  PnL, and per the README's bankruptcy note, the grader checks cash strictly and immediately
  (worst-case margin debited at trade time, not mark-to-market).

## What this repo's harness actually measures (and why that's a known gap)

`sim/harness.py` has no model of competing market makers -- it only simulates `AthenaBot` against
synthetic counterparties (`sim/counterparties.py`). It therefore cannot reproduce "#1 by PnL
among N market makers," and says so explicitly at import time (its own printed `WARNING`). As a
documented fallback, `SessionResult.score` is **terminal cash** (0 on bankruptcy, else the actual
end-of-session balance) -- a proxy for the real ordinal objective, not the objective itself. This
was already true before this task and is unchanged here; it is restated because every constant
tuned in `debug/CALIBRATION.md` is tuned against this proxy, and the proxy's blind spots directly
bound how much to trust the sweep:

- The proxy rewards *any* extra dollar of expected cash equally, including dollars earned by
  being marginally more aggressive once already comfortably ahead -- which the real ordinal
  objective does not reward (you cannot score more than "first").
- The proxy has no notion of *relative* performance, so it underweights it: a session where the
  proxy's cash is merely median-good but the competing MMs did *worse* still scores full credit
  under the real objective, in a way the proxy can't see.

## What this implies for the free constants

Given the real objective is **ordinal-with-a-hard-floor**, not **maximize E[cash]**:

- **The Prompt 2 worst-case feasibility gate should keep doing the primary work of preventing
  bankruptcy** -- it is a hard constraint on a hard, non-negotiable failure mode (0 credit), and
  no amount of utility-curve tuning is a substitute for it. This was already the design decision
  in Prompt 4 ("keep the Prompt 2 worst-case gate as the hard feasibility constraint; utility is
  the preference, the gate is the constraint") and nothing here changes that.
- **`gamma` (risk aversion in the exponential utility) should stay moderate, not large.** Because
  the true objective doesn't reward "safely mediocre" any more than "aggressively good" (both
  lose to whoever is actually #1), `gamma` too high would needlessly give up edge that the hard
  gate would have protected anyway. `gamma` too low reduces the exponential-utility layer to
  something close to expected-value pricing, which is fine given the gate is the real defense,
  but forfeits the correlation-aware / inventory-aware pricing benefit the whole Prompt 4 design
  exists for. So: `gamma` is doing real but secondary economic work here -- shaping *which* edge
  to take when the gate allows multiple options, not preventing the catastrophic failure mode.
  This argues for keeping the sweep's `gamma` range centered near the Prompt 4 provisional value
  (0.05) rather than searching orders of magnitude away from it.
- **The proxy objective (terminal cash) is what `debug/CALIBRATION.md`'s sweep actually
  optimizes**, since it's what the harness can measure. Given the analysis above, optimizing
  mean terminal cash while holding bankruptcy rate non-increasing and the 5th-percentile score
  non-decreasing (this task's acceptance rule, item B) is a reasonable proxy for the real
  ordinal objective: it directly enforces the hard floor (bankruptcy rate), and protecting the
  5th percentile is the closest available proxy for "don't sacrifice the tail to win on average,"
  which matters because a single bad tail session is exactly a lost-the-ranking / bankrupt
  session under the real objective, not a session that merely scores a bit lower.

## Bottom line

Optimize mean terminal cash on the harness proxy, subject to (a) bankruptcy rate not increasing
and (b) 5th-percentile score not decreasing, exactly as this task's acceptance rule specifies --
and treat `gamma` as a moderate, secondary knob for edge-selection, not the mechanism preventing
bankruptcy. The feasibility gate remains the mechanism for that, unchanged from Prompt 4.
