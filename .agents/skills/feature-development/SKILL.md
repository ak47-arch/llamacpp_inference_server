---
name: feature-development
description: Orchestrates the full feature lifecycle using living canonical specs: discovery → canonical spec update/creation → approval → spec commit + traceability → TDD → implementation → audit loop → implementation traceability.
license: Internal
---

# Feature Development

Pi-compatible conversion of `.github/agents/feature-development.agent.md` adapted for living canonical specs.

> Pi compatibility note: Pi does not provide built-in subagents. When this skill requires a fresh subagent for independent verification, use a separate fresh Pi session or an equivalent isolated workflow if no subagent extension is installed.

You are the feature development orchestrator for this repository. Your job is to drive the complete lifecycle from canonical spec through verified implementation and traceability.

**You are stateful.** At every phase boundary, surface the current phase status to the user before advancing. If a phase requires user input, collect it before proceeding.

---

## Hard Constraints (never violate)

- No code without an `APPROVED` canonical spec.
- No implementation without failing tests first.
- Specs are stable capability documents in `specs/`; never create date-based or numbered specs.
- When a related canonical spec already exists, update it in place.
- A feature is not complete until:
  - the approved spec change commit hash appears in the owning spec and `CHANGELOG.md`, and
  - the implementation commit hash appears in the owning spec and `CHANGELOG.md`.
- Traceability-only commits do not record themselves.
- All app lifecycle operations use `docker compose` commands only — never `python app.py`, `flask run`, or ad-hoc `pkill`.

---

## Phase 0 — Discovery (mandatory first stage)

Load the grill-me skill from disk before any spec work:

```text
read: .agents/skills/grill-me/SKILL.md
```

Run the grill-me questioning loop first, one question at a time, until the core design branches are resolved.

Then gather README context for the same feature scope:

- If a README skill is available in the current environment, run it and capture findings.
- If no README skill is available, read `README.md` directly and extract equivalent findings.

Then perform mandatory technical scoping before any spec draft activity:

- Read the nearest architecture/module-boundary context needed to place the feature in the correct module seam.
- Resolve and explicitly discuss whether the feature:
  - fits entirely inside one existing module
  - requires coordinated changes across multiple existing modules
  - requires a new module or a new boundary inside an existing module
- Finalize the module scope with the user before drafting the spec when the correct ownership is not already obvious from repository conventions.

Persist discovery findings in concise bullets before Phase 1:

- problem statement
- user/job-to-be-done
- constraints
- technical scope
- module ownership and boundaries
- edge cases
- explicit non-goals
- acceptance signal

The Phase 1 spec draft must be based on these discovery findings.

---

## Phase 1 — Canonical Spec

### 1a — Check for an existing canonical spec

Before drafting anything, search `specs/` for an existing spec covering the requested capability.

- Status `VERIFIED` or `APPROVED` and scope matches → update that spec in place.
- Status `DRAFT` → surface it to the user. Do not proceed until they confirm approval or revision.
- Status `DEPRECATED` → confirm with the user before reactivating or replacing it.
- Not found → create a new stable capability spec.

### 1b — Bootstrap rule

This repository may not yet have a canonical spec for the area being changed.

If no spec exists for the capability:

- create `specs/<capability>.md`
- first document the **current code reality** for that capability
- then update that same spec to reflect the approved new target behavior

Do not create chronological or ticket-numbered spec files.

### 1c — Draft or update the spec

Draft or update the canonical spec using `specs/TEMPLATE.md`.

Every canonical spec must contain all of these sections:

- **Status** — `DRAFT`, `APPROVED`, `VERIFIED`, or `DEPRECATED`
- **Purpose**
- **Scope**
- **Module Ownership**
- **Current Behavior**
- **Interfaces**
- **Data Model**
- **Rules and Invariants**
- **Edge Cases**
- **Acceptance Criteria**
- **Test Plan**
- **Out of Scope**
- **Traceability**

The spec body must describe **current truth only**. Do not preserve old behavior in the main body as a timeline.

### 1d — Wait for approval

**Stop here.** Do not write code until the user explicitly approves. Once approved, update the spec status to `APPROVED`.

### 1e — Commit the approved spec

Create a spec-only commit for the approved canonical spec change.

Recommended message:

```text
spec(<capability>): update canonical spec
```

### 1f — Record the spec commit hash

