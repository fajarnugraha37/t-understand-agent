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
