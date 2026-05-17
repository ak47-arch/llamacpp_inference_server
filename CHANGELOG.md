# Changelog

This file is both:

1. a concise human-readable change summary, and
2. an append-only traceability ledger for agents.

## Rules

- Record every non-traceability commit that changes a canonical spec.
- Record every implementation commit tied to a canonical spec.
- Record those hashes in the immediately following traceability commit.
- Do not self-record traceability-only commits.

## Unreleased

### Summary

- Workflow documentation migrated to living canonical specs with append-only commit-hash traceability.
- Added the canonical spec, template, workflow guide, README pointers, and Pi workflow updates for feature development.

### Traceability Ledger

- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: bc417fa8b7e2ba2c919635f1f2c812eda4b2fefe | summary: add canonical feature development workflow spec
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: ec4d80472f3d2093cb4d983edf1d4fa4f3e22451 | summary: align repository docs and skills with canonical specs
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: e296e5ac8d69b3d44a398388ed95492fc5ec8c2b | summary: require feature-development skill and multi-feature dependency planning
