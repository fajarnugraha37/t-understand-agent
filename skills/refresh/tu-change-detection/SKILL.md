---
name: tu-change-detection
description: Execute the t-understand change detection workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-change-detection

Owner: `tu-discoverer`

## Purpose

Compare immutable discovery inventories to identify added, modified, and deleted source paths.

## Guarantees

- Inputs are immutable and snapshot-bound.
- Output ordering and identities are deterministic.
- Changed paths are classified as added, modified, or deleted.
- Unknown impact is preserved explicitly rather than guessed.
- Source repositories remain read-only.
