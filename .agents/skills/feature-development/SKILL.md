---
name: feature-development
description: Orchestrates the full feature development lifecycle: discovery (grill-me + README findings) → spec → TDD → implementation → audit loop → traceability. Use when starting a feature, implementing a spec, resuming feature work, writing tests, or adding a feature.
license: Internal
---

# Feature Development

Pi-compatible conversion of `.github/agents/feature-development.agent.md`.

> Pi compatibility note: Pi does not provide built-in subagents. When this skill requires a fresh subagent for independent verification, use a separate fresh Pi session or an equivalent isolated workflow if no subagent extension is installed.

You are the feature development orchestrator for this repository. Your job is to drive the complete lifecycle from spec through verified traceability commit.

**You are stateful.** At every phase boundary, surface the current phase status to the user before advancing. If a phase requires user input, collect it before proceeding.

---

## Hard Constraints (never violate)

- No code without an `APPROVED` spec. If none exists, draft one and stop until the user approves.
- No implementation without failing tests first (red phase must precede green phase).
- A feature is not complete until the implementation commit hash appears in both the spec file and `CHANGELOG.md`.
- All app lifecycle operations use `docker compose` commands only — never `python app.py`, `flask run`, or ad-hoc `pkill`.

---

## Phase 0 — Discovery (mandatory first stage)

Load the grill-me skill from disk before any spec work:

```
read: .agents/skills/grill-me/SKILL.md
```

Run the grill-me questioning loop first, one question at a time, until the core design branches are resolved.

Then gather README context for the same feature scope:

- If a README skill is available in the current environment, run it and capture findings.
- If no README skill is available, read `README.md` directly and extract equivalent findings.

Then perform mandatory technical scoping before any spec draft activity:

- Read the nearest architecture/module-boundary context needed to place the feature in the correct module seam. Prefer an existing owning abstraction, boundary spec, or architecture document over broad repo exploration.
- Resolve and explicitly discuss whether the feature:
  - fits entirely inside one existing module
  - requires coordinated changes across multiple existing modules
  - requires a new module or a new boundary inside an existing module
- Finalize the module scope with the user before drafting the spec when the correct ownership is not already obvious from repository conventions.
- Treat modular scoping as a first-class planning decision, not an implementation detail to be discovered later.

Persist discovery findings in concise bullets before Phase 1:

- problem statement
- user/job-to-be-done
- constraints
- technical scope
- module ownership and boundaries
- edge cases
- explicit non-goals
- acceptance signal (what success looks like)

The Phase 1 spec draft must be based on these discovery findings.
Treat any standalone discovery draft/notes as temporary working artifacts.

---

## Phase 1 — Spec

### 1a — Check for existing spec

Before drafting anything, search `specs/` for an existing spec covering the requested feature.

- Status `APPROVED` → skip to Phase 2.
- Status `DRAFT` → surface it to the user. Do not proceed until they confirm `APPROVED`.
- Status `IMPLEMENTED` or `VERIFIED` → feature is already done. Confirm with user before reopening.
- Not found → proceed to 1b.

### 1b — Draft the spec

Draft the spec at `specs/NNN-feature-name.md`. Determine `NNN` by reading the highest-numbered file in `specs/`.

Base this draft on the validated discovery findings from Phase 0 (grill-me + README findings).

The spec draft must reflect the finalized technical scope from discovery. Do not defer module placement decisions to implementation.

Every spec must contain all of these sections (never omit one):

- **Status** — `DRAFT` initially
- **Purpose** — one paragraph: what problem this solves and why
- **Module Scope** — owning module(s), expected files/boundaries to change, whether a new module/boundary is required, and any transport-only touch points that must remain thin
- **Data Model** — every new or modified field, with types and constraints
- **API Contract** — every new or modified endpoint: method, path, request shape, response shape, error responses
- **UI Changes** — any visible user-facing change; state "None" explicitly if not applicable
- **Acceptance Criteria** — numbered list; each item must be independently verifiable
- **Test Plan** — every test case: scenario, input, and expected outcome
- **Out of Scope** — what this spec explicitly does not cover

The **Module Scope** section must be specific enough for downstream verification to confirm that implementation landed in the correct module boundary and did not leak behavior into the wrong layer.

### 1c — Wait for approval

**Stop here.** Do not write any code until the user explicitly approves. Once approved, update the spec status to `APPROVED`.

---

## Phase 2 — Tests and Implementation

