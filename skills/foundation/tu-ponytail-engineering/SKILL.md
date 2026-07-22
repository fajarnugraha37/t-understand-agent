---
name: tu-ponytail-engineering
description: Select the smallest complete solution that preserves correctness, safety, contracts, maintainability, and operational validity before proposing or reviewing code changes.
compatibility: t-understand, opencode, codex, claude-code, cursor
metadata:
  owner: t-understand
  source_write: denied
  external_ponytail_required: false
---

# tu-ponytail-engineering

## Objective

Apply `orchestrator/ponytail-engineering-policy.yaml` to planning, debugging, refactoring, suggested implementation, testing, documentation, and code review.

The goal is not the fewest lines. The goal is the fewest changed concepts that fully satisfy the current requirement while preserving correctness, security, data integrity, contracts, compatibility, maintainability, observability, operational safety, performance, compliance, and material testability.

## External Ponytail integration

Before referring to a Ponytail command, hook, file, or capability, inspect the first locally available source:

1. installed Ponytail skill documentation;
2. Ponytail `SKILL.md` files;
3. Ponytail rules or agent files;
4. repository integration files;
5. local command help;
6. existing project scripts.

Never invent commands, paths, hooks, modes, or platform support. Never install or upgrade Ponytail automatically. If no local integration exists, apply the canonical policy directly and continue normally.

## Decision procedure

Stop at the first option that completely satisfies the current contract:

1. **No change.** Confirm whether current behavior, documentation, an existing command, API, flag, component, or deployment option already solves the outcome.
2. **No application code.** Prefer a correct, visible, supportable, and verifiable configuration, data, schema, policy, routing, build, deployment, access-control, infrastructure, or workflow change.
3. **Platform-native.** Use the language, standard library, runtime, framework, operating system, database, browser, build system, container platform, infrastructure, or already-approved dependency when its behavior matches the contract.
4. **Existing repository solution.** Reuse an existing mechanism only when it represents the same semantic concept.
5. **Configuration, data, or composition.** Use an established declarative mechanism or extension point; do not build a generalized engine for one case.
6. **Localized code.** Modify the smallest cohesive responsible component. Minimize changed concepts, not only lines.
7. **Existing abstraction.** Extend it only when the responsibility and behavioral contract remain correct.
8. **New abstraction.** Require current evidence from the policy's admission criteria. Future-proofing, style, or one hypothetical consumer is insufficient.
9. **New dependency.** Require a current measurable benefit that outweighs security, licensing, maintenance, runtime, build, learning, and transitive costs.

## Correctness boundary

Reject simplification that removes necessary validation, error handling, transactions, concurrency protection, observability, audit behavior, compatibility, migration safety, meaningful boundaries, or material tests. Preserve necessary complexity and remove only accidental or speculative complexity.

## Compact decision for small tasks

For a local, low-risk change with a clear contract, record only:

```yaml
ponytail_context:
  required_outcome:
  - "<current outcome>"
  preserved_behavior:
  - "<must remain unchanged>"
  change_required: true
  selected_solution: "<smallest complete solution>"
  alternatives_checked:
    no_code: "<result>"
    platform_native: "<result>"
    existing_repository_solution: "<result>"
    configuration_or_data: "<result>"
    localized_change: "<result>"
  abstractions_approved: []
  dependencies_approved: []
  non_goals: []
  risks: []
  verification_required:
  - "<executable check>"
```

Do not create a multi-agent workflow or a long report solely to satisfy this format.

## Structured planning for higher-risk tasks

Include:

- actual required outcome versus assumed implementation;
- preserved behavior and explicit non-goals;
- result of each viable ladder rung;
- smallest responsible change surface;
- evidence for every approved abstraction or dependency;
- rejected alternatives and concrete reasons;
- risks and executable verification.

Do not fabricate alternatives merely to fill a template.

## Worker behavior

Consume delegated `ponytail_context` instead of repeating the complete ladder. Reopen a decision only when new evidence invalidates it. Do not broaden the scope, add cleanup, introduce dependencies, or create abstractions outside the approved context.
