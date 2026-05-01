"""Shared pytest fixtures.

Key responsibilities:

* Wire the global :class:`Settings` into Playwright's browser/context options.
* Provide a session-scoped login: log in once, save ``storage_state.json``,
  reuse it for every test in the run. Tests that prefer guest mode can use
  the ``guest_page`` fixture instead.
* Hook test failures so screenshots and Playwright traces land in Allure.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import allure
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

# Allow ``import src...`` from anywhere in the test process.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import get_settings  # noqa: E402
from src.flows.auth_flow import login as login_flow  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from src.utils.screenshot import attach_screenshot  # noqa: E402

_log = get_logger("conftest")

# Set FORCE_FRESH_LOGIN=false in the env to opt back into storage_state reuse.
# By default we always log in fresh: the reviewer sees the real login step in
# the Allure report, and there's no risk of a stale/expired session silently
# wrecking the rest of the suite. The TTL below is only consulted when the
# opt-in flag is set.
_FORCE_FRESH_LOGIN = os.environ.get("FORCE_FRESH_LOGIN", "true").lower() != "false"
_STORAGE_TTL_SECONDS = 12 * 3600


# ---------------------------------------------------------------------------- settings
@pytest.fixture(scope="session")
def settings():  # noqa: ANN201 - return type is the cached Settings singleton
    return get_settings()


# ---------------------------------------------------------------------- pytest-playwright
@pytest.fixture(scope="session")
def browser_type_launch_args(settings) -> dict[str, Any]:  # noqa: ANN001
    """Browser launch args.

    When running headed we maximize the window: large viewports avoid the
    responsive/mobile breakpoints that hide some site UI (e.g. price-filter
    sidebars) and make selectors more deterministic.
    """
    args: dict[str, Any] = {
        "headless": not settings.headed,
        "slow_mo": settings.slow_mo,
    }
    if settings.headed:
        args["args"] = ["--start-maximized"]
    return args


@pytest.fixture(scope="session")
def browser_context_args(settings) -> dict[str, Any]:  # noqa: ANN001
    """Context args.

    In headed mode we set ``no_viewport=True`` so the Page tracks the OS window
    size (which we maximize via launch args). In headless mode we use a fixed
    1920x1080 viewport - large enough to render the desktop layout without
    relying on a real window, and reproducible across CI machines.
    """
    args: dict[str, Any] = {
        "locale": "en-US",
        "ignore_https_errors": True,
    }
    if settings.headed:
        args["no_viewport"] = True
    else:
        args["viewport"] = {"width": 1920, "height": 1080}
    return args


# --------------------------------------------------------------------------- login state
def _storage_is_fresh(path: Path) -> bool:
    """Return True iff the cached storage_state should be reused.

    Defaults to False so login runs fresh on every session - the reviewer sees
    the real login step in the Allure report. Set FORCE_FRESH_LOGIN=false in
    the env to enable the time-based reuse cache below.
    """
    if _FORCE_FRESH_LOGIN:
        return False
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < _STORAGE_TTL_SECONDS


@pytest.fixture(scope="session", autouse=True)
def _wipe_stale_storage_state(settings) -> None:  # noqa: ANN001
    """Best-effort cleanup of a stale storage_state.json before the session starts.

    Only fires when fresh login is forced. We delete the file so that the
    ``context`` fixture below cannot accidentally pick up old session cookies
    while we're trying to demonstrate a live login flow.
    """
    if not _FORCE_FRESH_LOGIN:
        return
    target: Path = settings.storage_state_path
    if target.exists():
        try:
            target.unlink()
            _log.info(f"Removed stale storage_state at {target} (FORCE_FRESH_LOGIN=true)")
        except OSError as exc:
            _log.warning(f"Could not remove {target}: {exc}")


@pytest.fixture(scope="session")
def storage_state_path(settings) -> Path:  # noqa: ANN001
    """Login once per session (if creds are available) and return the storage state file.

    If ``SITE_EMAIL`` / ``SITE_PASSWORD`` are not set in the environment,
    returns the path even though it's empty - the per-test ``context`` fixture
    treats an empty file as "guest mode".
    """
    target = settings.storage_state_path
    if _storage_is_fresh(target):
        _log.info(f"Reusing storage_state from {target} (fresh).")
        return target
    if not settings.has_credentials():
        _log.info("No credentials in env; running as guest.")
        return target
    return target  # actual login happens in ``session_login``


@pytest.fixture(scope="session")
def session_login(playwright: Playwright, browser: Browser, settings, storage_state_path) -> Path:  # noqa: ANN001
    """Perform a real login once and persist storage_state."""
    if _storage_is_fresh(storage_state_path) or not settings.has_credentials():
        return storage_state_path

    _log.info("Performing one-time live login")
    context = browser.new_context()
    page = context.new_page()
    try:
        login_flow(page)
        context.storage_state(path=str(storage_state_path))
        _log.info(f"Saved storage_state to {storage_state_path}")
    finally:
        page.close()
        context.close()
    return storage_state_path


# --------------------------------------------------------------------------- pages
@pytest.fixture()
def context(
    browser: Browser,
    browser_context_args,  # noqa: ANN001
    session_login,
    settings,  # noqa: ANN001
) -> Generator[BrowserContext, None, None]:
    """Per-test context. Reuses ``storage_state.json`` if available."""
    args: dict[str, Any] = dict(browser_context_args)
    if settings.storage_state_path.exists() and settings.storage_state_path.stat().st_size > 0:
        args["storage_state"] = str(settings.storage_state_path)

    ctx = browser.new_context(**args)
    ctx.set_default_timeout(settings.action_timeout_ms)
    ctx.set_default_navigation_timeout(settings.navigation_timeout_ms)

    if settings.trace_mode in {"on", "retain-on-failure", "on-first-retry"}:
        ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

    yield ctx

    if settings.trace_mode in {"on", "retain-on-failure", "on-first-retry"}:
        trace_path = settings.reports_dir / f"trace_{int(time.time())}.zip"
        try:
            ctx.tracing.stop(path=str(trace_path))
            allure.attach.file(
                str(trace_path),
                name="playwright_trace",
                extension="zip",
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to stop/attach trace: {exc}")
    ctx.close()


@pytest.fixture()
def page(context: BrowserContext) -> Generator[Page, None, None]:  # noqa: F811 - override pytest-playwright's
    p = context.new_page()
    yield p
    p.close()


@pytest.fixture()
def guest_page(browser: Browser, browser_context_args, settings) -> Generator[Page, None, None]:  # noqa: ANN001
    """A page in a brand-new context with no auth - for guest tests."""
    ctx = browser.new_context(**browser_context_args)
    ctx.set_default_timeout(settings.action_timeout_ms)
    p = ctx.new_page()
    try:
        yield p
    finally:
        p.close()
        ctx.close()


# --------------------------------------------------------------------------- failure hook
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):  # noqa: ANN001
    """Attach a screenshot to Allure on failure if a ``page`` fixture is in use."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or report.passed:
        return
    page = item.funcargs.get("page") or item.funcargs.get("guest_page")
    if page is not None:
        try:
            attach_screenshot(page, f"FAILURE_{item.name}")
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to attach failure screenshot: {exc}")


# --------------------------------------------------------------------------- env shim
def pytest_configure(config: pytest.Config) -> None:  # noqa: D401
    """Make sure cwd is the repo root so .env loading works regardless of caller."""
    os.chdir(_REPO_ROOT)
