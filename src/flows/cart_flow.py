"""Cart flow.

Public API:
* :func:`add_items_to_cart` - brief section 4.2.
* :func:`assert_cart_total_not_exceeds` - brief section 4.3.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import allure

from src.pages.cart_page import CartPage
from src.pages.product_page import ProductPage
from src.utils.logger import get_logger
from src.utils.screenshot import attach_text

if TYPE_CHECKING:
    from playwright.sync_api import Page

_log = get_logger("cart_flow")


def add_items_to_cart(page: "Page", urls: list[str]) -> int:
    """Open each URL, pick a random in-stock variant if needed, add to cart.

    The brief (section 4.2) requires returning to the search screen between
    adds, so callers can keep the search tab as the "home base". We do that
    via :meth:`Page.go_back` rather than hard-navigating back to
    ``/products?search=...``: ``go_back`` reliably restores the result list
    that produced ``urls`` even if the search query is rebuilt at runtime,
    and it's a cheap operation (no extra network request when the page is
    cached). If go_back fails (e.g. first iteration), we silently move on -
    the next ``open_url`` is destination-correct regardless.

    Returns the number of items that were successfully added. Partial success
    is surfaced as the return value rather than raised, because the brief is
    silent on the all-or-nothing question and the caller has more context
    to decide pass/fail.
    """
    with allure.step(f"Add {len(urls)} item(s) to cart"):
        added = 0
        for index, url in enumerate(urls, start=1):
            with allure.step(f"({index}/{len(urls)}) Add to cart: {url}"):
                pdp = ProductPage(page).open_url(url)
                if pdp.has_size_picker():
                    size = pdp.select_random_in_stock_size()
                    if size is None:
                        _log.warning(f"  - skip (no in-stock sizes): {url}")
                        pdp.screenshot(f"skipped_no_stock_{index}")
                        _return_to_search(page)
                        continue
                ok = pdp.add_to_cart()
                pdp.screenshot(f"add_to_cart_{index}")
                if ok:
                    _log.info(f"  + added: {url}")
                    added += 1
                else:
                    _log.warning(f"  - add-to-cart failed: {url}")
                _return_to_search(page)
        _log.info(f"add_items_to_cart: {added}/{len(urls)} succeeded")
        return added


def _return_to_search(page: "Page") -> None:
    """Navigate back to the search/results screen between cart additions.

    Brief 4.2 step 4: "Return to the search screen / search tab". We use
    ``page.go_back`` because it's the closest analogue to a real shopper
    pressing the browser Back button after adding an item, and it
    sidesteps any need to remember the original search URL.
    """
    try:
        page.go_back(wait_until="domcontentloaded", timeout=4_000)
    except Exception as exc:  # noqa: BLE001 - non-fatal navigation hiccup
        _log.debug(f"go_back skipped: {type(exc).__name__}: {exc}")


# Pytest detects functions whose names start with ``assert_`` for rewriting in
# tests, but this is a flow helper that lives in src/, so we make it explicit.
@allure.step("Assert cart total <= {budget_per_item} * {items_count}")
def assert_cart_total_not_exceeds(
    page: "Page",
    budget_per_item: float,
    items_count: int,
) -> Decimal:
    """Assert ``cart subtotal <= budget_per_item * items_count``.

    Returns the parsed subtotal so callers can attach it to reports.
    """
    cart = CartPage(page).open()
    subtotal = cart.get_subtotal()
    threshold = Decimal(str(budget_per_item)) * Decimal(items_count)

    attach_text(
        "cart_assertion",
        (
            f"subtotal      = {subtotal}\n"
            f"budget/item   = {budget_per_item}\n"
            f"items_count   = {items_count}\n"
            f"threshold     = {threshold}\n"
            f"line_items    = {cart.line_item_count()}"
        ),
    )
    cart.screenshot("cart_total_assertion")
    _log.info(f"Cart subtotal = {subtotal}, threshold = {threshold}")

    assert subtotal <= threshold, (
        f"Cart subtotal {subtotal} exceeds budget threshold "
        f"{budget_per_item} * {items_count} = {threshold}"
    )
    return subtotal
