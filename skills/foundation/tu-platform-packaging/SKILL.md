---
name: tu-platform-packaging
description: Generate platform-specific agent, skill, and rule packages.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source-write: denied
---

# tu-platform-packaging

## Purpose

Generate platform-specific agent, skill, and rule packages.

## Hard rules

- Operate on immutable, explicitly identified inputs.
- Emit schema-valid deterministic artifacts with limitations.
- Never write registered application source repositories or mutate Git.
- Fail closed on stale, ambiguous, unsupported, or tampered inputs.
- Do not fabricate live-model, hosted-renderer, or remote-platform verification.
