"""
Synthetic counterparties for sim/harness.py's day loop. Each implements the two exchange
interactions MarketMaker can be offered: an RFQ (respond_to_quote, evaluating our two-sided
Quote and deciding whether/which side to hit) and a FOK (make_fok_order, deciding whether to
offer one at all, and at what price/quantity/side).

All randomness is drawn from the `rng: np.random.Generator` passed in at construction (never
from the stdlib `random` module or an unseeded source), so a counterparty's behaviour is
fully determined by that generator's state -- required for run_batch's common-random-numbers
guarantee.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Protocol

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Bot import BinaryOption, FokOrder, MarketParameters, OrderType, Quote, _BinaryOptionPricer  # noqa: E402


class Counterparty(Protocol):
    def respond_to_quote(
        self, params: MarketParameters, values: dict[int, float], option: BinaryOption, quote: Quote,
    ) -> Optional[tuple[OrderType, float, int]]:
        """Returns (side, price, quantity) if the counterparty trades, else None. `side` is
        the counterparty's side: BUY means they buy at quote.offer_price, SELL means they
        sell at quote.bid_price."""
        ...

    def make_fok_order(
        self, params: MarketParameters, values: dict[int, float], option: BinaryOption, counterparty_id: int,
    ) -> Optional[FokOrder]:
        """Returns a FokOrder to offer, or None if this counterparty has no order today."""
        ...


def _true_theo(params: MarketParameters, values: dict[int, float], option: BinaryOption) -> float:
    return _BinaryOptionPricer.price(params, values, option)


class NoiseCounterparty:
    """
    Uninformed flow: picks a side uniformly at random, and a reservation price equal to the
    true theo plus Gaussian noise (sd configurable). Trades against a Quote whenever the
    reservation price crosses the relevant side; for FOK, offers at its own noisy
    reservation price.
    """

    def __init__(self, rng: np.random.Generator, noise_sd: float = 0.05, fok_quantity_max: int = 8) -> None:
        self.rng = rng
        self.noise_sd = noise_sd
        self.fok_quantity_max = fok_quantity_max

    def _reservation(self, params: MarketParameters, values: dict[int, float], option: BinaryOption) -> float:
        theo = _true_theo(params, values, option)
        noisy = theo + float(self.rng.normal(0.0, self.noise_sd))
        return min(max(noisy, 0.0), 1.0)

    def respond_to_quote(self, params, values, option, quote):
        side = OrderType.BUY if self.rng.uniform() < 0.5 else OrderType.SELL
        reservation = self._reservation(params, values, option)
        quantity = int(self.rng.integers(1, self.fok_quantity_max + 1))
        if side == OrderType.BUY and reservation >= quote.offer_price:
            return OrderType.BUY, quote.offer_price, min(quantity, quote.offer_quantity)
        if side == OrderType.SELL and reservation <= quote.bid_price:
            return OrderType.SELL, quote.bid_price, min(quantity, quote.bid_quantity)
        return None

    def make_fok_order(self, params, values, option, counterparty_id):
        side = OrderType.BUY if self.rng.uniform() < 0.5 else OrderType.SELL
        reservation = self._reservation(params, values, option)
        price = round(min(max(reservation, 0.01), 0.99) * 100) / 100.0
        quantity = int(self.rng.integers(1, self.fok_quantity_max + 1))
        return FokOrder(counterparty_id=counterparty_id, option_id=option.option_id,
                         order_type=side, price=price, quantity=quantity)


class InformedCounterparty:
    """
    Informed flow: computes the true theo from the *true* MarketParameters (not our
    estimate), and only trades when our quote is mispriced by more than `threshold`, always
    picking the side that is profitable for them (i.e. adverse to us).
    """

    def __init__(self, rng: np.random.Generator, threshold: float = 0.03, quantity_max: int = 10) -> None:
        self.rng = rng
        self.threshold = threshold
        self.quantity_max = quantity_max

    def respond_to_quote(self, params, values, option, quote):
        theo = _true_theo(params, values, option)
        quantity = int(self.rng.integers(1, self.quantity_max + 1))
        # Our offer is too cheap (they buy from us) if true theo clears it by > threshold.
        if theo - quote.offer_price > self.threshold:
            return OrderType.BUY, quote.offer_price, min(quantity, quote.offer_quantity)
        # Our bid is too rich (they sell to us) if true theo is below it by > threshold.
        if quote.bid_price - theo > self.threshold:
            return OrderType.SELL, quote.bid_price, min(quantity, quote.bid_quantity)
        return None

    def make_fok_order(self, params, values, option, counterparty_id):
        theo = _true_theo(params, values, option)
        quantity = int(self.rng.integers(1, self.quantity_max + 1))
        # Offer a price on the side profitable to them, priced just inside their edge so a
        # rational MM sized on `_FOK_EDGE` sometimes still accepts (otherwise no FOK ever
        # trades and this counterparty type is a no-op).
        if self.rng.uniform() < 0.5:
            price = round(min(max(theo - self.threshold * 1.5, 0.0), 1.0), 2)
            return FokOrder(counterparty_id=counterparty_id, option_id=option.option_id,
                             order_type=OrderType.SELL, price=price, quantity=quantity)
        price = round(min(max(theo + self.threshold * 1.5, 0.0), 1.0), 2)
        return FokOrder(counterparty_id=counterparty_id, option_id=option.option_id,
                         order_type=OrderType.BUY, price=price, quantity=quantity)


class MixedCounterparty:
    """A per-interaction mixture of Noise and Informed flow, weighted by `informed_fraction`."""

    def __init__(
        self, rng: np.random.Generator, noise_sd: float = 0.05, informed_fraction: float = 0.3,
        informed_threshold: float = 0.03,
    ) -> None:
        self.rng = rng
        self.noise = NoiseCounterparty(rng, noise_sd=noise_sd)
        self.informed = InformedCounterparty(rng, threshold=informed_threshold)
        self.informed_fraction = informed_fraction

    def _pick(self) -> Counterparty:
        return self.informed if self.rng.uniform() < self.informed_fraction else self.noise

    def respond_to_quote(self, params, values, option, quote):
        return self._pick().respond_to_quote(params, values, option, quote)

    def make_fok_order(self, params, values, option, counterparty_id):
        return self._pick().make_fok_order(params, values, option, counterparty_id)
