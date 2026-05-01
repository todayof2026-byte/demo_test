"""Authentication flow.

Public API: :func:`login`. The function accepts a Playwright ``Page`` and
returns whether the user is authenticated. Tests typically receive an
already-authenticated ``page`` from the ``session_login`` fixture in
``tests/conftest.py``, which calls this flow once per session and reuses
``storage_state.json``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import allure

from src.config import get_settings
from src.pages.login_page import LoginPage
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

_log = get_logger("auth_flow")


@allure.step("Login as {email}")
def login(page: "Page", email: str | None = None, password: str | None = None) -> bool:
    """Log into the storefront. Falls back to env-supplied credentials if not provided.

    Returns ``True`` on success, ``False`` if credentials are missing or the
    site rejected the login. Tests may treat ``False`` as "fall back to guest".
    """
    settings = get_settings()
    email = email or settings.site_email
    password = password or settings.site_password.get_secret_value()

    if not email or not password:
        _log.warning("No credentials provided - continuing as guest.")
        return False

    page_obj = LoginPage(page).open()
    success = page_obj.login(email, password)
    if success:
        _log.info("Login succeeded; session is authenticated.")
        page_obj.screenshot("login_success")
    else:
        _log.warning("Login did not succeed - continuing as guest.")
        page_obj.screenshot("login_failed")
    return success
