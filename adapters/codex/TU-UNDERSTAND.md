# t-understand Codex profile

Codex engine path: `~/.codex/t-understand-engine/agent_runtime.py`.

`t-understand` is conversation-first. Ask Codex to understand, explain, document, or review the repository in the current working directory. Do not ask users for `ContextRoot`, `$TU`, internal IDs, or manual runtime commands.

The `tu-understand` skill silently bootstraps `<workspace>/.t-understand/`, generates internal operation IDs, selects immutable snapshots, and invokes the packaged deterministic engine. Internal commands are implementation details and are shown only for explicit diagnostics.

All packaged skills use the `tu-*` namespace. Start Codex with the packaged `tu-understand` profile when using CLI mode. The profile uses `approval_policy = "never"` with `sandbox_mode = "workspace-write"`; rules deny `gh` and mutating Git subcommands while preserving read-only Git inspection. Suggested patches remain advisory.

For structural cross-boundary work, `tu-understand` uses the packaged canonical repository-intelligence policy and `tu-repository-intelligence`. Graphify is optional, checked quietly, and queried only through locally documented read-only operations when a usable graph exists. Missing, stale, or failed Graphify never blocks source inspection, symbol resolution, compiler, build, or test verification. Graph installation, initialization, generation, mutation, update, and rebuild are never automatic.

## Greeting and artifact-first documentation

The `tu-understand` skill must call private `agent-plan` routing for each prompt. A greeting-only prompt displays capabilities. Explicit documentation generation must invoke `agent-document`, create the stable file view under `.t-understand/output/documentation/latest/`, and return only the completion summary. Chat-only documentation, private reasoning leakage, and unexecuted pass claims are forbidden.
