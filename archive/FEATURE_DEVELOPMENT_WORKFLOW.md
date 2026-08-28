> **DEPRECATED** — This file is part of the retired spec-driven development process (2026-08-28).
> The factory workflow (PRDs at `docs/prd/` + vision docs at `docs/vision/`) replaces it.
> Retained for retrospective analysis only. Do not use as active guidance.

# Feature Development Workflow

This repository uses **living canonical specs** rather than chronological per-change specs.

## Why

Chronological specs become a history of intent, not a description of the current system. As code evolves, the only way to reconstruct truth is to replay old specs in sequence against code history. That is not a feasible source-of-truth model for humans or agents.

## Core Rules

1. **All feature work must use the `feature-development` skill.**
   - This is a hard requirement.
   - Do not perform ad-hoc feature implementation outside that workflow.
2. **Specs are organized by capability, subsystem, or domain area.**
   - Use stable names such as `specs/routing.md`, `specs/provider-config.md`, `specs/local-runtime.md`.
   - Do not create date-based or numbered spec files.
3. **Specs are updated in place.**
   - When work is related to an existing capability, update the existing canonical spec.
   - Create a new spec only when the work introduces a new enduring capability or boundary.
4. **The main body of a spec describes current truth only.**
   - Remove or rewrite superseded behavior in the main sections.
   - Do not accumulate outdated behavior as a timeline in the spec body.
5. **Commit-hash traceability is mandatory.**
   - Every non-traceability commit that changes a canonical spec must be recorded in that spec and in `CHANGELOG.md`.
   - Every implementation commit must also be recorded in that spec and in `CHANGELOG.md`.
6. **Traceability is append-only.**
   - New traceability entries are appended; older entries are never rewritten except to fix formatting mistakes.
7. **Traceability-only commits are exempt from self-recording.**
   - Otherwise the workflow would recurse forever.
   - A traceability commit exists to record the hash of the immediately preceding non-traceability commit.
8. **Multi-requirement requests must be decomposed before spec drafting.**
   - Break the request into requirement items `R1..Rn`.
   - Identify the owning canonical spec and module boundary for each item.
   - Requirement items mapping to different canonical specs are separate features.
9. **Execution planning depends on feature dependencies.**
   - Independent features may proceed in parallel.
   - Dependent features must proceed sequentially in dependency order.
   - Even when discovered in one session, each independent feature keeps separate approval, spec, and traceability lifecycles.

## Repository Artifacts

- `specs/` — canonical living specs; source of truth for current behavior
- `specs/TEMPLATE.md` — required structure for new canonical specs
- `specs/feature-development-workflow.md` — canonical spec for this workflow
- `CHANGELOG.md` — append-only human + agent traceability ledger
- `docs/FEATURE_DEVELOPMENT_WORKFLOW.md` — this workflow document
- `specs/archive/` — optional archive for imported historical specs from older projects; never source of truth

## Status Values

Canonical specs use these statuses:

- `DRAFT` — proposed changes not yet approved
- `APPROVED` — approved target behavior; implementation may still be pending
- `VERIFIED` — code and tests currently match the spec
- `DEPRECATED` — no longer active; retained only for reference

## Choosing the Owning Spec

For every requested change:

1. Identify the capability or subsystem being changed.
2. Search `specs/` for the canonical spec for that area.
3. Decide one of the following:
   - **Update existing spec** — the change extends, fixes, or refines existing behavior.
   - **Create new spec** — the change introduces a new enduring capability or module boundary.
   - **Split/merge spec boundaries** — only when an existing spec has become too broad or two specs actually describe one capability.

Bias toward updating an existing spec.

## Bootstrap Rule for This Repository

This project currently has **no independent canonical specs**.

Therefore, the first change in any capability area must begin by creating a canonical spec from the **current code reality** for that area before the new behavior is added.

Bootstrap only the area being changed. Do **not** try to backfill the whole repository in one pass.

Example:

- Change request affects request routing.
- No `specs/routing.md` exists.
- First create `specs/routing.md` from the current routing behavior in code.
- Then update that same spec in place to reflect the approved new behavior.
- Implement against the updated spec.

## Standard Workflow

### Phase 0 — Discovery

- Clarify the requested behavior and boundaries.
- If the request contains multiple requirements, decompose it into requirement items `R1..Rn` before drafting specs.
- Identify the owning module or subsystem for each requirement item.
- Identify the owning canonical spec for each requirement item.
- If different requirement items map to different canonical specs, treat them as separate features.
- Determine whether the discovered features are independent or dependency-ordered.
- If none exists, plan a bootstrap spec for the affected area.

