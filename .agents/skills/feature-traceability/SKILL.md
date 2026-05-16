---
name: feature-traceability
description: "Use when finishing any feature implementation and preparing commits. Ensures spec and changelog are updated with the implementation commit hash in a mandatory follow-up traceability commit."
---

# Feature Traceability Skill

## Goal

Enforce commit-hash traceability for every feature.

## Required Workflow

1. Make the implementation commit.
2. Read the resulting commit hash.
3. Add the hash to:
   - the feature spec file in `specs/`
   - `CHANGELOG.md`
4. Create a second commit containing only traceability/instruction updates.

## Completion Criteria

- Spec references implementation hash.
- Changelog references same implementation hash.
- Follow-up traceability commit exists.
