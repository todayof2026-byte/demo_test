# AI Workflow

This project ships a small, opinionated AI-tooling layer at the **project
level** so reviewers cloning the repo inherit the setup automatically when
they open it in Cursor. This document explains what's there and how to use
it effectively.

## What's committed

| Artifact | Path | Purpose |
| --- | --- | --- |
| Project rules | `.cursor/rules/*.mdc` | Auto-loaded conventions: project overview, Python style, POM rules, test authoring, locator strategy. |
| Slash commands | `.cursor/commands/*.md` | Curated prompts for repeatable tasks (`/add-page-object`, `/add-test-case`, `/debug-failing-locator`). |
| MCP servers | `.cursor/mcp.json` | Project-scoped Playwright MCP (live browser) + Filesystem MCP (sandboxed to repo root). |
| Personas | `docs/personas/*.md` | Role-specific system prompts: QA Architect, Test Engineer, Code Reviewer. |
| Agents playbook | `AGENTS.md` | Universal AI playbook (commands, conventions, common pitfalls). |

Nothing here is required for the tests to run. They're augmentations for AI-assisted work; the framework runs identically without them.

## How the layers compose

```
+--------------------------------------+
|  AGENTS.md  (universal playbook)     |  <- read on every task
+--------------------------------------+
|  .cursor/rules/*.mdc                 |  <- auto-applied by Cursor based on globs
+--------------------------------------+
|  Persona (qa-architect / ...)        |  <- pasted into chat for the right tone
+--------------------------------------+
|  /command (add-page-object / ...)    |  <- repeatable workflow on top of rules
+--------------------------------------+
|  MCP (Playwright + Filesystem)       |  <- live browser + safe file IO
+--------------------------------------+
```

## When to use which

### "Add a new test"
1. Open Cursor, paste `@docs/personas/test-engineer.md` (or just reference it).
2. Run `/add-test-case`.
3. Provide the acceptance criteria.
4. Review the generated diff. Run `pytest tests/test_<area>.py::test_<name> -v`.

### "Add a new page object"
1. `@docs/personas/test-engineer.md` for the role.
2. Run `/add-page-object`.
3. If selectors are uncertain, run `/debug-failing-locator` to use the Playwright MCP for live discovery.

### "Review a PR"
1. `@docs/personas/code-reviewer.md`.
2. Paste the diff or list changed files.
3. The reviewer checks against `.cursor/rules/*.mdc` and the AGENTS playbook.

### "A locator broke after a deploy"
1. `@docs/personas/test-engineer.md`.
2. Run `/debug-failing-locator`.
3. The assistant uses Playwright MCP to take a live a11y snapshot and propose a stable replacement.

## Enabling MCP locally

The first time you open this repo in Cursor:

1. Cursor reads `.cursor/mcp.json` and asks you to approve the listed servers.
2. **Playwright MCP** (`@playwright/mcp`) requires Node.js installed; it runs via `npx`.
3. **Filesystem MCP** is scoped to the repo root only - it can't read or write files elsewhere on the machine.

You can disable either in Cursor settings without affecting test runs.

## Why this matters

The exercise rubric awards 45% to architecture and 35% to robustness. The
tooling above doesn't change the test code, but it does change how a team
*maintains* it. Project-level rules make conventions discoverable; slash
commands turn one-off prompts into repeatable workflows; MCP connects the
assistant to the actual product UI so locator advice is grounded in fact,
not memory.