Load the traceability skill from disk:

```text
read: .agents/skills/feature-traceability/SKILL.md
```

Capture the spec commit hash and append it to:

- the owning spec under `## Traceability > ### Spec Commits`
- `CHANGELOG.md`

Then create a traceability-only follow-up commit.

---

## Phase 2 — Tests and Implementation

Load the TDD skill from disk before doing anything in this phase:

```text
read: .agents/skills/tdd-karpathy-guidelines/SKILL.md
```

### 2a — Red phase (mandatory)

Write tests covering every Acceptance Criterion and Test Plan scenario.
Use a stable test file name derived from the capability, for example:

```text
tests/test_<capability>.py
```

Run tests and confirm they fail before writing any implementation code.

### 2b — Test quality verifier loop (mandatory)

Load the test-verifier skill from disk immediately after red is confirmed:

```text
read: .agents/skills/test-verifier/SKILL.md
```

Prepare verifier inputs:
1. Full spec file contents.
2. Full generated test file(s) for this spec.
3. Full red-phase test output from 2a.

Invoke a fresh subagent and pass only those artifacts plus the full skill text.

For each report outcome:
- If verdict is `CLEAN` and red-phase status is `VALID_RED`, continue to 2c.
- If verdict reports `TEST GAPS` or `RED PHASE INVALID`, fix tests, re-run red phase, then re-run test-verifier.
- If report has ambiguous gaps requiring requirement interpretation, batch all questions and ask the user once.

Repeat until test-verifier returns `CLEAN` with `VALID_RED`.

Append the final test-verifier report to the spec file before implementation begins.

### 2c — Green phase

Write the minimum code to make all tests pass.
Run the full test suite and confirm all tests pass.

If implementation reveals that the spec must change, stop and return to Phase 1. Update the same canonical spec in place, recommit the spec, and record the new spec commit hash before continuing.

---

## Phase 3 — Audit Loop

Load the spec-verifier skill from disk before running any audit:

```text
read: .agents/skills/spec-verifier/SKILL.md
```

### 3a — Prepare the diff

Generate the full feature delta:

```bash
git diff HEAD~N..HEAD
git diff
```

### 3b — Launch a fresh verifier subagent

Invoke a fresh subagent. Pass it:
1. Full contents of `.agents/skills/spec-verifier/SKILL.md`
2. Full contents of the canonical spec file
3. Full combined diff from 3a

Pass nothing else.

### 3c — Analyse the report

For each MISSING or PARTIAL item, classify:

- **Autonomous fix** — gap is unambiguous, fix is clear from spec alone
- **Needs user input** — requirement conflict, scope decision, or spec ambiguity

### 3d — Fix and re-test

Apply all fixes. Run the full test suite — all tests must pass before the next verifier run.

### 3e — Repeat

Repeat until verifier returns **CLEAN**.

### 3f — Confirm UNVERIFIABLE items

Manually confirm any item the verifier flagged as UNVERIFIABLE before advancing.

### 3g — Append final audit report to spec

Once the verifier returns CLEAN and all UNVERIFIABLE items are manually confirmed, append the full final audit report as a new section at the end of the spec file.

---

## Phase 4 — Implementation Traceability

1. Run the full test suite one final time.
2. Set the canonical spec status to `VERIFIED`.
3. Create the implementation commit:

```text
feat(<capability>): <summary>
```

4. Capture the implementation commit hash.
5. Append that hash to:
   - the owning spec under `## Traceability > ### Implementation Commits`
   - `CHANGELOG.md`
6. Create the traceability-only follow-up commit.
7. Remove any temporary discovery notes created in Phase 0.

---

## Phase Gate Summary

| Phase | Gate to advance | User input required |
|---|---|---|
| 0 — Discovery | Problem and boundary clarified | Yes |
| 1 — Canonical Spec | Spec approved; spec commit + spec traceability commit completed | Yes |
| 2 — Tests + Implement | Red confirmed; test-verifier CLEAN+VALID_RED; then all tests green | Only if test gaps are ambiguous |
| 3 — Audit Loop | Verifier returns CLEAN | Only if report has ambiguous gaps |
| 4 — Implementation Traceability | Tests green; implementation commit + traceability commit completed | No |

Never skip a phase. Never self-audit — the implementing agent must not run spec-verifier against its own work. Always use a subagent or a fresh isolated Pi session.
