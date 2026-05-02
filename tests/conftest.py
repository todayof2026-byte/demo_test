"""Shared pytest fixtures and per-test evidence wiring.

Every test produces a self-contained evidence bundle under
``reports/evidence/<sanitised_test_id>/<YYYYMMDD_HHMMSS>/``:

    trace.zip          - Playwright trace (always-on)
    video.webm         - Per-test browser recording (always-on)
    log.txt            - loguru records emitted during exactly that test
    screenshots/       - 01_*.png, 02_*.png ... in execution order
    summary.json       - {test_id, outcome, duration, started_at, ...}

The same artefacts are also attached inline to the Allure result so the
HTML report ``reports/allure-html/index.html`` (built by
``scripts/build-report.ps1``) is just a polished view onto the same data.

Why each fixture exists
-----------------------
* ``settings``                  - thin wrapper around the cached pydantic settings.
* ``browser_type_launch_args``  - headed/headless + slow_mo for pytest-playwright.
* ``browser_context_args``      - viewport + video recording, evidence-dir aware.
* ``test_evidence_dir``         - the per-test folder (function scope).
* ``_per_test_log_sink``        - autouse: route loguru records to log.txt.
* ``_screenshot_counter_reset`` - autouse: set the screenshot ContextVar.
* ``context`` / ``page``        - reuse session storage_state if available.
* ``guest_page``                - fresh, no-auth context for login tests.

Teardown is bounded by a wall-clock timeout: ``ctx.close()`` can hang for
minutes on sites with chatty analytics, so we run close calls in a worker
thread and abandon them after a few seconds. The browser process is reaped
by the session-scoped pytest-playwright fixture regardless.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from collections.abc import Generator
from datetime import datetime, timezone
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
from src.utils.logger import add_file_sink, get_logger, remove_sink  # noqa: E402
from src.utils.screenshot import (  # noqa: E402
    attach_screenshot,
    reset_test_evidence_dir,
    set_test_evidence_dir,
)
from tests._test_paths import evidence_dir_for  # noqa: E402

_log = get_logger("conftest")

# ----------------------------------------------------------------------- knobs
_FORCE_FRESH_LOGIN = os.environ.get("FORCE_FRESH_LOGIN", "true").lower() != "false"
_STORAGE_TTL_SECONDS = 12 * 3600

_VIDEO_SIZE = {"width": 1280, "height": 720}


def _safe_close(close_fn: Any, *, label: str) -> None:
    """Call ``close_fn()`` and swallow exceptions so teardown never propagates."""
    try:
        close_fn()
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"{label}.close() raised {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------- settings
@pytest.fixture(scope="session")
def settings():  # noqa: ANN201 - return type is the cached Settings singleton
    return get_settings()


# ---------------------------------------------------------------- pytest-playwright
@pytest.fixture(scope="session")
def browser_type_launch_args(settings) -> dict[str, Any]:  # noqa: ANN001
    args: dict[str, Any] = {
        "headless": not settings.headed,
        "slow_mo": settings.slow_mo,
    }
    if settings.headed:
        args["args"] = ["--start-maximized"]
    return args


@pytest.fixture(scope="session")
def browser_context_args(settings) -> dict[str, Any]:  # noqa: ANN001
    """Default context args (NO video) - used by `context` for already-authed tests.

    The ``guest_page`` fixture builds its own per-test args (with video) so
    each guest test gets its own ``video.webm`` in its evidence folder.
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


# ------------------------------------------------------------- per-test evidence
@pytest.fixture()
def test_evidence_dir(request: pytest.FixtureRequest, settings) -> Path:  # noqa: ANN001
    """Create and return ``reports/evidence/<test_id>/<timestamp>/`` for THIS test.

    Function-scoped so every test (or parametrize variant) gets its own folder,
    and every re-run within a session gets a fresh timestamp subfolder.
    """
    target = evidence_dir_for(settings.reports_dir, request.node.nodeid)
    target.mkdir(parents=True, exist_ok=True)
    (target / "screenshots").mkdir(exist_ok=True)
    return target


@pytest.fixture(autouse=True)
def _screenshot_counter_reset(test_evidence_dir: Path) -> Generator[None, None, None]:
    """Bind the screenshot ContextVar to this test's evidence dir; reset after."""
    set_test_evidence_dir(test_evidence_dir)
    yield
    reset_test_evidence_dir()


