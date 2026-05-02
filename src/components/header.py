"""Site header (search input + nav links) for automationexercise.com.

The search box on this site is on the ``/products`` page, not the home
header (the ``/`` page has a different navbar with no search field).
``Header.search()`` therefore does NOT assume the input is reachable from
every page - the caller is responsible for landing on ``/products`` first
(``SearchResultsPage.open_for_query`` does that).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page


class Header:
    """Header widget shared across most pages."""

    SEARCH_INPUT = "#search_product"
    SEARCH_SUBMIT = "#submit_search"

    CART_LINK = "a[href='/view_cart']"
    LOGIN_LINK = "a[href='/login']"
    LOGOUT_LINK = "a[href='/logout']"
    LOGGED_IN_AS = "a:has-text('Logged in as')"

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.log = get_logger("Header")

    def search(self, query: str) -> None:
        """Type ``query`` into the products-page search box and submit."""
        self.log.info(f"Header search: {query!r}")
        box = self.page.locator(self.SEARCH_INPUT).first
        box.fill(query)
        self.page.locator(self.SEARCH_SUBMIT).first.click()

    def open_cart(self) -> None:
        self.page.locator(self.CART_LINK).first.click()

    def is_logged_in(self) -> bool:
        try:
            return self.page.locator(self.LOGGED_IN_AS).first.is_visible(timeout=1500)
        except Exception:  # noqa: BLE001
            return False