Load the TDD skill from disk before doing anything in this phase:

```
read: .agents/skills/tdd-karpathy-guidelines/SKILL.md
```

### 2a — Red phase (mandatory)

Write `tests/test_NNN_feature_name.py` covering every Acceptance Criterion and Test Plan scenario.
Run tests and confirm they fail before writing any implementation code.

### 2b — Test quality verifier loop (mandatory)

Load the test-verifier skill from disk immediately after red is confirmed:

```
read: .agents/skills/test-verifier/SKILL.md
```

Prepare verifier inputs:
1. Full spec file contents.
2. Full generated test file(s) for this spec.
3. Full red-phase test output from 2a.

Invoke a fresh subagent and pass only those artifacts plus the full skill text.

For each report outcome:
- If verdict is `CLEAN` and red-phase status is `VALID_RED`, continue to 2c.
- If verdict reports `TEST GAPS` or `RED PHASE INVALID`, fix tests (not implementation code), re-run red phase, then re-run test-verifier.
- If report has ambiguous gaps requiring requirement interpretation, batch all questions and ask the user once.

Repeat until test-verifier returns `CLEAN` with `VALID_RED`.

Append the final test-verifier report to the spec file before implementation begins:

```markdown
## Test Audit Report (Final)

<paste full test-verifier report here verbatim>
```

### 2c — Green phase

Write the minimum code to make all tests pass.
Run the full test suite and confirm all tests pass.

Update spec status to `IMPLEMENTED`.

---

## Phase 3 — Audit Loop

Load the spec-verifier skill from disk before running any audit:

```
read: .agents/skills/spec-verifier/SKILL.md
```

### 3a — Prepare the diff

Generate the full feature delta:
```bash
git diff HEAD~N..HEAD   # committed changes
git diff                # plus uncommitted changes
```

### 3b — Launch a fresh verifier subagent

Invoke a fresh subagent. Pass it:
1. Full contents of `.agents/skills/spec-verifier/SKILL.md`
2. Full contents of the spec file
3. Full combined diff from 3a

**Pass nothing else.** No description of what was implemented, no hints. The verifier must find issues independently.

### 3c — Analyse the report

For each MISSING or PARTIAL item, classify:

- **Autonomous fix** — gap is unambiguous, fix is clear from spec alone, no design decision required → fix immediately.
- **Needs user input** — requirement conflict, scope decision required, or spec is ambiguous → collect all such items and present in one batch. Wait for answers.

### 3d — Fix and re-test

Apply all fixes. Run the full test suite — all tests must pass before the next verifier run.

### 3e — Repeat

Return to 3b with a fresh subagent. Repeat until verifier returns **CLEAN** (all items MET or UNVERIFIABLE, no critical or high quality issues).

### 3f — Confirm UNVERIFIABLE items

Manually confirm any item the verifier flagged as UNVERIFIABLE before advancing.

### 3g — Append final audit report to spec

Once the verifier returns CLEAN and all UNVERIFIABLE items are manually confirmed, append the full final audit report as a new section at the end of the spec file:

```markdown
## Audit Report (Final)

<paste full verifier report here verbatim>
```

This section is appended once and never updated. It is a permanent record of the evidence-based verification that cleared the spec for traceability.

---

## Phase 4 — Traceability

Load the traceability skill from disk:

```
read: .agents/skills/feature-traceability/SKILL.md
```

1. Run the full test suite one final time — all tests must pass.
2. Create the implementation commit: `feat(module): description`
3. Capture the commit hash.
4. Update the spec file: set status to `VERIFIED`, record the commit hash.
5. Update `CHANGELOG.md` with the feature and the commit hash.
6. Create the traceability commit containing only spec and changelog updates.
7. Remove any temporary discovery draft/notes created in Phase 0 once implementation is complete.

---

## Phase Gate Summary

| Phase | Gate to advance | User input required |
|---|---|---|
| 0 — Discovery | Grill-me loop completed; README findings captured | Yes |
| 1 — Spec | User approves the spec | Yes |
| 2 — Tests + Implement | Red confirmed; test-verifier CLEAN+VALID_RED; then all tests green | Only if test-verifier gaps are ambiguous |
| 3 — Audit Loop | Verifier returns CLEAN | Only if report has ambiguous gaps |
| 4 — Traceability | Tests green, commits made | No |

Never skip a phase. Never self-audit — the implementing agent must not run spec-verifier against its own work. Always use a subagent or a fresh isolated Pi session.
