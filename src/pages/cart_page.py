"""Shopping cart page POM.

Responsibilities:
* Read the cart subtotal, normalised to :class:`Decimal`.
* Count line items (used as a sanity check before assertions).
"""

from __future__ import annotations

from decimal import Decimal

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.pages.base_page import BasePage
from src.utils import PriceParser


class CartPage(BasePage):
    URL_PATH = "/cart"

    SUBTOTAL_CANDIDATES: tuple[str, ...] = (
        "[data-testid='cart-subtotal']",
        "[data-cart-subtotal]",
        "*:has-text('Subtotal') >> xpath=following::*[contains(text(),'$')][1]",
        "*:text-matches('Subtotal', 'i') ~ *",
        ".cart__subtotal-value",
        ".totals__subtotal-value",
    )
    SUBTOTAL_BLOCK_TEXT_CANDIDATES: tuple[str, ...] = (
        "[class*='subtotal' i]",
        "[class*='Subtotal' i]",
        "[class*='total' i]",
    )
    LINE_ITEM_SELECTOR = (
        "[data-testid='cart-line-item'], "
        "tr.cart-item, "
        "li.cart-item, "
        "div.cart-item, "
        "[class*='CartItem']"
    )

    def __init__(self, page) -> None:  # noqa: ANN001
        super().__init__(page)
        self._parser = PriceParser(self.settings.decimal_separator)

    # ---------------------------------------------------------------- navigation
    def open(self, path: str | None = None) -> "CartPage":  # noqa: D401
        super().open(path or self.URL_PATH)
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        return self

    # ---------------------------------------------------------------- assertions data
    def get_subtotal(self) -> Decimal:
        """Return the cart subtotal as :class:`Decimal`. Raises if not found."""
        # Strategy 1: tagged selectors.
        for selector in self.SUBTOTAL_CANDIDATES:
            try:
                locator = self.page.locator(selector).first
                if locator.count() == 0:
                    continue
                text = locator.inner_text(timeout=2000).strip()
                value = self._parser.try_parse(text)
                if value is not None:
                    self.log.info(f"Cart subtotal (selector={selector}): {value}")
                    return value
            except PlaywrightTimeout:
                continue

        # Strategy 2: scan blocks whose class name mentions subtotal/total.
        for selector in self.SUBTOTAL_BLOCK_TEXT_CANDIDATES:
            try:
                locator = self.page.locator(selector)
                for i in range(min(locator.count(), 8)):
                    block = locator.nth(i)
                    text = block.inner_text(timeout=2000)
                    if "sub" in text.lower():
                        value = self._parser.try_parse(text)
                        if value is not None:
                            self.log.info(f"Cart subtotal (block scan): {value}")
                            return value
            except PlaywrightTimeout:
                continue

        # Strategy 3: regex over the whole cart body as a last resort.
        body = self.page.locator("main, body").first.inner_text()
        for line in body.splitlines():
            if "subtotal" in line.lower():
                value = self._parser.try_parse(line)
                if value is not None:
                    self.log.info(f"Cart subtotal (text scan): {value}")
                    return value

        raise AssertionError("Could not locate cart subtotal on the page.")

    def line_item_count(self) -> int:
        try:
            return self.page.locator(self.LINE_ITEM_SELECTOR).count()
        except PlaywrightTimeout:
            return 0
