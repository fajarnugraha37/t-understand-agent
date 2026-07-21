from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tomllib
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import atomic_write_yaml, load_yaml, sha256_file, utc_now

INSTALL_ID_RE = re.compile(r"^INST-[A-Z0-9_-]{1,123}$")
PLATFORMS = ("opencode", "codex", "claude-code", "cursor")
MERGED_JSON_CONFIGS = {
    "claude-code": {"settings.json"},
    "cursor": {"cli-config.json"},
}
READ_ONLY_GIT_PATTERNS = (
    "git status*",
    "git diff*",
    "git log*",
    "git show*",
    "git rev-parse*",
    "git symbolic-ref*",
    "git branch --show-current*",
    "git branch --list*",
    "git tag --list*",
    "git ls-files*",
    "git ls-tree*",
    "git cat-file*",
    "git grep*",
    "git remote -v*",
    "git remote get-url*",
    "git config --get*",
    "git config --get-all*",
    "git config --list*",
    "git describe*",
    "git name-rev*",
    "git merge-base*",
    "git for-each-ref*",
    "git blame*",
    "git shortlog*",
    "git count-objects*",
    "git submodule status*",
    "git worktree list*",
    "git reflog show*",
    "git fsck*",
)
MUTATING_GIT_SUBCOMMANDS = (
    "add",
    "am",
    "apply",
    "bisect",
    "checkout",
    "cherry-pick",
    "clean",
    "clone",
    "commit",
    "fetch",
    "gc",
    "init",
    "maintenance",
    "merge",
    "mv",
    "notes",
    "prune",
    "pull",
    "push",
    "rebase",
    "repack",
    "replace",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "update-index",
    "update-ref",
)
MUTATING_GIT_PREFIXES = (
    ("branch", "-d"), ("branch", "-D"), ("branch", "--delete"),
    ("branch", "-m"), ("branch", "-M"), ("branch", "--move"),
    ("branch", "-c"), ("branch", "-C"), ("branch", "--copy"),
    ("branch", "--set-upstream-to"), ("branch", "--unset-upstream"),
    ("config", "--add"), ("config", "--replace-all"),
    ("config", "--unset"), ("config", "--unset-all"),
    ("config", "--rename-section"), ("config", "--remove-section"),
    ("remote", "add"), ("remote", "remove"), ("remote", "rename"),
    ("remote", "set-head"), ("remote", "set-branches"),
    ("remote", "set-url"), ("remote", "prune"), ("remote", "update"),
    ("submodule", "add"), ("submodule", "deinit"),
    ("submodule", "update"), ("submodule", "set-branch"),
    ("submodule", "set-url"), ("submodule", "sync"),
    ("submodule", "absorbgitdirs"), ("submodule", "foreach"),
    ("tag", "-a"), ("tag", "-s"), ("tag", "-u"),
    ("tag", "-f"), ("tag", "-d"), ("tag", "--delete"),
    ("worktree", "add"), ("worktree", "move"),
    ("worktree", "remove"), ("worktree", "prune"),
    ("worktree", "repair"), ("worktree", "lock"),
    ("worktree", "unlock"),
)


