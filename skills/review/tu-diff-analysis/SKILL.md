---
name: tu-diff-analysis
description: Execute the t-understand diff analysis workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-diff-analysis

## Purpose

Analyze comparative changes.

## Owner

`tu-reviewer`

## Inputs

- Immutable application or review snapshot binding.
- Schema-valid upstream artifacts.
- Explicit objective and output contract.

## Outputs

- Schema-valid, evidence-bound artifacts written only to the dedicated context repository.
- Explicit limitations, confidence, and verification status.

## Hard rules

- Never write to source repositories or mutate Git.
- Never fabricate evidence, citations, findings, human approval, or business intent.
- Use deterministic ordering and stable identifiers.
- Fail closed on stale, ambiguous, unsupported, or tampered inputs.
- Suggested patches are advisory and must never be applied by t-understand.

## Economy-model behavior

- One bounded objective per invocation.
- Structured inputs and outputs.
- Deterministic validators own correctness gates.
- Unsupported conclusions become `UNKNOWN` or are suppressed.
