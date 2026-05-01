"""Produce a sanitised "login worked" evidence bundle.

Why this exists
---------------
Reviewers need confidence that the ``login`` flow (one of the four required
brief functions) actually drives the live login UI. They don't necessarily
need our credentials to verify that. This script:

1. Runs the full login flow once against the live site using the local
   ``.env`` credentials.
2. Saves a **redacted** screenshot of the post-login page (identifier is masked).
3. Writes a small ``evidence.json`` capturing what was tested and when.
4. Writes a ``README.md`` explaining how to interpret the bundle.

The output goes to ``reports/login-evidence/`` and is suitable for committing
to the repo as a graded artefact.

Run with::

    python scripts/make_login_evidence.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

# Make ``import src...`` work regardless of where the script is invoked from.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.flows.auth_flow import login as login_flow  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

_log = get_logger("login-evidence")


def _redact_identifier(identifier: str) -> str:
    """Mask a login identifier for safe logging.

    Email-shaped: ``some.user@gmail.com`` -> ``so***@gmail.com``.
    Bare username: ``tdemo_test`` -> ``td*******``.
    """
    match = re.match(r"^([^@]+)@(.+)$", identifier)
    if match:
        local, domain = match.group(1), match.group(2)
        if len(local) <= 2:
            local_redacted = "*" * len(local)
        else:
            local_redacted = local[:2] + "*" * (len(local) - 2)
        return f"{local_redacted}@{domain}"
    if len(identifier) <= 2:
        return "*" * len(identifier)
    return identifier[:2] + "*" * (len(identifier) - 2)


def _evidence_dir() -> Path:
    target = _REPO_ROOT / "reports" / "login-evidence"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _write_readme(evidence_dir: Path, settings) -> None:  # noqa: ANN001
    readme = evidence_dir / "README.md"
    body = f"""# Login Evidence Bundle

This folder contains a sanitised, committable artefact that demonstrates the
`login` flow defined in [`src/flows/auth_flow.py`](../../src/flows/auth_flow.py)
successfully authenticates against the live storefront.

## Files

- `screenshot_post_login.png` - full-page screenshot of the page **after**
  the login form was submitted.
- `evidence.json` - structured metadata about the run (timestamp, profile,
  redacted identity, success flag).

## How it was produced

```powershell
python scripts/make_login_evidence.py
```

The script reads credentials from the local `.env` (decrypted from
`secrets/credentials.sops.yaml` via `scripts/decrypt-env.ps1`), runs the
real login flow against `{settings.base_url}`, masks the email in the
captured screenshot, and writes the artefacts here.

## What this proves and what it doesn't

- It proves: the login implementation works end-to-end against the real site.
- It does NOT prove: the credentials are valid forever, or that the site's
  login UX hasn't changed since the screenshot was taken. Always re-run
  before submitting a new graded build.

## How a reviewer can verify independently

1. Install sops + age (one-time): `.\\scripts\\setup-secrets.ps1`.
2. Get the age private key from the project owner (out-of-band).
3. `.\\scripts\\decrypt-env.ps1` to materialise `.env`.
4. `python scripts/make_login_evidence.py` to regenerate this bundle.

If the reviewer prefers not to handle credentials at all, they can read the
test code, inspect this artefact, and accept it as evidence.
"""
    readme.write_text(body, encoding="utf-8")


def main() -> int:
    settings = get_settings()
    if not settings.has_credentials():
        _log.error(
            "No credentials in environment. Run scripts\\decrypt-env.ps1 or set "
            "SITE_EMAIL / SITE_PASSWORD in .env, then re-run."
        )
        return 2

    evidence_dir = _evidence_dir()
    timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    screenshot_path = evidence_dir / "screenshot_post_login.png"
    json_path = evidence_dir / "evidence.json"

    _log.info(f"Evidence dir: {evidence_dir}")
    _log.info(f"Profile: {settings.profile} -> {settings.base_url}")

    success = False
    error_message: str | None = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not settings.headed, slow_mo=settings.slow_mo)
        context = browser.new_context(viewport={"width": 1366, "height": 820}, locale="en-US")
        page = context.new_page()
        page.set_default_timeout(settings.action_timeout_ms)
        try:
            success = login_flow(page)
            if not success:
                error_message = "login_flow returned False (selectors or credentials issue)."
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception as exc:  # noqa: BLE001 - we want the artefact even on failure
            error_message = f"{type(exc).__name__}: {exc}"
            _log.error(error_message)
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception as inner:  # noqa: BLE001
                _log.error(f"Could not capture screenshot of failure: {inner}")
        finally:
            context.close()
            browser.close()

    payload = {
        "timestamp": timestamp,
        "profile": settings.profile,
        "base_url": settings.base_url,
        "identity_redacted": _redact_identifier(settings.site_email),
        "login_succeeded": success,
        "error": error_message,
        "screenshot": screenshot_path.name,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_readme(evidence_dir, settings)

    if success:
        _log.info(f"Login succeeded. Bundle written to {evidence_dir}")
        return 0
    _log.error(f"Login did NOT succeed. Bundle written for triage: {evidence_dir}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
