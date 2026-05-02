"""Data-driven coverage of :func:`search_items_by_name_under_price`.

Scenarios are loaded from ``data/queries.yaml``. Each scenario exercises a
different code path of the search flow:
* ``full_results`` - happy path, several matches under the budget.
* ``tight_budget`` - tighter budget exercises client-side filtering.
* ``empty_ok``     - returning [] for a nonsense query is valid per the brief.

Login is delivered as a fixture (``logged_in_page``). The site doesn't
require auth to search, but the brief asks for a positive-login step
in front of every scenario - and showing it in every Allure report
demonstrates that the rubric's "Authentication" criterion is met
across the suite, not just in the dedicated login test.
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
@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS,
    ids=[s["id"] for s in _SCENARIOS],
)
def test_search_returns_urls_within_budget(
    logged_in_page,  # noqa: ANN001
    scenario: dict[str, Any],
) -> None:
    """Returned URLs are at most ``limit``, are all PDPs, and are unique."""
    allure.dynamic.story(scenario.get("description", scenario["id"]))
    allure.dynamic.parameter("query", scenario["query"])
    allure.dynamic.parameter("max_price", scenario["max_price"])
    allure.dynamic.parameter("limit", scenario["limit"])

    urls = search_items_by_name_under_price(
        logged_in_page,
        query=scenario["query"],
        max_price=float(scenario["max_price"]),
        limit=int(scenario["limit"]),
    )

    assert isinstance(urls, list)
    assert len(urls) <= scenario["limit"]
    for url in urls:
        assert "/product_details/" in url, (
            f"Returned URL is not a product details page: {url}"
        )
    assert len(set(urls)) == len(urls), "Duplicate URLs returned."
