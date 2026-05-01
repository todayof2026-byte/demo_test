"""Price filter widget on the search results page.

Different storefronts expose price filters differently: some are pairs of
``Min`` / ``Max`` text inputs, others are sliders, others are pre-bucketed
checkbox groups (e.g. ``$0-$50``). The component supports the text-input
flavour out of the box and falls back gracefully if no inputs are found
(see ``apply()`` returning ``False``). The search flow then applies the
price constraint client-side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


class PriceFilter:
    """Wraps the min/max price inputs."""

    MIN_INPUT_CANDIDATES: tuple[str, ...] = (
        "input[name='filter.v.price.gte']",
        "input[aria-label*='From' i]",
        "input[placeholder='Min']",
        "input[name*='price' i][name*='min' i]",
    )
    MAX_INPUT_CANDIDATES: tuple[str, ...] = (
        "input[name='filter.v.price.lte']",
        "input[aria-label*='To' i]",
        "input[placeholder='Max']",
        "input[name*='price' i][name*='max' i]",
    )
    APPLY_BUTTON_CANDIDATES: tuple[str, ...] = (
        "button:has-text('Apply')",
        "button[type='submit'][aria-label*='price' i]",
    )

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.log = get_logger("PriceFilter")

    def apply(self, min_price: float | None, max_price: float | None) -> bool:
        """Set min/max and submit. Return True if the filter was applied."""
        applied = False
        if min_price is not None:
            applied |= self._fill_first(self.MIN_INPUT_CANDIDATES, str(int(min_price)))
        if max_price is not None:
            applied |= self._fill_first(self.MAX_INPUT_CANDIDATES, str(int(max_price)))

        if not applied:
            self.log.warning("Price filter inputs not found - falling back to client-side filter")
            return False

        self._submit()
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        self.log.info(f"Applied price filter: min={min_price}, max={max_price}")
        return True

    def _fill_first(self, candidates: tuple[str, ...], value: str) -> bool:
        locator = self._first_visible(candidates)
        if locator is None:
            return False
        locator.click()
        locator.fill("")
        locator.fill(value)
        locator.press("Tab")
        return True

    def _submit(self) -> None:
        locator = self._first_visible(self.APPLY_BUTTON_CANDIDATES)
        if locator is not None:
            locator.click()
        else:
            self.page.keyboard.press("Enter")

    def _first_visible(self, candidates: tuple[str, ...]) -> "Locator | None":
        for selector in candidates:
            try:
                locator = self.page.locator(selector).first
                if locator.is_visible(timeout=1000):
                    return locator
            except PlaywrightTimeout:
                continue
        return None