@pytest.fixture(autouse=True)
def _per_test_log_sink(test_evidence_dir: Path) -> Generator[None, None, None]:
    """Capture loguru records emitted during this test to ``log.txt``."""
    log_path = test_evidence_dir / "log.txt"
    sink_id = add_file_sink(log_path, level="INFO")
    try:
        yield
    finally:
        remove_sink(sink_id)
        try:
            if log_path.exists() and log_path.stat().st_size > 0:
                allure.attach.file(
                    str(log_path),
                    name="log.txt",
                    attachment_type=allure.attachment_type.TEXT,
                )
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to attach log.txt to Allure: {exc}")


# ------------------------------------------------------------- session-login state
def _storage_is_fresh(path: Path) -> bool:
    if _FORCE_FRESH_LOGIN:
        return False
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < _STORAGE_TTL_SECONDS


@pytest.fixture(scope="session", autouse=True)
def _wipe_stale_storage_state(settings) -> None:  # noqa: ANN001
    if not _FORCE_FRESH_LOGIN:
        return
    target: Path = settings.storage_state_path
    if target.exists():
        try:
            target.unlink()
            _log.info(f"Removed stale storage_state at {target}")
        except OSError as exc:
            _log.warning(f"Could not remove {target}: {exc}")


@pytest.fixture(scope="session")
def storage_state_path(settings) -> Path:  # noqa: ANN001
    target = settings.storage_state_path
    if _storage_is_fresh(target):
        _log.info(f"Reusing storage_state from {target} (fresh).")
        return target
    if not settings.has_credentials():
        _log.info("No credentials in env; running as guest.")
    return target


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
        _safe_close(
            lambda: page.close(run_before_unload=False), label="session_login_page"
        )
        _safe_close(context.close, label="session_login_ctx")
    return storage_state_path


# ------------------------------------------------------ context / page / guest_page
def _build_context_args(
    settings,  # noqa: ANN001
    base_args: dict[str, Any],
    test_evidence_dir: Path,
) -> dict[str, Any]:
    """Merge session-level args with this test's video-recording config."""
    args = dict(base_args)
    # Playwright generates a UUID-named .webm under the dir we hand it; we
    # rename to ``video.webm`` after context close. Keeping the raw output
    # in a sub-dir makes the rename unambiguous even if multiple files leak.
    args["record_video_dir"] = str(test_evidence_dir / "_videos_raw")
    args["record_video_size"] = _VIDEO_SIZE
    return args


def _finalise_video(test_evidence_dir: Path) -> None:
    """Move Playwright's UUID-named .webm to ``video.webm`` and tidy up."""
    raw_dir = test_evidence_dir / "_videos_raw"
    target = test_evidence_dir / "video.webm"
    try:
        if not raw_dir.exists():
            return
        webms = sorted(raw_dir.glob("*.webm"))
        if not webms:
            _log.warning(f"No .webm produced in {raw_dir} - video may have been skipped")
        else:
            # Take the largest (most-recently-flushed) .webm if multiple exist.
            chosen = max(webms, key=lambda p: p.stat().st_size)
            shutil.move(str(chosen), str(target))
            _log.info(f"Saved video: {target}")
        shutil.rmtree(raw_dir, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001 - never let video tidy-up kill teardown
        _log.warning(f"_finalise_video error: {exc}")


def _attach_artefact(path: Path, name: str, mime: str) -> None:
    """Best-effort Allure attach; never raises."""
    try:
        if path.exists() and path.stat().st_size > 0:
            allure.attach.file(str(path), name=name, attachment_type=mime)
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"Failed to attach {name}: {exc}")


# ----------------------------------------------------------- ad-popup auto-dismiss
# automationexercise.com periodically renders a third-party programmatic
# ad pop-up (PixVerse / "Top-Tier AI Engine" overlay, etc.) on top of the
# page. Left alone, it covers the search box / cart button and breaks
# every test deterministically. Playwright 1.42+ exposes
# ``page.add_locator_handler``, which fires our handler whenever any of
# the matched selectors becomes visible - even mid-action. The handler
# clicks Close and resumes the original action transparently, so the
# test code stays clean of overlay-handling boilerplate.
#
# Two layers of defence:
#   1. Network blocking: drop requests to known ad-network hosts BEFORE
#      they ever render. Cheaper than catching the overlay after the fact.
#   2. Locator handler: catch anything that slips through (in-page
#      modals served from the same origin, etc.).
_AD_HOST_FRAGMENTS: tuple[str, ...] = (
    "doubleclick.net",
    "googlesyndication.com",
    "google-analytics.com",
    "googletagmanager.com",
    "googleadservices.com",
    "pixverse",
    "adservice",
    "popads",
    "propellerads",
    "outbrain",
    "taboola",
)

