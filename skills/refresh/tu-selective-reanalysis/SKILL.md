---
name: tu-selective-reanalysis
description: Execute the t-understand selective reanalysis workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-selective-reanalysis

Owner: `tu-analyzer`

## Purpose

Reuse unchanged evidence slices and reanalyze only added, modified, or deleted paths.

## Required guarantees

- Consume only schema-valid, snapshot-bound inputs.
- Preserve exact evidence provenance and epistemic classification.
- Produce deterministic, schema-valid artifacts.
- Never write to source repositories.
- Return explicit unknown, unresolved, stale, or conflict status instead of guessing.
