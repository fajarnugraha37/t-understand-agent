# t-understand Claude Code Instructions

Claude Code engine path: `~/.claude/t-understand-engine/agent_runtime.py`.

Use the `t-understand` coordinator and terminal `tu-*` subagents for repository understanding, documentation, source-grounded QnA, change impact, and review. The user communicates through normal conversation. Never require `ContextRoot`, `$TU`, internal artifact IDs, or manual pipeline commands.

Silently bootstrap the active Git worktree before the first substantive operation. Keep managed state under `<workspace>/.t-understand/`, exclude it from source evidence and review, and create all operation identifiers internally.

The installed settings use `acceptEdits` plus explicit allow/deny rules so local work proceeds without per-action prompts. Outside-workspace file access, `gh`, and mutating Git commands are denied; Git is read-only. Require immutable snapshots, evidence citations, independent critique, and deterministic verification. Subagents may not spawn subagents. Suggested patches are not applied to application source.
