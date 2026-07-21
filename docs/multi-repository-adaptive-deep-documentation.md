# Multi-repository adaptive deep documentation

Status: implemented in `t-understand 1.1.0`.

## Purpose

This release treats a directory containing several Git repositories as one application workspace when the active prompt explicitly requests all repositories or when an existing application workspace is already registered. It then creates an evidence-bound documentation plan whose size adapts to the repository and flow inventory.

The implementation has two non-negotiable properties:

1. document quantity may grow, but no planned requirement may be silently omitted;
2. documentation depth may grow, but unsupported business intent or runtime behavior may not be invented.

## Agent-native workspace resolution

A substantive prompt is resolved in this order:

1. reuse an existing ancestor application root containing `.t-understand/application.yaml`;
2. resolve the active Git root;
3. when the prompt explicitly requests multiple/all repositories, scan bounded sibling roots;
4. when the host opens a non-Git parent workspace, scan bounded child roots;
5. classify repository roles conservatively from source markers;
6. initialize one application manifest and one managed `.t-understand/` directory at the application root;
7. bind every repository to that application and capture one application snapshot containing repository-local revisions.

The resolver excludes generated, vendored, IDE, build, VCS, and `.t-understand` directories. Local filesystem paths remain machine-local bindings and are not used as portable repository identity.

## Adaptive documentation plan

The planner begins with 41 mandatory documents across:

- application;
- business;
- domain;
- flows;
- integrations;
- data;
- operations;
- reference.

It then adds seven documents for every repository:

- overview;
- architecture;
- interfaces;
- domain;
- flows;
- operations;
- limitations.

Flow planning is evidence- and risk-sensitive:

- Tier 1: five deep documents covering overview, interactions, failure/recovery, state/data/consistency, and security/observability/operations;
- Tier 2: one document containing all required flow perspectives;
- Tier 3: complete entry in the flow catalog.

Every planned document has a stable requirement ID, unique path, required section list, source-model set, scope, and generation mode.

## Business and domain truth model

Implementation evidence may support facts about technical structure and implemented behavior. It does not automatically prove business intent.

The model preserves these distinctions:

- `FACT` becomes `TECHNICAL_FACT` in documentation;
- `IMPLEMENTED_BEHAVIOR` remains implementation-grounded behavior;
- `BUSINESS_INFERENCE` must carry an explicit limitation;
- `HUMAN_CONFIRMED` becomes `HUMAN_CONFIRMED_RULE`;
- `UNKNOWN` becomes `UNKNOWN_INTENT`;
- conflicts and limitations remain visible.

Specific anti-hallucination rules include:

- repository boundary is only a bounded-context candidate;
- role/permission surface is only an actor candidate;
- enum/status vocabulary is not a complete state machine without transitions;
- exception/failure path may indicate an invariant candidate but does not prove the business policy;
- call graph is partial flow evidence, not a complete end-to-end use case;
- build/test commands are discovered, not passed, unless execution evidence exists.

## Application-flow depth

Important flows are documented through these perspectives:

- business and application intent;
- trigger and preconditions;
- participants and repository attribution;
- ordered interactions;
- synchronous and asynchronous boundaries;
- state and data impact;
- transaction and consistency boundaries;
- alternatives, failures, retry, compensation, and reconciliation;
- authentication, authorization, and sensitive-data concerns;
- logs, metrics, traces, alerts, SLOs, and recovery guidance;
- evidence, traceability, unknowns, and limitations.

Where evidence is absent, the required perspective remains present and explicitly states the gap. This is counted as documented unknown coverage, not as a supported fact.

## Completeness mechanism

Generation produces:

- `documentation-requirements.yaml`;
- `document-plan.yaml`;
- one Markdown file for every requirement;
- `generation-ledger.jsonl` with exactly one generated record per requirement;
- `sections.jsonl`;
- `traceability.jsonl`;
- `coverage-ledger.yaml`;
- verification and critique reports.

Publication is blocked unless all of these equal `1.0`:

- requirement coverage;
- model-record coverage;
- required-section coverage;
- repository coverage;
- flow coverage;
- inference disclosure;
- supported-section traceability.

Generation also fails on duplicate paths, duplicate model-record IDs, missing headings, unsupported facts, stale supported sections, placeholder content, shallow content, broken relative links, checksum mismatches, or a difference between planned and generated requirement sets.

## Stable user view

After canonical validation and critique pass, the complete docset is copied atomically to:

```text
<application-workspace>/.t-understand/output/documentation/latest/
```

The previous stable view remains intact if publication fails. Application source repositories and Git state are not modified.

## Incremental implications

The canonical model and documentation artifacts retain stable IDs, snapshot bindings, model-record references, and requirement IDs. This permits future refresh logic to identify changed repositories, relations, claims, flows, and dependent documents without rebuilding unrelated knowledge. `1.1.0` provides the complete generation contract; further optimization may reduce work while preserving the same completeness gates.
