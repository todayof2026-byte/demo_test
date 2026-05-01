"""Locale-aware price parsing.

Real-world e-commerce prices come in many shapes:

    "$140.00"        -> Decimal("140.00")     # US storefront
    "\u00a324.99"    -> Decimal("24.99")      # UK
    "24,99 \u20ac"   -> Decimal("24.99")      # France: comma as decimal
    "1\u00a0299,00 \u20ac" -> Decimal("1299.00")  # France with NBSP thousands
    "\u20aa89.90"    -> Decimal("89.90")      # Israel
    "Sale price $179.00 Regular price" -> Decimal("179.00")  # noisy DOM text

The parser must be deterministic, must always return :class:`decimal.Decimal`
(never float - we are doing money math), and must raise a clear error when
a value is unparseable instead of silently returning zero.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Final

# Currency symbols we know about. Strip them from the input before parsing.
_CURRENCY_SYMBOLS: Final[str] = "$\u00a3\u20ac\u20aa\u00a5\u20a9"

# Anything that is neither a digit, decimal separator, thousands separator,
# nor minus sign should be treated as noise.
_PRICE_SCAN: Final[re.Pattern[str]] = re.compile(
    r"-?\d{1,3}(?:[.,\u00a0\s]\d{3})*(?:[.,]\d+)?"
)


class PriceParser:
    """Parse human-formatted prices into :class:`Decimal`.

    The parser is configured with the **decimal separator** of the locale.
    Pass ``"."`` for en-US/en-GB, ``","`` for fr-FR/de-DE.
    """

    def __init__(self, decimal_separator: str = ".") -> None:
        if decimal_separator not in {".", ","}:
            raise ValueError(f"decimal_separator must be '.' or ',', got {decimal_separator!r}")
        self._decimal_separator = decimal_separator

    @property
    def decimal_separator(self) -> str:
        return self._decimal_separator

    def parse(self, raw: str) -> Decimal:
        """Convert a noisy price string into a :class:`Decimal`.

        Raises:
            ValueError: if no numeric value can be extracted.
        """
        if raw is None:
            raise ValueError("Cannot parse None as a price")
        text = str(raw).strip()
        if not text:
            raise ValueError("Cannot parse empty string as a price")

        for symbol in _CURRENCY_SYMBOLS:
            text = text.replace(symbol, "")

        match = _PRICE_SCAN.search(text)
        if not match:
            raise ValueError(f"No numeric value found in {raw!r}")

        token = match.group(0)
        normalized = self._normalize(token)
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError(f"Could not parse {raw!r} as a price") from exc

    def try_parse(self, raw: str | None) -> Decimal | None:
        """Like :meth:`parse` but returns ``None`` on failure instead of raising."""
        if raw is None:
            return None
        try:
            return self.parse(raw)
        except ValueError:
            return None

    def _normalize(self, token: str) -> str:
        """Convert ``token`` to a canonical ``str`` Decimal accepts."""
        if self._decimal_separator == ",":
            token = token.replace(".", "").replace("\u00a0", "").replace(" ", "")
            token = token.replace(",", ".")
        else:
            token = token.replace(",", "").replace("\u00a0", "").replace(" ", "")
        return token
