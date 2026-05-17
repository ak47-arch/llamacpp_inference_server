---
name: feature-traceability
description: "Use when a canonical spec or its implementation has been committed. Ensures the preceding non-traceability commit hash is appended to the owning spec and CHANGELOG.md in a mandatory follow-up traceability commit."
---

# Feature Traceability Skill

## Goal

Enforce append-only commit-hash traceability for living canonical specs.

## Required Workflow

1. Create a non-traceability commit that either:
   - changes a canonical spec, or
   - implements behavior governed by a canonical spec.
2. Read the resulting commit hash.
3. Append the hash to:
   - the owning spec file in `specs/` under `## Traceability`
   - `CHANGELOG.md`
4. Create a second commit containing only traceability updates.

## Important Rule

Traceability-only commits do **not** record themselves. They exist only to record the immediately preceding non-traceability commit. This prevents infinite recursion.

## Completion Criteria

- The preceding non-traceability commit hash is present in the owning spec.
- The same hash is present in `CHANGELOG.md`.
- A follow-up traceability commit exists.
