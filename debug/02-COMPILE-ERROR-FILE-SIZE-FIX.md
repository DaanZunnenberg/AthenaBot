# Debug log: "Server error while compiling" on HackerRank -- RESOLVED

> **What this improved / established:** Diagnosed and fixed the traceback-free "Server error while compiling" HackerRank submission failure. Root cause: file size crossing a ~65,536-byte ceiling, not a code defect. Fixed by trimming prose only (67,794 -> 60,060 bytes), zero logic changes. This exact bug recurred twice more later (see `09-MODEL-UNCERTAINTY-SIZE-CUTS.md` and `docs/history/JOURNEY.md` Phase 8) -- same diagnosis, same fix.

## Resolution

**Confirmed fixed.** `Bot.py` (60,060 bytes, trimmed from `BotFault.py`'s 67,794) compiled
and ran cleanly on HackerRank -- all checks passed. Root cause was file size crossing the
65,536-byte (2^16) threshold (see "Root cause" below), not any code content. `Bot.py` at the
repo root is the current submission; `debug/BotFinal.py` is an identical copy kept for the
record. No further action needed on the compile issue -- remaining work is tuning
quoting/risk parameters (bankruptcy rate, spread, sizing), which is a scoring question, not a
compilation one.

## Symptom

Submitting `Bot.py` to HackerRank returns `"Server error while compiling. Try again."` -- a
generic backend error with no traceback, no file/line, no exception type. This is distinct
from the ordinary Python errors we've hit before (e.g. `AttributeError: 'NoneType' object has
no attribute 'bid_price'`), which show a full traceback pointing into `Solution.py` and our
code. The file compiles and runs cleanly locally (`python3.11 -m py_compile`, `ast.parse`,
full behavioral test suite) in every version tried so far, so this is something specific to
HackerRank's environment/pipeline, not a plain Python syntax error.

## Files in this folder

| File | What it is | HackerRank result |
|---|---|---|
| `BotDefault.py` | The unimplemented stub HackerRank supplies (all six `MarketMaker` methods as `TODO`/`...`). | **Compiles and runs** (fails the checks, as expected -- stubs return `None`/`0.5`). |
| `BotBaseline.py` | Full pricing engine (`_BinaryOptionPricer`, `warm_up`, `price_option`) implemented, plus the *first*, simple `quote()`/`respond_to_fok()` (fixed half-spread, fixed size, fixed edge, no risk ledger). | **Compiles and runs** -- this is the version behind the real scored results logged in `test_case_handles.md`. |
| `BotBaseTest.py` | `BotBaseline.py` + the new risk-ledger *state plumbing only*: class-level constants, `__init__`'s cash/cap setup, `on_trade`'s debit, `on_step_advance`'s settlement credit, and their two new helper methods. `quote()`/`respond_to_fok()` left as the **old**, still-working versions (the new ledger fields are set but unused by them). | **Compiles and runs** -- scored 11/20, the same pass/fail pattern as `BotBaseline.py`'s real run in `test_case_handles.md`. Rules out the state/ledger plumbing as the cause. |
| `BotQuoteTest.py` | `BotBaseTest.py` + the new reservation-price `quote()` and its 4 helpers (`_reservation_price`, `_quote_half_spread`, `_round_quote_prices`, `_quote_quantities`). `respond_to_fok()` still the **old** version. | **Compiles and runs** -- all tests ran; 5 failed due to bankruptcy (a scoring/risk-tuning outcome, not a compile error). Rules out the new `quote()` as the cause. |
| `BotFokTest.py` | `BotBaseTest.py` with the old `quote()` untouched, + only the new risk-gated `respond_to_fok()`. | **Compiles and runs** -- some tests failed on bankruptcy (scoring outcome, not a compile error). Rules out the new `respond_to_fok()` alone as the cause too. |
| `BotFault.py` | The full reservation-price `quote()` (inventory skew, time-scaled penalty, risk-gated sizing) and risk-gated `respond_to_fok()`, plus two defensive fixes applied after the first failure (see below). Structurally equivalent to `Bot.py` at the time this was captured. **67,794 bytes.** | **Fails** with the server error. |
| `BotFinal.py` | `BotFault.py` with its most verbose docstrings (new `quote`/`respond_to_fok`/ledger methods) trimmed to 1-3 lines each; zero logic changes. **60,060 bytes.** Identical to `Bot.py` at the repo root. | **Compiles and runs -- all checks passed.** Confirms the 65,536-byte threshold theory and closes this investigation. |

## What's been ruled out (verified, not assumed)

Checked directly against `BotBaseline.py` and/or `BotDefault.py`:

- **Imports** -- identical `math`, `random`, `collections.defaultdict`, `dataclasses`,
  `enum.StrEnum`, `typing.Any/Final` in every version. Nothing third-party added.
- **Encoding** -- pure ASCII, no BOM, no CRLF, no tabs, no invisible/smart-quote characters.
- **Balanced syntax** -- triple-quotes even, brackets balanced, `ast.parse`/`py_compile`
  succeed on every version.
- **Python 3.12.4 compatibility** -- confirmed the target runtime; nothing used
  (`StrEnum`, builtin generic subscripting, `math.erf`) requires anything newer.
- **Template requirements** -- all six required `MarketMaker` method signatures are
  byte-identical to the template in every version; no class renamed; the 9 supplied classes
  (`BinaryOption`, `FokOrder`, `MarketHistory`, `MarketParameters`, `OptionLeg`, `OrderType`,
  `Position`, `Quote`, `Underlying`) are structurally identical to the template (verified via
  AST diff, docstrings aside) in every version.
- **Extra top-level class** (`_BinaryOptionPricer`, inserted between the "YOUR MARKET MAKER"
  banner and `class MarketMaker:`) -- present in **both** `BotBaseline.py`
  (works) and `BotFault.py` (fails), so this is not the cause. (This was an
  earlier hypothesis; refuted once `BotBaseline.py`'s actual content was
  compared directly.)
- **Union type hint in a string annotation**
  (`-> "tuple[float, float] | tuple[None, None]"` in `_round_quote_prices`) -- removed in
  `BotFault.py` (replaced with a plain `"tuple[float, float]"` return type and
  a `-1.0` sentinel instead of `(None, None)`). Did not fix the error on its own.
- **Unguarded computation in `__init__`** -- the original new `__init__` did
  `float(cash_balance)`/arithmetic with no `try/except`, unlike every other method. Wrapped in
  `try/except` with a safe fallback in `BotFault.py`. Did not fix the error on
  its own.
- **Private method/attribute access** -- every `self._x` reference in the new code was
  cross-checked against its definition (assignment, method, or class constant). All resolve
  correctly; no typos, no missing definitions, no scope bugs.

## Root cause: file size, not code content

Every individual piece of the `quote()`/`respond_to_fok()`/risk-ledger rewrite was bisected
and cleared on its own (state plumbing, new `quote()` alone, new `respond_to_fok()` alone --
see table above). The only variable left standing once every content-based hypothesis was
exhausted: **file size**. Lining up the actual byte counts against every confirmed result:

| File | Bytes | Result |
|---|---|---|
| `BotBaseTest.py` | 56,405 | PASS |
| `BotFokTest.py` | 57,151 | PASS |
| `BotQuoteTest.py` | 62,924 | PASS |
| `BotFault.py` | 67,794 | **FAIL** |

Every passing file is under 65,536 bytes (2^16); the one failing file is over it. That's an
extremely common hard limit (a 16-bit length-prefixed field, e.g. in a submission-size cap or
buffer somewhere in HackerRank's pipeline) and explains why "Server error while compiling"
never came with a Python traceback -- it's not a Python-level error at all, it's the
submission being rejected before actual compilation.

**Fix:** trim the file below the threshold without changing any logic. `BotFinal.py` /
`Bot.py` do this by shortening the newest, most verbose docstrings (added during the
reservation-price rewrite) from multi-paragraph derivations down to 1-3 line summaries --
every fact preserved, only the prose cut. Result: 60,060 bytes, ~5.5 KB of margin under the
threshold. Local regression confirms zero behavioral change.

**Confirmed:** `BotFinal.py`/`Bot.py` compiled and ran with all checks passed at 60,060 bytes.
The threshold theory holds; no further trimming needed.
