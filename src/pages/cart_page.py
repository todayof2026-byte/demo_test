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

    # "Proceed To Checkout" button: anchor with classes
    # ``btn btn-default check_out``. ``href`` is empty - it's bound to a
    # JS handler that navigates to ``/checkout`` (only works for
    # authenticated users; unauthenticated visitors get a modal).
    PROCEED_TO_CHECKOUT = "a.check_out"

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

    def delete_all_items(self) -> int:
        """Remove every item from the cart. Returns the number of items deleted."""
        count = self.line_item_count()
        if count == 0:
            return 0
        self.log.info(f"Clearing {count} stale item(s) from cart")
        deleted = 0
        while True:
            remove_btns = self.page.locator("a.cart_quantity_delete")
            try:
                if remove_btns.count() == 0:
                    break
            except PlaywrightTimeout:
                break
            try:
                remove_btns.first.click(timeout=3_000)
                self.page.wait_for_timeout(600)
                deleted += 1
            except PlaywrightTimeout:
                break
        self.log.info(f"Deleted {deleted} item(s) from cart")
        return deleted

    def is_empty(self) -> bool:
        try:
            return (
                self.page.locator(self.EMPTY_CART_MARKER).first.is_visible(timeout=1500)
                or self.line_item_count() == 0
            )
        except PlaywrightTimeout:
            return self.line_item_count() == 0

    # ---------------------------------------------------------------- transitions
    def proceed_to_checkout(self) -> None:
        """Click the "Proceed To Checkout" button and wait for ``/checkout``.

        The button's ``href`` is empty (JS-bound), so we wait for the URL
        change rather than relying on a hard navigation event. Caller is
        expected to construct a :class:`CheckoutPage` afterwards.
        """
        self.log.info("Clicking 'Proceed To Checkout'")
        try:
            self.page.locator(self.PROCEED_TO_CHECKOUT).first.click(timeout=5_000)
        except PlaywrightTimeout:
            self.log.warning(
                "'Proceed To Checkout' button not clickable; "
                "falling back to direct /checkout navigation"
            )
            self.open("/checkout")
            return

        try:
            self.page.wait_for_url("**/checkout", timeout=8_000)
        except PlaywrightTimeout:
            self.log.warning(
                "URL did not switch to /checkout within 8s; "
                "falling back to direct navigation"
            )
            self.open("/checkout")
