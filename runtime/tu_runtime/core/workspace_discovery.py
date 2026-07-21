from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import TUnderstandError
from .io import atomic_write_yaml, utc_now

PRUNED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".t-understand",
    ".idea",
    ".vscode",
    "node_modules",
    "vendor",
    "target",
    "build",
    "dist",
    "out",
    "coverage",
    ".gradle",
    ".mvn",
    ".venv",
    "venv",
    "__pycache__",
}

MULTI_REPO_CUES = (
    "multi repo",
    "multi-repo",
    "multiple repo",
    "multiple repository",
    "all repositories",
    "all repos",
    "seluruh repository",
    "semua repository",
    "semua repo",
    "workspace repositories",
    "repos in this workspace",
)


@dataclass(frozen=True)
class RepositoryCandidate:
    path: Path
    repository_id: str
    name: str
    role: str
    identity_kind: str
    identity_value: str
    remote: str | None
    inclusion_reason: str
    confidence: str
    markers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "name": self.name,
            "path": str(self.path),
            "role": self.role,
            "identity_kind": self.identity_kind,
            "identity_value": self.identity_value,
            "remote": self.remote,
            "inclusion_reason": self.inclusion_reason,
            "confidence": self.confidence,
            "markers": list(self.markers),
        }


@dataclass(frozen=True)
class WorkspaceDiscovery:
    workspace_root: Path
    workspace_model: str
    repositories: tuple[RepositoryCandidate, ...]
    mode: str
    prompt_requested_multi_repo: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_id": "https://t-understand.dev/schemas/agent-workspace-discovery.schema.json",
            "schema_version": "1.0.0",
            "workspace_root": str(self.workspace_root),
            "workspace_model": self.workspace_model,
            "mode": self.mode,
            "prompt_requested_multi_repo": self.prompt_requested_multi_repo,
            "repositories": [item.as_dict() for item in self.repositories],
            "generated_at": utc_now(),
        }


def _run_git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )


def git_root(path: Path) -> Path | None:
    completed = _run_git(path, "rev-parse", "--show-toplevel")
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return Path(completed.stdout.strip()).resolve()


def find_existing_application_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".t-understand" / "application.yaml").is_file():
            return candidate
    return None


def prompt_requests_multi_repo(prompt: str) -> bool:
    normalized = " ".join(prompt.lower().split())
    return any(cue in normalized for cue in MULTI_REPO_CUES)


def _is_git_root(path: Path) -> bool:
    marker = path / ".git"
    if marker.is_dir() or marker.is_file():
        return True
    root = git_root(path)
    return root == path.resolve() if root else False


def discover_git_roots(workspace: Path, max_depth: int = 3) -> list[Path]:
    workspace = workspace.resolve()
    if _is_git_root(workspace):
        return [workspace]
    roots: list[Path] = []
    queue: list[tuple[Path, int]] = [(workspace, 0)]
    while queue:
        current, depth = queue.pop(0)
        if current != workspace and _is_git_root(current):
            roots.append(current.resolve())
            continue
        if depth >= max_depth:
            continue
        try:
            children = sorted((item for item in current.iterdir() if item.is_dir()), key=lambda item: item.name.lower())
        except (OSError, PermissionError):
            continue
        for child in children:
            if child.name in PRUNED_DIRECTORIES or child.name.startswith("."):
                continue
            queue.append((child, depth + 1))
    return sorted(set(roots), key=lambda item: item.as_posix().lower())


