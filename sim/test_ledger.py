"""
Tests for the net-position risk ledger (`MarketMaker._cash`/`_short_exposure`/
`_worst_case_cash`/`grader_worst_case`) added in this task, plus the per-day fair-value
cache. The central property under test is the netting invariant: round-tripping a position
(buying then selling the same size, or vice versa) must release its reservation exactly,
regardless of the prices used or the path taken -- the bug the old per-trade-debit ledger
had (see debug/PHASE1_RESULTS.md).

Run with: python3.11 sim/test_ledger.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import (  # noqa: E402
    AJARAI_UNDERLYING_ID,
    FED_FUNDS_RATE_UNDERLYING_ID,
    THERIODIC_UNDERLYING_ID,
    BinaryOption,
    MarketMaker,
    OptionLeg,
    Underlying,
)


def _make_mm(starting_cash: float = 10.0) -> MarketMaker:
    values = {FED_FUNDS_RATE_UNDERLYING_ID: 2.0, AJARAI_UNDERLYING_ID: 100.0, THERIODIC_UNDERLYING_ID: 100.0}
    underlyings = [
        Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, values[FED_FUNDS_RATE_UNDERLYING_ID]),
        Underlying("AJR", AJARAI_UNDERLYING_ID, values[AJARAI_UNDERLYING_ID]),
        Underlying("THR", THERIODIC_UNDERLYING_ID, values[THERIODIC_UNDERLYING_ID]),
    ]
    return MarketMaker(underlyings, [], starting_cash)


def _make_option(option_id: int, steps: int = 5, strike: float = 100.0) -> BinaryOption:
    return BinaryOption(legs=(OptionLeg(AJARAI_UNDERLYING_ID, 1.0),), option_id=option_id, steps_until_expiry=steps, strike=strike)


# ---------------------------------------------------------------------------
# Netting invariant
# ---------------------------------------------------------------------------

def test_netting_invariant_random() -> list[str]:
    """q -> q+dq -> q (same option, arbitrary intermediate prices/sizes) must leave
    `_short_exposure` (the reservation) exactly where it started -- checked directly, since
    that's the quantity the task's "reserved capital" refers to (cash P&L is allowed to
    differ, since round-tripping at different prices is a real gain/loss)."""
    rng = np.random.default_rng(0)
    failures = []
    for trial in range(200):
        mm = _make_mm(starting_cash=100.0)
        option = _make_option(option_id=1)
        start_q = int(rng.integers(-10, 11))
        if start_q != 0:
            mm.on_trade(option, price=float(rng.uniform(0.05, 0.95)), quantity=start_q, counterparty_id=1)
        exposure_before = mm._short_exposure

        dq = int(rng.integers(-8, 9))
        if dq == 0:
            continue
        price1 = float(rng.uniform(0.01, 0.99))
        price2 = float(rng.uniform(0.01, 0.99))
        mm.on_trade(option, price=price1, quantity=dq, counterparty_id=1)
        mm.on_trade(option, price=price2, quantity=-dq, counterparty_id=1)

        exposure_after = mm._short_exposure
        final_q = mm.position.option_quantity_by_option_id.get(option.option_id, 0)
        if final_q != start_q:
            failures.append(f"trial {trial}: final_q={final_q} != start_q={start_q} (bookkeeping bug, not netting)")
            continue
        if abs(exposure_after - exposure_before) > 1e-9:
            failures.append(
                f"trial {trial}: start_q={start_q} dq={dq} exposure_before={exposure_before} "
                f"exposure_after={exposure_after} (should be identical)"
            )
    return failures


def test_netting_full_round_trip_to_flat() -> list[str]:
    """The specific case called out in the task: buy N then sell N (start flat) must return
    _short_exposure to exactly 0, and _worst_case_cash to exactly starting_cash + realised
    P&L (no phantom reservation left over)."""
    failures = []
    for buy_price, sell_price in [(0.20, 0.20), (0.20, 0.30), (0.30, 0.20), (0.01, 0.99), (0.99, 0.01)]:
        mm = _make_mm(starting_cash=10.0)
        option = _make_option(option_id=7)
        mm.on_trade(option, price=buy_price, quantity=5, counterparty_id=1)
        mm.on_trade(option, price=sell_price, quantity=-5, counterparty_id=1)
        if mm._short_exposure != 0.0:
            failures.append(f"buy@{buy_price} sell@{sell_price}: short_exposure={mm._short_exposure} != 0")
        expected_cash = 10.0 - 5 * buy_price - (-5) * sell_price
        if abs(mm._cash - expected_cash) > 1e-9:
            failures.append(f"buy@{buy_price} sell@{sell_price}: cash={mm._cash} != expected {expected_cash}")
        if abs(mm._worst_case_cash() - mm._cash) > 1e-9:
            failures.append(f"buy@{buy_price} sell@{sell_price}: W={mm._worst_case_cash()} != cash (flat book)")
    return failures


def test_short_round_trip_to_flat() -> list[str]:
    """Mirror case: sell N then buy N back (opening short, then closing it)."""
    failures = []
    for sell_price, buy_price in [(0.20, 0.20), (0.20, 0.10), (0.10, 0.20)]:
        mm = _make_mm(starting_cash=10.0)
        option = _make_option(option_id=9)
        mm.on_trade(option, price=sell_price, quantity=-5, counterparty_id=1)
        if mm._short_exposure != 5.0:
            failures.append(f"sell@{sell_price}: short_exposure={mm._short_exposure} != 5 while open")
        mm.on_trade(option, price=buy_price, quantity=5, counterparty_id=1)
        if mm._short_exposure != 0.0:
            failures.append(f"sell@{sell_price} buy@{buy_price}: short_exposure={mm._short_exposure} != 0 after closing")
    return failures


# ---------------------------------------------------------------------------
# Settlement releases reservation
# ---------------------------------------------------------------------------

def test_settlement_releases_reservation() -> list[str]:
    """A short position that expires must have its reservation released and never traded
    again -- position stays at 0 forever after, per _settle_expired_positions."""
    failures = []
    mm = _make_mm(starting_cash=10.0)
    option = _make_option(option_id=3, steps=0, strike=50.0)  # deep ITM at n=0: will lose
    mm.active_option_state = [option]
    mm.on_trade(option, price=0.5, quantity=-5, counterparty_id=1)
    if mm._short_exposure != 5.0:
        failures.append(f"pre-settlement short_exposure={mm._short_exposure} != 5")

    new_values = [
        Underlying("FED", FED_FUNDS_RATE_UNDERLYING_ID, 2.0),
        Underlying("AJR", AJARAI_UNDERLYING_ID, 200.0),  # >= strike 50 -> payoff 1.0, short loses
        Underlying("THR", THERIODIC_UNDERLYING_ID, 100.0),
    ]
    mm._settle_expired_positions(new_values, [])  # option not in new_option_state -> expired
    if mm._short_exposure != 0.0:
        failures.append(f"post-settlement short_exposure={mm._short_exposure} != 0")
    if mm.position.option_quantity_by_option_id.get(option.option_id, 0) != 0:
        failures.append("position not zeroed after settlement")
    expected_cash = 10.0 - (-5) * 0.5 + (-5) * 1.0  # trade debit-turned-credit, then payoff
    if abs(mm._cash - expected_cash) > 1e-9:
        failures.append(f"cash={mm._cash} != expected {expected_cash}")
    return failures


# ---------------------------------------------------------------------------
# grader_worst_case cross-check
# ---------------------------------------------------------------------------

def test_grader_worst_case_matches_w() -> list[str]:
    """As documented in debug/PHASE1_RESULTS.md, grader_worst_case is implemented to
    coincide with W (no distinct state-based rule could be derived from the README without
    guessing) -- this should hold for arbitrary positions."""
    rng = np.random.default_rng(1)
    failures = []
    for trial in range(50):
        mm = _make_mm(starting_cash=50.0)
        for i in range(5):
            option = _make_option(option_id=i)
            q = int(rng.integers(-10, 11))
            if q != 0:
                mm.on_trade(option, price=float(rng.uniform(0.05, 0.95)), quantity=q, counterparty_id=1)
        w = mm._worst_case_cash()
        g = MarketMaker.grader_worst_case(mm._cash, mm.position)
        if abs(w - g) > 1e-9:
            failures.append(f"trial {trial}: W={w} grader_worst_case={g}")
    return failures


# ---------------------------------------------------------------------------
# Per-day cache
# ---------------------------------------------------------------------------

def test_day_cache_hits_once_per_day() -> list[str]:
    """price_option should only actually run once per option_id per day; repeated quote/FOK
    lookups within the same day must read the cached value, and a new on_step_advance day
    must invalidate it."""
    failures = []
    mm = _make_mm(starting_cash=10.0)
    option = _make_option(option_id=1)

    call_count = {"n": 0}
    original = mm.price_option

    def counting_price_option(opt):
        call_count["n"] += 1
        return original(opt)

    mm.price_option = counting_price_option
    for _ in range(5):
        mm._get_cached_fair(option)
    if call_count["n"] != 1:
        failures.append(f"price_option called {call_count['n']} times for 5 same-day lookups, expected 1")

    mm._day_cache = {}  # simulate on_step_advance's invalidation
    mm._get_cached_fair(option)
    if call_count["n"] != 2:
        failures.append(f"price_option called {call_count['n']} times after cache invalidation, expected 2")

    entry = mm._day_cache[option.option_id]
    if set(entry.keys()) != {"P", "sigma_P", "U_P"}:
        failures.append(f"cache entry keys {set(entry.keys())} != reserved {{'P','sigma_P','U_P'}}")
    return failures


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    suites = [
        ("netting invariant (random)", test_netting_invariant_random),
        ("netting: full round trip to flat", test_netting_full_round_trip_to_flat),
        ("netting: short round trip to flat", test_short_round_trip_to_flat),
        ("settlement releases reservation", test_settlement_releases_reservation),
        ("grader_worst_case matches W", test_grader_worst_case_matches_w),
        ("per-day cache", test_day_cache_hits_once_per_day),
    ]
    total_failures = 0
    for name, fn in suites:
        failures = fn()
        total_failures += len(failures)
        print(f"[{'PASS' if not failures else 'FAIL'}] {name} ({len(failures)} failures)")
        for f in failures[:10]:
            print("   ", f)

    print()
    if total_failures == 0:
        print("ALL LEDGER/CACHE TESTS PASS.")
        return 0
    print(f"{total_failures} total failures.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
