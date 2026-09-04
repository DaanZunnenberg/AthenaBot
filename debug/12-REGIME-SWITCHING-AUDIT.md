# Regime-switching audit

> **What this improved / established:** Audit confirming no regime-switching/HMM/model-switching logic exists anywhere in `Bot.py` -- a negative result that ruled out one hypothesis rather than shipping a feature.

## Finding: no discrete regime-switching, HMM, or model-switching logic exists in `Bot.py`

`grep -niE "regime|hmm|hidden.markov|switch" Bot.py` returns zero matches. Manually re-checked
every branch in `MarketMaker`/`_ParameterEstimator` for anything that changes which *model*
governs pricing/quoting based on a discrete classification of market conditions (as opposed to
continuously updating the same model's parameters, which is what `_refit` does every day): none
found. The `if/else` branches present in the codebase (e.g. `_theta_cov_reliable`, degenerate
`sd < MIN_SD` cases in `_BinaryOptionPricer`, the feasibility-gate pass/fail branches) are all
numerical-edge-case handling within a single fixed model, not competing models being switched
between.

## Point 1 confirmed directly

The existing rate mean-reversion fit (`_ParameterEstimator._fit_rate`, producing
`kappa`/`r_target` in `MarketParameters`) is itself the only thing in this codebase that plays a
"regime" role — it's a single continuous Ornstein-Uhlenbeck-style mean-reversion model, refit
online every day via `_refit`, not a discrete switch between two or more branches. Per this
task's own instruction, no second, discrete regime layer is added on top of it.

## Stopping here

Per the task: "if so [no such logic exists], state that explicitly ... and stop here." No further
action taken for Part E — nothing to wrap in a confidence weight, no hysteresis to add, no
removal criterion to run, since there is no regime-switching logic in the codebase to audit,
confidence-weight, or remove. This is a stronger, more directly falsifiable claim than a
"probably fine" — it was checked by exhaustive keyword search plus manual review, not inferred.
