from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import stat
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .application import ApplicationManager
from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import (
    atomic_write_bytes,
    atomic_write_yaml,
    dump_yaml,
    ensure_relative_safe,
    load_yaml,
    resolve_within,
    sha256_bytes,
    sha256_file,
    utc_now,
)

SNAPSHOT_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,127}$")
REVIEW_ID_RE = SNAPSHOT_ID_RE
COMMIT_RE = re.compile(r"^[a-fA-F0-9]{7,64}$")
TARGET_TYPES = {"branch", "tag", "commit", "head", "index", "worktree"}
PURPOSES = {"foundation", "documentation", "qna", "review", "manual"}
MAX_PATCH_BYTES = 20 * 1024 * 1024
MAX_UNTRACKED_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_UNTRACKED_BYTES = 50 * 1024 * 1024
PROTECTED_PATTERNS = (
    ".env*",
    "**/.env*",
    "secrets/**",
    "**/secrets/**",
    "*credential*",
    "**/*credential*",
    "*.pem",
    "**/*.pem",
    "*.key",
    "**/*.key",
)


def _canonical_digest(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(encoded)


def _safe_posix_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    candidate = ensure_relative_safe(normalized)
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise TUnderstandError("SNAP-PATH-001", f"Snapshot path must be portable and relative: {value}")
    if ".git" in candidate.parts:
        raise TUnderstandError("SNAP-PATH-002", f"Git metadata paths cannot be captured: {value}")
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TUnderstandError("SNAP-PATH-003", f"Snapshot paths must be valid UTF-8: {value!r}") from exc
    return candidate.as_posix()


def _is_protected(path: str) -> bool:
    value = path.replace("\\", "/")
    lowered = value.lower()
    parts = lowered.split("/")
    if any(part in {".git", ".t-understand"} for part in parts):
        return True
    for pattern in PROTECTED_PATTERNS:
        if fnmatch.fnmatch(lowered, pattern.lower()):
            return True
    return False


def parse_target(value: str) -> dict[str, str | None]:
    raw = value.strip()
    if not raw:
        raise TUnderstandError("SNAP-TARGET-001", "Snapshot target cannot be empty")
    if ":" in raw:
        target_type, ref = raw.split(":", 1)
        target_type = target_type.lower()
        ref = ref.strip()
    else:
        target_type, ref = raw.lower(), None
    if target_type not in TARGET_TYPES:
        raise TUnderstandError("SNAP-TARGET-002", f"Unsupported snapshot target type: {target_type}")
    if target_type in {"branch", "tag", "commit"}:
        if not ref:
            raise TUnderstandError("SNAP-TARGET-003", f"Target {target_type} requires a ref")
    elif ref is not None:
        raise TUnderstandError("SNAP-TARGET-004", f"Target {target_type} does not accept a ref")
    if target_type == "commit" and not COMMIT_RE.fullmatch(ref or ""):
        raise TUnderstandError("SNAP-TARGET-005", "Commit targets require a 7-64 character hexadecimal object ID")
    return {"type": target_type, "ref": ref}


def parse_target_assignments(values: list[str]) -> dict[str, dict[str, str | None]]:
    targets: dict[str, dict[str, str | None]] = {}
    for value in values:
        if "=" not in value:
            raise TUnderstandError("SNAP-TARGET-006", "Repository target must use REPOSITORY_ID=TYPE[:REF]")
        repository_id, target = value.split("=", 1)
        repository_id = repository_id.strip()
        if not re.fullmatch(r"^[a-z][a-z0-9-]{1,62}$", repository_id):
            raise TUnderstandError("SNAP-TARGET-007", f"Invalid repository ID in target assignment: {repository_id}")
        if repository_id in targets:
            raise TUnderstandError("SNAP-TARGET-008", f"Duplicate target assignment for repository: {repository_id}")
        targets[repository_id] = parse_target(target)
    return targets


class GitReader:
    def __init__(self, repository: Path):
        self.repository = repository.resolve()
        self.env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "LC_ALL": "C",
            "LANG": "C",
        }

    def bytes(self, *args: str, allow_failure: bool = False) -> bytes | None:
        completed = subprocess.run(
            ["git", "-C", str(self.repository), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )
        if completed.returncode != 0:
            if allow_failure:
                return None
            message = completed.stderr.decode("utf-8", errors="replace").strip() or completed.stdout.decode("utf-8", errors="replace").strip() or "git command failed"
            raise TUnderstandError("SNAP-GIT-001", f"Git inspection failed for {self.repository}: {message}")
        return completed.stdout

    def text(self, *args: str, allow_failure: bool = False) -> str | None:
        value = self.bytes(*args, allow_failure=allow_failure)
        return None if value is None else value.decode("utf-8", errors="strict").strip()

    def nul_paths(self, *args: str) -> list[str]:
        output = self.bytes(*args) or b""
        paths = []
        for item in output.split(b"\0"):
            if not item:
                continue
            try:
                path = os.fsdecode(item)
                path.encode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError) as exc:
                raise TUnderstandError("SNAP-PATH-003", "Git paths must be valid UTF-8") from exc
            paths.append(_safe_posix_path(path))
        return sorted(set(paths))


class SnapshotManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root.resolve()
        self.context_root = context_root.expanduser().resolve()
        self.application = ApplicationManager(self.project_root, self.context_root)
        self.contracts = ContractValidator(self.project_root)

    @property
    def snapshots_root(self) -> Path:
        return self.context_root / "snapshots"

    @property
    def reviews_root(self) -> Path:
        return self.context_root / "reviews"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / ".locks" / "snapshot.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("SNAP-LOCK-001", "Snapshot or review target mutation is already in progress") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _snapshot_dir(self, snapshot_id: str) -> Path:
        if not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
            raise TUnderstandError("SNAP-ID-001", "snapshot_id must match ^[A-Z][A-Z0-9_-]{2,127}$")
        return self.snapshots_root / snapshot_id

    def _review_dir(self, review_id: str) -> Path:
        if not REVIEW_ID_RE.fullmatch(review_id):
            raise TUnderstandError("SNAP-REVIEW-001", "review_id must match ^[A-Z][A-Z0-9_-]{2,127}$")
        return self.reviews_root / review_id

    def create_snapshot(
        self,
        snapshot_id: str,
        targets: dict[str, dict[str, str | None]] | None = None,
        purpose: str = "manual",
    ) -> dict[str, Any]:
        if purpose not in PURPOSES:
            raise TUnderstandError("SNAP-PURPOSE-001", f"Unsupported snapshot purpose: {purpose}")
        final_dir = self._snapshot_dir(snapshot_id)
        if final_dir.exists():
            raise TUnderstandError("SNAP-ID-002", f"Snapshot ID already exists and is immutable: {snapshot_id}")
        with self.lock():
            if final_dir.exists():
                raise TUnderstandError("SNAP-ID-002", f"Snapshot ID already exists and is immutable: {snapshot_id}")
            manifest = self.application.load_manifest()
            resolution = self.application.resolve()
            repositories = {item["id"]: item for item in manifest["repositories"]}
            resolved_paths = {item["repository_id"]: Path(item["git_root"]) for item in resolution["repositories"]}
            provided = targets or {}
            unknown = sorted(set(provided) - set(repositories))
            if unknown:
                raise TUnderstandError("SNAP-TARGET-009", f"Targets reference unknown repositories: {', '.join(unknown)}")
            effective: dict[str, dict[str, str | None]] = {}
            for repository_id, repository in repositories.items():
                if repository_id in provided:
                    effective[repository_id] = provided[repository_id]
                elif repository.get("default_ref"):
                    effective[repository_id] = {"type": "branch", "ref": repository["default_ref"]}
                else:
                    effective[repository_id] = {"type": "head", "ref": None}

            self.snapshots_root.mkdir(parents=True, exist_ok=True)
            temp_dir = self.snapshots_root / f".tmp-{snapshot_id}-{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=False)
            try:
                repository_refs = []
                for repository_id in sorted(repositories):
                    descriptor = self._capture_repository(
                        snapshot_id,
                        manifest["application"]["id"],
                        repositories[repository_id],
                        resolved_paths[repository_id],
                        effective[repository_id],
                        temp_dir,
                    )
                    descriptor_path = temp_dir / "repositories" / f"{repository_id}.yaml"
                    atomic_write_yaml(descriptor_path, descriptor)
                    repository_refs.append({
                        "repository_id": repository_id,
                        "target_type": descriptor["target"]["type"],
                        "resolved_commit": descriptor["resolved"]["commit"],
                        "descriptor_path": descriptor_path.relative_to(temp_dir).as_posix(),
                        "descriptor_sha256": sha256_file(descriptor_path),
                        "content_digest": descriptor["content_digest"],
                    })
                snapshot_base = {
                    "schema_id": "https://t-understand.dev/schemas/application-snapshot.schema.json",
                    "schema_version": "1.0.0",
                    "snapshot_id": snapshot_id,
                    "application_id": manifest["application"]["id"],
                    "purpose": purpose,
                    "status": "CAPTURED",
                    "application_manifest_sha256": sha256_file(self.application.manifest_path),
                    "workspace_resolution_sha256": sha256_file(self.application.resolution_path),
                    "repositories": repository_refs,
                    "captured_at": utc_now(),
                }
                snapshot = {**snapshot_base, "content_digest": _canonical_digest(snapshot_base)}
                self.contracts.validate("application-snapshot", snapshot)
                atomic_write_yaml(temp_dir / "application-snapshot.yaml", snapshot)
                self._validate_snapshot_directory(temp_dir, snapshot_id, write_report=False)
                os.replace(temp_dir, final_dir)
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise
        return self.show_snapshot(snapshot_id)

    def _capture_repository(
        self,
        snapshot_id: str,
        application_id: str,
        repository: dict[str, Any],
        source: Path,
        target: dict[str, str | None],
        snapshot_root: Path,
    ) -> dict[str, Any]:
        git = GitReader(source)
        target_type = str(target["type"])
        if target_type in {"branch", "tag", "commit", "head"}:
            resolved = self._resolve_commit_target(git, target)
            submodules = self._submodules_at_commit(git, resolved["commit"])
            capture = {
                "mode": "commit-tree",
                "included": ["commit-tree"],
                "excluded": ["ignored", "unstaged", "untracked", "protected", "submodule-worktree"],
                "artifacts": [],
                "untracked_files": [],
                "state_digest": _canonical_digest({
                    "target": target,
                    "commit": resolved["commit"],
                    "tree": resolved["tree"],
                    "submodules": submodules,
                }),
            }
        else:
            first = self._collect_overlay_state(git, source, target_type)
            repo_payload_root = snapshot_root / "repositories" / repository["id"]
            artifacts, untracked_files = self._write_overlay_artifacts(snapshot_root, repo_payload_root, first, target_type)
            second = self._collect_overlay_state(git, source, target_type)
            if first["state_digest"] != second["state_digest"]:
                raise TUnderstandError("SNAP-RACE-001", f"Repository changed during {target_type} capture: {repository['id']}")
            resolved = first["resolved"]
            submodules = first["submodules"]
            capture = {
                "mode": "index-overlay" if target_type == "index" else "worktree-overlay",
                "included": ["commit-tree", "staged"] if target_type == "index" else ["commit-tree", "staged", "unstaged", "untracked-nonignored"],
                "excluded": ["ignored", "unstaged", "untracked", "protected", "submodule-worktree"] if target_type == "index" else ["ignored", "protected"],
                "artifacts": artifacts,
                "untracked_files": untracked_files,
                "state_digest": first["state_digest"],
            }
        descriptor_base = {
            "schema_id": "https://t-understand.dev/schemas/repository-snapshot.schema.json",
            "schema_version": "1.0.0",
            "snapshot_id": snapshot_id,
            "application_id": application_id,
            "repository_id": repository["id"],
            "repository_identity": repository["identity"],
            "target": target,
            "resolved": resolved,
            "capture": capture,
            "submodules": submodules,
            "captured_at": utc_now(),
        }
        descriptor = {**descriptor_base, "content_digest": _canonical_digest(descriptor_base)}
        self.contracts.validate("repository-snapshot", descriptor)
        return descriptor

    def _resolve_commit_target(self, git: GitReader, target: dict[str, str | None]) -> dict[str, Any]:
        target_type = str(target["type"])
        ref = target.get("ref")
        resolved_ref: str | None
        if target_type == "head":
            expression = "HEAD^{commit}"
            resolved_ref = "HEAD"
        elif target_type == "commit":
            expression = f"{ref}^{{commit}}"
            resolved_ref = str(ref)
        elif target_type == "tag":
            resolved_ref = str(ref) if str(ref).startswith("refs/tags/") else f"refs/tags/{ref}"
            expression = f"{resolved_ref}^{{commit}}"
        elif target_type == "branch":
            if str(ref).startswith(("refs/heads/", "refs/remotes/")):
                candidates = [str(ref)]
            else:
                candidates = [f"refs/heads/{ref}"]
                if ref and "/" in ref:
                    candidates.append(f"refs/remotes/{ref}")
            matches = []
            for candidate in candidates:
                value = git.text("rev-parse", "--verify", f"{candidate}^{{commit}}", allow_failure=True)
                if value:
                    matches.append((candidate, value))
            unique = {(candidate, value) for candidate, value in matches}
            if not unique:
                raise TUnderstandError("SNAP-REF-001", f"Branch target does not exist: {ref}")
            commits = {value for _, value in unique}
            if len(commits) > 1:
                raise TUnderstandError("SNAP-REF-002", f"Branch target is ambiguous between local and remote refs: {ref}")
            resolved_ref, commit = sorted(unique)[0]
            tree = git.text("rev-parse", "--verify", f"{commit}^{{tree}}")
            return self._resolved(git, commit, tree, resolved_ref)
        else:
            raise TUnderstandError("SNAP-TARGET-002", f"Unsupported commit target: {target_type}")
        commit = git.text("rev-parse", "--verify", expression, allow_failure=True)
        if not commit:
            raise TUnderstandError("SNAP-REF-003", f"Git target cannot be resolved: {target_type}:{ref or ''}")
        tree = git.text("rev-parse", "--verify", f"{commit}^{{tree}}")
        return self._resolved(git, commit, tree, resolved_ref)

    def _resolved(self, git: GitReader, commit: str | None, tree: str | None, resolved_ref: str | None) -> dict[str, Any]:
        if not commit or not tree:
            raise TUnderstandError("SNAP-REF-004", "Resolved Git target is missing commit or tree identity")
        object_format = git.text("rev-parse", "--show-object-format", allow_failure=True) or "sha1"
        current_branch = git.text("symbolic-ref", "--quiet", "--short", "HEAD", allow_failure=True)
        return {
            "commit": commit.lower(),
            "tree": tree.lower(),
            "resolved_ref": resolved_ref,
            "object_format": object_format,
            "current_branch": current_branch or None,
        }

    def _changed_paths(self, git: GitReader, target_type: str) -> list[str]:
        paths = git.nul_paths("diff", "--cached", "--name-only", "-z", "--")
        if target_type == "worktree":
            paths.extend(git.nul_paths("diff", "--name-only", "-z", "--"))
            paths.extend(git.nul_paths("ls-files", "--others", "--exclude-standard", "-z"))
        paths = sorted({path for path in paths if not path.replace("\\", "/").startswith(".t-understand/") and path != ".t-understand"})
        protected = [path for path in paths if _is_protected(path)]
        if protected:
            raise TUnderstandError("SNAP-PROTECTED-001", f"Snapshot capture denied for protected changed paths: {', '.join(protected[:10])}")
        return paths

    def _collect_overlay_state(self, git: GitReader, source: Path, target_type: str) -> dict[str, Any]:
        self._changed_paths(git, target_type)
        head = git.text("rev-parse", "--verify", "HEAD^{commit}", allow_failure=True)
        if not head:
            raise TUnderstandError("SNAP-REF-005", "Index and worktree snapshots require an existing HEAD commit")
        tree = git.text("rev-parse", "--verify", f"{head}^{{tree}}")
        resolved = self._resolved(git, head, tree, "HEAD")
        staged = git.bytes("diff", "--binary", "--full-index", "--no-ext-diff", "--cached", "--") or b""
        if len(staged) > MAX_PATCH_BYTES:
            raise TUnderstandError("SNAP-SIZE-001", f"Staged patch exceeds {MAX_PATCH_BYTES} bytes")
        unstaged = b""
        status_bytes = b""
        untracked: list[dict[str, Any]] = []
        if target_type == "worktree":
            unstaged = git.bytes("diff", "--binary", "--full-index", "--no-ext-diff", "--") or b""
            if len(unstaged) > MAX_PATCH_BYTES:
                raise TUnderstandError("SNAP-SIZE-002", f"Unstaged patch exceeds {MAX_PATCH_BYTES} bytes")
            status_bytes = git.bytes("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=no", "--", ".", ":(exclude).t-understand/**") or b""
            total = 0
            for relative in [path for path in git.nul_paths("ls-files", "--others", "--exclude-standard", "-z") if not path.startswith(".t-understand/") and path != ".t-understand"]:
                source_file = source / Path(relative)
                try:
                    metadata = source_file.lstat()
                except FileNotFoundError as exc:
                    raise TUnderstandError("SNAP-RACE-002", f"Untracked file disappeared during capture: {relative}") from exc
                if stat.S_ISLNK(metadata.st_mode):
                    raise TUnderstandError("SNAP-SYMLINK-001", f"Untracked symlinks are not captured: {relative}")
                if not stat.S_ISREG(metadata.st_mode):
                    raise TUnderstandError("SNAP-FILE-001", f"Untracked path is not a regular file: {relative}")
                if metadata.st_size > MAX_UNTRACKED_FILE_BYTES:
                    raise TUnderstandError("SNAP-SIZE-003", f"Untracked file exceeds {MAX_UNTRACKED_FILE_BYTES} bytes: {relative}")
                data = source_file.read_bytes()
                if len(data) != metadata.st_size:
                    raise TUnderstandError("SNAP-RACE-003", f"Untracked file changed size during capture: {relative}")
                total += len(data)
                if total > MAX_TOTAL_UNTRACKED_BYTES:
                    raise TUnderstandError("SNAP-SIZE-004", f"Total untracked payload exceeds {MAX_TOTAL_UNTRACKED_BYTES} bytes")
                untracked.append({
                    "source_path": relative,
                    "sha256": sha256_bytes(data),
                    "bytes": len(data),
                    "executable": bool(metadata.st_mode & stat.S_IXUSR),
                    "data": data,
                })
        submodules = self._submodules_at_index(git, source, require_clean=(target_type == "worktree"))
        state_payload = {
            "target_type": target_type,
            "resolved": resolved,
            "staged_sha256": sha256_bytes(staged),
            "unstaged_sha256": sha256_bytes(unstaged),
            "status_sha256": sha256_bytes(status_bytes),
            "untracked": [{key: item[key] for key in ("source_path", "sha256", "bytes", "executable")} for item in untracked],
            "submodules": submodules,
        }
        return {
            "resolved": resolved,
            "staged": staged,
            "unstaged": unstaged,
            "status": status_bytes,
            "untracked": untracked,
            "submodules": submodules,
            "state_digest": _canonical_digest(state_payload),
        }

    def _write_overlay_artifacts(
        self,
        snapshot_root: Path,
        repo_payload_root: Path,
        state: dict[str, Any],
        target_type: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        artifacts: list[dict[str, Any]] = []

        def write(kind: str, name: str, data: bytes) -> None:
            path = repo_payload_root / name
            atomic_write_bytes(path, data)
            artifacts.append({
                "kind": kind,
                "path": path.relative_to(snapshot_root).as_posix(),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            })

        write("staged-patch", "staged.patch", state["staged"])
        if target_type == "worktree":
            write("unstaged-patch", "unstaged.patch", state["unstaged"])
            write("status-manifest", "status.porcelain-v1.z", state["status"])

        untracked_files: list[dict[str, Any]] = []
        for item in state["untracked"]:
            relative = _safe_posix_path(item["source_path"])
            destination = repo_payload_root / "untracked" / Path(relative)
            atomic_write_bytes(destination, item["data"])
            os.chmod(destination, 0o755 if item["executable"] else 0o644)
            untracked_files.append({
                "source_path": relative,
                "artifact_path": destination.relative_to(snapshot_root).as_posix(),
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "executable": item["executable"],
            })
        if target_type == "worktree":
            manifest_bytes = dump_yaml({"files": untracked_files}).encode("utf-8")
            write("untracked-manifest", "untracked-manifest.yaml", manifest_bytes)
        return artifacts, untracked_files

    def _submodules_at_commit(self, git: GitReader, commit: str) -> list[dict[str, Any]]:
        output = git.bytes("ls-tree", "-r", "-z", commit) or b""
        submodules = []
        for record in output.split(b"\0"):
            if not record:
                continue
            metadata, path_bytes = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            if mode != "160000" or object_type != "commit":
                continue
            path = _safe_posix_path(os.fsdecode(path_bytes))
            submodules.append({"path": path, "index_commit": object_id.lower(), "worktree_commit": None, "status": "COMMIT_BOUND"})
        return sorted(submodules, key=lambda item: item["path"])

    def _submodules_at_index(self, git: GitReader, source: Path, require_clean: bool) -> list[dict[str, Any]]:
        output = git.bytes("ls-files", "--stage", "-z") or b""
        submodules = []
        for record in output.split(b"\0"):
            if not record:
                continue
            metadata, path_bytes = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split(" ")
            if mode != "160000" or stage != "0":
                continue
            path = _safe_posix_path(os.fsdecode(path_bytes))
            sub_path = source / Path(path)
            sub_git = GitReader(sub_path)
            worktree_commit = None
            status = "UNINITIALIZED"
            if sub_path.is_dir() and sub_git.text("rev-parse", "--is-inside-work-tree", allow_failure=True) == "true":
                worktree_commit = sub_git.text("rev-parse", "--verify", "HEAD^{commit}", allow_failure=True)
                dirty = sub_git.bytes("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=no") or b""
                if require_clean and dirty:
                    raise TUnderstandError("SNAP-SUBMODULE-001", f"Dirty submodule worktree cannot be captured safely: {path}")
                status = "CLEAN" if not dirty else "EXCLUDED_FROM_INDEX"
            elif not require_clean:
                status = "EXCLUDED_FROM_INDEX"
            submodules.append({
                "path": path,
                "index_commit": object_id.lower(),
                "worktree_commit": worktree_commit.lower() if worktree_commit else None,
                "status": status,
            })
        return sorted(submodules, key=lambda item: item["path"])

    def list_snapshots(self) -> dict[str, Any]:
        snapshots = []
        if self.snapshots_root.is_dir():
            for path in sorted(self.snapshots_root.iterdir(), key=lambda item: item.name):
                descriptor = path / "application-snapshot.yaml"
                if path.is_dir() and not path.name.startswith(".tmp-") and descriptor.is_file():
                    data = load_yaml(descriptor)
                    snapshots.append({
                        "snapshot_id": data.get("snapshot_id", path.name),
                        "application_id": data.get("application_id"),
                        "purpose": data.get("purpose"),
                        "content_digest": data.get("content_digest"),
                        "captured_at": data.get("captured_at"),
                    })
        return {"snapshots": snapshots}

    def show_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        path = self._snapshot_dir(snapshot_id) / "application-snapshot.yaml"
        snapshot = load_yaml(path)
        self.contracts.validate("application-snapshot", snapshot)
        return snapshot

    def validate_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        snapshot_dir = self._snapshot_dir(snapshot_id)
        report = self._validate_snapshot_directory(snapshot_dir, snapshot_id, write_report=True)
        return report

    def _validate_snapshot_directory(self, snapshot_dir: Path, snapshot_id: str, write_report: bool) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        checks = 0
        try:
            snapshot_path = snapshot_dir / "application-snapshot.yaml"
            snapshot = load_yaml(snapshot_path)
            self.contracts.validate("application-snapshot", snapshot)
            checks += 1
            if snapshot["snapshot_id"] != snapshot_id:
                raise TUnderstandError("SNAP-INTEGRITY-001", "Snapshot directory and descriptor IDs differ")
            checks += 1
            repository_refs = []
            for reference in snapshot["repositories"]:
                descriptor_path = resolve_within(snapshot_dir, reference["descriptor_path"])
                if sha256_file(descriptor_path) != reference["descriptor_sha256"]:
                    raise TUnderstandError("SNAP-INTEGRITY-002", f"Repository descriptor digest mismatch: {reference['repository_id']}")
                checks += 1
                descriptor = load_yaml(descriptor_path)
                self.contracts.validate("repository-snapshot", descriptor)
                checks += 1
                if descriptor["snapshot_id"] != snapshot_id or descriptor["repository_id"] != reference["repository_id"]:
                    raise TUnderstandError("SNAP-INTEGRITY-003", f"Repository descriptor identity mismatch: {reference['repository_id']}")
                payload = dict(descriptor)
                payload.pop("content_digest")
                if _canonical_digest(payload) != descriptor["content_digest"] or descriptor["content_digest"] != reference["content_digest"]:
                    raise TUnderstandError("SNAP-INTEGRITY-004", f"Repository content digest mismatch: {reference['repository_id']}")
                checks += 1
                for artifact in descriptor["capture"]["artifacts"]:
                    artifact_path = resolve_within(snapshot_dir, artifact["path"])
                    if not artifact_path.is_file() or artifact_path.stat().st_size != artifact["bytes"] or sha256_file(artifact_path) != artifact["sha256"]:
                        raise TUnderstandError("SNAP-INTEGRITY-005", f"Snapshot artifact mismatch: {artifact['path']}")
                    checks += 1
                for item in descriptor["capture"]["untracked_files"]:
                    artifact_path = resolve_within(snapshot_dir, item["artifact_path"])
                    if not artifact_path.is_file() or artifact_path.stat().st_size != item["bytes"] or sha256_file(artifact_path) != item["sha256"]:
                        raise TUnderstandError("SNAP-INTEGRITY-006", f"Untracked artifact mismatch: {item['artifact_path']}")
                    checks += 1
                repository_refs.append(reference)
            app_payload = dict(snapshot)
            app_payload.pop("content_digest")
            if _canonical_digest(app_payload) != snapshot["content_digest"]:
                raise TUnderstandError("SNAP-INTEGRITY-007", "Application snapshot content digest mismatch")
            checks += 1
        except TUnderstandError as exc:
            errors.append(exc.as_dict())
        report = {
            "schema_id": "https://t-understand.dev/schemas/snapshot-validation-report.schema.json",
            "schema_version": "1.0.0",
            "snapshot_id": snapshot_id,
            "status": "PASS" if not errors else "FAIL",
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "checked_at": utc_now(),
        }
        self.contracts.validate("snapshot-validation-report", report)
        if write_report:
            atomic_write_yaml(self.context_root / "reports" / "snapshots" / f"{snapshot_id}-validation.yaml", report)
        if errors and not write_report:
            first = errors[0]
            raise TUnderstandError(first["code"], first["message"])
        return report

    def drift(self, snapshot_id: str) -> dict[str, Any]:
        integrity = self.validate_snapshot(snapshot_id)
        if integrity["status"] != "PASS":
            raise TUnderstandError("SNAP-INTEGRITY-008", f"Cannot evaluate drift for an invalid snapshot: {snapshot_id}")
        snapshot = self.show_snapshot(snapshot_id)
        resolution = self.application.resolve()
        roots = {item["repository_id"]: Path(item["git_root"]) for item in resolution["repositories"]}
        repositories = []
        for reference in snapshot["repositories"]:
            repository_id = reference["repository_id"]
            descriptor = load_yaml(self._snapshot_dir(snapshot_id) / reference["descriptor_path"])
            changes: list[str] = []
            status = "UNCHANGED"
            try:
                git = GitReader(roots[repository_id])
                target = descriptor["target"]
                target_type = target["type"]
                if target_type in {"branch", "tag", "head"}:
                    current = self._resolve_commit_target(git, target)
                    if current["commit"] != descriptor["resolved"]["commit"]:
                        changes.append("resolved_commit_changed")
                    if current["tree"] != descriptor["resolved"]["tree"]:
                        changes.append("resolved_tree_changed")
                elif target_type == "commit":
                    stored_commit = descriptor["resolved"]["commit"]
                    stored_tree = descriptor["resolved"]["tree"]
                    current_commit = git.text("rev-parse", "--verify", f"{stored_commit}^{{commit}}", allow_failure=True)
                    current_tree = git.text("rev-parse", "--verify", f"{stored_commit}^{{tree}}", allow_failure=True)
                    if current_commit != stored_commit or current_tree != stored_tree:
                        changes.append("resolved_commit_unavailable")
                else:
                    current = self._collect_overlay_state(git, roots[repository_id], target_type)
                    if current["state_digest"] != descriptor["capture"]["state_digest"]:
                        changes.append("captured_state_changed")
                if changes:
                    status = "DRIFTED"
            except (TUnderstandError, KeyError) as exc:
                status = "UNAVAILABLE"
                changes.append(exc.message if isinstance(exc, TUnderstandError) else str(exc))
            repositories.append({
                "repository_id": repository_id,
                "target_type": descriptor["target"]["type"],
                "status": status,
                "changes": changes,
            })
        overall = "UNCHANGED"
        if any(item["status"] == "UNAVAILABLE" for item in repositories):
            overall = "UNAVAILABLE"
        elif any(item["status"] == "DRIFTED" for item in repositories):
            overall = "DRIFTED"
        report = {
            "schema_id": "https://t-understand.dev/schemas/snapshot-drift-report.schema.json",
            "schema_version": "1.0.0",
            "snapshot_id": snapshot_id,
            "application_id": snapshot["application_id"],
            "status": overall,
            "repositories": repositories,
            "checked_at": utc_now(),
        }
        self.contracts.validate("snapshot-drift-report", report)
        atomic_write_yaml(self.context_root / "reports" / "snapshots" / f"{snapshot_id}-drift.yaml", report)
        return report

    def create_review_target(
        self,
        review_id: str,
        mode: str,
        candidate_snapshot_id: str,
        baseline_snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_mode = mode.upper().replace("-", "_")
        if normalized_mode not in {"STATIC_AUDIT", "DIFF"}:
            raise TUnderstandError("SNAP-REVIEW-002", f"Unsupported review mode: {mode}")
        if normalized_mode == "STATIC_AUDIT" and baseline_snapshot_id:
            raise TUnderstandError("SNAP-REVIEW-003", "STATIC_AUDIT review targets cannot have a baseline")
        if normalized_mode == "DIFF" and not baseline_snapshot_id:
            raise TUnderstandError("SNAP-REVIEW-004", "DIFF review targets require a baseline snapshot")
        final_dir = self._review_dir(review_id)
        if final_dir.exists():
            raise TUnderstandError("SNAP-REVIEW-005", f"Review target already exists and is immutable: {review_id}")
        with self.lock():
            if final_dir.exists():
                raise TUnderstandError("SNAP-REVIEW-005", f"Review target already exists and is immutable: {review_id}")
            candidate = self._snapshot_ref(candidate_snapshot_id)
            baseline = self._snapshot_ref(baseline_snapshot_id) if baseline_snapshot_id else None
            candidate_snapshot = self.show_snapshot(candidate_snapshot_id)
            if baseline_snapshot_id:
                baseline_snapshot = self.show_snapshot(baseline_snapshot_id)
                if baseline_snapshot["application_id"] != candidate_snapshot["application_id"]:
                    raise TUnderstandError("SNAP-REVIEW-006", "Baseline and candidate snapshots belong to different applications")
            target_base = {
                "schema_id": "https://t-understand.dev/schemas/review-target.schema.json",
                "schema_version": "1.0.0",
                "review_id": review_id,
                "application_id": candidate_snapshot["application_id"],
                "mode": normalized_mode,
                "baseline": baseline,
                "candidate": candidate,
                "immutable": True,
                "created_at": utc_now(),
            }
            target = {**target_base, "content_digest": _canonical_digest(target_base)}
            self.contracts.validate("review-target", target)
            temp_dir = self.reviews_root / f".tmp-{review_id}-{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=True, exist_ok=False)
            try:
                atomic_write_yaml(temp_dir / "review-target.yaml", target)
                os.replace(temp_dir, final_dir)
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise
        return target

    def _snapshot_ref(self, snapshot_id: str | None) -> dict[str, str]:
        if not snapshot_id:
            raise TUnderstandError("SNAP-REVIEW-007", "Snapshot ID is required")
        validation = self.validate_snapshot(snapshot_id)
        if validation["status"] != "PASS":
            raise TUnderstandError("SNAP-REVIEW-008", f"Snapshot integrity validation failed: {snapshot_id}")
        path = self._snapshot_dir(snapshot_id) / "application-snapshot.yaml"
        snapshot = self.show_snapshot(snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "snapshot_path": path.relative_to(self.context_root).as_posix(),
            "snapshot_sha256": sha256_file(path),
            "content_digest": snapshot["content_digest"],
        }

    def show_review_target(self, review_id: str) -> dict[str, Any]:
        target = load_yaml(self._review_dir(review_id) / "review-target.yaml")
        self.contracts.validate("review-target", target)
        return target

    def validate_review_target(self, review_id: str) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        checks = 0
        try:
            target = self.show_review_target(review_id)
            checks += 1
            payload = dict(target)
            payload.pop("content_digest")
            if _canonical_digest(payload) != target["content_digest"]:
                raise TUnderstandError("SNAP-REVIEW-009", "Review target content digest mismatch")
            checks += 1
            for reference in [target["baseline"], target["candidate"]]:
                if reference is None:
                    continue
                snapshot_path = resolve_within(self.context_root, reference["snapshot_path"])
                if not snapshot_path.is_file() or sha256_file(snapshot_path) != reference["snapshot_sha256"]:
                    raise TUnderstandError("SNAP-REVIEW-010", f"Review snapshot digest mismatch: {reference['snapshot_id']}")
                checks += 1
                validation = self.validate_snapshot(reference["snapshot_id"])
                if validation["status"] != "PASS":
                    raise TUnderstandError("SNAP-REVIEW-008", f"Snapshot integrity validation failed: {reference['snapshot_id']}")
                checks += 1
        except TUnderstandError as exc:
            errors.append(exc.as_dict())
        return {
            "status": "PASS" if not errors else "FAIL",
            "review_id": review_id,
            "checks": checks,
            "errors": errors,
        }