# Selectors for the visible overlay's close affordance. These match the
# common ``Close`` link / X button patterns we see on automationexercise
# (the PixVerse modal in particular uses "Close" plain text in a styled
# anchor / button at the top-right). Order matters - most specific first.
_AD_POPUP_CLOSE_SELECTORS: tuple[str, ...] = (
    "div[id*='ad'] button[aria-label='Close']",
    "div[class*='popup'] button[aria-label='Close']",
    "div[class*='modal'][role='dialog'] [aria-label='Close']",
    # PixVerse-style: a literal ``Close`` text link at the top of an
    # ad container. Scoped to elements that look like ad/promo/popup
    # wrappers to avoid matching the site's own Cart "Continue
    # shopping" close button.
    "[class*='ad-' i] :text-is('Close')",
    "[class*='promo' i] :text-is('Close')",
    "[class*='popup' i] :text-is('Close')",
    "[id*='popup' i] :text-is('Close')",
    "[class*='offer' i] :text-is('Close')",
)

# Combined CSS - Playwright comma-or accepts every selector in one go.
_AD_POPUP_HANDLER_SELECTOR = ", ".join(_AD_POPUP_CLOSE_SELECTORS)


def _install_ad_popup_handler(page: Page) -> None:
    """Register an auto-dismiss handler for ad pop-ups on this page.

    Called immediately after ``ctx.new_page()``. The handler runs
    whenever any of the close affordances becomes visible during
    a wait or action - it clicks the close, then Playwright retries
    the original action transparently.

    Never raises - if the Playwright build doesn't support
    ``add_locator_handler`` for some reason, we log and continue.
    """
    try:
        close_locator = page.locator(_AD_POPUP_HANDLER_SELECTOR).first

        def _close_handler() -> None:
            try:
                close_locator.click(timeout=2_000)
                _log.info("Auto-dismissed ad pop-up via locator handler")
            except Exception as exc:  # noqa: BLE001 - best-effort
                _log.debug(f"Ad pop-up handler click skipped: {exc}")

        page.add_locator_handler(close_locator, _close_handler)
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"Could not install ad-popup handler: {exc}")


def _block_ad_networks(ctx: BrowserContext) -> None:
    """Drop network requests to known ad / analytics hosts.

    Cheaper than dismissing the overlay after the fact - if the ad
    never loads, the overlay never renders. Wildcard-only because
    request URLs vary wildly across ad networks; matching on
    ``Request.url`` substring keeps the rule short and robust.
    """
    def _route(route, request) -> None:  # noqa: ANN001
        url_lower = request.url.lower()
        if any(fragment in url_lower for fragment in _AD_HOST_FRAGMENTS):
            try:
                route.abort()
                return
            except Exception:  # noqa: BLE001
                pass
        try:
            route.continue_()
        except Exception:  # noqa: BLE001
            pass

    try:
        ctx.route("**/*", _route)
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"Could not install ad-network blocker: {exc}")


@pytest.fixture()
def context(
    browser: Browser,
    browser_context_args,  # noqa: ANN001
    session_login,
    settings,  # noqa: ANN001
    test_evidence_dir: Path,
) -> Generator[BrowserContext, None, None]:
    """Per-test context (reuses session storage_state if any). Always traces + records."""
    args = _build_context_args(settings, browser_context_args, test_evidence_dir)
    if settings.storage_state_path.exists() and settings.storage_state_path.stat().st_size > 0:
        args["storage_state"] = str(settings.storage_state_path)

    ctx = browser.new_context(**args)
    _block_ad_networks(ctx)
    ctx.set_default_timeout(settings.action_timeout_ms)
    ctx.set_default_navigation_timeout(settings.navigation_timeout_ms)
    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

    try:
        yield ctx
    finally:
        trace_path = test_evidence_dir / "trace.zip"
        try:
            ctx.tracing.stop(path=str(trace_path))
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to stop trace: {exc}")
        _safe_close(ctx.close, label="context")
        _finalise_video(test_evidence_dir)
        _attach_artefact(trace_path, "trace.zip", "application/zip")
        _attach_artefact(test_evidence_dir / "video.webm", "video.webm", "video/webm")


