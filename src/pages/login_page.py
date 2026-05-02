"""Login page POM for automationexercise.com.

The site exposes ``/login`` with TWO forms on one page:
* "Login to your account" - drives ``input[data-qa='login-email']`` +
  ``input[data-qa='login-password']`` + ``button[data-qa='login-button']``.
* "New User Signup!" - drives ``signup-name`` / ``signup-email`` / ``signup-button``.

We only model the login form here. Failure surfaces as a visible
``<p style="color: red;">Your email or password is incorrect!</p>`` paragraph
inside the ``.login-form`` block.

The selectors are stable (purpose-built ``data-qa`` attributes), so we don't
need a multi-candidate fallback pattern. We still return :class:`bool` from
:meth:`login` so the auth flow can drop to guest mode on failure rather than
raising mid-test.
"""

from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.pages.base_page import BasePage


class LoginPage(BasePage):
    URL_PATH = "/login"

    EMAIL_INPUT = "input[data-qa='login-email']"
    PASSWORD_INPUT = "input[data-qa='login-password']"
    SUBMIT_BUTTON = "button[data-qa='login-button']"

    LOGIN_FORM_HEADING = ".login-form h2"

    # Visible after a failed login attempt.
    ERROR_MESSAGE = ".login-form p[style*='color: red']"
    ERROR_MESSAGE_TEXT_FALLBACK = "p:has-text('Your email or password is incorrect')"

    # Markers that prove we're authenticated. Either is sufficient.
    LOGGED_IN_MARKER = "a:has-text('Logged in as')"
    LOGOUT_LINK = "a[href='/logout']"

    # ---------------------------------------------------------------- form actions
    def fill_credentials(self, email: str, password: str) -> "LoginPage":
        """Fill the login form without submitting. Returns self for chaining."""
        self.log.info(f"Filling login form for {email!r}")
        self.page.locator(self.EMAIL_INPUT).fill(email)
        self.page.locator(self.PASSWORD_INPUT).fill(password)
        return self

    def clear_credentials(self) -> "LoginPage":
        """Clear both inputs without leaving the page.

        Used when the same page is re-driven with different credentials (e.g.
        the negative-then-positive recovery flow). Playwright's ``.fill('')``
        empties the field reliably across browsers.
        """
        self.log.info("Clearing login form fields")
        self.page.locator(self.EMAIL_INPUT).fill("")
        self.page.locator(self.PASSWORD_INPUT).fill("")
        return self

    def submit(self) -> "LoginPage":
        """Click the submit button and wait for either auth-success OR error.

        Why we don't use ``networkidle``: automationexercise.com loads ads /
        analytics scripts asynchronously, so the network never actually goes
        idle - waiting on it would burn the full 10s timeout every submit
        even on a successful login. Instead we race two outcomes:

        * the ``Logged in as ...`` marker appears -> success path
        * the ``incorrect`` error <p> appears      -> rejection path

        Whichever fires first means the form has been processed by the
        server. Falls back to ``domcontentloaded`` if neither shows up
        (defensive - shouldn't happen on this site).
        """
        self.page.locator(self.SUBMIT_BUTTON).click()
        outcome_selector = (
            f"{self.LOGGED_IN_MARKER}, "
            f"{self.ERROR_MESSAGE}, "
            f"{self.ERROR_MESSAGE_TEXT_FALLBACK}"
        )
        try:
            self.page.locator(outcome_selector).first.wait_for(
                state="visible", timeout=8_000
            )
        except PlaywrightTimeout:
            self.log.warning(
                "Neither auth marker nor error appeared within 8s; "
                "falling back to domcontentloaded."
            )
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=3_000)
            except PlaywrightTimeout:
                pass
        return self

    def login(self, email: str, password: str) -> bool:
        """End-to-end login attempt. Returns True iff the auth marker is visible.

        On failure, callers can call :meth:`error_message` to retrieve the
        site's error text (useful for negative-case assertions).
        """
        if not email or not password:
            self.log.warning("Login skipped: empty credentials")
            return False

        self.fill_credentials(email, password).submit()
        return self.is_authenticated()

    # ---------------------------------------------------------------- assertions data
    def is_authenticated(self) -> bool:
        """True if any 'Logged in as ...' / logout marker is visible."""
        for selector in (self.LOGGED_IN_MARKER, self.LOGOUT_LINK):
            try:
                if self.page.locator(selector).first.is_visible(timeout=2000):
                    return True
            except PlaywrightTimeout:
                continue
        return False

    def displayed_username(self) -> str | None:
        """Return the 'Logged in as <name>' value, or None if not authenticated.

        The site renders this in the global header as
        ``<a href="/"> Logged in as <b>username</b></a>``. ``inner_text`` flattens
        the nested ``<b>``, so we strip the literal prefix.
        """
        try:
            locator = self.page.locator(self.LOGGED_IN_MARKER).first
            if not locator.is_visible(timeout=2000):
                return None
            text = locator.inner_text(timeout=1500).strip()
        except PlaywrightTimeout:
            return None
        # 'Logged in as demo_test' -> 'demo_test'
        return text.removeprefix("Logged in as").strip() or None

    def error_message(self) -> str | None:
        """Return the site's error text if a failed-login error is visible, else None."""
        for selector in (self.ERROR_MESSAGE, self.ERROR_MESSAGE_TEXT_FALLBACK):
            try:
                locator = self.page.locator(selector).first
                if locator.is_visible(timeout=2000):
                    return locator.inner_text(timeout=1500).strip()
            except PlaywrightTimeout:
                continue
        return None

    def is_on_login_page(self) -> bool:
        """True if the login form itself is visible. Useful as a negative-case marker."""
        try:
            return self.page.locator(self.LOGIN_FORM_HEADING).first.is_visible(timeout=2000)
        except PlaywrightTimeout:
            return False
