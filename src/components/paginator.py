"""Pagination widget for the search results page."""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


class Paginator:
    """Detects whether more pages exist and navigates to the next one."""

    NEXT_LINK_CANDIDATES: tuple[str, ...] = (
        "a[rel='next']",
        "a[aria-label='Next page']",
        "a[aria-label='Next']",
        "a:has-text('Next')",
        "button:has-text('Next')",
    )

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.log = get_logger("Paginator")

    def has_next(self) -> bool:
        locator = self._next_locator()
        if locator is None:
            return False
        try:
            if not locator.is_visible(timeout=1500):
                return False
            disabled = locator.get_attribute("aria-disabled")
            if disabled and disabled.lower() == "true":
                return False
            return True
        except PlaywrightTimeout:
            return False

    def go_next(self) -> bool:
        """Click the next-page control and wait for navigation. Return True on success."""
        locator = self._next_locator()
        if locator is None:
            return False
        try:
            locator.scroll_into_view_if_needed()
            locator.click()
        except Exception as exc:  # noqa: BLE001
            self.log.warning(f"Failed to click next page: {exc}")
            return False
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        self.log.info(f"Advanced to next results page: {self.page.url}")
        return True

    def _next_locator(self) -> "Locator | None":
        for selector in self.NEXT_LINK_CANDIDATES:
            locator = self.page.locator(selector).first
            try:
                if locator.count() > 0:
                    return locator
            except PlaywrightTimeout:
                continue
        return None
