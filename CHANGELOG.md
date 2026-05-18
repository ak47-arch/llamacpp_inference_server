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
- Added a canonical spec for isolated subagent verification commands and artifact-limited verifier handoffs.
- Recorded latest spec-verifier audit reports for the multimodal OpenAI-compatible provider and operational logging specs.
- Those two specs remain APPROVED with documented verifier findings; they are not yet VERIFIED.

### Traceability Ledger

- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: bc417fa8b7e2ba2c919635f1f2c812eda4b2fefe | summary: add canonical feature development workflow spec
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: ec4d80472f3d2093cb4d983edf1d4fa4f3e22451 | summary: align repository docs and skills with canonical specs
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: spec | commit: e296e5ac8d69b3d44a398388ed95492fc5ec8c2b | summary: require feature-development skill and multi-feature dependency planning
- 2026-05-17 | spec: specs/feature-development-workflow.md | kind: implementation | commit: 00d06ba5f804a325197e9d1d1aaa54434786171f | summary: require workflow skill and multi-feature planning in docs and prompts
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: spec | commit: 0affeba38d2f6c8f7cfe1652875649d54e8d8e40 | summary: consolidate bundled provider config and defaulting rules into canonical spec
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: implementation | commit: 4fbdb89841c35c5b522c187508dd04c3208bc476 | summary: add e4b q4 provider and remove implicit temperature and max_tokens defaults
- 2026-05-17 | spec: specs/monitoring.md | kind: spec | commit: 297a8299eb0eca77c33cd9118227f818e2b57cf2 | summary: add canonical monitoring and observability spec
- 2026-05-17 | spec: specs/monitoring.md | kind: implementation | commit: 99b4ff5d9b49d5220a7860ef52b693be064326b4 | summary: add Prometheus metrics endpoint and runtime telemetry
- 2026-05-17 | spec: specs/subagents.md | kind: spec | commit: ec7e0e02196dddeb848d84e8a88baaf474fe5868 | summary: add canonical isolated subagent verification commands spec
- 2026-05-17 | spec: specs/openai-compatible-provider.md | kind: spec | commit: bc6b4c9b70a7bd418991d808765f54210e60fc93 | summary: add multimodal pass-through and managed projector configuration to canonical spec
- 2026-05-17 | spec: specs/operational-logging.md | kind: spec | commit: 46e4e3fbf081af3ff6e11954031464a04ad8c8e3 | summary: add canonical operational logging spec
- 2026-05-18 | spec: specs/openai-compatible-provider.md | kind: spec | commit: 6f2f3e924021d83048462b5e4353ac924a7207d0 | summary: record multimodal provider verifier audit reports and status note
- 2026-05-18 | spec: specs/operational-logging.md | kind: spec | commit: 6f2f3e924021d83048462b5e4353ac924a7207d0 | summary: record operational logging verifier audit reports and status note
