"""Site header (search bar + mini cart + account)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page


class Header:
    """Header widget shared across every page."""

    SEARCH_INPUT = "input[type='search'], input[name='q'], input[placeholder*='Search' i]"
    SEARCH_SUBMIT = "form[action*='/search'] button[type='submit']"
    CART_ICON = "a[href*='/cart'], a[aria-label*='cart' i]"
    ACCOUNT_LINK = "a[href*='/account'], a[aria-label*='account' i]"

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.log = get_logger("Header")

    def search(self, query: str) -> None:
        """Type ``query`` into the header search box and submit."""
        self.log.info(f"Header search: {query!r}")
        box = self.page.locator(self.SEARCH_INPUT).first
        box.click()
        box.fill(query)
        box.press("Enter")

    def open_cart(self) -> None:
        self.page.locator(self.CART_ICON).first.click()

    def open_account(self) -> None:
        self.page.locator(self.ACCOUNT_LINK).first.click()
