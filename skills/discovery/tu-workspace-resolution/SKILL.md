---
name: tu-workspace-resolution
description: Execute the t-understand workspace resolution workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-workspace-resolution

Resolve portable repository identities to machine-local Git roots. Validate exact Git roots, remote or explicit identity, source/context disjointness, unique non-nested roots, and `READ_ONLY` access. Write only `workspace.local.yaml` and `runtime/workspace-resolution.yaml` inside the context root.
