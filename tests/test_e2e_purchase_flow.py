"""End-to-end purchase flow on automationexercise.com.

This is the headline scenario from the brief: login -> search -> add to cart
-> assert total. It chains the four required functions exactly as the
brief's example shows.

Login is delivered as a fixture precondition (``logged_in_page``) rather
than inlined in the test body so the test reads as the business flow,
not the plumbing. The fixture's Allure step is "Precondition: log in
with real credentials"; the test's own steps start from step 1 below.

automationexercise.com specifics that shape the test
----------------------------------------------------
* The catalogue uses INR ("Rs.") prices - typical t-shirts are ~Rs. 500
  so a budget of Rs. 1500/item gives plenty of matches without being
  trivially permissive.
* No UI price filter and no real pagination on search results, so the
  search flow filters client-side and stops after page 1; both behaviours
  are documented in :mod:`src.flows.search_flow` and
  :mod:`src.pages.search_results_page`.
"""

from __future__ import annotations

import allure
import pytest

from src.flows import (
    add_items_to_cart,
    assert_cart_total_not_exceeds,
    search_items_by_name_under_price,
)


@allure.epic("automationexercise.com E2E")
@allure.feature("Purchase flow")
@allure.story("Logged-in user: search, add to cart, assert subtotal")
@pytest.mark.e2e
def test_full_purchase_flow_under_budget(logged_in_page) -> None:  # noqa: ANN001
    """Search -> add to cart -> assert subtotal, all in one logged-in session."""
    page = logged_in_page
    query = "tshirt"
    budget_per_item = 1500.0
    limit = 5

    with allure.step(f"1. Find up to {limit} '{query}' priced <= Rs.{budget_per_item}"):
        urls = search_items_by_name_under_price(page, query, budget_per_item, limit)
        assert isinstance(urls, list), "search_items_by_name_under_price must return a list"

    if not urls:
        pytest.skip(
            "No items matched the price condition - the catalogue may have "
            "shifted. Cannot exercise add-to-cart with zero matches."
        )

    with allure.step(f"2. Add {len(urls)} items to the cart"):
        added = add_items_to_cart(page, urls)
        assert added > 0, "Expected at least one item to be added to the cart."

    with allure.step("3. Assert cart subtotal does not exceed budget * count"):
        assert_cart_total_not_exceeds(page, budget_per_item, added)
