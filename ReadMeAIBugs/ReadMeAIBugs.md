# ReadMeAIBugs

Static-analysis review for **section 5** of the exercise brief
("Bug-Hunting Exercise"). A teammate used an AI tool to generate a
Playwright test, but it does not behave as expected. Below: the
exact snippet they shared, six concrete issues identified by reading
the code (no execution), and a line-by-line corrected version.

> Companion file: [`ReadMeAIBugs.html`](ReadMeAIBugs.html) - same
> content, dashboard-styled to match `exercise-brief.html`.

---

## The snippet under review

```python
 1  from playwright.sync_api import sync_playwright
 2  from selenium import webdriver
 3  import time
 4
 5  def test_search_functionality():
 6      browser = sync_playwright().start().chromium.launch()
 7      page = browser.new_page()
 8      page.goto("https://example.com")
 9
10      time.sleep(2)
11
12      search_box = page.locator("#search")
13      search_box.fill("playwright testing")
14
15      page.locator(".button").click()
16
17      time.sleep(3)
18
19      results = page.locator(".result-item")
20
21      browser.close()
```

---

## Issues found

Each issue follows the same shape: **Where -> Symptom -> Root cause -> Fix.**

### Issue 1 - Wrong framework imported

- **Where:** line 2 (`from selenium import webdriver`).
- **Symptom:** the test imports Selenium but never uses it. If
  Selenium isn't installed, the test fails at import time with
  `ModuleNotFoundError: No module named 'selenium'`. If it IS
  installed, it pollutes the environment with an unrelated
  dependency.
- **Root cause:** classic AI-assistant mistake - the model mixed
  Selenium and Playwright examples from its training data and left
  a dangling import. There is no Selenium API call anywhere in the
  function body; the test is 100% Playwright.
- **Fix:**
  ```diff
  - from selenium import webdriver
  ```
  Delete line 2 outright. The remaining `playwright.sync_api` import
  is sufficient (and `expect` should be added for issue 5).

---

### Issue 2 - Resource leak: Playwright driver process is never stopped

- **Where:** line 6 (`browser = sync_playwright().start().chromium.launch()`)
  combined with line 21 (`browser.close()`).
- **Symptom:** every run leaves an orphaned `node` /
  `playwright-driver` process behind. After a few runs the machine
  has dozens of stale Playwright processes; on CI this looks like
  "tests pass but the agent runs out of file descriptors".
- **Root cause:** `sync_playwright().start()` returns a
  `Playwright` handle that owns the underlying driver subprocess.
  Chaining `.chromium.launch()` immediately discards that handle,
  so there is nothing to call `.stop()` on at teardown.
  `browser.close()` only closes the Chromium browser - the driver
  itself stays alive forever. The idiomatic Playwright entrypoint
  is the `with sync_playwright() as p:` context manager, which
  calls `.stop()` automatically on exit (including on exceptions).
- **Fix:**
  ```diff
  - browser = sync_playwright().start().chromium.launch()
  - page = browser.new_page()
  + with sync_playwright() as p:
  +     browser = p.chromium.launch()
  +     context = browser.new_context()
  +     page = context.new_page()
        ...
  ```
  See the corrected version at the bottom for the full structure.

---

### Issue 3 - `time.sleep()` instead of Playwright auto-waits

- **Where:** line 10 (`time.sleep(2)`) and line 17 (`time.sleep(3)`).
- **Symptom:** the test is slow on fast machines (always burns a
  full 5 seconds even when the page is ready in 200ms) AND flaky
  on slow ones (3 seconds is sometimes not enough for the search
  results to render). Both classic anti-patterns.
- **Root cause:** Playwright's `Locator` actions (`fill`, `click`,
  etc.) auto-wait for the target element to be visible, enabled,
  and stable before acting - that's the framework's headline
  feature. Hard-coded sleeps defeat that mechanism, replacing
  reliable event-driven waits with arbitrary wall-clock pauses.
- **Fix:**
  ```diff
  - time.sleep(2)
  + page.wait_for_load_state("domcontentloaded")
    ...
  - time.sleep(3)
  + expect(page.locator(".result-item").first).to_be_visible()
  ```
  - The first sleep was meant to "wait for the page to load" - use
    `wait_for_load_state` instead, which actually waits for the
    DOM event.
  - The second sleep was meant to "wait for results to appear" -
    use `expect(locator).to_be_visible()` (or
    `to_have_count`), which auto-retries up to the configured
    timeout. Drop `import time` once both sleeps are gone.

---

### Issue 4 - Strict-mode violation: `.button` is non-unique

- **Where:** line 15 (`page.locator(".button").click()`).
- **Symptom:** Playwright raises
  `Error: locator.click: Error: strict mode violation:
  locator(".button") resolved to N elements`. The test fails -
  not because the search broke, but because the locator is
  ambiguous.
- **Root cause:** `.button` is a generic CSS class used by every
  styled button on most modern sites (Bootstrap, Tailwind component
  kits, hand-rolled design systems all reuse this name). Playwright
  defaults to **strict mode** since v1.14: any locator that
  resolves to more than one element fails the action. Even if it
  matched a single element today, the test would silently click
  the wrong button on some other page tomorrow.
