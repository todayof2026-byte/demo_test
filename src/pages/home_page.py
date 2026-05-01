"""Home page POM."""

from __future__ import annotations

from src.components import Header
from src.pages.base_page import BasePage


class HomePage(BasePage):
    URL_PATH = "/"

    def __init__(self, page) -> None:  # noqa: ANN001
        super().__init__(page)
        self.header = Header(page)

    def search(self, query: str) -> None:
        """Type ``query`` into the header search box and submit."""
        self.header.search(query)
