---
name: tdd-karpathy-guidelines
description: Strict TDD-first coding discipline plus surgical Karpathy-style constraints. Use when writing, reviewing, refactoring, or debugging code.
license: MIT
---

# TDD Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876), with **mandatory test-driven development**.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them instead of choosing silently.
- If a simpler approach exists, call it out.
- If requirements are unclear, stop and clarify.

## 2. TDD Is Mandatory

**No production code without a failing test first.**

Required loop for every behavior change:
1. Write or update a test that fails for the intended behavior.
2. Run the targeted test to confirm failure.
3. Write the minimum production code required to pass.
4. Re-run targeted tests, then relevant suite tests.
5. Refactor only with tests staying green.

Hard rules:
- Do not skip the red step.
- Do not merge code that lacks a test covering the changed behavior.
- For bug fixes, the first artifact is a failing regression test.

## 3. Simplicity First

**Minimum code that solves the tested requirement. Nothing speculative.**

- No features beyond what was requested.
- No abstractions for single-use paths.
- No speculative flexibility.
- Keep implementations as small as possible while passing tests.

## 4. Surgical Changes

**Touch only what the tests and request require.**

- Avoid unrelated refactors or formatting edits.
- Match existing project style and structure.
- Remove only the dead code introduced by your own change.

The test: each changed line should map to a failing test or explicit user requirement.

## 5. Goal-Driven Verification

**Define success as executable checks and finish only when green.**

For multi-step tasks, write a short plan with checks:
```
1. Add failing test -> verify: test fails for expected reason
2. Implement minimum fix -> verify: targeted tests pass
3. Run relevant suite -> verify: no regressions
```

If verification fails, continue iterating until all required checks are green.
