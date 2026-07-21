---
name: tu-snapshot-capture
description: Execute the t-understand snapshot capture workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-snapshot-capture

## Objective

Create an immutable, portable application snapshot from registered Git repositories without mutating source repositories.

## Inputs

- validated `application.yaml` and `workspace-resolution.yaml`;
- snapshot ID and purpose;
- one explicit Git target per repository or its registered default.

## Procedure

1. Resolve branch, tag, commit, HEAD, index, or worktree targets.
2. Capture commit/tree identity and permitted overlays.
3. Reject protected paths, ignored files, symlink payloads, dirty submodules, races, and size-limit violations.
4. Validate descriptors and hashes before atomic publication.

## Outputs

- `application-snapshot`;
- one `repository-snapshot` per repository;
- validation and drift reports when requested.

## Stop conditions

Return `BLOCKED` for unresolved refs, workspace mismatch, source drift, protected content, or failed integrity checks. Never modify Git state.
