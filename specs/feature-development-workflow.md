# Feature Development Workflow

## Status

APPROVED

## Purpose

Define how feature work is specified, implemented, verified, and traced in this repository so that canonical specs remain the current source of truth while commit hashes remain directly usable by agents.

## Scope

This spec covers the repository workflow for creating and updating canonical specs, recording traceability, updating workflow documentation, and coordinating the supporting Pi skills and prompts.

It does not define application runtime behavior.

## Module Ownership

Owning documentation and workflow artifacts:

- `docs/FEATURE_DEVELOPMENT_WORKFLOW.md`
- `specs/feature-development-workflow.md`
- `specs/TEMPLATE.md`
- `CHANGELOG.md`
- `.agents/skills/feature-development/SKILL.md`
- `.agents/skills/feature-traceability/SKILL.md`
- `.pi/prompts/feature-development.md`
- `README.md`

The workflow skill is the execution entry point. The canonical spec and workflow document are the durable description. README remains a pointer, not the full source of truth.

## Current Behavior

Feature development uses stable capability-based specs under `specs/` instead of date-based or chronological specs. When a change affects an existing capability, the owning canonical spec is updated in place. When no spec exists for an affected capability, the first change bootstraps a canonical spec for that capability from the current code reality before describing the approved new target behavior.

The main body of each canonical spec describes only the current truth of the system. Superseded behavior is not preserved as a timeline in the main spec body.

Every non-traceability commit that changes a canonical spec or implements behavior governed by a canonical spec must be recorded in both the owning spec and `CHANGELOG.md` by a dedicated follow-up traceability commit. Traceability-only commits do not record themselves.

## Interfaces

Workflow-facing artifacts and interfaces:

- Canonical specs live in `specs/*.md` using stable capability names.
- New canonical specs start from `specs/TEMPLATE.md`.
- Human-readable workflow guidance lives in `docs/FEATURE_DEVELOPMENT_WORKFLOW.md`.
- Pi feature orchestration entry point: `.pi/prompts/feature-development.md`.
- Pi skills implementing workflow rules:
  - `.agents/skills/feature-development/SKILL.md`
  - `.agents/skills/feature-traceability/SKILL.md`
- Traceability ledger: `CHANGELOG.md`.

## Data Model

Required workflow metadata for each canonical spec:

- `Status`: one of `DRAFT`, `APPROVED`, `VERIFIED`, `DEPRECATED`
- `Traceability.Spec Commits[]`: append-only list of `{date, commit_hash, summary}`
- `Traceability.Implementation Commits[]`: append-only list of `{date, commit_hash, summary}`

Required workflow metadata for each changelog traceability entry:

- `date`
- `spec path`
- `kind`: `spec` or `implementation`
- `commit hash`
- `summary`

## Rules and Invariants

1. Canonical specs are organized by capability, subsystem, or enduring domain area.
2. Canonical specs are updated in place whenever related behavior changes.
3. The main body of a canonical spec describes current truth only.
4. This repository does not use chronological or numbered spec files for new work.
5. The first change in an undocumented capability area must bootstrap a canonical spec for that area.
6. Every non-traceability commit that changes a canonical spec must be appended to that spec and to `CHANGELOG.md` in the immediately following traceability commit.
7. Every implementation commit tied to a canonical spec must be appended to that spec and to `CHANGELOG.md` in the immediately following traceability commit.
8. Traceability-only commits do not self-record.

## Edge Cases

- If a change spans multiple capabilities, each affected canonical spec must be updated or one owning spec must explicitly define the boundary.
- If implementation reveals the approved spec is incomplete or wrong, the same canonical spec must be updated in place rather than creating a new chronological spec.
- If historical specs from a previous project are imported, they must live under `specs/archive/` and clearly point to the canonical spec that supersedes them.
- If a change is documentation-only but changes canonical workflow behavior, it still requires commit-hash traceability.

## Acceptance Criteria

1. Repository documentation describes feature development in terms of living canonical specs updated in place.
2. Repository documentation states that canonical specs are the source of truth for current behavior.
3. Repository documentation states that chronological or numbered specs are not used for new work.
4. Repository documentation defines the bootstrap rule for capability areas that do not yet have canonical specs.
5. Repository documentation requires appending spec-change and implementation commit hashes to both the owning spec and `CHANGELOG.md`.
6. Repository documentation explicitly exempts traceability-only commits from self-recording.
7. Pi workflow skills align with the canonical-spec workflow and traceability rules.
8. README points readers to the workflow documentation and related artifacts.

## Test Plan

- Review workflow documentation for canonical-spec terminology and in-place update rules.
- Review workflow skill text for spec commit and implementation traceability steps.
- Review `CHANGELOG.md` and canonical spec format for append-only hash recording structure.
- Review README for workflow pointers.

## Out of Scope

- Defining application runtime APIs or provider behavior
- Backfilling canonical specs for every existing subsystem in one change
- Importing archived historical specs from the previous project

## Traceability

### Spec Commits

### Implementation Commits
