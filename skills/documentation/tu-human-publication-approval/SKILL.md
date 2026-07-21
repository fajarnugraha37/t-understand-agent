---
name: tu-human-publication-approval
description: Execute the t-understand human publication approval workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-human-publication-approval

Present verified publication artifacts and their digests to the human. Record `APPROVE` or `REJECT` with rationale. Never infer approval. Rejection requires an explicit earlier loopback target.
