# E-commerce E2E - Playwright + pytest (POM, OOP, Data-Driven)

End-to-end automation framework targeting
[automationexercise.com](https://www.automationexercise.com).
Implements the four functions required by the exercise brief
(`login`, `search_items_by_name_under_price`, `add_items_to_cart`,
`assert_cart_total_not_exceeds`) over a clean Page Object Model with
typed configuration, YAML-driven inputs, and Allure reporting.

> **Status:** the **login** flow is fully ported and covered by
> [`tests/test_login.py`](tests/test_login.py) (positive + negative
> data-driven cases). The search / add-to-cart / cart-subtotal flows are
> still being pivoted from the previous target site - the relevant tests
> are explicitly skipped with a reason until that work lands. See
> [Status & roadmap](#status--roadmap).

> The full exercise brief in English is available as a one-page dashboard:
> [`exercise-brief.html`](exercise-brief.html).

## Table of contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [Security & credentials](#security--credentials)
- [Running the tests](#running-the-tests)
- [Reports & Evidence](#reports--evidence)
- [Architecture](#architecture)
- [Data-driven scenarios](#data-driven-scenarios)
- [AI-assisted workflow](#ai-assisted-workflow)
- [Assumptions and limitations](#assumptions-and-limitations)
- [Project layout](#project-layout)

## Prerequisites

- **Python 3.11 or newer**.
- **Node.js 18+** (only required if you want to use the Playwright MCP for AI-assisted locator discovery).
- **Allure CLI 2.x** to view the Allure HTML report. Install with [`scoop install allure`](https://scoop.sh/) on Windows or `brew install allure` on macOS. JUnit XML is also produced as a fallback.

## Setup

```powershell
# Clone, then from the repo root:
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
playwright install chromium

# Create your local .env from the template:
copy .env.example .env
# (macOS/Linux: cp .env.example .env)
```

Open `.env` and fill in `SITE_EMAIL` and `SITE_PASSWORD` (and optionally
toggle `HEADED=true` for a visible browser).

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PROFILE` | `default` | Storefront profile (`default` -> automationexercise.com). Add new profiles in [`src/config/settings.py`](src/config/settings.py). |
| `SITE_EMAIL` | _empty_ | Login email. If empty, login tests run as guest / are skipped. |
| `SITE_PASSWORD` | _empty_ | Login password. Stored as `SecretStr` so it never appears in logs. |
| `HEADED` | `false` | `true` to run the browser in headed mode. |
| `SLOW_MO` | `0` | Slow each Playwright action by N ms (debugging). |
| `ACTION_TIMEOUT_MS` | `15000` | Default per-action timeout. |
| `NAVIGATION_TIMEOUT_MS` | `30000` | Default navigation timeout. |
| `TRACE_MODE` | `retain-on-failure` | Playwright trace policy: `on`, `off`, `retain-on-failure`, `on-first-retry`. |

The `.env` file is gitignored. The committed template lives in [`.env.example`](.env.example).

## Security & credentials

This project demonstrates **production-grade secret management** for test
credentials. The login user and password are committed to the repo
**encrypted** (with [SOPS][sops] + [age][age]); the plaintext `.env` never
leaves the machine that produced it.

> **Note on the credentials themselves:** the account in this repo is a
> dedicated, throwaway test account created specifically for this exercise
> on automationexercise.com. The point is to demonstrate the *pattern*
> (encrypted-at-rest secrets, allow-listed scanners, sanitised evidence
> artefacts) rather than to protect a high-value secret.

### Files involved

| File | Purpose | Committed? |
| --- | --- | --- |
| [`.env.example`](.env.example) | Template showing every var the framework reads. | Yes |
| `.env` | Local plaintext credentials. **Never commit.** | **No** (gitignored) |
| [`.sops.yaml`](.sops.yaml) | SOPS policy: which age public keys may decrypt. | Yes |
| `secrets/credentials.sops.yaml` | The encrypted ciphertext. Safe to commit. | Yes (after encryption) |
| `~/.config/sops/age/keys.txt` | Your private age key. **Never commit.** | **No** (lives in user profile) |

### One-time setup (per machine)

The bootstrap script installs sops + age via `winget`, generates an age
keypair if one doesn't exist, and prints the **public** half so you can
paste it into `.sops.yaml`:

```powershell
.\scripts\setup-secrets.ps1
```

After that, edit `.sops.yaml` and replace the `age:` placeholder with the
public key the script printed. (Yes, the public key is safe to commit.)

### Encrypt your credentials

1. Edit `.env` with real credentials (`SITE_EMAIL`, `SITE_PASSWORD`).
2. Run:

   ```powershell
   .\scripts\encrypt-env.ps1
   ```

3. This produces `secrets/credentials.sops.yaml`. Commit it.
4. The plaintext `.env` is gitignored and stays on your machine.

### Decrypt on a fresh checkout (your second machine, or a teammate)

1. Install sops + age (`scripts\setup-secrets.ps1` does this).
2. Place your **private** age key at `%USERPROFILE%\.config\sops\age\keys.txt`.
3. Run:

   ```powershell
   .\scripts\decrypt-env.ps1
   ```

4. `.env` is recreated locally; `pytest` works as usual.

### Granting the reviewer decryption access

Two options, in order of preference:

1. **Add the reviewer's age public key to `.sops.yaml`**, then re-encrypt
   with `sops updatekeys secrets/credentials.sops.yaml`. They generate
   their own keypair locally and send you the public half. **Their private
   key never leaves their machine, your private key never leaves yours.**
   This is the model used at Mozilla, CNCF, etc. - it's the right answer
   for production teams.
2. **Share your private age key out-of-band** - one-time-secret links
   ([onetimesecret.com][ots], [pwpush.com][pwpush]), Signal disappearing
   messages, or a 1Password / Bitwarden shared item with link expiry. This
   is acceptable for a graded throwaway account but **never** for a
   shared production secret.

If the reviewer prefers to inspect the framework without handling
credentials, they can rely on the [login evidence bundle](#login-evidence)
described below.

### Pre-commit secret scanning

A [`.pre-commit-config.yaml`](.pre-commit-config.yaml) wires up
[`gitleaks`][gitleaks] alongside the standard hygiene hooks (large-file,
private-key detection, YAML/JSON validation, `ruff`, `black`). The
[`.gitleaks.toml`](.gitleaks.toml) ruleset allow-lists the SOPS-encrypted
file and example templates so they don't trip the scanner.

```powershell
pip install pre-commit
pre-commit install                # runs on every commit going forward
pre-commit run --all-files        # one-off scan of the whole tree
```

### Login evidence

If the reviewer prefers to inspect the framework without handling
credentials, [`scripts/make_login_evidence.py`](scripts/make_login_evidence.py)
runs the login flow once against the live site and writes a sanitised
artefact bundle to `reports/login-evidence/`:

- A full-page screenshot of the post-login state.
- An `evidence.json` capturing timestamp, profile, redacted identity,
  and success flag.
- A `README.md` explaining how the bundle was produced.

The reviewer can browse the bundle, read the flow code, and accept that
as proof of correctness without needing to run the login themselves.

```powershell
python scripts\make_login_evidence.py
```

[sops]: https://github.com/getsops/sops
[age]: https://github.com/FiloSottile/age
[gitleaks]: https://github.com/gitleaks/gitleaks
[ots]: https://onetimesecret.com
[pwpush]: https://pwpush.com

## Running the tests

```powershell
pytest                                       # full suite, Allure results in reports/
pytest tests/test_login.py -v                # login flow (positive + negative)
pytest -k price_parser                       # unit tests, no browser
pytest -m smoke                              # fast sanity only
pytest -m "search and not e2e"               # data-driven search scenarios (skipped pending pivot)
$env:HEADED="true"; pytest tests/test_login.py    # watch the browser
```

Useful flags:

- `-n auto` runs tests in parallel via `pytest-xdist`.
- `--reruns 1` retries flaky tests once via `pytest-rerunfailures`.

## Reports & Evidence

Every test run produces a multi-format evidence bundle so the reviewer
never has to ask "what actually happened in that run?". The capture
is **always-on** (pass or fail) so a green run still has the same
evidence as a failure.

### What is captured per test

| Artefact | Content | Status |
| --- | --- | --- |
| Playwright **trace** (`.zip`) | Full DOM snapshots, network, console, screenshots-per-action - opens with `playwright show-trace`. | Wired (always-on) |
| **Video recording** (`.webm`) | One video per test, recording the whole browser context end-to-end. Demonstrates the user journey at human speed. | Planned (fixtures in flight - see [`AGENTS.md`](AGENTS.md)) |
| **Screenshots** (`.png`) | Every `BasePage.screenshot(name)` call lands in `screenshots/` and is attached to the matching Allure step. Numbered per-test (`01_login_page.png`, `02_login_rejected_with_error.png`, ...). | Wired (sequence numbering in flight) |
| **Per-test log** (`log.txt`) | The `loguru` records emitted during exactly that test, captured via a per-test sink (`add_file_sink` in [`src/utils/logger.py`](src/utils/logger.py)). | Helper landed; per-test wiring in flight |
| `summary.json` | `{test_id, outcome, duration_seconds, started_at, scenario}` - machine-readable test ledger. | Planned |

### Where the evidence lives

```
reports/
+-- allure-results/                   raw Allure JSON (one file per result)
+-- allure-html/                      static HTML report (built on demand)
+-- evidence/
|   \-- <test_id>/<timestamp>/
|       +-- trace.zip
|       +-- video.webm
|       +-- log.txt
|       +-- screenshots/
|       \-- summary.json
+-- junit.xml                         CI-consumer-friendly test summary
\-- last_login_run.log                last pytest stdout (debug aid)
```

Everything in `reports/` is gitignored (it's evidence, not source).
The folder layout means the reviewer can either:
* Browse the HTML Allure report (recommended), OR
* Open `reports/evidence/<test_id>/<timestamp>/` directly without
  installing any tools - the same artefacts are there as flat files.

### Building the HTML report

```powershell
# After a test run, build a self-contained HTML site you can zip & email:
.\scripts\build-report.ps1
Start-Process reports\allure-html\index.html

# OR live-view (auto-opens browser, auto-reloads):
.\scripts\view-report.ps1
```

Each Allure test result shows: test name, parametrize id, total duration,
each Allure step (with its own duration), and every attached artefact
inline (logs, screenshots, video, trace).

### Login-flow specific evidence

The combined login test [`tests/test_login.py`](tests/test_login.py) drives
the full **negative-then-positive recovery flow in a single browser
window** - so the resulting video shows: form rendered -> wrong creds
typed -> red error appears -> fields cleared -> real creds typed ->
header shows `Logged in as <username>`. One scenario, one watchable
recording, all the rubric points.

## Architecture

Layered top-down. Each layer only depends on the layer below it.

```
tests/         pytest cases (only assertions live here)
src/flows/     the 4 brief functions; orchestrate page objects
src/pages/     Page Object Model (one class per page, extends BasePage)
src/components/  reusable widgets (header, price filter, paginator, product card)
src/utils/     price parser, screenshot helper, loguru, variant picker
src/config/    pydantic-settings + site profiles
data/          YAML inputs for parameterized tests
```

Hard-line rules enforced via [`.cursor/rules/*.mdc`](.cursor/rules/) and documented in [`AGENTS.md`](AGENTS.md):

- **`Decimal` for money**, never `float`. The `PriceParser` is the single source of truth.
- **No `time.sleep`** in `src/`; only Playwright waits.
- **No assertions** in pages or components - assertions belong to tests/flows.
- **No cross-page imports** - cross-page orchestration happens in `src/flows/`.
- **Locator priority**: role -> data-testid -> text -> CSS attr -> XPath. The brief mandates XPath for `SearchResultsPage.PRODUCT_CARD_XPATH` only.
- **Credentials** never live in code - only in `.env`.

## Data-driven scenarios

Two YAML files drive parameterised tests today:

| File | Drives | Status |
| --- | --- | --- |
| [`data/login.yaml`](data/login.yaml) | `tests/test_login.py` (positive + negative login) | **Active** |
| [`data/queries.yaml`](data/queries.yaml) | `tests/test_search_data_driven.py` (search + price filter) | Skipped (pending search pivot) |

Each entry exercises a distinct code path. For login that means: env-driven
positive case, wrong-password negative, and unknown-user negative (the
last two assert the site's own error message). For search:
`full_results_running_shoes`, `with_pagination_jacket`, and
`empty_ok_nonsense` (empty result is valid per the brief).

Real credentials are never written to `data/`; they live only in `.env`
(gitignored) or in `secrets/credentials.sops.yaml` (SOPS-encrypted). Adding
a scenario is one YAML entry; the parameterised tests pick them up
automatically.

## Status & roadmap

| Brief function | File | Status |
| --- | --- | --- |
| `login` | [`src/flows/auth_flow.py`](src/flows/auth_flow.py) + [`src/pages/login_page.py`](src/pages/login_page.py) | **Done.** Covered by `tests/test_login.py` (3 data-driven scenarios). |
| `search_items_by_name_under_price` | [`src/flows/search_flow.py`](src/flows/search_flow.py) | Selectors target the previous storefront. To port: rewrite `SearchResultsPage` for automationexercise.com's `/products` listing, then unskip `tests/test_search_data_driven.py`. |
| `add_items_to_cart` | [`src/flows/cart_flow.py`](src/flows/cart_flow.py) | Pending. PDP and Add-to-Cart selectors need updating to the new site. |
| `assert_cart_total_not_exceeds` | [`src/flows/cart_flow.py`](src/flows/cart_flow.py) | Pending. Cart subtotal selector needs updating. |

## AI-assisted workflow

A small project-scoped AI tooling layer is committed to the repo to
demonstrate effective AI usage and to make ongoing maintenance reproducible
across reviewers:

| Artifact | What it does |
| --- | --- |
| [`.cursor/rules/*.mdc`](.cursor/rules/) | Five focused rule files auto-applied by Cursor based on file globs. |
| [`.cursor/commands/`](.cursor/commands/) | Slash commands `/add-page-object`, `/add-test-case`, `/debug-failing-locator`. |
| [`.cursor/mcp.json`](.cursor/mcp.json) | Project-scoped Playwright MCP (live browser) + Filesystem MCP (sandboxed to repo root). |
| [`docs/personas/`](docs/personas/) | Three role personas: QA Architect, Test Engineer, Code Reviewer. |
| [`AGENTS.md`](AGENTS.md) | Universal AI playbook (commands, conventions, common pitfalls). |
| [`docs/ai-workflow.md`](docs/ai-workflow.md) | When to use which artifact, with concrete examples. |

Nothing here is required for the tests to run - they're augmentations.
The MCP servers in `.cursor/mcp.json` are scoped to this project only;
they do not affect global Cursor settings.

## Assumptions and limitations

- **Login**: live credentials per `.env`. The login tests in
  [`tests/test_login.py`](tests/test_login.py) deliberately use a fresh
  guest context each run so the assertion ("the login flow itself
  authenticated the session") is meaningful. The session-scoped
  `storage_state` fixture in [`tests/conftest.py`](tests/conftest.py)
  authenticates once for the wider suite and caches `auth/storage_state.json`
  (gitignored) for up to 12 hours; set `FORCE_FRESH_LOGIN=true` (the
  default) to opt out of caching. If credentials are absent or invalid the
  suite falls back to guest mode (the brief explicitly allows this).
- **Site profiles**: only the `default` profile (`automationexercise.com`)
  is exercised today. Adding a new profile is one entry in
  [`src/config/settings.py`](src/config/settings.py) (`PROFILES` dict).
- **Currency / decimal separator** is locale-aware via the `PriceParser`
  and the `decimal_separator` field on each profile. The default profile
  uses `Rs.` (INR) since that's what automationexercise.com displays.
- **Captcha / anti-bot challenges** are not bypassed. automationexercise.com
  is a public testing site and does not currently present any.
- **Section 5 (AI-Bugs review) is intentionally not included** - it's
  tracked as a separate task in
  [`ReadMeAIBugs.md`](ReadMeAIBugs.md).

## Project layout

```
.
+-- .cursor/                           Cursor project rules, commands, MCP
|   +-- rules/                         5 .mdc rule files (auto-applied)
|   +-- commands/                      Slash commands for repeatable workflows
|   \-- mcp.json                       Project-scoped MCP servers
+-- docs/
|   +-- personas/                      QA Architect / Test Engineer / Code Reviewer
|   \-- ai-workflow.md                 How the AI layer fits together
+-- src/
|   +-- config/                        pydantic-settings + region profiles
|   +-- pages/                         Page Object Model
|   +-- components/                    Reusable widgets
|   +-- flows/                         The 4 brief functions
|   \-- utils/                         price_parser, screenshot, logger, variant_picker
+-- tests/
|   +-- conftest.py                    Fixtures (browser/context/page, login, allure hooks)
|   +-- test_login.py                  Login flow (positive + negative, data-driven)
|   +-- test_e2e_purchase_flow.py      Headline scenario from the brief (skipped pending pivot)
|   +-- test_search_data_driven.py     Parameterized over queries.yaml (skipped pending pivot)
|   \-- test_price_parser_unit.py      Fast unit tests, no browser
+-- data/                              login.yaml + queries.yaml (data-driven inputs)
+-- scripts/
|   +-- setup-secrets.ps1              Install sops+age, generate age key
|   +-- encrypt-env.ps1                .env  ->  secrets/credentials.sops.yaml
|   +-- decrypt-env.ps1                secrets/credentials.sops.yaml  ->  .env
|   \-- make_login_evidence.py         Run login + save sanitised evidence
+-- secrets/
|   \-- credentials.sops.yaml          Encrypted credentials (committed)
+-- AGENTS.md                          Universal AI playbook
+-- README.md
+-- ReadMeAIBugs.md                    Stub for the section-5 task
+-- exercise-brief.html                Full English brief, dashboard view
+-- pyproject.toml
+-- pytest.ini
+-- .env.example
+-- .sops.yaml                         SOPS policy (which age keys may decrypt)
+-- .gitleaks.toml                     Project-specific gitleaks allow-list
+-- .pre-commit-config.yaml            gitleaks + ruff/black/hygiene hooks
\-- .gitignore
```
