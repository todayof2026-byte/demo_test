# /add-page-object

Add a new page object that complies with this project's POM rules.

## Inputs (ask if not provided)

- **Page name** (e.g. `WishlistPage`, `CheckoutPage`).
- **URL path** relative to `BASE_URL` (e.g. `/wishlist`, `/checkout`).
- **Public actions** the page must expose, as a bullet list.
- **Reusable widgets** the page uses (header, paginator, etc.) - look in `src/components/`.

## Steps

1. Re-read `.cursor/rules/20-playwright-pom.mdc` and `.cursor/rules/40-locator-strategy.mdc`.
2. Create `src/pages/<snake_case_name>.py`:
   - Module docstring describing what the page wraps.
   - Class extends `BasePage` (`from src.pages.base_page import BasePage`).
   - Class-level `URL_PATH` constant.
   - Class-level **selector candidate tuples** (UPPER_SNAKE) for every locator.
   - Constructor calls `super().__init__(page)` and instantiates any components.
   - Public methods describe **user actions** (no generic `click_X`).
   - **No** assertions, **no** Allure decorators, **no** `time.sleep`.
3. Re-export the class from `src/pages/__init__.py`.
4. If a new reusable widget shows up, add it to `src/components/` instead of inlining it.
5. If the page uses the Playwright MCP, run `/debug-failing-locator` first to discover stable selectors before writing them.

## Output

- Print a short summary of what was created and which selectors were chosen.
- List any TODOs the implementer must verify against a real page.
