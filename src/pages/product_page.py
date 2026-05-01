"""Product detail page (PDP) POM.

Responsibilities:
* Read available size variants and their stock state.
* Pick a random in-stock size when required.
* Click "Add to cart" and confirm acceptance.
* Dismiss the post-add side panel / modal so we can return to search.
"""

from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.pages.base_page import BasePage
from src.utils import pick_random_in_stock


class ProductPage(BasePage):
    """Wraps ``/products/<slug>``."""

    SIZE_OPTION_CANDIDATES: tuple[str, ...] = (
        "fieldset[data-product-option*='size' i] input[type='radio']",
        "fieldset:has(legend:text-matches('size', 'i')) input[type='radio']",
        "[data-option-name='Size'] input",
        "input[name*='Size' i]",
    )
    SIZE_OPTION_LABEL = "label[for='{id}']"

    ADD_TO_CART_CANDIDATES: tuple[str, ...] = (
        "button[name='add']",
        "button[aria-label*='Add to cart' i]",
        "button:has-text('Add to cart')",
        "button:has-text('Add to bag')",
        "button:has-text('Add to basket')",
    )

    POST_ADD_DIALOG_CLOSE = (
        "button:has-text('Continue shopping')",
        "button[aria-label='Close']",
        "[role='dialog'] button[aria-label='Close']",
    )

    CART_BADGE = "a[href*='/cart'] [data-cart-count], a[href*='/cart'] .cart-count, a[href*='/cart'] span"

    # ---------------------------------------------------------------- navigation
    def open_url(self, url: str) -> "ProductPage":
        self.open(url)
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        return self

    # ------------------------------------------------------------------ variants
    def has_size_picker(self) -> bool:
        for selector in self.SIZE_OPTION_CANDIDATES:
            try:
                if self.page.locator(selector).count() > 0:
                    return True
            except PlaywrightTimeout:
                continue
        return False

    def select_random_in_stock_size(self) -> str | None:
        """Pick a random size whose radio is enabled. Returns the size value or None."""
        radios = self._size_radios()
        if not radios:
            self.log.info("No size picker on this PDP - assuming single variant.")
            return None

        values: list[str] = []
        in_stock: list[bool] = []
        for radio in radios:
            try:
                value = radio.get_attribute("value") or ""
                disabled = (radio.get_attribute("disabled") is not None) or (
                    (radio.get_attribute("aria-disabled") or "").lower() == "true"
                )
                values.append(value)
                in_stock.append(not disabled)
            except PlaywrightTimeout:
                continue

        chosen = pick_random_in_stock(values, in_stock=in_stock)
        if chosen is None:
            self.log.warning("No in-stock sizes available")
            return None

        for radio in radios:
            try:
                if (radio.get_attribute("value") or "") == chosen:
                    radio_id = radio.get_attribute("id")
                    if radio_id:
                        label = self.page.locator(f"label[for='{radio_id}']").first
                        if label.is_visible(timeout=1500):
                            label.click()
                            self.log.info(f"Selected size: {chosen}")
                            return chosen
                    radio.check(force=True)
                    self.log.info(f"Selected size: {chosen}")
                    return chosen
            except PlaywrightTimeout:
                continue
        return None

    def _size_radios(self) -> list:
        for selector in self.SIZE_OPTION_CANDIDATES:
            try:
                locator = self.page.locator(selector)
                count = locator.count()
                if count > 0:
                    return [locator.nth(i) for i in range(count)]
            except PlaywrightTimeout:
                continue
        return []

    # ---------------------------------------------------------------- add to cart
    def add_to_cart(self) -> bool:
        """Click Add-to-cart. Return True if the click landed on an enabled button."""
        for selector in self.ADD_TO_CART_CANDIDATES:
            try:
                btn = self.page.locator(selector).first
                if not btn.is_visible(timeout=2000):
                    continue
                if btn.is_disabled():
                    self.log.warning(f"Add-to-cart disabled (selector={selector})")
                    return False
                btn.click()
                self.log.info("Clicked Add-to-cart")
                self._dismiss_post_add_dialog()
                return True
            except PlaywrightTimeout:
                continue
        self.log.error("Add-to-cart button not found on this PDP")
        return False

    def _dismiss_post_add_dialog(self) -> None:
        for selector in self.POST_ADD_DIALOG_CLOSE:
            try:
                btn = self.page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    return
            except PlaywrightTimeout:
                continue