def _digest(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = dict(base)
        for key, value in overlay.items():
            result[key] = _deep_merge(result[key], value) if key in result else value
        return result
    if isinstance(base, list) and isinstance(overlay, list):
        result = list(base)
        for value in overlay:
            if value not in result:
                result.append(value)
        return result
    return overlay


def default_target_root(platform: str) -> Path:
    """Return the normal global configuration root for a supported host.

    This is intentionally an installer concern. Application agents continue to
    operate from the user's current workspace and keep project state in the
    auto-managed ``.t-understand`` directory.
    """
    if platform not in PLATFORMS:
        raise TUnderstandError(
            "INSTALL-PLATFORM-001", f"Unsupported platform: {platform}"
        )
    home = Path.home()
    overrides = {
        "opencode": "T_UNDERSTAND_OPENCODE_ROOT",
        "codex": "T_UNDERSTAND_CODEX_ROOT",
        "claude-code": "T_UNDERSTAND_CLAUDE_ROOT",
        "cursor": "T_UNDERSTAND_CURSOR_ROOT",
    }
    override = os.environ.get(overrides[platform])
    if override:
        return Path(override).expanduser().resolve()
    if platform == "opencode":
        xdg = os.environ.get("XDG_CONFIG_HOME")
        return (Path(xdg).expanduser() if xdg else home / ".config") / "opencode"
    if platform == "codex":
        return Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    if platform == "claude-code":
        return home / ".claude"
    return home / ".cursor"


class InstallationManager:
    """Materializes platform adapters into an explicit non-source target."""

    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.contracts = ContractValidator(project_root)

    @property
    def package_root(self) -> Path:
        return self.context_root / "platform-packages"

    def _install_meta(self, target: Path) -> Path:
        return target / ".t-understand-install"

    def _check_id(self, iid: str) -> None:
        if not INSTALL_ID_RE.fullmatch(iid):
            raise TUnderstandError(
                "INSTALL-ID-001",
                "install_id must match ^INST-[A-Z0-9_-]{1,123}$",
            )

    def _source_roots(self) -> list[Path]:
        roots: list[Path] = []
        workspace = self.context_root / "workspace.local.yaml"
        if workspace.exists():
            data = load_yaml(workspace) or {}
            mappings = data.get("repositories", data.get("bindings", {}))
            if isinstance(mappings, dict):
                for value in mappings.values():
                    candidate = value.get("path") if isinstance(value, dict) else value
                    if candidate:
                        roots.append(Path(candidate).expanduser().resolve())
        return roots

    def _ensure_safe_target(self, target: Path) -> Path:
        resolved = target.expanduser().resolve()
        for protected in [self.context_root, *self._source_roots()]:
            try:
                resolved.relative_to(protected)
                raise TUnderstandError(
                    "INSTALL-SOURCE-001",
                    f"Installation target is inside protected context/source root: {protected}",
                )
            except ValueError:
                pass
        return resolved

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock_path = self.context_root / "runtime" / "locks" / "installation.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_path.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError(
                "INSTALL-LOCK-001", "Installation operation already active"
            ) from exc
        try:
            yield
        finally:
            lock_path.rmdir()

    def platforms(self) -> dict[str, Any]:
        return {
            "platforms": [
                load_yaml(self.project_root / "adapters" / platform / "adapter.yaml")
                for platform in PLATFORMS
            ]
        }

    def _skill_dirs(self) -> list[Path]:
        return sorted({p.parent for p in (self.project_root / "skills").rglob("SKILL.md")})

    def _engine_files(self) -> dict[str, bytes]:
        """Package the deterministic engine as an implementation detail.

        Humans interact with the host agent. The host agent may invoke this
        engine silently to build snapshots, memory, documentation, QnA, and
        review artifacts. No standalone CLI knowledge is required from users.
        """
        files: dict[str, bytes] = {}
        included_roots = (
            "runtime",
            "schemas",
            "orchestrator",
            "language-adapters",
            "templates",
        )
        for root_name in included_roots:
            root = self.project_root / root_name
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                relative_parts = path.relative_to(root).parts
                if "__pycache__" in relative_parts or path.suffix in {".pyc", ".pyo"}:
                    continue
                relative = Path("t-understand-engine") / root_name / path.relative_to(root)
                files[relative.as_posix()] = path.read_bytes()
        files["t-understand-engine/VERSION"] = (self.project_root / "VERSION").read_bytes()
        launcher = """from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime'))
from tu_runtime.cli import main
raise SystemExit(main())
"""
        files["t-understand-engine/agent_runtime.py"] = launcher.encode()
        return files

    def _managed_ids(self, platform: str) -> tuple[str, str]:
        version = (self.project_root / "VERSION").read_text().strip()
        safe_version = re.sub(r"[^A-Za-z0-9]+", "_", version).upper()
        safe_platform = platform.replace("-", "_").upper()
        return (f"INST-PKG-{safe_platform}-{safe_version}", f"INST-{safe_platform}")

    def _opencode_permission(self, root: bool) -> dict[str, Any]:
        # OpenCode uses last matching command rule. Deny Git first, then reopen
        # the explicit read-only commands; gh remains denied last.
        bash: dict[str, str] = {"*": "allow", "git": "deny", "git *": "deny"}
        for pattern in READ_ONLY_GIT_PATTERNS:
            bash[pattern] = "allow"
        bash["gh"] = "deny"
        bash["gh *"] = "deny"
        return {
            "*": "allow",
            "external_directory": "deny",
            "bash": bash,
            "skill": {"*": "deny", "tu-*": "allow"},
            "task": {"*": "deny", "tu-*": "allow"} if root else "deny",
        }

    def _claude_settings(self) -> dict[str, Any]:
        deny = [
            "Read(../**)",
            "Edit(../**)",
            "Write(../**)",
            "Bash(gh:*)",
            "Bash(gh *)",
            "Bash(git -C:*)",
            "Bash(git -c:*)",
            "Bash(git --git-dir:*)",
            "Bash(git --work-tree:*)",
        ]
        deny.extend(f"Bash(git {command}:*)" for command in MUTATING_GIT_SUBCOMMANDS)
        deny.extend(f"Bash(git {' '.join(parts)}:*)" for parts in MUTATING_GIT_PREFIXES)
        return {
            "permissions": {
                "defaultMode": "acceptEdits",
                "allow": [
                    "Read(**)",
                    "Edit(**)",
                    "Write(**)",
                    "Glob",
                    "Grep",
                    "LS",
                    "WebFetch",
                    "WebSearch",
                    "Bash(*)",
                ],
                "deny": deny,
            }
        }

    def _cursor_settings(self) -> dict[str, Any]:
        deny = ["Read(../**)", "Write(../**)", "Shell(gh)"]
        deny.extend(f"Shell(git {command})" for command in MUTATING_GIT_SUBCOMMANDS)
        deny.extend(f"Shell(git {' '.join(parts)})" for parts in MUTATING_GIT_PREFIXES)
        return {
            "version": 1,
            "permissions": {
                "allow": ["Read(**)", "Write(**)", "Shell(*)"],
                "deny": deny,
            },
        }

    @staticmethod
    def _codex_profile() -> str:
        return (
            'approval_policy = "never"\n'
            'sandbox_mode = "workspace-write"\n'
            'web_search = "cached"\n\n'
            '[sandbox_workspace_write]\n'
            'network_access = false\n'
        )

    @staticmethod
    def _codex_rules() -> str:
        rules: list[tuple[str, ...]] = [("gh",)]
        rules.extend(("git", command) for command in MUTATING_GIT_SUBCOMMANDS)
        rules.extend(("git", *parts) for parts in MUTATING_GIT_PREFIXES)
        rendered = []
        for parts in rules:
            pattern = ", ".join(json.dumps(part) for part in parts)
            rendered.append(
                "prefix_rule("
                f"pattern = [{pattern}], "
                'decision = "forbidden", '
                'justification = "t-understand permits read-only Git only and denies GitHub CLI"'
                ")"
            )
        return "\n".join(rendered) + "\n"

    def _render_files(self, platform: str) -> dict[str, bytes]:
        if platform not in PLATFORMS:
            raise TUnderstandError(
                "INSTALL-PLATFORM-001", f"Unsupported platform: {platform}"
            )
        files: dict[str, bytes] = {}
        agents = sorted((self.project_root / "agents").glob("*/AGENT.md"))
        skills = self._skill_dirs()

        def opencode_agent(path: Path) -> bytes:
            agent_id = path.parent.name
            frontmatter = {
                "description": f"t-understand role {agent_id}",
                "mode": "primary" if agent_id == "t-understand" else "subagent",
                "permission": self._opencode_permission(agent_id == "t-understand"),
            }
            return (
                "---\n"
                + yaml.safe_dump(frontmatter, sort_keys=False)
                + "---\n\n"
                + path.read_text(encoding="utf-8")
            ).encode()

        def claude_agent(path: Path) -> bytes:
            agent_id = path.parent.name
            if agent_id == "t-understand":
                terminal_agents = ", ".join(
                    candidate.parent.name
                    for candidate in agents
                    if candidate.parent.name != "t-understand"
                )
                tools = (
                    f"Agent({terminal_agents}), Read, Write, Edit, Glob, Grep, "
                    "Bash, WebFetch, WebSearch"
                )
            else:
                tools = "Read, Write, Edit, Glob, Grep, Bash, WebFetch, WebSearch"
            frontmatter = {
                "name": agent_id,
                "description": f"t-understand role {agent_id}",
                "tools": tools,
                "model": "inherit",
                "permissionMode": "acceptEdits",
            }
            return (
                "---\n"
                + yaml.safe_dump(frontmatter, sort_keys=False)
                + "---\n\n"
                + path.read_text(encoding="utf-8")
            ).encode()

        if platform == "opencode":
            for path in agents:
                files[f"agents/{path.parent.name}.md"] = opencode_agent(path)
            for directory in skills:
                files[f"skills/{directory.name}/SKILL.md"] = (
                    directory / "SKILL.md"
                ).read_bytes()
            files["AGENTS.md"] = (
                self.project_root / "adapters" / "opencode" / "AGENTS.md"
            ).read_bytes()
        elif platform == "claude-code":
            for path in agents:
                files[f"agents/{path.parent.name}.md"] = claude_agent(path)
            for directory in skills:
                files[f"skills/{directory.name}/SKILL.md"] = (
                    directory / "SKILL.md"
                ).read_bytes()
            files["CLAUDE.md"] = (
                self.project_root / "adapters" / "claude-code" / "CLAUDE.md"
            ).read_bytes()
            files["settings.json"] = (
                json.dumps(self._claude_settings(), indent=2, sort_keys=True) + "\n"
            ).encode()
        elif platform == "codex":
            for directory in skills:
                files[f"skills/{directory.name}/SKILL.md"] = (
                    directory / "SKILL.md"
                ).read_bytes()
            aggregate_root = self.project_root / "adapters" / "codex" / "tu-understand"
            for path in aggregate_root.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(aggregate_root).as_posix()
                    files[f"skills/tu-understand/{relative}"] = path.read_bytes()
            files["tu-understand.config.toml"] = self._codex_profile().encode()
            files["rules/tu-understand.rules"] = self._codex_rules().encode()
            files["TU-UNDERSTAND.md"] = (
                self.project_root / "adapters" / "codex" / "TU-UNDERSTAND.md"
            ).read_bytes()
        else:
            files["rules/t-understand.mdc"] = (
                self.project_root / "adapters" / "cursor" / "t-understand.mdc"
            ).read_bytes()
            files["cli-config.json"] = (
                json.dumps(self._cursor_settings(), indent=2, sort_keys=True) + "\n"
            ).encode()
            for path in agents:
                files[f"t-understand/agents/{path.parent.name}.md"] = path.read_bytes()
            for directory in skills:
                files[f"t-understand/skills/{directory.name}/SKILL.md"] = (
                    directory / "SKILL.md"
                ).read_bytes()
        files.update(self._engine_files())
        return dict(sorted(files.items()))

    def _validate_platform_payload(self, platform: str, directory: Path) -> list[str]:
        errors: list[str] = []
        payload = directory / "payload"
        for skill in payload.rglob("SKILL.md"):
            try:
                text = skill.read_text()
                frontmatter = yaml.safe_load(text.split("---", 2)[1])
                name = frontmatter.get("name")
                if not isinstance(name, str) or not name.startswith("tu-"):
                    errors.append(
                        f"non-namespaced skill: {skill.relative_to(payload).as_posix()}"
                    )
            except Exception as exc:
                errors.append(
                    f"invalid skill frontmatter {skill.relative_to(payload).as_posix()}: {exc}"
                )
        for path in payload.rglob("*"):
            relative = path.relative_to(payload)
            if relative.parts and relative.parts[0] == "t-understand-engine":
                continue
            if path.is_file() and path.suffix in {".md", ".json", ".toml", ".rules"}:
                text = path.read_text(errors="replace")
                if "bash: ask" in text or '"ask"' in text:
                    errors.append(
                        f"permission prompt remains in {relative.as_posix()}"
                    )
        try:
            if platform == "claude-code":
                json.loads((payload / "settings.json").read_text())
            elif platform == "cursor":
                json.loads((payload / "cli-config.json").read_text())
            elif platform == "codex":
                tomllib.loads((payload / "tu-understand.config.toml").read_text())
        except Exception as exc:
            errors.append(f"invalid platform permission config: {exc}")
        return errors

    def package(
        self, package_id: str, platform: str, force: bool = False
    ) -> dict[str, Any]:
        self._check_id(package_id)
        final = self.package_root / package_id
        if final.exists():
            if not force and self.validate_package(package_id).get("status") == "PASS":
                return self.show_package(package_id)
            if not force:
                raise TUnderstandError(
                    "INSTALL-ID-002", f"Package already exists: {package_id}"
                )
            shutil.rmtree(final, ignore_errors=True)
        files = self._render_files(platform)
        temporary = self.package_root / f".{package_id}.{uuid.uuid4().hex}.tmp"
        temporary.mkdir(parents=True, exist_ok=False)
        try:
            for relative, data in files.items():
                output = temporary / "payload" / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
            entries = [
                {
                    "path": relative,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
                for relative, data in files.items()
            ]
            base = {
                "schema_id": "https://t-understand.dev/schemas/platform-package.schema.json",
                "schema_version": "1.0.0",
                "package_id": package_id,
                "platform": platform,
                "status": "READY",
                "files": entries,
                "generated_at": utc_now(),
            }
            manifest = {**base, "content_digest": _digest(base)}
            self.contracts.validate("platform-package", manifest)
            atomic_write_yaml(temporary / "platform-package.yaml", manifest)
            os.replace(temporary, final)
            if self.validate_package(package_id)["status"] != "PASS":
                raise TUnderstandError(
                    "INSTALL-PACKAGE-001",
                    "Generated platform package failed validation",
                )
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            if final.exists():
                shutil.rmtree(final, ignore_errors=True)
            raise
        return self.show_package(package_id)

    def show_package(self, package_id: str) -> dict[str, Any]:
        self._check_id(package_id)
        return load_yaml(self.package_root / package_id / "platform-package.yaml")

    def validate_package(self, package_id: str) -> dict[str, Any]:
        errors: list[str] = []
        checks = 0
        directory = self.package_root / package_id
        try:
            manifest = load_yaml(directory / "platform-package.yaml")
            checks += 1
            self.contracts.validate("platform-package", manifest)
            for entry in manifest["files"]:
                checks += 1
                path = directory / "payload" / entry["path"]
                if (
                    not path.is_file()
                    or sha256_file(path) != entry["sha256"]
                    or path.stat().st_size != entry["size"]
                ):
                    errors.append(f"invalid package file: {entry['path']}")
            checks += 1
            if (
                _digest({k: v for k, v in manifest.items() if k != "content_digest"})
                != manifest["content_digest"]
            ):
                errors.append("package content digest mismatch")
            checks += 1
            errors.extend(
                self._validate_platform_payload(manifest["platform"], directory)
            )
        except Exception as exc:
            errors.append(str(exc))
        return {
            "status": "PASS" if not errors else "FAIL",
            "package_id": package_id,
            "checks": checks,
            "errors": errors,
            "generated_at": utc_now(),
        }

    def install(
        self,
        install_id: str,
        package_id: str,
        target_root: Path,
        force: bool = False,
    ) -> dict[str, Any]:
        self._check_id(install_id)
        target = self._ensure_safe_target(target_root)
        package = self.show_package(package_id)
        if self.validate_package(package_id)["status"] != "PASS":
            raise TUnderstandError(
                "INSTALL-PACKAGE-002", "Package validation failed"
            )
        metadata_root = self._install_meta(target)
        manifest_path = metadata_root / "install-manifest.yaml"
        if manifest_path.exists():
            current = load_yaml(manifest_path)
            if (
                current["install_id"] == install_id
                and current.get("package_id") == package_id
                and self.doctor(target)["status"] == "PASS"
                and not force
            ):
                return current
            if not force:
                raise TUnderstandError(
                    "INSTALL-CONFLICT-001",
                    "Target already has a managed t-understand installation; rerun with Force to replace it",
                )
            # Force means a real managed replacement, not merely permission to
            # overwrite individual files. Restore the pre-install backup first,
            # then install the new package and create a fresh ownership manifest.
            self.uninstall(target, force=True)
        payload = self.package_root / package_id / "payload"
        target.mkdir(parents=True, exist_ok=True)
        backup_root = metadata_root / "backups" / install_id
        installed: list[dict[str, str]] = []
        backups: list[dict[str, str]] = []
        with self.lock():
            try:
                for entry in package["files"]:
                    relative = Path(entry["path"])
                    source = payload / relative
                    destination = target / relative
                    merge_json = (
                        relative.as_posix()
                        in MERGED_JSON_CONFIGS.get(package["platform"], set())
                    )
                    existing_json: Any = {}
                    if destination.exists():
                        backup = backup_root / relative
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(destination, backup)
                        backups.append(
                            {
                                "path": relative.as_posix(),
                                "sha256": sha256_file(backup),
                            }
                        )
                        if merge_json:
                            try:
                                existing_json = json.loads(destination.read_text())
                            except Exception as exc:
                                if not force:
                                    raise TUnderstandError(
                                        "INSTALL-CONFLICT-003",
                                        f"Existing managed JSON is invalid: {relative}",
                                    ) from exc
                                existing_json = {}
                        elif not force:
                            raise TUnderstandError(
                                "INSTALL-CONFLICT-002",
                                f"Unmanaged destination exists: {relative}",
                            )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if merge_json:
                        overlay = json.loads(source.read_text())
                        merged = _deep_merge(existing_json, overlay)
                        destination.write_text(
                            json.dumps(merged, indent=2, sort_keys=True) + "\n"
                        )
                    else:
                        shutil.copy2(source, destination)
                    installed.append(
                        {
                            "path": relative.as_posix(),
                            "sha256": sha256_file(destination),
                        }
                    )
                base = {
                    "schema_id": "https://t-understand.dev/schemas/install-manifest.schema.json",
                    "schema_version": "1.0.0",
                    "install_id": install_id,
                    "package_id": package_id,
                    "platform": package["platform"],
                    "target_root": str(target),
                    "status": "INSTALLED",
                    "files": installed,
                    "backups": backups,
                    "installed_at": utc_now(),
                }
                manifest = {**base, "content_digest": _digest(base)}
                self.contracts.validate("install-manifest", manifest)
                atomic_write_yaml(manifest_path, manifest)
                if self.doctor(target)["status"] != "PASS":
                    raise TUnderstandError(
                        "INSTALL-VERIFY-001", "Post-install doctor failed"
                    )
            except Exception:
                for item in reversed(installed):
                    (target / item["path"]).unlink(missing_ok=True)
                for item in backups:
                    backup = backup_root / item["path"]
                    destination = target / item["path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, destination)
                shutil.rmtree(metadata_root, ignore_errors=True)
                raise
        return load_yaml(manifest_path)

    def install_platform(
        self,
        platform: str,
        target_root: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Generate and install the current release for one host platform.

        Package IDs, installation IDs, installer state, and default host paths
        are implementation details. ``force`` rebuilds the package and replaces
        any existing managed or unmanaged installation after creating backups.
        """
        if platform not in PLATFORMS:
            raise TUnderstandError(
                "INSTALL-PLATFORM-001", f"Unsupported platform: {platform}"
            )
        package_id, install_id = self._managed_ids(platform)
        self.package(package_id, platform, force=force)
        target = target_root or default_target_root(platform)
        return self.install(install_id, package_id, target, force=force)

    def doctor_platform(
        self, platform: str, target_root: Path | None = None
    ) -> dict[str, Any]:
        return self.doctor(target_root or default_target_root(platform))

    def uninstall_platform(
        self,
        platform: str,
        target_root: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        return self.uninstall(target_root or default_target_root(platform), force=force)

    def doctor(self, target_root: Path) -> dict[str, Any]:
        target = target_root.expanduser().resolve()
        errors: list[str] = []
        checks = 0
        try:
            manifest = load_yaml(
                self._install_meta(target) / "install-manifest.yaml"
            )
            checks += 1
            self.contracts.validate("install-manifest", manifest)
            checks += 1
            if Path(manifest["target_root"]).resolve() != target:
                errors.append("target root mismatch")
            for entry in manifest["files"]:
                checks += 1
                path = target / entry["path"]
                if not path.is_file() or sha256_file(path) != entry["sha256"]:
                    errors.append(f"missing or modified: {entry['path']}")
            checks += 1
            if (
                _digest({k: v for k, v in manifest.items() if k != "content_digest"})
                != manifest["content_digest"]
            ):
                errors.append("install manifest digest mismatch")
        except Exception as exc:
            errors.append(str(exc))
        return {
            "status": "PASS" if not errors else "FAIL",
            "target_root": str(target),
            "checks": checks,
            "errors": errors,
            "generated_at": utc_now(),
        }

    def uninstall(self, target_root: Path, force: bool = False) -> dict[str, Any]:
        target = target_root.expanduser().resolve()
        metadata_root = self._install_meta(target)
        manifest = load_yaml(metadata_root / "install-manifest.yaml")
        modified = []
        for entry in manifest["files"]:
            path = target / entry["path"]
            if path.exists() and sha256_file(path) != entry["sha256"] and not force:
                modified.append(entry["path"])
        if modified:
            raise TUnderstandError(
                "INSTALL-UNINSTALL-001",
                f"Managed files were modified: {', '.join(modified)}",
            )
        for entry in sorted(
            manifest["files"],
            key=lambda item: len(Path(item["path"]).parts),
            reverse=True,
        ):
            (target / entry["path"]).unlink(missing_ok=True)
        backup_root = metadata_root / "backups" / manifest["install_id"]
        for entry in manifest["backups"]:
            source = backup_root / entry["path"]
            destination = target / entry["path"]
            if source.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        shutil.rmtree(metadata_root, ignore_errors=True)
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        return {
            "status": "UNINSTALLED",
            "install_id": manifest["install_id"],
            "target_root": str(target),
            "restored_backups": len(manifest["backups"]),
            "generated_at": utc_now(),
        }
