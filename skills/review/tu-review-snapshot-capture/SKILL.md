---
name: tu-review-snapshot-capture
description: Execute the t-understand review snapshot capture workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-review-snapshot-capture

Capture or validate the baseline and candidate snapshots required by a review scope, then create the immutable review-target descriptor. This skill performs no diff analysis and emits no findings.
