---
name: tu-integration-scenarios
description: Execute and aggregate complete end-to-end integration scenarios.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: tu-verifier
  source-write: denied
---

# tu-integration-scenarios

## Purpose

Execute and aggregate complete end-to-end integration scenarios.

## Hard rules

- Operate on immutable, explicitly identified inputs.
- Emit schema-valid deterministic artifacts with limitations.
- Never write registered application source repositories or mutate Git.
- Fail closed on stale, ambiguous, unsupported, or tampered inputs.
- Do not fabricate live-model, hosted-renderer, or remote-platform verification.
