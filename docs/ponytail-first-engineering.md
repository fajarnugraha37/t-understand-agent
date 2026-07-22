# Ponytail-first engineering

`t-understand` applies a Ponytail-first engineering policy to planning, debugging, refactoring, suggested implementation, testing, documentation, and code review.

The invariant is:

> The smallest acceptable solution is the smallest solution that remains correct, safe, understandable, maintainable, and operationally valid.

Ponytail-first reduces unnecessary code, files, abstractions, dependencies, configuration, speculative extensibility, unrelated refactoring, duplicated platform mechanisms, and hypothetical complexity. It does not optimize line count at the expense of correctness or safety.

## Architecture

The canonical policy is `orchestrator/ponytail-engineering-policy.yaml`. The shared `tu-ponytail-engineering` skill implements it. The root `t-understand` agent owns the initial decision ladder and places a concise optional `ponytail_context` in delegated work.

Terminal agents reuse that context. They reopen a decision only when new evidence invalidates it. This prevents every worker from repeating repository exploration or independently inventing a larger design.

The repository has no application-source-writing builder. `t-understand` remains source-read-only and produces evidence, plans, suggested patches, reviews, tests, documentation, and handoff context. An approved source-writing system such as `t-think` must consume the selected solution, non-goals, approved abstractions, approved dependencies, risks, and verification requirements.

## External Ponytail integration

An installed Ponytail plugin or skill is optional. Before using a Ponytail-specific command, hook, file, or capability, an agent must inspect local skill documentation, `SKILL.md`, rules, integration files, command help, or project scripts.

No command or path is hardcoded by this repository. The system never installs or upgrades Ponytail automatically. When local Ponytail integration is absent, the canonical policy remains active and the task continues normally.

## Decision ladder

The orchestrator stops at the first rung that completely satisfies the current requirement.

### 1. No change

First determine whether the request is already satisfied by current behavior, documented usage, an existing command, an API, a component, a feature flag, deployment configuration, or a misunderstanding.

When no change is required, do not change code merely because the request assumed an implementation.

### 2. No application code

Consider configuration, environment variables, policy, database data, schema constraints, declarative validation, routing, build configuration, deployment configuration, access control, infrastructure, and workflow configuration.

A no-code solution is valid only when it is correct, supportable, visible, verifiable, and owned by the correct boundary. Complex business rules must not be hidden in untestable configuration or deployment scripts.

### 3. Platform-native capability

Prefer the programming language, standard library, runtime, framework, operating system, database, browser, build system, container platform, infrastructure, or an already-approved dependency.

Use the native capability only when its semantics satisfy the actual product contract. Platform-first is invalid when compatibility, security, accessibility, data integrity, operational, or business behavior differs.

### 4. Existing repository mechanism

Search for an existing helper, service, adapter, extension point, component, validator, mapper, error convention, test utility, configuration mechanism, or dependency already used for the same concept.

Reuse must be semantic. Similar syntax is not enough when the business concepts or ownership boundaries differ.

### 5. Configuration, data, or composition

Prefer data-driven rules, lookup tables, established strategy registration, configuration objects, schema metadata, declarative mappings, composition, or a new variant of an existing extension point.

Do not build a generalized rule engine or registry for one isolated case.

### 6. Localized code

When code is required, edit the smallest cohesive responsible component. Preserve contracts, validation, error handling, observability, transactions, concurrency, compatibility, and operational behavior.

Minimize changed concepts, not merely changed lines. A one-line global hack can be worse than a small explicit multi-line change.

### 7. Existing abstraction

Extend an existing abstraction only when it owns the same responsibility and the new behavior preserves its contract and cohesion.

### 8. New abstraction

A new interface, base class, factory, registry, plugin, strategy, middleware, wrapper, facade, adapter, or framework requires current evidence. At least one must be true:

- multiple current variants exist;
- a stable public contract is required;
- infrastructure volatility must be isolated from policy;
- independent ownership boundaries exist;
- contract testing across implementations is valuable;
- an external integration requires an adapter boundary;
- testability cannot reasonably be achieved otherwise;
- the repository already uses the pattern for the same concept;
- an approved near-term requirement explicitly depends on it.

Future-proofing, generic best practice, style preference, hypothetical consumers, or small obvious duplication are not enough.

### 9. New dependency

A dependency is admitted only when its current measurable benefit outweighs supply-chain, security, licensing, maintenance, runtime, build, learning, upgrade, and transitive costs.

The decision records the current problem, platform options, repository options, benefit, security and licensing, maintenance cost, runtime or build cost, simpler alternative, and final decision.

## Correctness and safety boundary

Ponytail-first never overrides:

1. correctness and required behavior;
2. security, safety, and data integrity;
3. public and internal contracts;
4. backward compatibility;
5. regulatory and compliance obligations;
6. operational safety and required observability;
7. required performance characteristics;
8. clear domain invariants.

Necessary complexity comes from the domain, contract, safety, security, compliance, performance, or operational requirements. Accidental complexity comes from the chosen implementation. Speculative complexity serves only hypothetical future needs.

Agents preserve and clarify necessary complexity. They remove accidental and speculative complexity.

## Engineering principles

- **Ponytail + SRP:** prefer fewer components without combining unrelated responsibilities.
- **Ponytail + OCP:** use an existing extension point when it fits; do not create a new extension framework without current variation.
- **Ponytail + LSP:** reject shorter implementations that weaken behavioral contracts.
- **Ponytail + DIP:** preserve meaningful dependency boundaries; do not place interfaces around every concrete class.
- **Ponytail + DRY:** remove duplicated knowledge; tolerate small duplication when abstraction would increase coupling.
- **Ponytail + KISS:** optimize simplicity across the complete system, not only local line count.
- **Ponytail + YAGNI:** exclude future-only mechanisms, fields, options, dependencies, and abstractions.