- **Fix:**
  ```diff
  - page.locator(".button").click()
  + page.get_by_role("button", name="Search").click()
  ```
  Role-based locators are accessibility-driven, and the accessible
  name (`Search`) makes the intent explicit. Acceptable
  alternatives in order of preference:
  1. `page.get_by_role("button", name="Search")` - best.
  2. `page.get_by_test_id("search-submit")` - if the team owns the
     site and can add `data-testid`.
  3. `page.locator("form#search button[type='submit']")` - fallback
     when the button has no accessible name.

---

### Issue 5 - The test asserts nothing

- **Where:** line 19 (`results = page.locator(".result-item")`).
- **Symptom:** the function passes regardless of whether the search
  returned any results - even if the search box is broken, the
  page is showing "No results", or the network errored out, the
  test reports green. It is not a test, it is a script.
- **Root cause:** `page.locator(...)` returns a lazy `Locator`
  handle - it doesn't query the DOM until something is done with
  it. The variable is assigned, never read, and never compared.
  No `assert`, no `expect`, no `count()`. The author probably
  intended to verify that results appeared but stopped one line
  short.
- **Fix:**
  ```diff
  - results = page.locator(".result-item")
  + results = page.locator(".result-item")
  + expect(results.first).to_be_visible()
  + assert results.count() >= 1, (
  +     f"Search returned 0 .result-item elements - did the search "
  +     f"submit succeed?"
  + )
  ```
  Two checks because they catch different bugs:
  - `expect(results.first).to_be_visible()` auto-retries while the
    page renders (no flake).
  - `results.count() >= 1` is a hard guarantee that the assertion
    actually compared something - useful when the locator string
    itself is wrong (e.g. site renamed `.result-item` to
    `.search-result`).

---

### Issue 6 - Teardown is not exception-safe

- **Where:** line 21 (`browser.close()`).
- **Symptom:** any exception between line 6 and line 21 (a 404, a
  selector that doesn't match, a network timeout) leaves the
  Chromium process orphaned. `browser.close()` is on the happy
  path only.
- **Root cause:** no `try/finally`, no context manager, no pytest
  fixture. Python's garbage collector will eventually close the
  browser, but "eventually" can be minutes - and on Windows the
  `.exe` lock prevents a fresh test run until it does.
- **Fix:** the `with sync_playwright() as p:` block from issue 2
  already solves this for the driver; wrap the test body in a
  `try/finally` to guarantee the browser/context close even when
  an assertion fails:
  ```diff
  + try:
        page.goto(...)
        ...
  -     browser.close()
  + finally:
  +     context.close()
  +     browser.close()
  ```

---

## Bonus smells (noticed but not numbered)

These didn't make the headline list because the brief asks for "at
least 3" and the six above are clearly the highest-impact, but a
thorough reviewer should call them out:

- **`test_*` name without a pytest fixture.** The function is named
  like a pytest test but takes no `page` fixture from
  `pytest-playwright`. Under pytest, the function would still be
  collected and run, but it manages its own browser lifecycle -
  defeating the entire reason the team installed
  `pytest-playwright`. Either rename to
  `def search_demo()` (it's a script) or refactor to use the
  `page` fixture (it's a real test).
- **No `BrowserContext`.** `browser.new_page()` creates the page
  in the browser's default context - all tests would share
  cookies, storage, and viewport settings. Every test should
  create its own `browser.new_context()` for isolation.
- **No headed/slow-mo knob.** `chromium.launch()` defaults to
  headless. Adding `headless=False, slow_mo=120` (or wiring the
  decision to an env var) makes the test debuggable when it fails.

---

## Corrected version

All six issues fixed in one drop-in replacement:

```python
from playwright.sync_api import expect, sync_playwright


def test_search_functionality() -> None:
    """Search 'playwright testing' on example.com and verify results render.

    Fixes applied vs. the original snippet:
        1. Removed the unused ``selenium`` import.
        2. Wrapped Playwright bring-up in a ``with sync_playwright()``
           context manager so the driver process is always stopped.
        3. Replaced both ``time.sleep`` calls with event-driven waits.
        4. Replaced the brittle ``.button`` locator with a role-based
           locator that has an explicit accessible name.
        5. Added ``expect`` + ``assert`` so the test actually verifies
           the search returned results.
        6. Wrapped the test body in ``try/finally`` so the browser is
           closed even if an assertion fails.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(
                "https://example.com",
                wait_until="domcontentloaded",
            )

            page.locator("#search").fill("playwright testing")
            page.get_by_role("button", name="Search").click()

            results = page.locator(".result-item")
            expect(results.first).to_be_visible()
            assert results.count() >= 1, (
                "Search returned 0 .result-item elements - did the "
                "search submit succeed?"
            )
        finally:
            context.close()
            browser.close()
```

---

## Summary table

| # | Severity | Category | One-line fix |
|---|---|---|---|
| 1 | Low | Hygiene | Delete the `selenium` import. |
| 2 | High | Resource leak | Use `with sync_playwright() as p:` instead of `.start()`. |
| 3 | High | Flake / Speed | Replace `time.sleep` with `wait_for_load_state` / `expect`. |
| 4 | High | Brittle locator | Use `get_by_role("button", name="Search")`. |
| 5 | Critical | False green | Add `expect(...)` + `assert results.count() >= 1`. |
| 6 | Medium | Teardown | Wrap body in `try/finally`. |

Critical = test passes when the feature is broken. High = test fails or flakes for the wrong reason. Medium / Low = code-quality smell that bites later.
