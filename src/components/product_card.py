"""Product card model.

A ProductCard wraps a single result tile on the search results page.
It exposes the data tests care about (title, price, URL, in-stock state)
and hides the DOM. The card is **immutable** by design - parse once,
read many times - so tests can rely on stable values.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProductCard:
    """Snapshot of a single search result tile."""

    title: str
    price: Decimal | None
    url: str
    is_sold_out: bool

    @property
    def is_purchasable(self) -> bool:
        """True if the card has a price and is not marked sold out."""
        return self.price is not None and not self.is_sold_out

    def matches_max_price(self, max_price: Decimal | float | int) -> bool:
        if self.price is None:
            return False
        return self.price <= Decimal(str(max_price))
