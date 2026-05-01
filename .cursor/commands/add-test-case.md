# /add-test-case

Author a new pytest test that complies with this project's test rules.

## Inputs (ask if not provided)

- **Scenario name** in plain English ("user filters by brand and adds to wishlist").
- **Acceptance criteria** as Given/When/Then bullets.
- **Markers**: which of `e2e`, `smoke`, `search`, `cart`, `data_driven` apply.
- **Data-driven?** If yes, propose a YAML schema and add scenarios to `data/queries.yaml` (or a new file under `data/`).

## Steps

1. Re-read `.cursor/rules/30-test-authoring.mdc`.
2. Pick the appropriate test file (`tests/test_<area>_*.py`) or create a new one.
3. Each test:
   - Uses the `page` fixture (or `guest_page` to skip login).
   - Calls into `src/flows/` for user-flow logic; never instantiates page objects directly.
   - Wraps phases in `with allure.step(...)`.
   - Has descriptive `assert ..., "message"` failures.
   - Carries the right `@pytest.mark.<marker>` decorations.
4. If data-driven, parametrize over a list loaded from YAML and surface inputs via `allure.dynamic.parameter(...)`.

## Output

- Show the new test file diff.
- List the markers used and the YAML scenarios added.
- Suggest a single command to run only this test (e.g. `pytest tests/test_x.py::test_y -v`).