def _slug(value: str, fallback: str = "repository") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"repo-{slug}"
    if len(slug) < 2:
        slug = f"{slug}-repo"
    return slug[:63].rstrip("-")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _files(root: Path, patterns: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        try:
            found.extend(root.glob(pattern))
        except OSError:
            continue
    return [item for item in found if item.is_file()]


def infer_repository_role(root: Path) -> tuple[str, tuple[str, ...]]:
    markers: list[str] = []
    name = root.name.lower()
    package = _read_json(root / "package.json") if (root / "package.json").is_file() else {}
    dependencies = {
        **(package.get("dependencies") if isinstance(package.get("dependencies"), dict) else {}),
        **(package.get("devDependencies") if isinstance(package.get("devDependencies"), dict) else {}),
    }
    has_java = (root / "pom.xml").is_file() or (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file()
    has_dotnet = bool(_files(root, ("*.sln", "**/*.csproj", "**/*.fsproj")))
    has_go = (root / "go.mod").is_file()
    has_rust = (root / "Cargo.toml").is_file()
    has_python = (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file()
    has_node = bool(package)
    frontend_dependencies = {"react", "vue", "@angular/core", "next", "nuxt", "svelte", "@sveltejs/kit"}
    has_frontend = bool(frontend_dependencies & set(dependencies)) or bool(
        _files(root, ("vite.config.*", "next.config.*", "nuxt.config.*", "angular.json", "src/App.*", "src/main.tsx", "src/main.ts"))
    )
    contract_files = _files(root, ("**/*openapi*.yaml", "**/*openapi*.yml", "**/*asyncapi*.yaml", "**/*asyncapi*.yml", "**/*.proto"))
    infra_files = _files(root, ("**/*.tf", "**/Chart.yaml", "**/kustomization.yaml", "**/docker-compose*.yml", "**/docker-compose*.yaml"))
    docs_files = _files(root, ("mkdocs.yml", "docusaurus.config.*", "mint.json", "docs/**/*.md"))
    migration_files = _files(root, ("**/db/changelog/**/*", "**/db/migration/**/*", "**/liquibase/**/*", "**/flyway/**/*"))

    if infra_files and not any((has_java, has_dotnet, has_go, has_rust, has_python, has_node)):
        markers.extend(["infrastructure", *[item.name for item in infra_files[:5]]])
        return "infrastructure", tuple(sorted(set(markers)))
    if contract_files and ("contract" in name or "schema" in name or "api" in name) and not has_frontend:
        markers.extend(["contracts", *[item.name for item in contract_files[:5]]])
        return "shared-contracts", tuple(sorted(set(markers)))
    if has_frontend:
        markers.extend(["frontend", *sorted(frontend_dependencies & set(dependencies))])
        return "frontend", tuple(sorted(set(markers)))
    if migration_files and not any((has_java, has_dotnet, has_go, has_rust, has_python, has_node)):
        markers.extend(["database-migrations", *[item.name for item in migration_files[:5]]])
        return "database-migrations", tuple(sorted(set(markers)))
    if any(token in name for token in ("test", "e2e", "acceptance", "performance")):
        markers.append("test-name")
        return "test-automation", tuple(markers)
    if docs_files and not any((has_java, has_dotnet, has_go, has_rust, has_python, has_node)):
        markers.extend(["documentation", *[item.name for item in docs_files[:5]]])
        return "documentation", tuple(sorted(set(markers)))
    if any((has_java, has_dotnet, has_go, has_rust, has_python, has_node)):
        for marker, enabled in (
            ("java", has_java), ("dotnet", has_dotnet), ("go", has_go), ("rust", has_rust),
            ("python", has_python), ("node", has_node),
        ):
            if enabled:
                markers.append(marker)
        if "worker" in name or "consumer" in name or "processor" in name:
            return "worker-service", tuple(sorted(set(markers)))
        if "gateway" in name or "bff" in name:
            return "api-gateway", tuple(sorted(set(markers)))
        if "library" in name or name.startswith("lib-") or name.endswith("-lib") or "common" in name or "shared" in name:
            return "shared-library", tuple(sorted(set(markers)))
        return "backend-service", tuple(sorted(set(markers)))
    if contract_files:
        markers.extend(["contracts", *[item.name for item in contract_files[:5]]])
        return "shared-contracts", tuple(sorted(set(markers)))
    if infra_files:
        markers.extend(["infrastructure", *[item.name for item in infra_files[:5]]])
        return "infrastructure", tuple(sorted(set(markers)))
    return "application-repository", tuple(markers)


def _repository_identity(root: Path) -> tuple[str, str, str | None]:
    remote = _run_git(root, "remote", "get-url", "origin")
    if remote.returncode == 0 and remote.stdout.strip():
        return "remote", remote.stdout.strip(), remote.stdout.strip()
    first = _run_git(root, "rev-list", "--max-parents=0", "HEAD")
    root_commit = first.stdout.splitlines()[0].strip() if first.returncode == 0 and first.stdout.strip() else "unborn"
    digest = hashlib.sha256(f"{root.name}\x1f{root_commit}".encode("utf-8")).hexdigest()[:20]
    return "explicit", f"local-{_slug(root.name)}-{digest}", None


def _unique_repository_ids(roots: list[Path]) -> dict[Path, str]:
    result: dict[Path, str] = {}
    used: set[str] = set()
    for root in roots:
        base = _slug(root.name)
        candidate = base
        counter = 2
        while candidate in used:
            suffix = f"-{counter}"
            candidate = f"{base[:63-len(suffix)]}{suffix}"
            counter += 1
        used.add(candidate)
        result[root] = candidate
    return result


def resolve_workspace(start: Path, prompt: str = "", max_depth: int = 3) -> WorkspaceDiscovery:
    start = start.resolve()
    existing = find_existing_application_root(start)
    if existing:
        roots = discover_git_roots(existing, max_depth=max_depth)
        if not roots:
            current = git_root(start)
            if current:
                roots = [current]
        return _build_discovery(existing, roots, "existing-application", prompt_requests_multi_repo(prompt))

    current_git = git_root(start)
    multi_requested = prompt_requests_multi_repo(prompt)
    if current_git:
        if multi_requested:
            parent = current_git.parent
            sibling_roots = discover_git_roots(parent, max_depth=2)
            if len(sibling_roots) > 1 and current_git in sibling_roots:
                return _build_discovery(parent, sibling_roots, "prompt-expanded-siblings", True)
        return _build_discovery(current_git, [current_git], "current-git-root", multi_requested)

    roots = discover_git_roots(start, max_depth=max_depth)
    if not roots:
        raise TUnderstandError("AGENT-WORKSPACE-001", "Open a Git repository or a workspace containing Git repositories before asking for repository analysis")
    return _build_discovery(start, roots, "workspace-scan", multi_requested)


def _build_discovery(workspace: Path, roots: list[Path], mode: str, multi_requested: bool) -> WorkspaceDiscovery:
    roots = sorted(set(item.resolve() for item in roots), key=lambda item: item.as_posix().lower())
    if not roots:
        raise TUnderstandError("AGENT-WORKSPACE-002", "No Git repositories were discovered in the active workspace")
    ids = _unique_repository_ids(roots)
    candidates: list[RepositoryCandidate] = []
    for root in roots:
        role, markers = infer_repository_role(root)
        identity_kind, identity_value, remote = _repository_identity(root)
        reason = "active repository" if len(roots) == 1 else "Git root discovered beneath the active application workspace"
        confidence = "high" if len(roots) == 1 or workspace != root else "medium"
        candidates.append(
            RepositoryCandidate(
                path=root,
                repository_id=ids[root],
                name=root.name,
                role=role,
                identity_kind=identity_kind,
                identity_value=identity_value,
                remote=remote,
                inclusion_reason=reason,
                confidence=confidence,
                markers=markers,
            )
        )
    model = "single-repo" if len(candidates) == 1 else "multi-repo"
    return WorkspaceDiscovery(workspace.resolve(), model, tuple(candidates), mode, multi_requested)


def write_workspace_discovery(context_root: Path, discovery: WorkspaceDiscovery) -> Path:
    path = context_root / "runtime" / "agent-workspace-discovery.yaml"
    atomic_write_yaml(path, discovery.as_dict())
    return path
