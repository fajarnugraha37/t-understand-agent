---
name: tu-source-inventory
description: Execute the t-understand source inventory workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-source-inventory

## Objective

Produce a complete snapshot-bound file inventory with content identity, classification, adapter candidates, and explicit exclusions.

## Rules

- Never read protected, ignored, or symlink content.
- Preserve metadata for excluded generated, vendored, binary, oversized, protected, symlink, and submodule paths.
- Hash included content with SHA-256.
- Bind every record to snapshot ID and repository ID.
- Sort records by repository-relative path.

## Output

`file-inventory-record` JSONL validated against the canonical schema.
