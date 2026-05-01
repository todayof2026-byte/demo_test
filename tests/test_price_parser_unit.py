"""Unit tests for :class:`PriceParser`.

These tests run without a browser - they're fast, deterministic, and catch
parsing regressions early. The XPath-driven cart total reading depends on
this module being correct.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.utils import PriceParser


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$140.00", Decimal("140.00")),
        ("$1,299.00", Decimal("1299.00")),
        ("Sale price $179.00 Regular price", Decimal("179.00")),
        ("\u00a324.99", Decimal("24.99")),
        ("\u20aa89.90", Decimal("89.90")),
        ("$0.99", Decimal("0.99")),
        ("$140", Decimal("140")),
    ],
)
def test_parse_us_format(raw: str, expected: Decimal) -> None:
    assert PriceParser(".").parse(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("24,99 \u20ac", Decimal("24.99")),
        ("1.299,00 \u20ac", Decimal("1299.00")),
        ("1\u00a0299,00 \u20ac", Decimal("1299.00")),
    ],
)
def test_parse_eu_format(raw: str, expected: Decimal) -> None:
    assert PriceParser(",").parse(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "no number here", "$"])
def test_parse_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        PriceParser(".").parse(raw)


def test_try_parse_returns_none_on_failure() -> None:
    assert PriceParser(".").try_parse("nope") is None


def test_try_parse_returns_decimal_on_success() -> None:
    assert PriceParser(".").try_parse("$1.50") == Decimal("1.50")


def test_invalid_separator_raises() -> None:
    with pytest.raises(ValueError):
        PriceParser(";")
