"""Search results / Products page POM for automationexercise.com.

The site has only ONE listing page for both browse and search:
``/products``. Submitting the search form updates the same page in place
(``Searched Products`` heading appears) - there is no dedicated
``/search?q=..`` URL.

Constraints we work with
------------------------
* **No UI price filter** - the page exposes none, so :meth:`apply_max_price`
  is a no-op and the search flow filters client-side via the price parsed
  off each :class:`ProductCard`.
* **No real pagination on search results** - the search shows all matches
  on one page. The :class:`Paginator` therefore reports ``has_next() ==
  False`` after the first page, which the search flow handles correctly.
* **XPath-mandated card collection** - the brief explicitly requires XPath
  for collecting the result tiles, so :data:`PRODUCT_CARD_XPATH` is the
  one place in the project where we deliberately use XPath instead of
  CSS / role selectors.
"""

from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.components import Paginator, PriceFilter, ProductCard
from src.pages.base_page import BasePage
from src.utils import PriceParser


class SearchResultsPage(BasePage):
    """Wraps ``/products`` (browse) and ``/products`` after a search submit."""

    URL_PATH = "/products"

    SEARCH_INPUT = "#search_product"
    SEARCH_SUBMIT = "#submit_search"
    SEARCHED_HEADING = "h2.title:has-text('Searched Products')"
    FEATURES_HEADING = "h2.title:has-text('Features Items')"

    # --- XPath: brief-mandated for card collection. -----------------------
    # Matches every ``.col-sm-4`` tile inside ``.features_items`` that has
    # a working product-detail link. Using XPath here (and only here) keeps
    # the brief satisfied without polluting the rest of the project.
    PRODUCT_CARD_XPATH = (
        "//div[contains(@class,'features_items')]"
        "//div[contains(@class,'col-sm-4') and "
        ".//a[contains(@href,'/product_details/')]]"
    )

    PRODUCT_LINK_XPATH = ".//a[contains(@href,'/product_details/')]"
    PRICE_TEXT_XPATH = ".//div[contains(@class,'productinfo')]/h2"
    TITLE_XPATH = ".//div[contains(@class,'productinfo')]/p"

    # automationexercise.com doesn't render an explicit "Sold out" indicator
    # on the listing - every product is purchasable - but we keep the hook
    # so the ProductCard contract stays consistent with other storefronts.
    SOLD_OUT_XPATH = ".//*[contains(translate(., 'SOLDOUT', 'soldout'),'sold out')]"

    def __init__(self, page) -> None:  # noqa: ANN001
        super().__init__(page)
        self.filter = PriceFilter(page)
        self.paginator = Paginator(page)
        self._parser = PriceParser(self.settings.decimal_separator)

    # ------------------------------------------------------------------ navigation
    def open_for_query(self, query: str) -> "SearchResultsPage":
        """Open ``/products`` then submit the search form for ``query``."""
        self.open(self.URL_PATH)
        try:
            self.page.locator(self.SEARCH_INPUT).first.fill(query)
            self.page.locator(self.SEARCH_SUBMIT).first.click()
        except PlaywrightTimeout:
            self.log.warning("Search form not found - falling back to /products")
        try:
            self.page.locator(self.SEARCHED_HEADING).first.wait_for(
                state="visible", timeout=5_000
            )
        except PlaywrightTimeout:
            self.log.info(
                "'Searched Products' heading not visible - the query may have "
                "yielded zero results, which is a valid outcome."
            )
        return self

    # ---------------------------------------------------------------- filtering
    def apply_max_price(self, max_price: float) -> bool:
        """No-op on this site: there is no UI price filter.

        Documented as a no-op (rather than raising) so the search flow's
        decision tree stays linear: it checks the return value, falls
        through to client-side filtering when ``False``.
        """
        self.log.info(
            "automationexercise.com has no UI price filter; applying "
            f"max_price={max_price} client-side via ProductCard."
        )
        return False

    # ---------------------------------------------------------------- collection
    def collect_cards(self) -> list[ProductCard]:
        """Return every product card visible on the current results page."""
        cards: list[ProductCard] = []
        seen_urls: set[str] = set()
        elements = self.page.locator(f"xpath={self.PRODUCT_CARD_XPATH}")

        try:
            count = elements.count()
        except PlaywrightTimeout:
            count = 0
        self.log.info(f"Discovered {count} candidate product elements")

        for i in range(count):
            element = elements.nth(i)
            try:
                href = element.locator(
                    f"xpath={self.PRODUCT_LINK_XPATH}"
                ).first.get_attribute("href", timeout=2000)
            except PlaywrightTimeout:
                continue
            if not href or "/product_details/" not in href:
                continue

            url = self._absolute_url(href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = self._safe_inner_text(element, self.TITLE_XPATH) or url.rsplit("/", 1)[-1]
            price_text = self._safe_inner_text(element, self.PRICE_TEXT_XPATH)
            price = self._parser.try_parse(price_text)

            sold_out = False
            try:
                sold_out = element.locator(f"xpath={self.SOLD_OUT_XPATH}").count() > 0
            except PlaywrightTimeout:
                sold_out = False

            cards.append(
                ProductCard(title=title.strip(), price=price, url=url, is_sold_out=sold_out)
            )

        self.log.info(f"Parsed {len(cards)} unique product cards")
        return cards

    # ---------------------------------------------------------------- helpers
    def _absolute_url(self, href: str) -> str:
        if href.startswith("http"):
            return href.split("?")[0] if "?" in href else href
        base = self.settings.base_url.rstrip("/")
        return f"{base}{href}"

    def _safe_inner_text(self, element, xpath: str) -> str:  # noqa: ANN001
        try:
            locator = element.locator(f"xpath={xpath}").first
            if locator.count() == 0:
                return ""
            return locator.inner_text(timeout=2000)
        except PlaywrightTimeout:
            return ""
        except Exception:  # noqa: BLE001
            return ""
