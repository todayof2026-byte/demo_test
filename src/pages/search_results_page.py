"""Search results page POM.

Responsibilities:
* Apply the price filter (delegated to :class:`PriceFilter`).
* Detect pagination (delegated to :class:`Paginator`).
* Iterate visible product cards and turn them into :class:`ProductCard`
  data objects via XPath. The brief mandates XPath here, so the collection
  XPath is the only XPath in the project.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.components import Paginator, PriceFilter, ProductCard
from src.pages.base_page import BasePage
from src.utils import PriceParser


class SearchResultsPage(BasePage):
    """Wraps ``/search?q=...``."""

    # Brief mandate: collect items via XPath. We keep the XPath broad enough
    # to match Shopify's two common card structures (anchor-wrapped & section).
    PRODUCT_CARD_XPATH = (
        "//*[self::li or self::article or self::div]"
        "[.//a[contains(@href,'/products/')]]"
        "[.//*[contains(translate(text(),'$\u00a3\u20ac\u20aa','$$$$'),'$') or "
        " contains(translate(text(),'$\u00a3\u20ac\u20aa','$$$$'),'\u00a3') or "
        " contains(@class,'price') or @data-price]]"
    )

    PRODUCT_LINK_XPATH = ".//a[contains(@href,'/products/')]"
    PRICE_TEXT_XPATH = ".//*[contains(@class,'price') or contains(@class,'Price')]"
    SOLD_OUT_XPATH = ".//*[contains(translate(., 'SOLDOUT', 'soldout'),'sold out')]"
    TITLE_XPATH = ".//h2 | .//h3 | .//*[contains(@class,'title') or contains(@class,'Title')]"

    def __init__(self, page) -> None:  # noqa: ANN001
        super().__init__(page)
        self.filter = PriceFilter(page)
        self.paginator = Paginator(page)
        self._parser = PriceParser(self.settings.decimal_separator)

    # ------------------------------------------------------------------ navigation
    def open_for_query(self, query: str) -> "SearchResultsPage":
        """Navigate directly to the search URL for ``query``."""
        self.open(f"/search?q={quote_plus(query)}")
        try:
            self.page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass
        return self

    # ---------------------------------------------------------------- filtering
    def apply_max_price(self, max_price: float) -> bool:
        return self.filter.apply(min_price=0, max_price=max_price)

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
                href = element.locator(f"xpath={self.PRODUCT_LINK_XPATH}").first.get_attribute(
                    "href", timeout=2000
                )
            except PlaywrightTimeout:
                continue
            if not href or "/products/" not in href:
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
            return href.split("?")[0] if "?" not in href else href
        return f"{self.settings.base_url}{href}"

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
