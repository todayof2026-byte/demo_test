"""Screenshot helpers that also attach to Allure.

Centralising this here keeps page objects free of test-reporter specifics
(SRP). If we ever swap Allure for another reporter, only this file changes.

Per-test directory + sequence numbering
---------------------------------------
At the start of each test, ``tests/conftest.py`` calls
:func:`set_test_evidence_dir` with the test's evidence folder. From then
on, every ``screenshot()`` call from a page object lands at
``<dir>/screenshots/NN_<name>.png`` where ``NN`` is a per-test sequence
counter that auto-increments. This makes it trivial to read the test's
PNG folder top-to-bottom in execution order.

If no per-test directory is set (e.g. running a unit test outside a
Playwright fixture), screenshots fall back to ``reports/evidence/_loose/``
so we never crash - just degrade gracefully.
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

import allure

from src.config import get_settings
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

_log = get_logger("screenshot")

# A function-scoped pytest fixture sets these before each test. Using
# ContextVars keeps the state thread-safe (pytest-xdist), even though we
# don't currently parallelise.
_test_dir_var: ContextVar[Path | None] = ContextVar("_test_dir_var", default=None)
_test_seq_var: ContextVar[int] = ContextVar("_test_seq_var", default=0)


def set_test_evidence_dir(path: Path) -> None:
    """Bind the per-test evidence directory; resets the sequence counter."""
    _test_dir_var.set(path)
    _test_seq_var.set(0)


def reset_test_evidence_dir() -> None:
    """Detach the per-test directory (call in fixture teardown)."""
    _test_dir_var.set(None)
    _test_seq_var.set(0)


def _next_seq() -> int:
    n = _test_seq_var.get() + 1
    _test_seq_var.set(n)
    return n


def _screenshots_dir() -> Path:
    """Resolve the directory PNGs should land in for the current test."""
    test_dir = _test_dir_var.get()
    if test_dir is not None:
        target = test_dir / "screenshots"
    else:
        # Fallback for callers outside a per-test fixture (unit tests, scripts).
        target = get_settings().reports_dir / "evidence" / "_loose" / "screenshots"
    target.mkdir(parents=True, exist_ok=True)
    return target


def take_screenshot(page: "Page", name: str) -> Path:
    """Save a full-page screenshot under the per-test folder and return the path."""
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    seq = f"{_next_seq():02d}"
    target = _screenshots_dir() / f"{seq}_{safe_name}.png"
    page.screenshot(path=str(target), full_page=True)
    _log.info(f"Saved screenshot: {target}")
    return target


def attach_screenshot(page: "Page", name: str) -> Path:
    """Take a screenshot and attach it to the current Allure step."""
    path = take_screenshot(page, name)
    try:
        allure.attach.file(
            str(path),
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception as exc:  # noqa: BLE001 - never let reporting kill a test
        _log.warning(f"Failed to attach screenshot to Allure: {exc}")
    return path


def attach_text(name: str, body: str) -> None:
    """Attach an arbitrary string (URL list, parsed price, etc.) to Allure."""
    try:
        allure.attach(body, name=name, attachment_type=allure.attachment_type.TEXT)
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"Failed to attach text to Allure: {exc}")
