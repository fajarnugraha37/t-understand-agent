# t-understand 1.0.2

`t-understand` 1.0.2 changes the product from CLI-oriented onboarding to an agent-native conversational workflow.

## Human-facing changes

- The normal interface is now the conversation in OpenCode, Codex, Claude Code, or Cursor.
- Users are never asked for `ContextRoot`, `$TU`, internal artifact IDs, package IDs, installation IDs, or pipeline commands.
- The active Git worktree is detected automatically.
- Workspace state is managed automatically under `<workspace>/.t-understand/`.
- Internal state is excluded from snapshots, discovery, code review, and Git operations.
- Platform packages now include the private deterministic engine, schemas, policies, adapters, and templates.

## Installer changes

PowerShell installation is now:

```powershell
.\bin\install.ps1 -Target opencode
```

Replacement is explicit:

```powershell
.\bin\install.ps1 -Target opencode -Force
```

The same semantics are available in shell through `./bin/install.sh opencode [--force]`.

`-Force` now replaces both unmanaged collisions and an existing managed installation. Existing files are backed up, prior installation backups are restored before replacement, a fresh manifest is written, and doctor validation remains mandatory.

## Preserved guarantees

- all skills remain namespaced `tu-*`;
- local work does not fall back to permission prompts;
- `gh` remains denied;
- Git remains read-only;
- application source remains read-only to t-understand;
- suggested review patches remain advisory;
- all Phase 1–20 capabilities remain included.
