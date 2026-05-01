# /debug-failing-locator

Diagnose a failing or flaky locator and propose a stable replacement.

## Inputs (ask if not provided)

- **The locator** (selector string) and **the file/line** where it lives.
- **What it's supposed to match** (button label, field name, etc.).
- **Reproduction**: target URL or pytest command that exposes the failure.

## Steps

1. Read the affected page object and its component imports.
2. Use the **Playwright MCP** (configured in `.cursor/mcp.json`) to:
   - Navigate to the affected URL.
   - Take an accessibility snapshot.
   - Identify candidate elements that match the intent.
3. Re-read `.cursor/rules/40-locator-strategy.mdc`.
4. Propose 2-3 candidate selectors, in priority order:
   1. Role + accessible name
   2. data-testid
   3. Visible text
   4. CSS attribute selector
   5. XPath (last resort)
5. Update the page object to use the **multiple-candidate tuple pattern** (see `LoginPage.EMAIL_CANDIDATES`).
6. If the new locator depends on text that may be localised, add a TODO comment with the affected locales (`us`, `uk`, etc.) so future maintainers update them.

## Output

- A diff of the page object change.
- A short note explaining why the chosen selector(s) are more stable than the original.
- If the issue cannot be solved by a locator change (e.g. the element only appears after scroll/hover), flag the root cause instead of patching around it.
