# t-understand Claude Code Instructions

Claude Code engine path: `~/.claude/t-understand-engine/agent_runtime.py`.

Use the `t-understand` coordinator and terminal `tu-*` subagents for repository understanding, documentation, source-grounded QnA, change impact, and review. The user communicates through normal conversation. Never require `ContextRoot`, `$TU`, internal artifact IDs, or manual pipeline commands.

Silently bootstrap the active Git worktree before the first substantive operation. Keep managed state under `<workspace>/.t-understand/`, exclude it from source evidence and review, and create all operation identifiers internally.

The installed settings use `acceptEdits` plus explicit allow/deny rules so local work proceeds without per-action prompts. Outside-workspace file access, `gh`, and mutating Git commands are denied; Git is read-only. Require immutable snapshots, evidence citations, independent critique, and deterministic verification. Subagents may not spawn subagents. Suggested patches are not applied to application source.

For structural cross-file, cross-module, cross-service, flow, integration, or change-impact tasks, the coordinator applies the packaged `orchestrator/repository-intelligence-policy.yaml` through `tu-repository-intelligence`. Graphify is checked quietly and used first only when a locally documented usable graph and permitted read-only query exist. Subagents reuse delegated findings rather than repeating discovery. Missing, stale, or failed Graphify is fail-open and never replaces source, configuration, compiler, build, or test verification. Never install, initialize, generate, mutate, update, or rebuild Graphify automatically.

For planning, debugging, refactoring, suggested implementation, tests, documentation, and review, apply the packaged `orchestrator/ponytail-engineering-policy.yaml` through `tu-ponytail-engineering`. Separate required outcomes from implementation assumptions, evaluate the decision ladder in order, and stop at the first complete valid solution. Correctness, security, data integrity, contracts, compatibility, compliance, observability, operational safety, performance, and material testability take precedence over minimality. Use a lightweight path for trivial work, pass one reusable `ponytail_context`, and require evidence before new abstractions or dependencies. External Ponytail integration is optional and must never be installed, upgraded, or invented automatically.

## Greeting and artifact-first documentation

Use the private `agent-plan` operation for every prompt. Greeting-only prompts render capabilities without heavyweight analysis. Explicit documentation requests must invoke `agent-document`, create files under `.t-understand/output/documentation/latest/`, and return only a concise completion summary. Never use a chat-only documentation dump as completion and never expose private reasoning, todos, internal IDs, or unsupported verification claims.
