# t-understand OpenCode Instructions

OpenCode engine path: `~/.config/opencode/t-understand-engine/agent_runtime.py`.

Use the `t-understand` primary agent for repository understanding, documentation, source-grounded questions, change impact, and code review. Humans interact only by asking questions or describing outcomes; never ask them for `ContextRoot`, `$TU`, internal IDs, or pipeline commands.

On the first substantive request in a Git worktree, silently run the installed engine bootstrap and manage state under `<workspace>/.t-understand/`. Exclude that directory from source snapshots and review. Load only installed `tu-*` skills.

Local tools inside the active working directory are pre-authorized and must not request per-action permission. Outside-workspace access, `gh`, and mutating Git commands are denied; Git is limited to read-only inspection. Workers are terminal and may not delegate. Suggested patches remain advisory and application source is never modified by t-understand.

For structural cross-file, cross-module, cross-service, flow, integration, or change-impact tasks, the primary agent applies the packaged `orchestrator/repository-intelligence-policy.yaml` through `tu-repository-intelligence`. Graphify is checked quietly and used first only when a locally documented usable graph and permitted read-only query exist. Workers reuse delegated findings. Missing, stale, or failed Graphify never blocks normal source, search, language-server, compiler, build, or test work. Never install, initialize, generate, mutate, update, or rebuild Graphify automatically.

## Greeting and artifact-first documentation

For every human prompt, run the private `agent-plan` operation first. Greeting-only prompts return the capability card without heavyweight analysis. A substantive task overrides a greeting prefix.

Use the exact option form below; never pass the prompt as a positional argument:

```bash
python "$HOME/.config/opencode/t-understand-engine/agent_runtime.py" agent-plan --prompt "<exact human prompt>"
```

When intent is documentation generation, run the private `agent-document` operation using the same required `--prompt` option:

```bash
python "$HOME/.config/opencode/t-understand-engine/agent_runtime.py" agent-document --prompt "<exact human prompt>"
```

Deep repository documentation is a synchronous evidence, modeling, generation, and validation workflow. When invoking `agent-document` through OpenCode's shell tool, always set the tool timeout to at least `1800000` milliseconds (30 minutes). Never use or inherit the shell tool's default `120000` millisecond timeout for this operation. The installed launcher emits a stderr heartbeat while work is active; treat it as liveness information, not as final output, and continue waiting for the final JSON result.

Documentation must be created under `.t-understand/output/documentation/latest/`; a long chat answer is not completion. Return only the completion summary and never expose internal todos, raw tracebacks, operation IDs, unexecuted pass claims, shell heartbeat lines, or internal progress narration. Do not narrate retries or internal investigation unless the human explicitly asks for diagnostics.
