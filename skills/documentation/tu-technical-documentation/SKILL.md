---
name: tu-technical-documentation
description: Generate complete application, repository, integration, data, operational, and end-to-end flow documentation from validated evidence.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-technical-documentation

## Owner

`tu-technical-writer`

## Objective

Write application-level and per-repository technical documentation, including cross-repository contracts and application flows.

## Required application-flow perspectives

- Business and application intent.
- Trigger and preconditions.
- Participants and repository attribution.
- Ordered synchronous and asynchronous interactions.
- State and data impact.
- Transaction, consistency, idempotency, retry, compensation, and reconciliation boundaries.
- Alternative paths, failures, and recovery.
- Authentication, authorization, classification, and sensitive-data considerations.
- Logs, metrics, traces, alerts, SLOs, runbooks, and operational unknowns.
- Evidence, traceability, and explicit limitations.

## Scale behavior

- Generate the mandatory application catalog first.
- Repeat repository documentation for every repository.
- Generate deep Tier-1 flow documents and standard Tier-2 flow documents.
- Retain Tier-3 flows in the complete catalog.
- Process requirements sequentially when necessary; never silently truncate a large plan.

## Safety and accuracy

- Never write to source repositories or mutate Git.
- Do not turn a call graph into a complete use-case claim.
- Do not claim observed runtime ordering without execution evidence.
- Do not claim tests or builds passed unless execution evidence exists.
- Prefer unknown or partial coverage over fabricated detail.

## Completion criteria

- Every planned document exists.
- Every required heading exists.
- Every supported section is traceable.
- Repository, flow, requirement, model-record, and section coverage all pass.
