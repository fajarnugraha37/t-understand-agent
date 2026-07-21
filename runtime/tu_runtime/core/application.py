from __future__ import annotations

import os
import re
import socket
import subprocess
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit

from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now

APP_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
MACHINE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,126}$")
SCP_REMOTE_RE = re.compile(r"^(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)$")

CONTEXT_DIRECTORIES = (
    "snapshots",
    "evidence",
    "memory",
    "models/flows",
    "documentation/canonical",
    "documentation/mintlify",
    "documentation/traceability",
    "qna",
    "reviews",
    "approvals",
    "reports",
    "runtime/cache",
    "runtime/delegations",
    "runtime/results",
    "runtime/temporary",
    ".locks",
)


def _normalized_path(path: str) -> str:
    value = unicodedata.normalize("NFC", unquote(path)).replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    value = value.strip("/")
    if value.endswith(".git"):
        value = value[:-4]
    value = value.rstrip("/")
    if not value or value in {".", ".."} or any(part in {"", ".", ".."} for part in value.split("/")):
        raise TUnderstandError("APP-REMOTE-003", "Remote repository path is empty or unsafe")
    return value


def normalize_remote(remote: str) -> tuple[str, str]:
    """Return a stable host/path identity and a credential-free clone hint."""
    value = remote.strip()
    if not value or any(ch.isspace() for ch in value):
        raise TUnderstandError("APP-REMOTE-001", "Remote URL must be non-empty and contain no whitespace")

    scp = SCP_REMOTE_RE.fullmatch(value) if "://" not in value else None
    if scp:
        host = scp.group("host").lower().rstrip(".")
        path = _normalized_path(scp.group("path"))
        if not host:
            raise TUnderstandError("APP-REMOTE-002", "Remote host is missing")
        return f"{host}/{path}", f"ssh://{host}/{path}.git"

    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "ssh"}:
        raise TUnderstandError("APP-REMOTE-004", "Only HTTPS, SSH, and SCP-like Git remotes are portable")
    if parsed.query or parsed.fragment:
        raise TUnderstandError("APP-REMOTE-005", "Remote URL query strings and fragments are not allowed")
    if not parsed.hostname:
        raise TUnderstandError("APP-REMOTE-002", "Remote host is missing")
    if parsed.scheme == "https" and parsed.username:
        raise TUnderstandError("APP-REMOTE-006", "Credential-bearing HTTPS remote URLs are not allowed")
    if parsed.password:
        raise TUnderstandError("APP-REMOTE-006", "Credential-bearing remote URLs are not allowed")
    host = parsed.hostname.lower().rstrip(".")
    if parsed.port and not ((parsed.scheme == "https" and parsed.port == 443) or (parsed.scheme == "ssh" and parsed.port == 22)):
        host = f"{host}:{parsed.port}"
    path = _normalized_path(parsed.path)
    scheme = "https" if parsed.scheme == "https" else "ssh"
    return f"{host}/{path}", f"{scheme}://{host}/{path}.git"


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _run_git(path: Path, *args: str, allow_failure: bool = False) -> str | None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
    completed = subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        if allow_failure:
            return None
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise TUnderstandError("APP-GIT-001", f"Git inspection failed for {path}: {message}")
    return completed.stdout.strip()


class ApplicationManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root.resolve()
        self.context_root = context_root.expanduser().resolve()
        self.contracts = ContractValidator(self.project_root)

    @property
    def manifest_path(self) -> Path:
        return self.context_root / "application.yaml"

    @property
    def workspace_path(self) -> Path:
        return self.context_root / "workspace.local.yaml"

    @property
    def resolution_path(self) -> Path:
        return self.context_root / "runtime" / "workspace-resolution.yaml"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / ".locks" / "application.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("APP-LOCK-001", "Application context is already being mutated") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def initialize(self, application_id: str, name: str, workspace_model: str, machine_id: str, description: str = "") -> dict[str, Any]:
        if not APP_ID_RE.fullmatch(application_id):
            raise TUnderstandError("APP-ID-001", "application_id must match ^[a-z][a-z0-9-]{1,62}$")
        if not MACHINE_ID_RE.fullmatch(machine_id):
            raise TUnderstandError("APP-MACHINE-001", "machine_id contains unsupported characters")
        if workspace_model not in {"single-repo", "monorepo", "multi-repo"}:
            raise TUnderstandError("APP-MODEL-001", f"Unsupported workspace model: {workspace_model}")
        if self.manifest_path.exists() or self.workspace_path.exists():
            raise TUnderstandError("APP-INIT-001", f"Application context is already initialized: {self.context_root}")
        self._assert_context_not_inside_git_worktree()
        self.context_root.mkdir(parents=True, exist_ok=True)
        for relative in CONTEXT_DIRECTORIES:
            (self.context_root / relative).mkdir(parents=True, exist_ok=True)
        now = utc_now()
        manifest = {
            "schema_id": "https://t-understand.dev/schemas/application-manifest.schema.json",
            "schema_version": "1.0.0",
            "application": {"id": application_id, "name": name, "description": description},
            "workspace_model": workspace_model,
            "repositories": [],
            "created_at": now,
            "updated_at": now,
        }
        workspace = {
            "schema_id": "https://t-understand.dev/schemas/workspace-map.schema.json",
            "schema_version": "1.0.0",
            "application_id": application_id,
            "machine_id": machine_id,
            "repositories": {},
            "updated_at": now,
        }
        self.contracts.validate("application-manifest", manifest)
        self.contracts.validate("workspace-map", workspace)
        atomic_write_yaml(self.manifest_path, manifest)
        atomic_write_yaml(self.workspace_path, workspace)
        atomic_write_text(
            self.context_root / ".gitignore",
            "workspace.local.yaml\nruntime/\n*.tmp\n.DS_Store\n",
        )
        return {"status": "INITIALIZED", "context_root": str(self.context_root), "application": manifest}

    def load_manifest(self) -> dict[str, Any]:
        data = load_yaml(self.manifest_path)
        self.contracts.validate("application-manifest", data)
        self._validate_manifest_semantics(data, require_resolvable=False)
        return data

    def load_workspace(self) -> dict[str, Any]:
        data = load_yaml(self.workspace_path)
        self.contracts.validate("workspace-map", data)
        if not Path(self.workspace_path).is_file():
            raise TUnderstandError("APP-WORKSPACE-001", "Local workspace map is missing")
        for repository_id, binding in data["repositories"].items():
            if not Path(binding["path"]).expanduser().is_absolute():
                raise TUnderstandError("APP-WORKSPACE-003", f"Workspace path must be absolute for {repository_id}")
        return data

    def add_repository(
        self,
        repository_id: str,
        name: str,
        role: str,
        remote: str | None = None,
        identity_key: str | None = None,
        default_ref: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if bool(remote) == bool(identity_key):
            raise TUnderstandError("APP-IDENTITY-001", "Exactly one of remote or identity_key is required")
        with self.lock():
            manifest = self.load_manifest()
            if any(item["id"] == repository_id for item in manifest["repositories"]):
                raise TUnderstandError("APP-REPO-001", f"Repository ID already exists: {repository_id}")
            if remote:
                identity, hint = normalize_remote(remote)
                identity_type = "remote"
            else:
                identity = identity_key.strip() if identity_key else ""
                if not identity or any(ch.isspace() for ch in identity):
                    raise TUnderstandError("APP-IDENTITY-002", "Explicit identity must be a stable non-whitespace key")
                hint = None
                identity_type = "explicit"
            if any(item["identity"]["value"] == identity for item in manifest["repositories"]):
                raise TUnderstandError("APP-REPO-002", f"Repository identity is already registered: {identity}")
            repository = {
                "id": repository_id,
                "name": name,
                "role": role,
                "vcs": "git",
                "identity": {"type": identity_type, "value": identity},
                "source_access": "READ_ONLY",
            }
            if hint:
                repository["remote_hint"] = hint
            if default_ref:
                repository["default_ref"] = default_ref
            if tags:
                repository["tags"] = sorted(set(tags))
            manifest["repositories"].append(repository)
            manifest["repositories"].sort(key=lambda item: item["id"])
            manifest["updated_at"] = utc_now()
            self.contracts.validate("application-manifest", manifest)
            self._validate_manifest_semantics(manifest, require_resolvable=False)
            atomic_write_yaml(self.manifest_path, manifest)
            return repository

    def remove_repository(self, repository_id: str) -> dict[str, Any]:
        with self.lock():
            manifest = self.load_manifest()
            workspace = self.load_workspace()
            if repository_id in workspace["repositories"]:
                raise TUnderstandError("APP-REPO-003", "Unbind the repository before removing it")
            original = len(manifest["repositories"])
            manifest["repositories"] = [item for item in manifest["repositories"] if item["id"] != repository_id]
            if len(manifest["repositories"]) == original:
                raise TUnderstandError("APP-REPO-004", f"Unknown repository ID: {repository_id}")
            manifest["updated_at"] = utc_now()
            atomic_write_yaml(self.manifest_path, manifest)
            return {"status": "REMOVED", "repository_id": repository_id}

    def bind_repository(self, repository_id: str, path: Path) -> dict[str, Any]:
        source = path.expanduser().resolve()
        with self.lock():
            manifest = self.load_manifest()
            workspace = self.load_workspace()
            repository = self._repository(manifest, repository_id)
            inspection = self._inspect_repository(repository, source)
            for other_id, binding in workspace["repositories"].items():
                if other_id == repository_id:
                    continue
                other_path = Path(binding["path"]).expanduser().resolve()
                if source == other_path:
                    raise TUnderstandError("APP-BOUNDARY-003", f"Duplicate Git root is already bound to {other_id}")
                if _is_within(source, other_path) or _is_within(other_path, source):
                    raise TUnderstandError("APP-BOUNDARY-004", f"Nested repository roots are not allowed: {repository_id} and {other_id}")
            workspace["repositories"][repository_id] = {"path": str(source), "bound_at": utc_now()}
            workspace["updated_at"] = utc_now()
            self.contracts.validate("workspace-map", workspace)
            atomic_write_yaml(self.workspace_path, workspace)
            return {"status": "BOUND", **inspection}

    def unbind_repository(self, repository_id: str) -> dict[str, Any]:
        with self.lock():
            workspace = self.load_workspace()
            if repository_id not in workspace["repositories"]:
                raise TUnderstandError("APP-BIND-001", f"Repository is not bound: {repository_id}")
            del workspace["repositories"][repository_id]
            workspace["updated_at"] = utc_now()
            atomic_write_yaml(self.workspace_path, workspace)
            return {"status": "UNBOUND", "repository_id": repository_id}

    def resolve(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        workspace = self.load_workspace()
        self._validate_manifest_semantics(manifest, require_resolvable=True)
        if workspace["application_id"] != manifest["application"]["id"]:
            raise TUnderstandError("APP-WORKSPACE-002", "Workspace map application_id does not match application manifest")
        registered = {item["id"] for item in manifest["repositories"]}
        bound = set(workspace["repositories"])
        missing = sorted(registered - bound)
        unknown = sorted(bound - registered)
        if missing:
            raise TUnderstandError("APP-BIND-002", f"Repositories are not bound: {', '.join(missing)}")
        if unknown:
            raise TUnderstandError("APP-BIND-003", f"Workspace map contains unknown repositories: {', '.join(unknown)}")
        resolved = []
        roots: list[tuple[str, Path]] = []
        for repository in manifest["repositories"]:
            source = Path(workspace["repositories"][repository["id"]]["path"]).expanduser().resolve()
            inspection = self._inspect_repository(repository, source)
            for other_id, other_root in roots:
                if source == other_root:
                    raise TUnderstandError("APP-BOUNDARY-003", f"Duplicate Git root: {repository['id']} and {other_id}")
                if _is_within(source, other_root) or _is_within(other_root, source):
                    raise TUnderstandError("APP-BOUNDARY-004", f"Nested repository roots: {repository['id']} and {other_id}")
            roots.append((repository["id"], source))
            resolved.append(inspection)
        result = {
            "schema_id": "https://t-understand.dev/schemas/workspace-resolution.schema.json",
            "schema_version": "1.0.0",
            "application_id": manifest["application"]["id"],
            "workspace_model": manifest["workspace_model"],
            "machine_id": workspace["machine_id"],
            "manifest_sha256": sha256_file(self.manifest_path),
            "status": "RESOLVED",
            "repositories": resolved,
            "resolved_at": utc_now(),
        }
        self.contracts.validate("workspace-resolution", result)
        atomic_write_yaml(self.resolution_path, result)
        return result

    def validate(self, inspect_workspace: bool = False) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        checks = 0
        application_id: str | None = None
        try:
            manifest = self.load_manifest()
            application_id = manifest["application"]["id"]
            checks += 1
            self._validate_manifest_semantics(manifest, require_resolvable=inspect_workspace)
            checks += 1
            workspace = self.load_workspace()
            checks += 1
            if workspace["application_id"] != application_id:
                raise TUnderstandError("APP-WORKSPACE-002", "Workspace map application_id does not match application manifest")
            checks += 1
            if inspect_workspace:
                self.resolve()
                checks += len(manifest["repositories"]) + 1
            elif set(workspace["repositories"]) - {item["id"] for item in manifest["repositories"]}:
                warnings.append({"code": "APP-WARN-001", "message": "Workspace map has bindings not present in the manifest"})
        except TUnderstandError as exc:
            errors.append(exc.as_dict())
        report = {
            "schema_id": "https://t-understand.dev/schemas/application-validation-report.schema.json",
            "schema_version": "1.0.0",
            "status": "PASS" if not errors else "FAIL",
            "application_id": application_id,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
        }
        self.contracts.validate("application-validation-report", report)
        return report

    def show(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        workspace = self.load_workspace()
        bindings = [
            {"repository_id": repository["id"], "bound": repository["id"] in workspace["repositories"]}
            for repository in manifest["repositories"]
        ]
        return {"context_root": str(self.context_root), "application": manifest, "machine_id": workspace["machine_id"], "bindings": bindings}


    def _is_managed_workspace_context(self, git_root: Path) -> bool:
        return self.context_root == (git_root.resolve() / ".t-understand")

    def _assert_context_not_inside_git_worktree(self) -> None:
        probe = self.context_root
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        root = _run_git(probe, "rev-parse", "--show-toplevel", allow_failure=True) if probe.exists() else None
        if root:
            git_root = Path(root).resolve()
            if _is_within(self.context_root, git_root) and not self._is_managed_workspace_context(git_root):
                raise TUnderstandError("APP-BOUNDARY-001", f"Application context must not be created inside a source Git repository except for the managed .t-understand directory: {git_root}")

    def _repository(self, manifest: dict[str, Any], repository_id: str) -> dict[str, Any]:
        for item in manifest["repositories"]:
            if item["id"] == repository_id:
                return item
        raise TUnderstandError("APP-REPO-004", f"Unknown repository ID: {repository_id}")

    def _validate_manifest_semantics(self, manifest: dict[str, Any], require_resolvable: bool) -> None:
        ids = [item["id"] for item in manifest["repositories"]]
        identities = [item["identity"]["value"] for item in manifest["repositories"]]
        if len(ids) != len(set(ids)):
            raise TUnderstandError("APP-MANIFEST-001", "Repository IDs must be unique")
        if len(identities) != len(set(identities)):
            raise TUnderstandError("APP-MANIFEST-002", "Repository identities must be unique")
        serialized = self.manifest_path.read_text(encoding="utf-8") if self.manifest_path.is_file() else ""
        for line in serialized.splitlines():
            if re.search(r"(^|:\s*)(/[A-Za-z0-9_.-]|[A-Za-z]:[\\/])", line):
                raise TUnderstandError("APP-MANIFEST-003", "Portable application manifest must not contain absolute local paths")
        if not require_resolvable:
            return
        count = len(ids)
        model = manifest["workspace_model"]
        if model in {"single-repo", "monorepo"} and count != 1:
            raise TUnderstandError("APP-MODEL-002", f"{model} requires exactly one registered repository")
        if model == "multi-repo" and count < 2:
            raise TUnderstandError("APP-MODEL-003", "multi-repo requires at least two registered repositories")

    def _inspect_repository(self, repository: dict[str, Any], source: Path) -> dict[str, Any]:
        if not source.is_dir():
            raise TUnderstandError("APP-PATH-001", f"Repository path is not a directory: {source}")
        if _is_within(self.context_root, source) and not self._is_managed_workspace_context(source):
            raise TUnderstandError("APP-BOUNDARY-001", f"Application context must not be inside source repository except for the managed .t-understand directory: {source}")
        if _is_within(source, self.context_root):
            raise TUnderstandError("APP-BOUNDARY-002", f"Source repository must not be inside application context: {source}")
        inside = _run_git(source, "rev-parse", "--is-inside-work-tree")
        if inside != "true":
            raise TUnderstandError("APP-GIT-002", f"Path is not a Git worktree: {source}")
        git_root_text = _run_git(source, "rev-parse", "--show-toplevel")
        git_root = Path(git_root_text).resolve() if git_root_text else source
        if git_root != source:
            raise TUnderstandError("APP-GIT-003", f"Mapped path must be the Git root; resolved root is {git_root}")
        origin = _run_git(source, "remote", "get-url", "origin", allow_failure=True)
        actual_identity = None
        if origin:
            actual_identity, _ = normalize_remote(origin)
        expected = repository["identity"]["value"]
        if repository["identity"]["type"] == "remote":
            if actual_identity is None:
                raise TUnderstandError("APP-IDENTITY-003", f"Repository {repository['id']} requires an origin remote")
            if actual_identity != expected:
                raise TUnderstandError("APP-IDENTITY-004", f"Remote identity mismatch for {repository['id']}: expected {expected}, got {actual_identity}")
            identity_status = "MATCH"
        else:
            identity_status = "EXPLICIT"
        return {
            "repository_id": repository["id"],
            "local_path": str(source),
            "git_root": str(git_root),
            "identity_type": repository["identity"]["type"],
            "expected_identity": expected,
            "actual_identity": actual_identity,
            "identity_status": identity_status,
            "source_access": "READ_ONLY",
        }


def default_machine_id() -> str:
    host = socket.gethostname().strip() or "local-machine"
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "-", host)
    return sanitized[:127] if len(sanitized) >= 2 else f"{sanitized}-machine"
