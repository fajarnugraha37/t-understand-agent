# Platform Adapters and Managed Installation

`t-understand` installs as agents, skills, host permissions, and a private deterministic engine under the global configuration root of the selected coding-agent host.

## Human-facing installation

PowerShell:

```powershell
.\bin\install.ps1 -Target opencode
.\bin\install.ps1 -Target opencode -Force
```

Shell:

```bash
./bin/install.sh opencode
./bin/install.sh opencode --force
```

The only required argument is the host:

```text
opencode
codex
claude-code
cursor
```

The installer automatically determines:

- installer state location;
- package ID;
- installation ID;
- standard host configuration root;
- ownership manifest location;
- backup location.

No `ContextRoot` is requested.

## Force semantics

Without force:

- a valid identical managed install is idempotent;
- a different managed install is rejected;
- unmanaged file collisions are rejected;
- modified managed files block replacement.

With `-Force` or `--force`:

1. an existing managed installation is uninstalled forcefully;
2. its original pre-install backups are restored;
3. the current platform package is rebuilt;
4. conflicting destination files are backed up;
5. the new payload is installed;
6. checksums and a new ownership manifest are written;
7. post-install doctor must pass.

Force is explicit replacement authority, not permission to skip validation.

## Installed payload

```text
platform agents/rules
platform skills
permission configuration
t-understand-engine/
  agent_runtime.py
  runtime/
  schemas/
  orchestrator/
  language-adapters/
  templates/
```

The engine is called by the installed root agent. Humans use conversation instead of the engine command line.

## Automatic workspace state

When a user opens a Git repository and asks a t-understand question, the root agent silently initializes:

```text
<workspace>/.t-understand/
```

This directory is excluded from snapshots, discovery, review, and Git mutation.

## Default host roots

```text
OpenCode     ~/.config/opencode
Codex        ~/.codex
Claude Code  ~/.claude
Cursor       ~/.cursor
```

Environment-specific overrides and `-InstallRoot`/`--install-root` are supported for advanced installation.

## Managed installation safety

- every installed file has a SHA-256 digest;
- existing files are backed up before replacement;
- JSON host configuration is deep-merged where supported;
- doctor detects missing and modified managed files;
- uninstall restores original backups;
- source-project installation targets are rejected by the advanced installer path;
- package generation and installation are lock-protected;
- generated platform payloads contain no `ask` permission fallback.

## Doctor and uninstall

```powershell
.\bin\doctor.ps1 -Target opencode
.\bin\uninstall.ps1 -Target opencode
.\bin\uninstall.ps1 -Target opencode -Force
```

```bash
./bin/doctor.sh opencode
./bin/uninstall.sh opencode
./bin/uninstall.sh opencode --force
```

Uninstall without force refuses modified managed files. Force removes them and restores backups where available.
