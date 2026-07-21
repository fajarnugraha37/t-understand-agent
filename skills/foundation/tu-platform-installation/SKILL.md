---
name: tu-platform-installation
description: Install managed platform packages into explicit non-source targets.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source-write: denied
---

# tu-platform-installation

## Purpose

Install managed platform packages into explicit non-source targets.

## Hard rules

- Operate on immutable, explicitly identified inputs.
- Emit schema-valid deterministic artifacts with limitations.
- Never write registered application source repositories or mutate Git.
- Fail closed on stale, ambiguous, unsupported, or tampered inputs.
- Do not fabricate live-model, hosted-renderer, or remote-platform verification.
