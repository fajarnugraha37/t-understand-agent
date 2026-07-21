from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from tu_runtime.core.application import ApplicationManager
from tu_runtime.core.discovery import AdapterManager, DiscoveryManager
from tu_runtime.core.snapshot import SnapshotManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def git(path: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, check=True)
    return completed.stdout.strip()


class DiscoveryFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.context = self.root / "context"
        self.application = ApplicationManager(PROJECT_ROOT, self.context)
        self.snapshots = SnapshotManager(PROJECT_ROOT, self.context)
        self.discovery = DiscoveryManager(PROJECT_ROOT, self.context)
        self.adapters = AdapterManager(PROJECT_ROOT, self.context)

    def close(self): self.temp.cleanup()

    def make_repo(self, name: str, files: dict[str, str | bytes]) -> Path:
        path = self.sources / name
        path.mkdir(parents=True)
        git(path, "init", "-q")
        git(path, "config", "user.email", "discovery@t-understand.dev")
        git(path, "config", "user.name", "Discovery Tests")
        for relative, content in files.items():
            target = path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes): target.write_bytes(content)
            else: target.write_text(content, encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-qm", "initial")
        return path

    def setup(self, repos: dict[str, Path], model: str | None = None) -> None:
        model = model or ("single-repo" if len(repos) == 1 else "multi-repo")
        self.application.initialize("application-a", "Application A", model, "machine-a")
        for repository_id, path in repos.items():
            self.application.add_repository(repository_id, repository_id, "service", identity_key=f"local/{repository_id}")
            self.application.bind_repository(repository_id, path)

    def sample_files(self) -> dict[str, str | bytes]:
        return {
            "pom.xml": "<project/>",
            "src/main/java/acme/App.java": "package acme; import java.util.List; public class App { public static void main(String[] args) {} }",
            "src/test/java/acme/AppTest.java": "package acme; class AppTest {}",
            "openapi.yaml": "openapi: 3.0.0\ninfo: {title: Sample, version: '1'}\npaths:\n  /orders:\n    get: {operationId: listOrders}\n",
            "db/migration/V1__init.sql": "create table orders(id bigint primary key);",
            ".github/workflows/ci.yml": "name: ci\n",
            "Dockerfile": "FROM eclipse-temurin:21\nEXPOSE 8080\nENTRYPOINT [\"java\"]\n",
            "README.md": "# Sample\n",
            ".env": "PASSWORD=secret\n",
            "node_modules/pkg/index.js": "module.exports = {};\n",
            "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00",
        }
