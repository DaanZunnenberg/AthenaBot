# `archive/` — archived scratch material (not part of the public project narrative)

Everything in this folder was moved here from elsewhere in the repo because it's working
scratch or superseded material — real project history, kept in full (nothing was deleted,
only moved), but not the material a reader should have to wade through to understand the
current state of the project. For that, start at the root `README.md` and
`docs/history/JOURNEY.md`, then `experimental/README.md` and `debug/README.md` for the curated,
explained versions of this same history.

Organized by topic, not by where it used to live:

- **`debug-snapshots/`** — the raw `.py` bisection/reference snapshots that used to sit
  alongside `debug/`'s `.md` writeups. The writeups themselves (renamed, each with a "what
  this improved" summary) stayed public in `debug/`; only the bisection code snapshots moved
  here. See `debug-snapshots/README.md`.
- **`experiment-archive/`** — the `experimental/` bot variants that didn't make the curated
  top-10 cut kept in the public `experimental/` folder, plus a superseded duplicate snapshot
  of the folder structure used before this reorganization. See
  `experiment-archive/README.md`.
- **`akuna-log/`** — the former top-level `akuna/` scratch workspace (an early standalone
  pricing prototype + regression tests against `Bot.py`), archived with an explainer of what
  worked and what didn't. See `akuna-log/README.md`.

Nothing in `archive/` is imported by `Bot.py` or by anything in `experimental/`, `debug/`,
or `sim/` — it's read-only archival material.