When principles conflict, correctness, safety, contracts, domain invariants, and whole-system simplicity take priority over local brevity.

## Workflow behavior

### Orchestrator

`t-understand` separates the required outcome from the requested implementation, applies the ladder, identifies the smallest responsible surface, chooses lightweight or structured planning, delegates only when specialist analysis reduces risk, and requires correctness plus Ponytail review.

A request for a new service, dependency, framework, abstraction, or refactor is treated as an implementation assumption until evidence shows it is necessary. When a simpler alternative materially changes the requested architecture, the trade-off is explained rather than silently overriding the request.

### Analysis and debugging

`tu-analyzer` identifies current behavior, native capabilities, repository mechanisms, consumers, violated invariants, and the smallest responsible component. It stops when enough evidence exists for a safe decision.

A bug fix must reproduce or characterize the failure, identify the violated invariant, fix the root cause, add regression verification, and stop. Broader debt is reported separately.

### Planning and modeling

`tu-modeler` records the actual outcome, assumptions, preserved behavior, ladder results, selected solution, rejected alternatives, non-goals, risks, and verification. It does not create options merely to fill a template.

For trivial work it emits a compact decision. Structured planning is reserved for cross-module, contract, persistence, messaging, concurrency, security, migration, service-boundary, abstraction, or dependency changes.

### Suggested implementation and handoff

The handoff names the smallest responsible component and coherent diff. It excludes unrelated cleanup, broad renaming, file moves without concrete benefit, speculative configuration, unused parameters, future-only interfaces, forwarding wrappers, generic frameworks for isolated cases, and unapproved dependencies.

### Refactoring

Refactoring requires a concrete structural problem, practical consequence, preserved behavior, evidence that total complexity decreases, and executable protection.

The final assessment compares concepts, files, and abstraction layers before and after without treating those metrics as mechanical goals.

### Review

`tu-reviewer` reviews correctness first: required and preserved behavior, security, data integrity, contracts, errors, concurrency, transactions, observability, deployment, migrations, and tests.

It then checks whether every changed file, type, abstraction, option, dependency, and cleanup is currently necessary. It also checks under-engineering: removed validation, weakened error handling, bypassed boundaries, hidden logic, duplicate business rules, missing observability, ignored concurrency or transactions, migration omissions, and fragile hacks.

Findings remain evidence-based:

- `blocker`: correctness, security, data-integrity, or contract violation;
- `major`: material complexity, coupling, unnecessary dependency, or architectural risk;
- `minor`: localized unnecessary complexity or maintainability issue;
- `suggestion`: optional simplification that does not block approval.

Theoretical minimalism is not a review finding.

### Testing

`tu-verifier` tests required behavior and preserved contracts, adds regression checks for actual risk, prefers stable behavioral assertions, and reuses existing fixtures. It does not create a large test framework for one case or test hypothetical unsupported behavior.

### Documentation

Documentation agents update actual affected sections, reuse existing structure, avoid speculative capabilities, avoid unnecessary new documents, and remove obsolete guidance when behavior is simplified.

## Delegation context

The optional `ponytail_context` carries decisions without breaking existing packets:

```yaml
ponytail_context:
  required_outcome:
  - reject duplicate active subscriptions
  preserved_behavior:
  - existing renewal behavior remains unchanged
  change_required: true
  selected_solution: add one database uniqueness constraint and map the existing conflict error
  alternatives_checked:
    no_code: not sufficient
    platform_native: database uniqueness provides the required atomic guarantee
    existing_repository_solution: existing conflict mapper is reusable
    configuration_or_data: schema change is required
    localized_change: one migration plus existing mapper update
  abstractions_approved: []
  dependencies_approved: []
  non_goals:
  - no subscription-service redesign
  risks:
  - existing duplicate data must be checked before migration
  verification_required:
  - migration validation
  - concurrency integration test
```

Workers consume this package and reopen decisions only when new evidence invalidates them.

## Example: no custom component required

```text
User requests a new custom component
    ↓
t-understand identifies the actual required outcome
    ↓
tu-modeler checks platform and repository capabilities
    ↓
existing supported capability fully satisfies the contract
    ↓
no component, abstraction, or dependency is created
    ↓
configuration and focused tests are updated
    ↓
tu-reviewer confirms correctness and lower total complexity
```

## Example: localized code is justified

```text
User requests behavior not supported by existing capabilities
    ↓
no-change, no-code, platform, repository, and composition options are checked
    ↓
none satisfies the required contract
    ↓
selected solution changes one cohesive responsible component
    ↓
no new framework, abstraction, or dependency is introduced
    ↓
regression tests verify required and preserved behavior
```

## Incorrect interpretations

- **Bad minimalism:** removing validation because it reduces code.
- **Bad minimalism:** bypassing an adapter boundary and coupling domain code to infrastructure.
- **Bad minimalism:** hiding business logic inside configuration.
- **Bad minimalism:** choosing one global flag when per-entity behavior is required.
- **Bad reuse:** using a helper that represents another business concept.
- **Bad platform-first:** selecting a native feature whose contract does not meet product requirements.
- **Bad no-code:** moving complex rules into untestable deployment scripts.
- **Bad abstraction avoidance:** duplicating a critical rule across services when one justified shared policy boundary is required.

## Platform packaging

OpenCode, Codex, Claude Code, and Cursor receive the same canonical policy and skill through the existing installer. Platform adapters remain thin and preserve their existing permission and delegation models. No Ponytail-specific permission is added.
