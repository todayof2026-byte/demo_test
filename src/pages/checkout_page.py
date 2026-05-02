"""Checkout summary POM for automationexercise.com.

URL: ``/checkout``. The site reaches this page from ``/view_cart`` via the
"Proceed To Checkout" button (only visible for authenticated users -
unauthenticated visitors get a "Register / Login" modal instead).

Page structure (probed live - see notes below)
----------------------------------------------
* Two ``<h2>`` headings: "Address Details" and "Review Your Order".
* Two address blocks side-by-side: ``#address_delivery`` and
  ``#address_invoice``, populated from the user's profile.
* A "Review Your Order" table that **reuses the same DOM as
  ``/view_cart``**: rows are still ``tbody tr[id^="product-"]`` and
  per-line totals are still ``td.cart_total p.cart_total_price``. There
  is **no** grand-total element on the site - we compute it the same
  way :class:`CartPage` does (sum of per-line totals).
* A "Place Order" button (``a.check_out``). We deliberately stop here:
  clicking Place Order leads to a fake credit-card form that we do NOT
  exercise in automated tests (it's an external checkout simulation).

Why a separate POM (vs. reusing CartPage)
-----------------------------------------
The selectors are identical, but the meaning is different and the user
flow is different (we got here via a button click, addresses are now
visible, payment is the next user action). Keeping a dedicated POM:
1. lets the e2e test express *intent* clearly ("verify the checkout
   summary"), not just "read the same totals from a different URL", and
2. gives us a place to assert checkout-only artefacts (the headings, the
   address blocks, the Place Order button) without polluting CartPage.
"""

from __future__ import annotations

from decimal import Decimal

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.pages.base_page import BasePage
from src.utils import PriceParser


class CheckoutPage(BasePage):
    URL_PATH = "/checkout"

    REVIEW_HEADING = "h2:has-text('Review Your Order')"
    ADDRESS_HEADING = "h2:has-text('Address Details')"
    ADDRESS_DELIVERY = "#address_delivery"
    ADDRESS_INVOICE = "#address_invoice"

    LINE_ITEM_SELECTOR = "tbody tr[id^='product-']"
    LINE_TOTAL_SELECTOR = "td.cart_total p.cart_total_price"

    PLACE_ORDER_BUTTON = "a.check_out"

    def __init__(self, page) -> None:  # noqa: ANN001
        super().__init__(page)
        self._parser = PriceParser(self.settings.decimal_separator)

    # ---------------------------------------------------------------- navigation
    def open(self, path: str | None = None) -> "CheckoutPage":  # noqa: D401
        super().open(path or self.URL_PATH)
        try:
            self.page.locator(self.REVIEW_HEADING).first.wait_for(
                state="visible", timeout=8_000
            )
        except PlaywrightTimeout:
            self.log.warning(
                "'Review Your Order' heading did not appear within 8s on /checkout"
            )
        return self

    # ---------------------------------------------------------------- presence checks
    def has_review_heading(self) -> bool:
        try:
            return self.page.locator(self.REVIEW_HEADING).first.is_visible(timeout=2_000)
        except PlaywrightTimeout:
            return False

    def has_address_heading(self) -> bool:
        try:
            return self.page.locator(self.ADDRESS_HEADING).first.is_visible(timeout=2_000)
        except PlaywrightTimeout:
            return False

    def has_delivery_address(self) -> bool:
        try:
            return self.page.locator(self.ADDRESS_DELIVERY).first.is_visible(timeout=2_000)
        except PlaywrightTimeout:
            return False

    def has_billing_address(self) -> bool:
        try:
            return self.page.locator(self.ADDRESS_INVOICE).first.is_visible(timeout=2_000)
        except PlaywrightTimeout:
            return False

    def has_place_order_button(self) -> bool:
        try:
            return self.page.locator(self.PLACE_ORDER_BUTTON).first.is_visible(timeout=2_000)
        except PlaywrightTimeout:
            return False

    # ---------------------------------------------------------------- summary data
    def line_item_count(self) -> int:
        try:
            return self.page.locator(self.LINE_ITEM_SELECTOR).count()
        except PlaywrightTimeout:
            return 0

    def get_total(self) -> Decimal:
        """Sum every per-line total in the Review-Your-Order table.

        Mirrors :meth:`CartPage.get_subtotal` because automationexercise.com
        renders the same table on both pages and exposes no aggregate
        element. Raises :class:`AssertionError` if the table is empty so
        a misrouted test fails loudly instead of asserting "0 <= X".
        """
        if self.line_item_count() == 0:
            raise AssertionError(
                "Checkout 'Review Your Order' table is empty - we likely "
                "navigated here without items in the cart."
            )

        totals = self.page.locator(self.LINE_TOTAL_SELECTOR)
        try:
            count = totals.count()
        except PlaywrightTimeout:
            count = 0

        running = Decimal("0")
        parsed_lines: list[str] = []
        for i in range(count):
            text = totals.nth(i).inner_text(timeout=2_000).strip()
            value = self._parser.try_parse(text)
            if value is None:
                self.log.warning(f"Could not parse checkout line total: {text!r}")
                continue
            running += value
            parsed_lines.append(f"  line {i + 1}: {text!r} -> {value}")

        self.log.info(
            f"Checkout total computed from {count} line(s): {running}\n"
            + "\n".join(parsed_lines)
        )
        return running
