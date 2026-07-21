from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

from tu_runtime.core.application import ApplicationManager
from tu_runtime.core.snapshot import SnapshotManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def git(path: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, check=check)
    return completed.stdout.strip()


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".git" not in item.parts):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class SnapshotFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.context = self.root / "context"
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.application = ApplicationManager(PROJECT_ROOT, self.context)
        self.snapshots = SnapshotManager(PROJECT_ROOT, self.context)

    def close(self) -> None:
        self.temp.cleanup()

    def make_repo(self, name: str, remote: str | None = None, files: dict[str, str] | None = None) -> Path:
        path = self.sources / name
        path.mkdir(parents=True)
        git(path, "init", "-q")
        git(path, "config", "user.email", "snapshot@t-understand.dev")
        git(path, "config", "user.name", "t-understand snapshot tests")
        for relative, content in (files or {"README.md": f"# {name}\n"}).items():
            target = path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-qm", "initial")
        if remote:
            git(path, "remote", "add", "origin", remote)
        return path

    def setup_single(self, repo: Path, repository_id: str = "repo-a", default_ref: str | None = None) -> None:
        self.application.initialize("application-a", "Application A", "single-repo", "machine-a")
        self.application.add_repository(repository_id, "Repository A", "backend", identity_key=f"local/{repository_id}", default_ref=default_ref)
        self.application.bind_repository(repository_id, repo)

    def setup_multi(self, repos: dict[str, Path]) -> None:
        self.application.initialize("application-a", "Application A", "multi-repo", "machine-a")
        for repository_id, path in repos.items():
            self.application.add_repository(repository_id, repository_id, "service", identity_key=f"local/{repository_id}")
            self.application.bind_repository(repository_id, path)
