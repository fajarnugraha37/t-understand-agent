---
name: tu-target-resolution
description: Execute the t-understand target resolution workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-target-resolution

Normalize static-audit or diff targets into immutable application snapshot references. Enforce one candidate, a baseline only for diff mode, exact snapshot digests, and immutable review IDs.
