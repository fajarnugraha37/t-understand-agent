from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from tu_runtime.core.application import ApplicationManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def git(path: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, check=True)
    return completed.stdout.strip()


class ApplicationFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.context = self.root / "context"
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.manager = ApplicationManager(PROJECT_ROOT, self.context)

    def close(self) -> None:
        self.temp.cleanup()

    def make_repo(self, name: str, remote: str | None = None, files: dict[str, str] | None = None) -> Path:
        path = self.sources / name
        path.mkdir(parents=True)
        git(path, "init", "-q")
        git(path, "config", "user.email", "tests@t-understand.dev")
        git(path, "config", "user.name", "t-understand tests")
        for relative, content in (files or {"README.md": f"# {name}\n"}).items():
            target = path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-qm", "initial")
        if remote:
            git(path, "remote", "add", "origin", remote)
        return path