### Phase 1 — Spec Update

- Create or update the canonical spec in `specs/`.
- Use a stable capability filename.
- Make the spec describe the new intended current truth.
- Keep only current behavior in the main body.
- Add or update acceptance criteria and tests.
- Mark the spec `DRAFT` until approved.
- If multiple independent features were discovered, each feature gets its own spec lifecycle even if discovery was shared.

### Phase 2 — Approval

- Obtain explicit approval for the spec.
- Change status to `APPROVED`.

### Phase 3 — Spec Commit

- Commit the approved spec change as a **spec commit**.
- This commit may contain the canonical spec and closely related workflow/template updates only.

Recommended message:

```text
spec(<capability>): update canonical spec
```

### Phase 4 — Spec Traceability Commit

- Capture the hash of the spec commit.
- Append that hash to:
  - the owning canonical spec under `## Traceability`
  - `CHANGELOG.md`
- Create a **traceability-only** follow-up commit.

Recommended message:

```text
chore(traceability): record spec commit for <capability>
```

### Phase 5 — Tests First

- Write or update tests from the approved spec.
- Confirm tests fail before implementation.
- Ensure tests encode the acceptance criteria rather than implementation details.

### Phase 6 — Implementation

- Implement the minimum code required to satisfy the spec.
- Run the full relevant test suite until green.
- If implementation reveals that the spec must change, stop and return to **Phase 1**.
  - Update the same canonical spec in place.
  - Commit the spec change.
  - Record its commit hash in a traceability commit.
  - Then continue implementation.

### Phase 7 — Verification

- Verify code, tests, and spec all match.
- Confirm the canonical spec is still accurate as current truth.
- Change status to `VERIFIED` when the spec is aligned with the implemented system.

### Phase 8 — Implementation Commit

- Create the implementation commit.

Recommended message:

```text
feat(<capability>): <summary>
```

### Phase 9 — Implementation Traceability Commit

- Capture the implementation commit hash.
- Append that hash to:
  - the owning canonical spec under `## Traceability`
  - `CHANGELOG.md`
- Create a **traceability-only** follow-up commit.

Recommended message:

```text
chore(traceability): record implementation commit for <capability>
```

## Traceability Rules

### What must be recorded

Record every **non-traceability** commit that:

- creates or updates a canonical spec
- implements behavior governed by a canonical spec
- materially changes acceptance criteria or verification evidence for a canonical spec

### What does not get recorded

Do not self-record pure traceability commits.

### Canonical spec traceability format

Each canonical spec must contain a `## Traceability` section with at least:

- `### Spec Commits`
- `### Implementation Commits`

Append entries using this format:

```text
- YYYY-MM-DD | <commit-hash> | <summary>
```

### Changelog traceability format

`CHANGELOG.md` must keep matching append-only entries so an agent can find the same hash from either location.

## Changelog Rules

`CHANGELOG.md` serves two audiences:

1. humans looking for a concise summary of changes
2. agents looking for machine-friendly commit traceability

Every recorded hash should identify:

- date
- capability/spec name
- commit hash
- commit kind (`spec` or `implementation`)
- short summary

## PR / Review Checklist

Every feature change should be reviewed against this checklist:

- [ ] `feature-development` skill used for the feature
- [ ] Owning canonical spec identified
- [ ] Multi-requirement requests decomposed into requirement items before spec drafting
- [ ] Different owning specs treated as separate features
- [ ] Dependencies analyzed to decide parallel vs sequential execution
- [ ] Existing spec updated in place, or new spec justified
- [ ] Spec main body reflects current truth only
- [ ] Spec approved before implementation
- [ ] Spec commit created
- [ ] Spec commit hash appended to spec and changelog in a traceability commit
- [ ] Tests derived from spec and fail before implementation
- [ ] Implementation matches acceptance criteria
- [ ] Implementation commit created
- [ ] Implementation commit hash appended to spec and changelog in a traceability commit
- [ ] Final spec status is `VERIFIED`

## Naming Guidance

Prefer stable filenames such as:

- `specs/routing.md`
- `specs/providers.md`
- `specs/openai-compatible-api.md`
- `specs/local-server-runtime.md`

Avoid:

- `specs/2026-05-17-001-routing.md`
- `specs/034-provider-cleanup.md`

## Migration Guidance

If historical specs from the previous project are imported later:

- place them in `specs/archive/`
- add a banner stating they are not source of truth
- link each archived spec to the owning canonical spec in `specs/`

The canonical spec remains the only current truth document.
