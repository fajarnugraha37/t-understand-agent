---
name: tu-application-alignment
description: Execute the t-understand application alignment workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-application-alignment

Align the human objective, application identity, repository scope, desired workflow, and evidence freshness before delegation. Only `t-understand` performs this skill. Missing application boundaries or semantic intent must produce a human question or `BLOCKED`, never an assumption.
