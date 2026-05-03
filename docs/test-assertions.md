# Test Assertions Reference

> Every assertion in the E2E test suite, grouped by test.
> This document is auto-maintained alongside the test code.

---

## 1. `test_login_negative_then_positive`

**File:** `tests/test_login.py`
**Fixture:** `guest_page` (fresh browser context, no auth)
**Severity:** BLOCKER
**Tags:** `smoke`, `auth`, `login`, `brief-section-4`

A single browser window drives a wrong-password attempt, verifies the error,
then retries with correct credentials and verifies the authenticated state.

| # | Allure Step | Assertion | Failure means |
|---|-------------|-----------|---------------|
| 1 | Submit wrong credentials | `not login_page.is_authenticated()` | Bogus creds were accepted - possible auth bypass or stale session leak |
| 2 | Assert rejection | `login_page.is_on_login_page()` | User was redirected away from `/login` after a bad login |
| 3 | Assert rejection | `error_message is not None` | No visible error rendered after wrong password |
| 4 | Assert rejection | `"incorrect" in error.lower()` | Error text doesn't mention "incorrect" - site wording changed |
| 5 | Retry with real credentials | `login_page.is_authenticated()` | Real credentials from `.env` did not authenticate - account issue or site down |
| 6 | Capture username | `username` is truthy | "Logged in as \<name\>" marker not readable - selector drift |
| 7 | Assert logged out | `login_page.is_on_login_page()` | After logout the login form is not visible - no redirect to /login |
| 8 | Assert logged out | `not login_page.is_authenticated()` | After logout "Logged in as" is still visible - session not invalidated |
| 9 | Assert logged out | `"/login" in page.url` | URL doesn't contain /login after logout |

---

## 2. `test_full_purchase_flow_under_budget`

**File:** `tests/test_e2e_purchase_flow.py`
**Fixture:** `logged_in_page` (fresh context, UI login as precondition)
**Severity:** CRITICAL
**Tags:** `e2e`, `purchase-flow`, `search`, `cart`, `checkout`,
`brief-section-4-1`, `brief-section-4-2`, `brief-section-4-3`

End-to-end: clear cart -> search -> add items -> assert cart total ->
proceed to checkout -> verify summary page.

| # | Allure Step | Assertion | Failure means |
|---|-------------|-----------|---------------|
| 1 | Step 0: Clear stale cart | *(no assertion - best-effort cleanup)* | — |
| 2 | Step 1: Search | `isinstance(urls, list)` | `search_items_by_name_under_price` returned wrong type |
| 3 | Step 1: Search | `urls` is non-empty (else `pytest.skip`) | No products matched the budget - catalogue shifted |
| 4 | Step 2: Add to cart | `added > 0` | Not a single item was successfully added to cart |
| 5 | Step 3: Cart total | `subtotal <= budget_per_item * added` | Cart subtotal exceeds the calculated budget threshold |
| 6 | Step 3: Cart total | *(inside flow)* Cart is not empty | Cart appears empty even though `added > 0` - add-to-cart silently failed |
| 7 | Step 4: Checkout | `checkout.has_review_heading()` | "Review Your Order" heading not visible on `/checkout` |
| 8 | Step 4: Checkout | `checkout.has_address_heading()` | "Address Details" heading not visible on `/checkout` |
| 9 | Step 4: Checkout | `checkout.has_delivery_address()` | `#address_delivery` block missing - user has no saved address |
| 10 | Step 4: Checkout | `checkout.has_billing_address()` | `#address_invoice` block missing |
| 11 | Step 4: Checkout | `checkout.has_place_order_button()` | "Place Order" button not visible |
| 12 | Step 4: Checkout | `checkout_lines == added` | Checkout shows different item count than what was added |
| 13 | Step 4: Checkout | `checkout_total == cart_subtotal` | Checkout total differs from cart subtotal - DOM inconsistency |
| 14 | Step 4: Checkout | `float(checkout_total) <= threshold` | Checkout total exceeds budget * items |

---

## 3. `test_search_returns_urls_within_budget` (x3 scenarios)

**File:** `tests/test_search_data_driven.py`
**Fixture:** `logged_in_page` (fresh context, UI login as precondition)
**Severity:** NORMAL (MINOR for the empty-result scenario)
**Tags:** `search`, `data-driven`, `brief-section-4-1`

Data-driven from `data/queries.yaml`. Three scenarios:

| Scenario | Query | Max Price | Limit |
|----------|-------|-----------|-------|
| `full_results_tshirt` | `tshirt` | Rs. 1500 | 5 |
| `tight_budget_dress` | `dress` | Rs. 600 | 5 |
| `empty_ok_nonsense` | `asdfqwerty12345nope` | Rs. 100 | 5 |

| # | Assertion | Failure means |
|---|-----------|---------------|
| 1 | `isinstance(urls, list)` | `search_items_by_name_under_price` returned wrong type |
| 2 | `len(urls) <= scenario["limit"]` | More URLs returned than the requested limit |
| 3 | `"/product_details/" in url` (for each url) | A returned URL is not a real product detail page |
| 4 | `len(set(urls)) == len(urls)` | Duplicate URLs in the result list |

---

## Fixture-level assertions (implicit)

These are asserted inside `conftest.py` fixtures, not in test bodies:

| Fixture | Assertion | Failure means |
|---------|-----------|---------------|
| `logged_in_page` | `login_page.login(email, password)` returns `True` | Login precondition failed - `.env` credentials are wrong or site is down |

---

## Summary

| Test | Total assertions | Severity |
|------|-----------------|----------|
| `test_login_negative_then_positive` | 9 | BLOCKER |
| `test_full_purchase_flow_under_budget` | 14 | CRITICAL |
| `test_search_returns_urls_within_budget` (x3) | 4 per scenario (12 total) | NORMAL / MINOR |
| **Grand total** | **35** | |
