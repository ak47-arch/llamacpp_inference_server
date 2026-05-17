# Isolated Subagent Verification Commands

## Status

APPROVED

## Purpose

Define the repository's project-local isolated subagent command capability for read-only audit and verifier workflows so mandatory independent checks can run inside Pi using a constrained child session instead of relying on ad hoc manual fresh-session workarounds.

## Scope

This spec covers:

- the project-local subagent extension in `.pi/extensions/subagents/`
- slash commands that launch isolated child sessions for allowlisted audit/verifier skills
- artifact-limited handoff construction for verifier commands
- read-only child-session execution constraints
- tests covering command helper logic and verifier handoff generation
- lightweight repository documentation updates describing the command surface

This spec does not cover:

- general-purpose arbitrary subagent orchestration
- mutating child sessions
- background async subagent execution
- worktree isolation
- parent/child intercom or supervision channels
- generic execution of all repository skills
- replacing external packages such as `pi-subagents`

## Module Ownership

Owning modules and files:

- `.pi/extensions/subagents/index.ts` — registers slash commands and launches isolated child sessions
- `.pi/extensions/subagents/helpers.mjs` — argument parsing, allowlist enforcement, artifact loading, and prompt construction helpers
- `tests/subagents.test.mjs` — regression tests for helper behavior and command handoff generation
- `README.md` — brief documentation of the verifier command surface if updated
- `FEATURE_MATRIX.md` — optional inventory update for the implemented command surface if updated

The extension module owns command registration and session launching. Helper functions own parsing, validation, prompt assembly, and artifact shaping. The child session remains read-only and must not be used as a general-purpose mutating worker.

## Current Behavior

The repository exposes project-local slash commands for isolated read-only audit workflows.

The existing `/module-boundary` command remains available and continues to run the `module-boundary` skill in an isolated child session.

The extension also exposes a generic `/isolated-skill` command for an allowlisted set of read-only audit skills.

Allowed skill names are limited to:

- `module-boundary`
- `spec-verifier`
- `test-verifier`

If a caller requests a non-allowlisted skill, the command rejects the request before launching a child session.

The generic `/isolated-skill` command launches a child session with:

- the requested allowlisted skill only
- no prompt templates
- no agent files
- read-only tools only
- an appended system instruction stating that the child is isolated and must not assume parent-session context

The generic command may target an explicit cwd. If no cwd is supplied, it defaults to the current session cwd.

For verifier workflows, the extension exposes dedicated slash commands that construct artifact-limited handoff prompts before launching the child session.

`/spec-verify` requires explicit artifact inputs for:

- the canonical spec file path
- the diff source, supplied either as a commit-ish/range to resolve with git or as a file path containing diff text

`/spec-verify` reads those artifacts in the parent session, builds a handoff prompt containing only the required verifier inputs, and then launches an isolated child session with the `spec-verifier` skill.

`/test-verify` requires explicit artifact inputs for:

- the canonical spec file path
- the generated test file path
- the red-phase test output file path

`/test-verify` reads those artifacts in the parent session, builds a handoff prompt containing only the required verifier inputs, and then launches an isolated child session with the `test-verifier` skill.

Verifier commands do not ask the child to rediscover parent context. They pass the required verifier artifacts directly in the prompt so the child session can operate with a minimal, deterministic handoff.

Child sessions created by these commands use read-only tools and do not receive unrestricted skill access.

Verifier command results are posted back into the parent session as displayed subagent reports with metadata indicating the skill name, cwd, isolated execution, and read-only tools.

## Interfaces

### Slash commands

#### `/module-boundary [path]`

Runs the `module-boundary` skill in an isolated child session.

Arguments:

- optional path or cwd override

#### `/isolated-skill <skill-name> [path]`

Runs one allowlisted read-only audit skill in an isolated child session.

Arguments:

- required `skill-name`
- optional path or cwd override

Valid `skill-name` values:

- `module-boundary`
- `spec-verifier`
- `test-verifier`

#### `/spec-verify <spec-path> <diff-source>`

Runs `spec-verifier` in an isolated child session using explicit verifier artifacts.

Arguments:

- `spec-path` — path to the canonical spec file
- `diff-source` — either:
  - a path to a file containing diff text, or
  - a git commit-ish/range string that the parent resolves into diff text before launch

The child handoff must include:

- full contents of `.agents/skills/spec-verifier/SKILL.md`
- full contents of the spec file
- full diff text

The parent may also include the workflow document as optional additional context only if explicitly chosen by the command implementation. If omitted, the child report must still remain valid per the verifier skill.

#### `/test-verify <spec-path> <test-path> <red-output-path>`

Runs `test-verifier` in an isolated child session using explicit verifier artifacts.

Arguments:

- `spec-path` — path to the canonical spec file
- `test-path` — path to the generated test file
- `red-output-path` — path to a file containing red-phase failing test output

The child handoff must include:

- full contents of `.agents/skills/test-verifier/SKILL.md`
- full contents of the spec file
- full contents of the test file
- full red-phase output text

### Child session constraints

All isolated commands run child sessions with:

