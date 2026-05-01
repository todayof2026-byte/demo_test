"""Random variant selection helpers.

When a product has variants (size, color), the test must pick one. Picking
deterministically (e.g. always the first) hides bugs that only manifest on
specific variants. Picking truly randomly hurts reproducibility.

Compromise: optionally seedable random pick that prefers in-stock options.
"""

from __future__ import annotations

import os
import random
from typing import Sequence, TypeVar

T = TypeVar("T")


def _rng() -> random.Random:
    """Return a Random instance seeded by ``RANDOM_SEED`` env var if present."""
    seed = os.environ.get("RANDOM_SEED")
    if seed is None:
        return random.Random()
    try:
        return random.Random(int(seed))
    except ValueError:
        return random.Random(seed)


def pick_random_in_stock(
    options: Sequence[T],
    *,
    in_stock: Sequence[bool] | None = None,
) -> T | None:
    """Return a random element from ``options``, biased towards in-stock items.

    Args:
        options: candidate values (typically size labels or option ids).
        in_stock: parallel boolean sequence; ``True`` = available. If omitted,
            every option is treated as available.

    Returns:
        A randomly chosen value, or ``None`` if there are no available options.
    """
    if not options:
        return None

    if in_stock is None:
        return _rng().choice(list(options))

    if len(in_stock) != len(options):
        raise ValueError(
            f"options ({len(options)}) and in_stock ({len(in_stock)}) lengths must match"
        )

    available = [opt for opt, ok in zip(options, in_stock) if ok]
    if not available:
        return None
    return _rng().choice(available)
