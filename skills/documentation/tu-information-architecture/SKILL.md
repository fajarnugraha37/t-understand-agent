---
name: tu-information-architecture
description: Execute the t-understand information architecture workflow with evidence-first, schema-bound, read-only behavior.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-information-architecture

## Owner

`tu-technical-writer`

## Objective

Plan comprehensive information architecture.

## Required inputs

- Immutable application snapshot or an artifact already bound to one.
- Canonical memory/model identifiers required by the current workflow state.
- A delegation packet with one bounded objective and explicit expected outputs.

## Output contract

- Produce only the artifact type assigned by the workflow and artifact registry.
- Preserve application, snapshot, memory, model, and document identifiers.
- Classify statements as fact, implemented behavior, business inference, human-confirmed, unknown, conflict, or limitation.
- Bind every supported statement to canonical claims and evidence.

## Safety rules

- Never write to source repositories.
- Never invent product intent, business ownership, requirements, runtime behavior, or human approval.
- Prefer an explicit unknown or limitation over unsupported completion.
- Do not delegate to another worker.
- Return schema-valid structured output for deterministic verification.

## Completion criteria

- All required records are present and deterministically ordered.
- Evidence and claim references resolve.
- Conflicts and stale inputs remain visible.
- The relevant critique and verification gates can pass.
