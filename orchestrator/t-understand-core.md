# t-understand Core Contract

`t-understand` is the sole control-plane agent. It resolves the requested application and snapshot, selects one registered workflow, produces bounded delegation packets, validates worker result envelopes, controls loopbacks, records human decisions, and advances state only when contract gates pass.

## Topology

```text
human ↔ t-understand → one terminal worker invocation
```

Workers never call one another. Parallelism, when introduced in later phases, is orchestrator-controlled and limited to independent read-only tasks.

## Repository intelligence

`t-understand` owns the first repository-intelligence decision. For work crossing files, modules, services, repositories, flows, integrations, contracts, schemas, deployment boundaries, or impact boundaries, it applies `repository-intelligence-policy.yaml` through `tu-repository-intelligence` before broad source exploration.

Graphify is optional and used first only when a locally documented executable or integration, usable graph, and permitted read-only query are confirmed. The orchestrator performs focused discovery, passes concise reusable findings in the optional delegation context, and prevents duplicate worker discovery by default. Missing, stale, permission-denied, or failed Graphify is fail-open and never blocks normal source, search, language-server, compiler, build, or test work.

Graphify findings are navigation and impact candidates. Final implementation claims require revision-bound source or authoritative configuration evidence plus executable checks where applicable. Installation, upgrade, initialization, graph generation, mutation, update, and rebuild are never automatic.

## Ponytail-first engineering

`t-understand` owns the initial engineering decision through `ponytail-engineering-policy.yaml` and `tu-ponytail-engineering`.

It separates the required outcome from the requested implementation, then evaluates no change, no application code, platform-native behavior, existing repository mechanisms, configuration/data/composition, localized code, an existing abstraction, a new abstraction, and a new dependency in that order. It stops at the first option that completely satisfies the current contract.

The orchestrator uses a compact decision for local low-risk work and reserves structured planning or specialist review for cross-module, contract, persistence, messaging, concurrency, security, migration, service-boundary, abstraction, or dependency changes. It passes one optional `ponytail_context` so workers reuse the selected solution, non-goals, approved abstractions, approved dependencies, risks, and verification requirements instead of repeating the complete decision ladder.

External Ponytail integration is optional. Missing integration never blocks the task, and the system never installs, upgrades, or invents Ponytail commands, files, hooks, or platform behavior.

Correctness, security, data integrity, contracts, compatibility, compliance, observability, operational safety, performance, and material testability always take precedence over minimality. Necessary complexity is preserved and clarified; accidental and speculative complexity is removed.

## Source boundary

Every source repository is immutable from the perspective of t-understand. Runtime-generated context artifacts live in a dedicated application context repository or local runtime directory, never in source repositories unless a human separately copies them.

## State advancement

A state advances only when:

1. the expected artifact exists;
2. the artifact validates against its schema;
3. the result envelope identifies the correct worker and skill;
4. evidence and snapshot references are valid;
5. required critique and verification gates pass;
6. no unresolved blocker or freshness violation remains;
7. required human authority is recorded.

Worker prose alone cannot advance state.

## Implemented runtime foundation

Phase 2 implements the registry-driven lifecycle control plane through the `tu_runtime` package. Phase 3 adds portable application manifests, machine-local workspace maps, repository identity normalization, and read-only source-boundary resolution. Phase 4 adds immutable Git target resolution, application snapshots, overlay integrity, drift detection, and immutable review-target binding. Repository discovery and semantic domain analysis remain assigned to later phases.
