---
name: tu-business-modeling
description: Construct conservative business, domain, and application-flow models while preserving evidence boundaries, unknowns, and conflicts.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-business-modeling

## Owner

`tu-modeler`

## Objective

Construct the complete evidence-backed semantic model required for business, domain, and application-flow documentation.

## Model areas

- Goals and outcomes.
- Hierarchical capabilities.
- Business processes.
- Human/system actors and stakeholders.
- Rules, policies, decisions, controls, and compliance concerns.
- Candidate bounded contexts and ownership boundaries.
- Aggregates, entities, value objects, invariants, services, commands, domain events, state models, and decision tables.
- Application, cross-repository, event, data, security, failure, and consistency flows.

## Conservative promotion rules

- Source structure may create a `BUSINESS_INFERENCE`, never an unsupported business fact.
- Repository boundaries create bounded-context candidates, not confirmed bounded contexts.
- Role or permission surfaces create actor candidates, not confirmed personas.
- Events, commands, aggregates, and invariants remain candidates until semantics are evidenced.
- Missing intent becomes an explicit `UNKNOWN` record.

## Completion criteria

Every produced record has stable identity, classification, source entities/relations, claims, evidence, attributes, and limitations where required. Duplicate records and unsupported facts are rejected.
