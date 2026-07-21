---
name: tu-document-plan
description: Build a requirements-driven adaptive documentation plan that cannot silently omit repositories, flows, model records, or required sections.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-document-plan

## Owner

`tu-technical-writer`

## Objective

Create a deterministic documentation requirements ledger and adaptive document plan for the complete application snapshot.

## Required inputs

- Immutable application snapshot containing every registered repository.
- Validated canonical memory and model set.
- Repository, integration, business, domain, flow, data, security, deployment, and operational records.

## Planning rules

- Start from the mandatory application/business/domain/flow/integration/data/operations/reference catalog.
- Add the complete repository document set once for every repository.
- Add five deep documents for every Tier-1 flow.
- Add one full-perspective document for every Tier-2 flow.
- Cover every Tier-3 flow in the flow catalog.
- Give every document a unique requirement ID, path, scope, source-model set, generation mode, and required headings.
- Never reduce the plan because it is large. Generation may be sequential, but no requirement may disappear.

## Output contract

- `documentation-requirements.yaml`
- `document-plan.yaml`
- Exact one-to-one relationship between requirements and generation records.
- Deterministic ordering and stable paths.

## Safety and truth rules

- Never write to source repositories.
- Never invent product intent, business ownership, bounded-context status, runtime behavior, or human approval.
- Preserve unknowns and conflicts as required documentation scope.

## Completion criteria

- Every repository and flow has a planned coverage location.
- Every model type and model record can be mapped to at least one planned document.
- Required sections are explicit before drafting begins.
- Duplicate document IDs and paths are rejected.
