---
name: tu-behavior-analysis
description: Execute the t-understand behavior analysis workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-behavior-analysis

Owner: `tu-analyzer`

## Purpose

Extract evidence-bound calls, data access, events, HTTP surfaces, transactions, failures, configuration, and tests.

## Required guarantees

- Consume only schema-valid, snapshot-bound inputs.
- Preserve exact evidence provenance and epistemic classification.
- Produce deterministic, schema-valid artifacts.
- Never write to source repositories.
- Return explicit unknown, unresolved, stale, or conflict status instead of guessing.