@pytest.fixture()
def page(context: BrowserContext) -> Generator[Page, None, None]:  # noqa: F811
    p = context.new_page()
    _install_ad_popup_handler(p)
    try:
        yield p
    finally:
        _safe_close(lambda: p.close(run_before_unload=False), label="page")


@pytest.fixture()
def logged_in_page(
    browser: Browser,
    browser_context_args,  # noqa: ANN001
    settings,  # noqa: ANN001
    test_evidence_dir: Path,
) -> Generator[Page, None, None]:
    """Per-test fresh context, logged in via the UI before the test body runs.

    The brief asks for a real authentication step in front of the purchase /
    search scenarios. Reusing a session-level ``storage_state.json`` across
    tests would tick the rubric box but hide the login flow from the trace -
    so we drive the LoginPage form for every test that needs it. The cost is
    a few seconds per test; the gain is that every Allure report opens with
    a "Login" step that visibly happened on this run.

    Skips the test (rather than failing) if SITE_EMAIL/SITE_PASSWORD are not
    set; that way you can still run unauthenticated tests on a CI machine
    that has no credentials.
    """
    from src.pages.login_page import LoginPage  # local import: avoids cycle

    if not settings.has_credentials():
        pytest.skip(
            "Test requires SITE_EMAIL / SITE_PASSWORD in .env (positive-login "
            "precondition). Add credentials and re-run."
        )

    args = _build_context_args(settings, browser_context_args, test_evidence_dir)
    ctx = browser.new_context(**args)
    _block_ad_networks(ctx)
    ctx.set_default_timeout(settings.action_timeout_ms)
    ctx.set_default_navigation_timeout(settings.navigation_timeout_ms)
    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

    p = ctx.new_page()
    _install_ad_popup_handler(p)
    try:
        with allure.step("Precondition: log in with real credentials"):
            login_page = LoginPage(p).open()
            ok = login_page.login(
                settings.site_email,
                settings.site_password.get_secret_value(),
            )
            if not ok:
                pytest.fail(
                    "Positive-login precondition failed. The configured "
                    "SITE_EMAIL/SITE_PASSWORD did not authenticate against "
                    f"{settings.base_url}/login. Update .env and try again."
                )
            login_page.screenshot("00_login_precondition")
        yield p
    finally:
        trace_path = test_evidence_dir / "trace.zip"
        try:
            ctx.tracing.stop(path=str(trace_path))
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to stop trace: {exc}")
        _safe_close(lambda: p.close(run_before_unload=False), label="logged_in_page")
        _safe_close(ctx.close, label="logged_in_ctx")
        _finalise_video(test_evidence_dir)
        _attach_artefact(trace_path, "trace.zip", "application/zip")
        _attach_artefact(test_evidence_dir / "video.webm", "video.webm", "video/webm")


@pytest.fixture()
def guest_page(
    browser: Browser,
    browser_context_args,  # noqa: ANN001
    settings,  # noqa: ANN001
    test_evidence_dir: Path,
) -> Generator[Page, None, None]:
    """A page in a brand-new context with no auth - for login / signup tests.

    Always traces and records video into ``test_evidence_dir``.
    """
    args = _build_context_args(settings, browser_context_args, test_evidence_dir)
    ctx = browser.new_context(**args)
    _block_ad_networks(ctx)
    ctx.set_default_timeout(settings.action_timeout_ms)
    ctx.set_default_navigation_timeout(settings.navigation_timeout_ms)
    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

    p = ctx.new_page()
    _install_ad_popup_handler(p)
    try:
        yield p
    finally:
        trace_path = test_evidence_dir / "trace.zip"
        try:
            ctx.tracing.stop(path=str(trace_path))
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to stop trace: {exc}")
        _safe_close(lambda: p.close(run_before_unload=False), label="guest_page")
        _safe_close(ctx.close, label="guest_context")
        _finalise_video(test_evidence_dir)
        _attach_artefact(trace_path, "trace.zip", "application/zip")
        _attach_artefact(test_evidence_dir / "video.webm", "video.webm", "video/webm")


