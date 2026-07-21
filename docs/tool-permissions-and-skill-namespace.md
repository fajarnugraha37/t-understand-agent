# Tool Permissions and Skill Namespace

## Skill namespace

Every t-understand skill is named `tu-*`. This includes the Codex aggregate entry point, `tu-understand`. The product, CLI, and root orchestrator remain named `t-understand`; they are not skills and therefore do not share the skill namespace.

Package validation rejects any `SKILL.md` whose frontmatter name does not begin with `tu-`.

## Permission model

The platform adapters use a no-prompt local policy:

- local file and process tools inside the active working directory are allowed;
- outside-workspace access is denied;
- every `gh` command is denied;
- mutating Git commands are denied;
- explicitly read-only Git inspection is allowed;
- denial fails closed and is not converted into an interactive `ask` decision.

This is a platform permission policy, not an expansion of agent authority. t-understand continues to treat registered application source as analysis input and writes durable artifacts only to approved context/runtime targets.

## Platform realization

### OpenCode

Generated agent frontmatter uses `allow`/`deny` rules only. `external_directory` is denied, local tools are allowed, `git *` is denied and explicit read-only Git patterns are reopened, and `gh *` remains denied. Only the root orchestrator may delegate to `tu-*` terminal agents.

### Claude Code

The package includes a mergeable `settings.json` overlay with `defaultMode: acceptEdits`, broad local tool allow rules, and deny rules for outside-relative paths, `gh`, and Git mutation. Existing unrelated settings are preserved and restored during uninstall.

### Codex

The package includes `tu-understand.config.toml` with `approval_policy = "never"` and `sandbox_mode = "workspace-write"`, plus command rules that forbid `gh` and mutating Git subcommands. Start it with `codex --profile tu-understand`.

### Cursor

The package includes `cli-config.json` with local `Read`, `Write`, and `Shell` authorization and deny entries for outside-relative paths, `gh`, and Git mutation. Existing configuration is merged and restored safely.

## Installer behavior

JSON permission overlays are deep-merged rather than replacing an existing Claude or Cursor configuration. Array values are unioned deterministically. The original file is checksummed and backed up. `doctor` validates the resulting merged file, and uninstall restores the exact backup.
