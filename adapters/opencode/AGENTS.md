# t-understand OpenCode Instructions

OpenCode engine path: `~/.config/opencode/t-understand-engine/agent_runtime.py`.

Use the `t-understand` primary agent for repository understanding, documentation, source-grounded questions, change impact, and code review. Humans interact only by asking questions or describing outcomes; never ask them for `ContextRoot`, `$TU`, internal IDs, or pipeline commands.

On the first substantive request in a Git worktree, silently run the installed engine bootstrap and manage state under `<workspace>/.t-understand/`. Exclude that directory from source snapshots and review. Load only installed `tu-*` skills.

Local tools inside the active working directory are pre-authorized and must not request per-action permission. Outside-workspace access, `gh`, and mutating Git commands are denied; Git is limited to read-only inspection. Workers are terminal and may not delegate. Suggested patches remain advisory and application source is never modified by t-understand.

For structural cross-file, cross-module, cross-service, flow, integration, or change-impact tasks, the primary agent applies the packaged `orchestrator/repository-intelligence-policy.yaml` through `tu-repository-intelligence`. Graphify is checked quietly and used first only when a locally documented usable graph and permitted read-only query exist. Workers reuse delegated findings. Missing, stale, or failed Graphify never blocks normal source, search, language-server, compiler, build, or test work. Never install, initialize, generate, mutate, update, or rebuild Graphify automatically.

## Greeting and artifact-first documentation

For every human prompt, run the private `agent-plan` operation first. Greeting-only prompts return the capability card without heavyweight analysis. A substantive task overrides a greeting prefix.

When intent is documentation generation, run the private `agent-document` operation. Documentation must be created under `.t-understand/output/documentation/latest/`; a long chat answer is not completion. Return only the completion summary and never expose internal todos, thoughts, IDs, or unexecuted pass claims.
