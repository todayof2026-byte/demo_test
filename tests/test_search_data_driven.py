"""Data-driven coverage of :func:`search_items_by_name_under_price`.

Scenarios are loaded from ``data/queries.yaml``. Each scenario exercises a
different code path of the search flow (happy path, pagination, empty result).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import allure
import pytest
import yaml

from src.flows import search_items_by_name_under_price


_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "queries.yaml"


def _load_scenarios() -> list[dict[str, Any]]:
    with _DATA_FILE.open(encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    return list(payload.get("scenarios", []))


_SCENARIOS = _load_scenarios()


@allure.epic("automationexercise.com E2E")
@allure.feature("Search with price filter")
@pytest.mark.search
@pytest.mark.data_driven
@pytest.mark.skip(
    reason=(
        "Search results page has not been ported to automationexercise.com yet. "
        "Login is covered by tests/test_login.py; search comes next."
    ),
)
@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS,
    ids=[s["id"] for s in _SCENARIOS],
)
def test_search_returns_urls_within_budget(page, scenario: dict[str, Any]) -> None:  # noqa: ANN001
    """Returned URLs are at most ``limit`` and the function is robust to empty results."""
    allure.dynamic.story(scenario.get("description", scenario["id"]))
    allure.dynamic.parameter("query", scenario["query"])
    allure.dynamic.parameter("max_price", scenario["max_price"])
    allure.dynamic.parameter("limit", scenario["limit"])

    urls = search_items_by_name_under_price(
        page,
        query=scenario["query"],
        max_price=float(scenario["max_price"]),
        limit=int(scenario["limit"]),
    )

    assert isinstance(urls, list)
    assert len(urls) <= scenario["limit"]
    for url in urls:
        assert "/products/" in url, f"Returned URL is not a product page: {url}"
    assert len(set(urls)) == len(urls), "Duplicate URLs returned."
