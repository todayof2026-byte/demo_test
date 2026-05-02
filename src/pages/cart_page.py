"""Shopping cart POM for automationexercise.com.

URL: ``/view_cart``. Each cart row is rendered as ``<tr id='product-<n>'>``
with a per-line total in ``td.cart_total p.cart_total_price`` (e.g.
``Rs. 500``). The site does NOT expose an explicit "subtotal" element -
instead it's the sum of the per-line totals - so :meth:`get_subtotal`
sums the parsed per-line prices and returns the result.
"""

from __future__ import annotations

from decimal import Decimal

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.pages.base_page import BasePage
from src.utils import PriceParser


class CartPage(BasePage):
    URL_PATH = "/view_cart"

    LINE_ITEM_SELECTOR = "tbody tr[id^='product-']"
    LINE_TOTAL_SELECTOR = "td.cart_total p.cart_total_price"
    LINE_PRICE_SELECTOR = "td.cart_price p"
    LINE_QUANTITY_SELECTOR = "td.cart_quantity button.disabled"

    # Empty-cart marker: the site renders this paragraph + a "Click here to buy
    # more products" anchor when the cart has zero rows.
    EMPTY_CART_MARKER = "#empty_cart"

    def __init__(self, page) -> None:  # noqa: ANN001
        super().__init__(page)
        self._parser = PriceParser(self.settings.decimal_separator)

    # ---------------------------------------------------------------- navigation
    def open(self, path: str | None = None) -> "CartPage":  # noqa: D401
        super().open(path or self.URL_PATH)
        try:
            self.page.locator(
                f"{self.LINE_ITEM_SELECTOR}, {self.EMPTY_CART_MARKER}"
            ).first.wait_for(state="visible", timeout=6_000)
        except PlaywrightTimeout:
            self.log.warning("Neither cart rows nor empty-cart marker appeared")
        return self

    # ---------------------------------------------------------------- assertions data
    def get_subtotal(self) -> Decimal:
        """Return the cart subtotal (sum of per-line totals).

        Raises :class:`AssertionError` if the cart is empty (so a misconfigured
        test fails loudly rather than asserting "0 <= threshold").
        """
        if self.is_empty():
            raise AssertionError(
                "Cart is empty - cannot compute subtotal. The add-to-cart "
                "step likely failed to add any items."
            )

        totals = self.page.locator(self.LINE_TOTAL_SELECTOR)
        try:
            count = totals.count()
        except PlaywrightTimeout:
            count = 0

        running = Decimal("0")
        parsed_lines: list[str] = []
        for i in range(count):
            text = totals.nth(i).inner_text(timeout=2000).strip()
            value = self._parser.try_parse(text)
            if value is None:
                self.log.warning(f"Could not parse cart line total: {text!r}")
                continue
            running += value
            parsed_lines.append(f"  line {i + 1}: {text!r} -> {value}")

        self.log.info(
            f"Cart subtotal computed from {count} line(s): {running}\n"
            + "\n".join(parsed_lines)
        )
        return running

    def line_item_count(self) -> int:
        try:
            return self.page.locator(self.LINE_ITEM_SELECTOR).count()
        except PlaywrightTimeout:
            return 0

    def is_empty(self) -> bool:
        try:
            return (
                self.page.locator(self.EMPTY_CART_MARKER).first.is_visible(timeout=1500)
                or self.line_item_count() == 0
            )
        except PlaywrightTimeout:
            return self.line_item_count() == 0
