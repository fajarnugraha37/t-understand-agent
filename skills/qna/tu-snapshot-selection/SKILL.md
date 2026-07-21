---
name: tu-snapshot-selection
description: Execute the t-understand snapshot selection workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-snapshot-selection

Select or capture the immutable application snapshot that answers the aligned question. Record the exact snapshot digest and reject stale or mutable targets. This skill does not retrieve evidence or synthesize an answer.
