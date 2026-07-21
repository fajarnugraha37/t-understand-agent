---
name: tu-memory-invalidation
description: Execute the t-understand memory invalidation workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-memory-invalidation

Owner: `tu-memory-curator`

## Purpose

Identify changed source digests and propagate affected canonical record identities.

## Required guarantees

- Consume only schema-valid, snapshot-bound inputs.
- Preserve exact evidence provenance and epistemic classification.
- Produce deterministic, schema-valid artifacts.
- Never write to source repositories.
- Return explicit unknown, unresolved, stale, or conflict status instead of guessing.
