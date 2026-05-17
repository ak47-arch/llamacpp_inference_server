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

All feature work in this repository must be executed through the `feature-development` skill. This is a hard requirement. Agents must not bypass the skill and perform ad-hoc feature implementation outside the workflow it defines.

Feature development uses stable capability-based specs under `specs/` instead of date-based or chronological specs. When a change affects an existing capability, the owning canonical spec is updated in place. When no spec exists for an affected capability, the first change bootstraps a canonical spec for that capability from the current code reality before describing the approved new target behavior.

When a user request contains multiple requirements, the workflow must decompose the request into distinct requirement items before drafting or updating specs. For each requirement item, the workflow must identify the owning canonical spec and owning module boundary.

If multiple requirement items map to different canonical specs, they are treated as separate features even if they were requested in the same user message. The workflow must then determine whether those features are independent or whether one depends on another.

Independent features may be developed in parallel. Dependent features must be developed sequentially in dependency order. This decomposition and dependency analysis must work for any number of requirement items, not only two.

When multiple independent features are discovered in one session, each feature still requires its own canonical-spec lifecycle: separate approval, separate spec commit, separate traceability recording, and separate implementation traceability.

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

Workflow decomposition interface for any feature request:

- Input: one user request containing requirement items `R1..Rn`
- For each `Ri`:
  - determine owning spec
  - determine owning module boundary
  - determine whether a canonical spec already exists
- Build a dependency graph across `R1..Rn`
- Partition requirement items into feature groups by owning canonical spec
- Execution mode:
  - parallel for independent feature groups
  - sequential in dependency order for dependent feature groups
- Output: one explicit lifecycle per feature group, each with its own approval, commits, traceability, and verification

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

Required in-memory workflow planning model for a multi-requirement request:

- `requirements[]`: list of `{id, summary, owning_spec, owning_modules}`
- `feature_groups[]`: list of `{owning_spec, requirement_ids[]}`
- `dependencies[]`: directed edges `{from_feature_group, to_feature_group}`
- `execution_plan`: either parallel feature groups or a dependency-ordered sequence

## Rules and Invariants

1. All feature implementations must use the `feature-development` skill. This is mandatory.
2. Canonical specs are organized by capability, subsystem, or enduring domain area.
3. Canonical specs are updated in place whenever related behavior changes.
4. The main body of a canonical spec describes current truth only.
5. This repository does not use chronological or numbered spec files for new work.
6. The first change in an undocumented capability area must bootstrap a canonical spec for that area.
7. A request containing multiple requirements must be decomposed into individual requirement items before spec drafting begins.
8. Requirement items that map to different canonical specs are separate features.
9. The workflow must perform dependency analysis across all discovered features.
10. Independent features may proceed in parallel.
11. Dependent features must proceed sequentially in dependency order.
12. Even when multiple independent features are discovered together, each feature must keep its own approval, spec commit, traceability entries, implementation commit, and verification status.
13. Every non-traceability commit that changes a canonical spec must be appended to that spec and to `CHANGELOG.md` in the immediately following traceability commit.
14. Every implementation commit tied to a canonical spec must be appended to that spec and to `CHANGELOG.md` in the immediately following traceability commit.
15. Traceability-only commits do not self-record.

## Edge Cases

- If a change spans multiple capabilities, each affected canonical spec must be updated or one owning spec must explicitly define the boundary.
- If multiple requirements mention the same capability, they may remain one feature group under a single owning spec.
- If multiple requirements mention different capabilities but one cannot be implemented correctly without another landing first, they must be split into separate features and executed sequentially.
- If multiple requirements are independent but share a discovery session, they may share discovery notes but not approval or traceability lifecycles.
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
7. Repository documentation states that all feature work must use the `feature-development` skill and treats that requirement as mandatory.
8. Repository documentation requires decomposition of multi-requirement requests into individual requirement items before spec drafting.
9. Repository documentation defines that requirement items mapping to different canonical specs are separate features.
10. Repository documentation defines dependency analysis across all discovered features and supports both parallel and sequential execution planning.
11. Repository documentation requires separate approval and traceability lifecycles for each independent feature, even when discovered in one session.
12. Pi workflow skills and prompts align with the canonical-spec workflow, the mandatory skill requirement, and the multi-feature decomposition rules.
13. README points readers to the workflow documentation and related artifacts.

## Test Plan

- Review workflow documentation for canonical-spec terminology, in-place update rules, and the hard requirement to use the `feature-development` skill for all feature work.
- Review workflow documentation and skill text for multi-requirement decomposition, feature grouping by owning spec, and dependency analysis across `R1..Rn`.
- Review workflow documentation and skill text for separate approval and traceability lifecycles per independent feature.
- Review workflow skill text for spec commit and implementation traceability steps.
- Review `CHANGELOG.md` and canonical spec format for append-only hash recording structure.
- Review README for workflow pointers.

## Out of Scope

- Defining application runtime APIs or provider behavior
- Backfilling canonical specs for every existing subsystem in one change
- Importing archived historical specs from the previous project

## Traceability

### Spec Commits

- 2026-05-17 | bc417fa8b7e2ba2c919635f1f2c812eda4b2fefe | add canonical feature development workflow spec
- 2026-05-17 | e296e5ac8d69b3d44a398388ed95492fc5ec8c2b | require feature-development skill and multi-feature dependency planning

### Implementation Commits

- 2026-05-17 | ec4d80472f3d2093cb4d983edf1d4fa4f3e22451 | align repository docs and skills with canonical specs
