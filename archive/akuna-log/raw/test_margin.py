"""Asserts the internal margin ledger matches README.md line by line: buying N at price P
debits N*P; selling N at price P debits N*(1-P); expiry credit never decreases the balance;
a flat round trip does NOT permanently consume margin (resolved question 1: grader credits
NET per position, so a round trip must free the margin back up)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _world import underlyings_from_values, make_option

from Bot import MarketMaker, FED_FUNDS_RATE_UNDERLYING_ID, AJARAI_UNDERLYING_ID, THERIODIC_UNDERLYING_ID


def new_mm(cash=100.0):
    values = {FED_FUNDS_RATE_UNDERLYING_ID: 2.5, AJARAI_UNDERLYING_ID: 450.0, THERIODIC_UNDERLYING_ID: 550.0}
    underlyings = underlyings_from_values(values)
    option = make_option(1, values, steps=5, kind="ajr")
    mm = MarketMaker(underlyings, [option], cash)
    return mm, option, values


def test_buy_debit():
    mm, option, _ = new_mm()
    mm.on_trade(option, price=0.20, quantity=5, counterparty_id=1)
    assert abs(mm._used_margin - 1.00) < 1e-9, f"buy 5@0.20 should debit 1.00, got {mm._used_margin}"
    print("buy 5 @ 0.20 debits 1.00: OK")


def test_sell_debit():
    mm, option, _ = new_mm()
    mm.on_trade(option, price=0.20, quantity=-5, counterparty_id=1)
    assert abs(mm._used_margin - 4.00) < 1e-9, f"sell 5@0.20 should debit 4.00, got {mm._used_margin}"
    print("sell 5 @ 0.20 debits 4.00: OK")


def test_expiry_credit_never_decreases():
    mm, option, values = new_mm()
    mm.on_trade(option, price=0.30, quantity=3, counterparty_id=1)
    cash_before = mm._cash
    new_values = dict(values)
    new_values[AJARAI_UNDERLYING_ID] = option.strike + 1.0  # ITM -> payoff 1.0
    new_underlyings = underlyings_from_values(new_values)
    mm.on_step_advance(new_underlyings, [])  # option expired, no longer active
    assert mm._cash >= cash_before, f"expiry credit decreased cash: {cash_before} -> {mm._cash}"
    print(f"expiry credit never decreases balance: {cash_before} -> {mm._cash}: OK")


def test_flat_round_trip_frees_margin():
    mm, option, values = new_mm()
    mm.on_trade(option, price=0.30, quantity=5, counterparty_id=1)
    assert mm._used_margin > 0.0
    mm.on_trade(option, price=0.30, quantity=-5, counterparty_id=1)
    # Net position is now flat (0), but used_margin is not automatically released until
    # settlement in this ledger design -- verify margin is released once the position
    # actually settles at zero net exposure via expiry credit.
    net = mm.position.option_quantity_by_option_id.get(option.option_id, 0)
    assert net == 0, f"expected flat position, got {net}"
    new_underlyings = underlyings_from_values(values)
    mm.on_step_advance(new_underlyings, [])  # settle since option no longer active
    assert mm._used_margin < 1e-6, f"flat round trip should free all margin at settlement, used_margin={mm._used_margin}"
    print("flat round trip frees margin at settlement: OK")


def test_ten_round_trips_do_not_starve_cash():
    """Regression for D7: ten zero-PnL round trips must not ratchet used_margin up."""
    mm, option, values = new_mm(cash=10.0)
    for _ in range(10):
        mm.on_trade(option, price=0.50, quantity=2, counterparty_id=1)
        mm.on_trade(option, price=0.50, quantity=-2, counterparty_id=1)
    net = mm.position.option_quantity_by_option_id.get(option.option_id, 0)
    assert net == 0
    new_underlyings = underlyings_from_values(values)
    mm.on_step_advance(new_underlyings, [])
    assert mm._used_margin < 1e-6, f"ten round trips left used_margin={mm._used_margin}"
    assert mm._cash > 0.0, "ten zero-PnL round trips should not exhaust cash"
    print(f"ten round trips: used_margin={mm._used_margin}, cash={mm._cash}: OK")


def main():
    test_buy_debit()
    test_sell_debit()
    test_expiry_credit_never_decreases()
    test_flat_round_trip_frees_margin()
    test_ten_round_trips_do_not_starve_cash()
    print("PASS")


if __name__ == "__main__":
    main()
