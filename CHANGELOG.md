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
- Feature work now hard-requires the `feature-development` skill, with multi-requirement decomposition and dependency planning rules.
- Added a canonical spec for bundled OpenAI-compatible provider config and request-defaulting behavior.
- Bundled provider config now includes E4B Q4, keeps reasoning flags commented out, and no longer injects implicit temperature/max_tokens defaults.
- Added a canonical monitoring and observability spec for Prometheus metrics, readiness telemetry, and managed runtime startup instrumentation.
- Implemented Prometheus `/metrics`, request/readiness metrics, and managed llama-server startup/restart telemetry.

### Traceability Ledger

- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: bc417fa8b7e2ba2c919635f1f2c812eda4b2fefe | summary: add canonical feature development workflow spec
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: ec4d80472f3d2093cb4d983edf1d4fa4f3e22451 | summary: align repository docs and skills with canonical specs
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: e296e5ac8d69b3d44a398388ed95492fc5ec8c2b | summary: require feature-development skill and multi-feature dependency planning
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: 00d06ba5f804a325197e9d1d1aaa54434786171f | summary: require workflow skill and multi-feature planning in docs and prompts
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: spec | commit: 0affeba38d2f6c8f7cfe1652875649d54e8d8e40 | summary: consolidate bundled provider config and defaulting rules into canonical spec
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: implementation | commit: 4fbdb89841c35c5b522c187508dd04c3208bc476 | summary: add e4b q4 provider and remove implicit temperature and max_tokens defaults
- 2026-05-17 | spec: specs/monitoring.md | kind: spec | commit: 297a8299eb0eca77c33cd9118227f818e2b57cf2 | summary: add canonical monitoring and observability spec
- 2026-05-17 | spec: specs/monitoring.md | kind: implementation | commit: 99b4ff5d9b49d5220a7860ef52b693be064326b4 | summary: add Prometheus metrics endpoint and runtime telemetry