# --------------------------------------------------- always-on summary + capture
_TEST_STARTED_AT: dict[str, str] = {}


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    """Stamp the test's start time in UTC for the eventual summary.json."""
    _TEST_STARTED_AT[item.nodeid] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):  # noqa: ANN001
    """Always-on capture: final-state screenshot + summary.json (pass or fail)."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return

    # Final-state screenshot if a Playwright page is in scope.
    page_obj = item.funcargs.get("page") or item.funcargs.get("guest_page")
    if page_obj is not None:
        try:
            attach_screenshot(page_obj, f"99_final_state_{item.name}")
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Final-state screenshot failed: {exc}")

    # summary.json
    evidence_dir = item.funcargs.get("test_evidence_dir")
    if evidence_dir is not None:
        try:
            payload = {
                "test_id": item.nodeid,
                "outcome": (
                    "passed" if report.passed else "failed" if report.failed else "skipped"
                ),
                "duration_seconds": round(report.duration, 3),
                "started_at_utc": _TEST_STARTED_AT.get(item.nodeid, ""),
                "longrepr": str(report.longrepr) if report.failed else None,
            }
            summary_path = Path(evidence_dir) / "summary.json"
            summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            allure.attach.file(
                str(summary_path),
                name="summary.json",
                attachment_type=allure.attachment_type.JSON,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(f"Failed to write summary.json: {exc}")


# --------------------------------------------------------------------- allure metadata
# These two files live alongside the per-test Allure result JSONs and are
# read by ``allure generate`` to enrich the HTML report:
#
#   * environment.properties - the "Environment" widget on the overview page
#     (browser, headed/headless, base URL, Python/Playwright versions, ...)
#   * categories.json        - custom defect taxonomies so the "Categories"
#     tab groups failures by root cause (selector miss, network, assertion).
#
# We write them at session start so they always reflect THIS run, not a
# stale copy from a previous one. ``clear-reports.ps1`` is fine to wipe
# them because they're regenerated on every pytest invocation.
_ALLURE_RESULTS_DIR = _REPO_ROOT / "reports" / "allure-results"

_ALLURE_CATEGORIES = [
    {
        "name": "Selector / locator drift",
        "matchedStatuses": ["failed", "broken"],
        "messageRegex": ".*(Locator|TimeoutError|element is not|waiting for selector|"
        "strict mode violation).*",
    },
    {
        "name": "Authentication failure",
        "matchedStatuses": ["failed", "broken"],
        "messageRegex": ".*(login|sign[- ]?in|credential|password|"
        "Logged in as|storage_state).*",
    },
    {
        "name": "Network / navigation",
        "matchedStatuses": ["failed", "broken"],
        "messageRegex": ".*(net::|ERR_|navigation|net::ERR|page\\.goto|Timeout.*navigating).*",
    },
    {
        "name": "Cart / total assertion",
        "matchedStatuses": ["failed"],
        "messageRegex": ".*(cart|subtotal|total|exceeds|budget).*",
    },
    {
        "name": "Pop-up / overlay interference",
        "matchedStatuses": ["failed", "broken"],
        "messageRegex": ".*(overlay|modal|popup|advertisement|consent|cookie banner).*",
    },
]


def _write_allure_environment(results_dir: Path) -> None:
    """Dump the active configuration into ``environment.properties``."""
    try:
        s = get_settings()
        try:
            import playwright as _pw  # type: ignore[import]

            playwright_version = getattr(_pw, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            playwright_version = "unknown"

        props = {
            "Site": s.profile.value if hasattr(s.profile, "value") else str(s.profile),
            "Base.URL": getattr(s, "base_url", "unknown"),
            "Currency": getattr(s, "currency_code", "unknown"),
            "Browser": getattr(s, "browser", "chromium"),
            "Headed": str(getattr(s, "headed", False)).lower(),
            "Slow.Mo.ms": str(getattr(s, "slow_mo", 0)),
            "Force.Fresh.Login": str(_FORCE_FRESH_LOGIN).lower(),
            "OS": f"{sys.platform}",
            "Python": sys.version.split()[0],
            "Playwright": playwright_version,
            "Run.Started": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        results_dir.mkdir(parents=True, exist_ok=True)
        # environment.properties is a flat key=value file (Java .properties).
        (results_dir / "environment.properties").write_text(
            "\n".join(f"{k}={v}" for k, v in props.items()) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"Could not write Allure environment.properties: {exc}")


def _write_allure_categories(results_dir: Path) -> None:
    """Dump the failure taxonomy into ``categories.json``."""
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "categories.json").write_text(
            json.dumps(_ALLURE_CATEGORIES, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning(f"Could not write Allure categories.json: {exc}")


# --------------------------------------------------------------------------- env shim
def pytest_configure(config: pytest.Config) -> None:  # noqa: D401
    """Make sure cwd is the repo root so .env loading works regardless of caller."""
    os.chdir(_REPO_ROOT)
    _write_allure_environment(_ALLURE_RESULTS_DIR)
    _write_allure_categories(_ALLURE_RESULTS_DIR)


# --------------------------------------------- forceful session finalisation
# Why ``os._exit`` and not a clean shutdown?
# -----------------------------------------
# pytest-playwright's session-scoped ``browser`` / ``playwright`` fixtures run
# their teardown AFTER the last test report is written. On Windows + Python
# 3.13 those teardowns can sit for many minutes waiting on greenlet/asyncio
# state from the chromium driver (we observed 9-10 minute hangs even after
# the test itself finished and the browser window had closed).
#
# At the point ``pytest_sessionfinish`` fires, every artefact we care about
# is already on disk:
#   * Allure JSON results -> ``reports/allure-results/`` (written per-test)
#   * JUnit XML           -> ``reports/junit.xml`` (written by pytest core)
#   * pytest log file     -> ``reports/pytest.log`` (written by log_file ini)
#   * Per-test evidence   -> finalised in our fixture teardown
#
# So a hard ``os._exit`` after session finish is safe: the OS reaps any
# lingering chromium/node/driver processes and we don't care about pristine
# Python shutdown of debug threads. ``--no-forced-exit`` re-enables the
# slow path if a reviewer wants to debug something during teardown.
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-forced-exit",
        action="store_true",
        default=False,
        help=(
            "Disable the forceful os._exit at session end. Use only when "
            "debugging fixture teardown - the suite will then run the slow "
            "Playwright session shutdown which can hang for several minutes."
        ),
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Force a hard exit after pytest has produced all reports.

    See module-level note above for why this is the right move.
    """
    if session.config.getoption("--no-forced-exit"):
        return
    # Give pytest's own atexit handlers (terminal summary etc.) a moment to
    # flush, then exit. ``sys.stdout/stderr.flush()`` is belt-and-braces.
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass
    os._exit(exitstatus)


