# t-understand Codex profile

Codex engine path: `~/.codex/t-understand-engine/agent_runtime.py`.

`t-understand` is conversation-first. Ask Codex to understand, explain, document, or review the repository in the current working directory. Do not ask users for `ContextRoot`, `$TU`, internal IDs, or manual runtime commands.

The `tu-understand` skill silently bootstraps `<workspace>/.t-understand/`, generates internal operation IDs, selects immutable snapshots, and invokes the packaged deterministic engine. Internal commands are implementation details and are shown only for explicit diagnostics.

All packaged skills use the `tu-*` namespace. Start Codex with the packaged `tu-understand` profile when using CLI mode. The profile uses `approval_policy = "never"` with `sandbox_mode = "workspace-write"`; rules deny `gh` and mutating Git subcommands while preserving read-only Git inspection. Suggested patches remain advisory.
