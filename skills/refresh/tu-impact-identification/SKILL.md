---
name: tu-impact-identification
description: Execute the t-understand impact identification workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-impact-identification

Owner: `tu-analyzer`

## Purpose

Propagate changed evidence identities to affected entities, relations, and claims.

## Guarantees

- Inputs are immutable and snapshot-bound.
- Output ordering and identities are deterministic.
- Changed paths are classified as added, modified, or deleted.
- Unknown impact is preserved explicitly rather than guessed.
- Source repositories remain read-only.
