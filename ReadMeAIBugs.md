# ReadMeAIBugs

> **Status**: not implemented yet. This file is a placeholder for the
> exercise's section 5 ("Bug-Hunting Exercise"), which is tracked as a
> separate task from the main framework build.

## What this file will contain

Per the brief (section 5), this is a static-analysis exercise: a teammate
used an AI tool to generate test code that "doesn't work as expected". The
deliverable is to:

1. Identify **at least 3 issues** in the AI-generated code.
2. Explain each issue **in detail** - what's wrong and *why* it's wrong.
3. Propose a **line-by-line fix** for each problematic block.

## Suggested structure (to be filled in)

```markdown
## Issue #1 - <short title>
**Where:** `<file>:<line-range>`
**Symptom:** <what fails / wrong behaviour>
**Root cause:** <why>
**Fix:**
<unified diff or annotated snippet>

## Issue #2 ...
## Issue #3 ...
```

## Why it isn't here yet

This branch is scoped to delivering the framework itself (architecture,
POM, the four flow functions, data-driven, reports, AI-tooling layer). The
bug-hunt is a self-contained exercise that doesn't depend on the framework
above and is best done as a separate, focused review pass.