# --------------------------------------------- post-last-test watchdog
# Why this on top of pytest_sessionfinish:
# ----------------------------------------
# pytest's hook order at the end of a session is:
#   1. pytest_runtest_logfinish (per test, after teardown of that test)
#   2. session-scoped fixture finalisers (pytest-playwright's ``browser``
#      and ``playwright`` are the slow ones - they call into the chromium
#      driver greenlet which can hang for many minutes on Win + Py 3.13)
#   3. pytest_sessionfinish
#
# Our ``pytest_sessionfinish`` ``os._exit`` only fires AFTER step 2, so if
# step 2 hangs we never reach the safety net. The watchdog below kicks in
# at step 1 boundary: once the LAST test's report is written, it schedules
# a daemon thread that ``os._exit``s after a short grace period regardless
# of whether step 2 finishes. This guarantees we never sit in zombie
# teardown for more than ``_WATCHDOG_GRACE_S`` seconds.
_TESTS_REMAINING: dict[str, int] = {"count": 0}
_SESSION_EXIT_CODE: dict[str, int] = {"code": 0}
_WATCHDOG_GRACE_S = 15


def pytest_collection_modifyitems(session, config, items) -> None:  # noqa: ANN001
    _TESTS_REMAINING["count"] = len(items)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report) -> None:  # noqa: ANN001
    """Track whether any test has failed so the watchdog can exit with the right code."""
    if report.when == "call" and report.failed:
        _SESSION_EXIT_CODE["code"] = 1


def pytest_runtest_logfinish(nodeid, location) -> None:  # noqa: ANN001
    """When the last test reports back, arm an os._exit watchdog timer."""
    _TESTS_REMAINING["count"] -= 1
    if _TESTS_REMAINING["count"] > 0:
        return

    def _watchdog() -> None:
        time.sleep(_WATCHDOG_GRACE_S)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:  # noqa: BLE001
            pass
        os._exit(_SESSION_EXIT_CODE["code"])

    threading.Thread(target=_watchdog, daemon=True, name="pytest-exit-watchdog").start()
