# `experimental/src/` — tuning variant implementations

Each file is one `MarketMaker` implementation, structurally identical to `Bot.py` (same
six-method interface) so any of them could be promoted directly. Each imports the shared
interface classes (`BinaryOption`, `MarketHistory`, `MarketParameters`, etc.) from the private
`src` submodule (`src.taqf.akuna.market_types`) and contains only its own `MarketMaker` plus its
own helper classes.

See `../README.md` for naming conventions, the curated-10 selection rationale, and the full
list of files. Each file's own scorecard lives alongside it in `../scores/`, not here.
