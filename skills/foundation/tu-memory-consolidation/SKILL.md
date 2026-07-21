---
name: tu-memory-consolidation
description: Execute the t-understand memory consolidation workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-memory-consolidation

Owner: `tu-memory-curator`

## Purpose

Publish immutable canonical memory from validated analysis and application graph artifacts.

## Required guarantees

- Consume only schema-valid, snapshot-bound inputs.
- Preserve exact evidence provenance and epistemic classification.
- Produce deterministic, schema-valid artifacts.
- Never write to source repositories.
- Return explicit unknown, unresolved, stale, or conflict status instead of guessing.
