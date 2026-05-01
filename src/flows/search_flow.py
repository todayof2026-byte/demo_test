"""Search flow.

Public API: :func:`search_items_by_name_under_price` (brief section 4.1).

Behaviour:
1. Open ``/search?q=<query>``.
2. Apply max-price filter via the UI (best-effort).
3. Collect cards via XPath; keep only purchasable cards whose price <= max.
4. If still under ``limit`` and a Next page exists, recurse into it until
   we hit ``limit`` or run out of pages.
5. Return up to ``limit`` URLs (zero is a valid result).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import allure

from src.pages.search_results_page import SearchResultsPage
from src.utils.logger import get_logger
from src.utils.screenshot import attach_text

if TYPE_CHECKING:
    from playwright.sync_api import Page

_log = get_logger("search_flow")

# Hard cap on how many pages we will traverse before giving up. Prevents
# accidentally crawling 50 pages on a vague query.
_MAX_PAGES = 5


@allure.step("Search '{query}' under price {max_price} (limit={limit})")
def search_items_by_name_under_price(
    page: "Page",
    query: str,
    max_price: float,
    limit: int = 5,
) -> list[str]:
    """Return up to ``limit`` URLs of in-stock items priced <= ``max_price``."""
    if limit <= 0:
        return []

    threshold = Decimal(str(max_price))
    results = SearchResultsPage(page).open_for_query(query)
    results.apply_max_price(max_price)

    collected: list[str] = []
    pages_visited = 0

    while True:
        pages_visited += 1
        cards = results.collect_cards()
        for card in cards:
            if len(collected) >= limit:
                break
            if not card.is_purchasable:
                continue
            if not card.matches_max_price(threshold):
                continue
            if card.url in collected:
                continue
            _log.info(f"  + {card.title} @ {card.price} -> {card.url}")
            collected.append(card.url)

        if len(collected) >= limit:
            break

        if pages_visited >= _MAX_PAGES:
            _log.info(f"Reached page-traversal cap ({_MAX_PAGES}); stopping.")
            break

        if not results.paginator.has_next():
            _log.info("No more pages; stopping with what we have.")
            break

        if not results.paginator.go_next():
            _log.info("Failed to navigate to next page; stopping.")
            break

    final = collected[:limit]
    _log.info(f"Returning {len(final)} URLs (limit={limit}, pages={pages_visited})")
    attach_text("collected_urls", "\n".join(final) or "(no results)")
    results.screenshot(f"search_{query.replace(' ', '_')}_under_{int(max_price)}")
    return final
