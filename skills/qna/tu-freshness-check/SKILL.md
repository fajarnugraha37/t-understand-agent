---
name: tu-freshness-check
description: Execute the t-understand freshness check workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-freshness-check

Owner: `tu-memory-curator`

## Purpose

Determine whether a memory version can support answers for a requested application snapshot.

## Required guarantees

- Consume only schema-valid, snapshot-bound inputs.
- Preserve exact evidence provenance and epistemic classification.
- Produce deterministic, schema-valid artifacts.
- Never write to source repositories.
- Return explicit unknown, unresolved, stale, or conflict status instead of guessing.
