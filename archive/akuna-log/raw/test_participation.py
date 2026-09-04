"""Instantiates MarketMaker at capital 10, 20, 40, warms up on a 60-day synthetic
history, advances 40 days, and asserts fewer than 5% of quotes are the degenerate
0.00/1.00 fallback. Baseline (pre-fix) code failed this at 100% / 100% / 17%."""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _world import make_history, underlyings_from_values, advance_values, make_option

from Bot import MarketMaker


def run(capital, seed):
    random.seed(seed)
    history, values = make_history(60, seed=seed)
    underlyings = underlyings_from_values(values)
    option_id_counter = [0]

    def new_options(values, n=3):
        opts = []
        for i in range(n):
            option_id_counter[0] += 1
            kind = random.choice(["fed", "ajr", "thr", "spread"])
            opts.append(make_option(option_id_counter[0], values, steps=random.randint(1, 8), kind=kind))
        return opts

    options = new_options(values)
    mm = MarketMaker(underlyings, options, capital)
    mm.warm_up(history)

    total_quotes = 0
    degenerate = 0
    counterparty = 1
    for day in range(40):
        for option in mm.active_option_state:
            q = mm.quote(option, counterparty)
            total_quotes += 1
            if q.bid_price == 0.0 and q.offer_price == 1.0:
                degenerate += 1
        values = advance_values(values)
        underlyings = underlyings_from_values(values)
        options = [o.advance_step() for o in options if o.steps_until_expiry > 0]
        if len(options) < 3:
            options = options + new_options(values, 3 - len(options))
        mm.on_step_advance(underlyings, options)

    rate = degenerate / total_quotes if total_quotes else 1.0
    print(f"capital={capital}: {degenerate}/{total_quotes} degenerate ({rate:.1%})")
    return rate


def main():
    max_rate = 0.0
    for capital in (10, 20, 40):
        rate = run(capital, seed=capital)
        max_rate = max(max_rate, rate)
        assert rate < 0.05, f"degenerate rate {rate:.1%} at capital {capital} exceeds 5%"
    print(f"max degenerate rate across capital levels: {max_rate:.1%}")
    print("PASS")


if __name__ == "__main__":
    main()
