"""Forces net long 1, 2, 4, 6 in one option and asserts the quote stays live (never both
sides withdrawn) and the mid moves monotonically down as inventory grows. Baseline
(pre-fix) code failed at long 1 (bid/offer collapsed to 0.00/1.00)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _world import make_history, underlyings_from_values, make_option

from Bot import MarketMaker


def main():
    history, values = make_history(60, seed=7)
    underlyings = underlyings_from_values(values)
    option = make_option(1, values, steps=5, kind="ajr")
    mm = MarketMaker(underlyings, [option], 40)
    mm.warm_up(history)

    mids = []
    for net in (0, 1, 2, 4, 6):
        mm.position.option_quantity_by_option_id[option.option_id] = net
        q = mm.quote(option, counterparty_id=1)
        is_fallback = q.bid_price == 0.0 and q.offer_price == 1.0 and q.bid_quantity == mm._Q_MAX
        assert not is_fallback, f"net={net}: quote collapsed to risk-free fallback"
        assert q.bid_price < q.offer_price
        mid = (q.bid_price + q.offer_price) / 2.0
        mids.append(mid)
        print(f"net={net}: bid={q.bid_price:.4f} offer={q.offer_price:.4f} mid={mid:.4f} "
              f"bid_qty={q.bid_quantity} offer_qty={q.offer_quantity}")

    for i in range(1, len(mids)):
        assert mids[i] <= mids[i - 1] + 1e-9, f"mid did not move monotonically down: {mids}"
    print("PASS")


if __name__ == "__main__":
    main()
