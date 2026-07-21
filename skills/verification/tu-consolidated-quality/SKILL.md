---
name: tu-consolidated-quality
description: Consolidate validation, critique, traceability, freshness, and integrity verdicts.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: tu-verifier
  source-write: denied
---

# tu-consolidated-quality

## Purpose

Consolidate validation, critique, traceability, freshness, and integrity verdicts.

## Hard rules

- Operate on immutable, explicitly identified inputs.
- Emit schema-valid deterministic artifacts with limitations.
- Never write registered application source repositories or mutate Git.
- Fail closed on stale, ambiguous, unsupported, or tampered inputs.
- Do not fabricate live-model, hosted-renderer, or remote-platform verification.
