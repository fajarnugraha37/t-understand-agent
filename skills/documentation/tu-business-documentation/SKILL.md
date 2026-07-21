---
name: tu-business-documentation
description: Generate evidence-grounded business and domain documentation without promoting implementation inference into business fact.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-business-documentation

## Owner

`tu-business-writer`

## Objective

Document business goals, outcomes, capability hierarchy, actors, stakeholders, processes, policies, controls, domain language, boundaries, aggregates, invariants, commands, events, and lifecycle semantics.

## Required distinctions

- Business outcome is not a class or endpoint description.
- Business capability is not a flat list of services.
- A security role is not automatically a business persona.
- A repository is not automatically a bounded context.
- An enum is not automatically a complete state machine.
- A failure branch may indicate an invariant candidate but does not prove business intent.

## Evidence classifications

- `TECHNICAL_FACT`
- `IMPLEMENTED_BEHAVIOR`
- `BUSINESS_INFERENCE`
- `HUMAN_CONFIRMED_RULE`
- `UNKNOWN_INTENT`
- `LIMITATION`

## Required perspectives

- Goals and measurable outcomes, or explicit unknowns.
- Hierarchical capabilities and implementation ownership mapping.
- Human actors, system actors, organizations, and stakeholders as separate concepts.
- Business processes with trigger, participants, decisions, outputs, and exceptional outcomes.
- Domain vocabulary with contextual meanings and conflicts.
- Candidate bounded contexts with confidence and confirmation limitations.
- Aggregates, entities, value objects, invariants, domain services, commands, events, state models, and decision tables.

## Completion criteria

- Every supported statement resolves to claims and evidence.
- Every inference discloses its limitation.
- Missing business intent remains visible as an unknown.
- Conflicting terminology or ownership remains visible.
- The generated business/domain coverage ledger reaches the required release threshold.
