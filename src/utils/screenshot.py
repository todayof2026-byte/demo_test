"""Screenshot helpers that also attach to Allure.

Centralising this here keeps page objects free of test-reporter specifics
(SRP). If we ever swap Allure for another reporter, only this file changes.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import allure

from src.config import get_settings
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

_log = get_logger("screenshot")


def take_screenshot(page: "Page", name: str) -> Path:
    """Save a full-page screenshot under ``screenshots/`` and return the path."""
    settings = get_settings()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    target = settings.screenshots_dir / f"{timestamp}_{safe_name}.png"
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
