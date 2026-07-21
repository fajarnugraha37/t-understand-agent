# Phase 2 Assurance — Core Runtime and Lifecycle Engine

## Scope delivered

Phase 2 implements the deterministic control-plane runtime for all canonical t-understand workflows. It does not implement source-code understanding itself; it ensures later agents and skills execute within registered ownership, transition, evidence, and permission boundaries.

Implemented capabilities:

- lifecycle work initialization;
- registry-driven owner, skill, output, and transition resolution;
- explicit runtime-root boundary;
- atomic work-state persistence;
- one active worker invocation per work item;
- depth-one delegation packets;
- worker result identity binding;
- exact expected-output enforcement;
- relative-path containment;
- SHA-256 artifact validation;
- validate-before-commit result acceptance;
- root-owned state completion;
- human approval and rejection records;
- blocked and resume behavior;
- backward loopbacks;
- stale artifact marking after loopback;
- transition and append-only event records;
- runtime integrity validation;
- CLI entry points for all control-plane operations.

## Validated lifecycle surface

The runtime reads the canonical workflow registry rather than encoding separate state machines in code.

Validated inventory:

- 5 workflow families;
- 55 workflow states;
- 3 model profiles;
- 10 terminal worker roles;
- 6 runtime JSON Schemas;
- 11 CLI commands.

Every workflow was executed through a synthetic end-to-end test from its registered initial state to its registered terminal state.

## Negative guarantees tested

The suite verifies rejection of:

- nested delegation;
- wrong worker identity;
- stale state-version results;
- path traversal;
- artifact digest mismatch;
- result replay;
- invalid transition skipping;
- forward loopback;
- documentation publication without human approval;
- implicit work-item runtime root;
- invalid work IDs and model profiles.

## Cheap-model support

The runtime moves correctness obligations away from free-form model reasoning and into deterministic mechanisms:

- one primary objective per delegation;
- bounded evidence inputs;
- fixed output paths and types;
- schema validation;
- exact worker/state binding;
- explicit stop conditions;
- critic and verifier lifecycle states;
- deterministic transition rules;
- no flagship-model dependency.

## Explicit limitations

The following are intentionally not claimed in Phase 2:

- application and repository registration;
- Git target and worktree snapshot capture;
- language parsing or semantic extraction;
- source-derived canonical memory;
- technical or business document generation;
- QnA synthesis;
- code-review analysis;
- Mintlify or CodeRabbit-style export;
- live OpenCode, Codex, Claude Code, or Cursor subagent invocation;
- global installation.

These remain assigned to their declared later phases.
