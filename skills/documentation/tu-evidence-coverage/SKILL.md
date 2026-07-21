---
name: tu-evidence-coverage
description: Enforce complete requirement, model-record, section, repository, flow, inference, and traceability coverage for generated documentation.
compatibility: t-understand, opencode, codex, claude-code
metadata:
  owner: t-understand
  source_write: denied
---

# tu-evidence-coverage

## Owner

`tu-analyzer`

## Objective

Prove that documentation generation did not silently skip planned knowledge.

## Required measures

- Documentation-requirement coverage.
- Model-record coverage.
- Required-section coverage.
- Repository coverage.
- Flow coverage.
- Business-inference disclosure.
- Supported-section traceability.
- Unsupported, stale, conflicting, and unknown area counts.

## Gate behavior

- A missing planned document is a blocker.
- An uncovered model record, repository, or flow is a blocker.
- A supported section without claim and evidence references is a blocker.
- An undisclosed business inference is a blocker.
- Unknowns count as covered only when explicitly documented as unknowns, not when omitted.

## Completion criteria

All mandatory coverage metrics equal `1.0`, every gap list is empty, and all generated artifacts validate against their schemas.
