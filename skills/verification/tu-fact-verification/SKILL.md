---
name: tu-fact-verification
description: Verify claims and citations.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: tu-verifier
  source-write: denied
---

# tu-fact-verification

## Purpose

Verify claims and citations.

## Hard rules

- Operate on immutable, explicitly identified inputs.
- Emit schema-valid deterministic artifacts with limitations.
- Never write registered application source repositories or mutate Git.
- Fail closed on stale, ambiguous, unsupported, or tampered inputs.
- Do not fabricate live-model, hosted-renderer, or remote-platform verification.
