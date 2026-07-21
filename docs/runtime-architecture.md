# Phase 2 Runtime Architecture

## Purpose

The Phase 2 runtime turns the Phase 1 governance contracts into a deterministic local control plane. It does not perform code analysis itself. It controls who may act, what they must produce, and whether the lifecycle may advance.

## Components

```text
bin/t-understand
    ↓
tu_runtime.cli
    ↓
LifecycleEngine
    ├── Registry
    ├── ContractValidator
    └── RuntimeWorkspace
```

### Registry

Loads canonical workflow, agent, artifact, authority, and model-profile registries. Runtime behavior is derived from those registries rather than duplicated in command-specific code.

### Contract validator

Validates delegation packets, result envelopes, work state, approval records, transition records, and loopback records against JSON Schema.

### Runtime workspace

Owns the writable `.t-understand/<work-id>/` boundary. It provides atomic YAML writes, append-only JSONL events, SHA-256 calculation, artifact import, and a single local mutation lock.

### Lifecycle engine

Provides:

- work initialization;
- current-state inspection;
- root action routing;
- worker delegation generation;
- worker result acceptance;
- root state completion;
- human decision recording;
- transition recording;
- loopback and artifact invalidation;
- blocked work resume;
- runtime integrity verification.

## Validate-before-commit

For worker results, the runtime checks:

1. result JSON Schema;
2. active invocation identity;
3. expected worker;
4. workflow and current state;
5. state-version binding;
6. permitted loopback target;
7. exact artifact type set;
8. exact delegated output path;
9. path containment;
10. SHA-256 digest.

Only after those checks pass is the result accepted and the state transitioned.

## State statuses

```text
ACTIVE
  ├── root completion → next state
  └── worker routing → WAITING_RESULT

WAITING_RESULT
  ├── completed result → next state
  ├── blocked/failed result → BLOCKED
  └── loopback result → earlier state

BLOCKED
  └── explicit resume → ACTIVE

terminal state
  └── COMPLETED
```

## Honest boundary

The runtime validates control-plane contracts and artifact integrity. It does not yet validate the domain semantics of artifacts such as source inventories, system models, documents, answers, or review findings. Those implementations and their content validators belong to later phases.