- `readOnlyTools`
- filtered skills containing only the selected allowlisted skill
- prompts disabled
- agent files disabled
- no parent-session mutating context

### Parent-side validations

The extension validates before launch:

- requested skill is allowlisted
- required artifact paths exist for verifier commands
- required artifact text is non-empty where applicable
- command argument counts are valid

If validation fails, the extension surfaces an error to the user and does not launch a child session.

## Data Model

### Allowlisted isolated skills

Allowed values:

- `module-boundary`
- `spec-verifier`
- `test-verifier`

### Generic isolated run summary

A displayed result summary contains at least:

- `skillName`
- `cwd`
- `isolated: true`
- `tools: "readOnlyTools"`

### Verifier handoff payloads

#### Spec verifier payload

Contains:

- verifier skill name: `spec-verifier`
- target cwd
- spec path
- full spec contents
- diff source descriptor
- full diff contents

#### Test verifier payload

Contains:

- verifier skill name: `test-verifier`
- target cwd
- spec path
- full spec contents
- test path
- full test contents
- red output path
- full red output contents

Invariants:

- verifier payloads are artifact-limited and deterministic
- child sessions remain read-only
- non-allowlisted skills are rejected before child-session creation
- verifier commands require explicit artifact inputs and do not infer them from recent activity

## Rules and Invariants

1. The project-local extension must continue to provide `/module-boundary`.
2. The extension must provide `/isolated-skill` for allowlisted read-only audit skills.
3. The extension must reject non-allowlisted skill names.
4. Allowed isolated skills are limited to `module-boundary`, `spec-verifier`, and `test-verifier`.
5. Child sessions launched by these commands must use `readOnlyTools`.
6. Child sessions launched by these commands must disable prompts and agent files.
7. Child sessions launched by these commands must filter skills down to the single requested allowlisted skill.
8. `/spec-verify` must require explicit `spec-path` and `diff-source` arguments.
9. `/test-verify` must require explicit `spec-path`, `test-path`, and `red-output-path` arguments.
10. Verifier commands must read artifacts in the parent and pass them directly to the child as handoff content.
11. Verifier commands must not rely on the child to rediscover parent-session context.
12. Validation failures must prevent child-session launch.
13. Result messages must clearly indicate that the run was isolated and read-only.

## Edge Cases

- If a requested allowlisted skill file cannot be discovered by the resource loader, the command fails before reporting success.
- If `/isolated-skill` receives an unknown skill name, the extension rejects it without launching a child session.
- If `/spec-verify` receives a diff source that is neither a readable file nor a git-resolvable diff descriptor, the extension reports an error and does not launch the child session.
- If `/spec-verify` resolves an empty diff, the extension reports an error and does not launch the child session.
- If `/test-verify` receives a missing or empty red-output file, the extension reports an error and does not launch the child session.
- If a verifier artifact file exists but is unreadable, the extension reports an error and does not launch the child session.
- If the parent session is busy, the command warns the user and does not start a child session.
- If the child session produces no output, the extension warns the user rather than posting an empty success report.

## Acceptance Criteria

1. `.pi/extensions/subagents/index.ts` supports `/isolated-skill` in addition to `/module-boundary`.
2. `/isolated-skill` accepts only allowlisted skill names and rejects all others.
3. The allowlist includes `module-boundary`, `spec-verifier`, and `test-verifier`.
4. `/spec-verify` exists and launches `spec-verifier` in an isolated read-only child session.
5. `/test-verify` exists and launches `test-verifier` in an isolated read-only child session.
6. Verifier commands require explicit artifact arguments and do not infer them from recent history.
7. Verifier commands build artifact-limited prompts from parent-read artifact contents.
8. Child sessions created by these commands use only the selected allowlisted skill, no prompts, no agent files, and `readOnlyTools`.
9. Existing `/module-boundary` behavior remains available.
10. Tests cover allowlist filtering, verifier prompt construction, cwd/path resolution, and validation behavior for missing/invalid verifier artifacts.

## Test Plan

- verify helper logic still resolves cwd correctly for blank and relative command arguments
- verify allowlist filtering keeps only explicitly allowed isolated skills
- verify `/isolated-skill` prompt construction targets only the requested skill and cwd
- verify spec-verifier handoff construction includes the full skill text, spec contents, and diff contents
- verify test-verifier handoff construction includes the full skill text, spec contents, test contents, and red output text
- verify validation rejects non-allowlisted skills
- verify validation rejects missing spec/test/red-output files
- verify validation rejects empty diff or empty red-output inputs
- verify summary metadata still records skill name and cwd for display

## Out of Scope

- generic arbitrary-skill child execution
- write-capable child sessions
- background verifier jobs
- automatic discovery of latest red output or latest changed tests
- git worktree orchestration
- replacing the local extension with `pi-subagents`
- TUI widgets beyond the existing report/notification surface

## Traceability

Append only non-traceability commit hashes here. Traceability-only commits do not record themselves.

### Spec Commits

- YYYY-MM-DD | <commit-hash> | <summary>

### Implementation Commits

- YYYY-MM-DD | <commit-hash> | <summary>
