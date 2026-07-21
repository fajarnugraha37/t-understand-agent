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
