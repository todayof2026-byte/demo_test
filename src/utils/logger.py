"""Centralised loguru configuration.

Importing :func:`get_logger` anywhere in the project returns a logger whose
output is correctly formatted, level-controlled by the ``LOG_LEVEL`` env
variable, and free from duplicate handlers.

Per-test file sinks
-------------------
:func:`add_file_sink` / :func:`remove_sink` let the pytest fixtures hook a
fresh ``log.txt`` for the duration of a single test, then cleanly detach
it. The same loguru records still flow to the original stderr sink, so the
console output during a run is unchanged.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger as _logger


_CONFIGURED = False


_FILE_SINK_FORMAT = (
    "{time:HH:mm:ss.SSS} "
    "| {level: <8} "
    "| {extra[component]} "
    "| {name}:{function}:{line} "
    "- {message}"
)


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    _logger.remove()
    _logger.configure(extra={"component": "-"})
    _logger.add(
        sys.stderr,
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> "
            "| <level>{level: <8}</level> "
            "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        ),
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None):
    """Return a bound loguru logger; ``name`` is added as an extra field."""
    _configure_once()
    return _logger.bind(component=name or "-") if name else _logger


def add_file_sink(path: Path, level: str = "INFO") -> int:
    """Attach a per-file loguru sink and return its handler id.

    Pair with :func:`remove_sink` in a ``try/finally`` so the sink is always
    detached - leaked sinks accumulate handlers across tests and can pin
    file handles open on Windows.
    """
    _configure_once()
    path.parent.mkdir(parents=True, exist_ok=True)
    return _logger.add(
        str(path),
        level=level.upper(),
        format=_FILE_SINK_FORMAT,
        encoding="utf-8",
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )


def remove_sink(handler_id: int) -> None:
    """Detach a sink previously registered via :func:`add_file_sink`. Never raises."""
    try:
        _logger.remove(handler_id)
    except (ValueError, KeyError):
        pass
