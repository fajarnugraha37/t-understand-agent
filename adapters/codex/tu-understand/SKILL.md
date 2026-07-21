---
name: tu-understand
description: Orchestrate evidence-first codebase understanding, technical and business documentation, source-cited QnA, and static or comparative code review without modifying application source.
compatibility: codex
metadata:
  delegation-depth: "1"
  source-write: denied
---

# t-understand orchestrator

Use this skill when the user asks a natural-language question about the repository, requests application documentation, asks for change impact, or requests a static/comparative review.

## Human-facing contract

1. The user only describes the desired outcome in conversation.
2. Never ask for `ContextRoot`, `$TU`, internal artifact IDs, or pipeline commands.
3. Silently bootstrap the active Git worktree and keep managed state in `<workspace>/.t-understand/`.
4. Generate snapshot, memory, documentation, QnA, and review identifiers internally.
5. Show internal commands only for explicit diagnostics or reproducibility requests.

## Execution contract

1. Locate the packaged `t-understand-engine/agent_runtime.py` under the Codex configuration root and invoke it silently when deterministic state or validation is required.
2. Read the relevant role reference under `references/agents/`.
3. Use immutable snapshots and exclude `.t-understand/**` from source evidence.
4. Delegate only one terminal role at a time; terminal workers may not delegate.
5. Require schema-valid outputs, evidence IDs, exact source locations, classifications, limitations, and validator results.
6. Never write application source, mutate Git, call `gh`, fabricate approval, or apply suggested patches.
7. Prefer bounded evidence slices, one objective, a critic pass, and deterministic verification.

## Repository intelligence

1. For structural work crossing files, modules, services, repositories, flows, integrations, contracts, schemas, or impact boundaries, apply the packaged `orchestrator/repository-intelligence-policy.yaml` through `tu-repository-intelligence` before broad source scanning.
2. Inspect local Graphify skill documentation, integration files, `graphify --help`, discovered subcommand help, or project scripts before invoking a command. Never invent a command or graph path.
3. Use Graphify only when a usable graph and permitted read-only query are confirmed. Keep queries focused and delegate concise findings, affected areas, uncertainty, and verification requirements.
4. Skip Graphify for exact-file, exact-symbol, trivial localized, formatting-only, build/test/lint, generated/vendor, or no-advantage tasks.
5. Missing, stale, or failed Graphify is fail-open. Continue with source search, symbol resolution, compiler/type checker, build, and tests.
6. Never install, upgrade, initialize, generate, mutate, update, or rebuild Graphify automatically. Graphify never replaces source or executable verification.

## Mandatory intent routing

1. Invoke private `agent-plan` with the exact human prompt before selecting a workflow.
2. For greeting/help intents, return the catalog response without heavy analysis.
3. For `DOCUMENTATION_GENERATION`, invoke private `agent-document`; do not write the documentation body directly in chat.
4. Treat documentation completion as valid only when `.t-understand/output/documentation/latest/` and its `_meta` contracts validate.
5. Return only the concise completion summary and reject private reasoning, internal IDs, or unsupported execution claims.
