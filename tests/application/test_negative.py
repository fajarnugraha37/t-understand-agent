from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from tu_runtime.core.application import ApplicationManager
from tu_runtime.core.errors import TUnderstandError
from tests.application.common import ApplicationFixture


class ApplicationNegativeTests(unittest.TestCase):
    def test_remote_identity_mismatch_is_rejected(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("service", "https://github.com/acme/actual.git")
            fx.manager.initialize("service-app", "Service", "single-repo", "machine-a")
            fx.manager.add_repository("service", "Service", "backend", remote="https://github.com/acme/expected.git")
            with self.assertRaises(TUnderstandError) as raised:
                fx.manager.bind_repository("service", repo)
            self.assertEqual("APP-IDENTITY-004", raised.exception.code)
        finally:
            fx.close()

    def test_subdirectory_is_not_accepted_as_repository_root(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("mono", "https://github.com/acme/mono.git", {"services/api/a.txt": "a"})
            fx.manager.initialize("mono-app", "Mono", "monorepo", "machine-a")
            fx.manager.add_repository("mono", "Mono", "monorepo", remote="https://github.com/acme/mono.git")
            with self.assertRaises(TUnderstandError) as raised:
                fx.manager.bind_repository("mono", repo / "services" / "api")
            self.assertEqual("APP-GIT-003", raised.exception.code)
        finally:
            fx.close()

    def test_context_inside_source_repository_is_rejected(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("source", "https://github.com/acme/source.git")
            manager = ApplicationManager(fx.manager.project_root, repo / "t-understand-context")
            with self.assertRaises(TUnderstandError) as raised:
                manager.initialize("source-app", "Source", "single-repo", "machine-a")
            self.assertEqual("APP-BOUNDARY-001", raised.exception.code)
            self.assertFalse((repo / "t-understand-context").exists())
        finally:
            fx.close()

    def test_unbound_repository_blocks_resolution(self) -> None:
        fx = ApplicationFixture()
        try:
            fx.manager.initialize("application-a", "Application A", "multi-repo", "machine-a")
            fx.manager.add_repository("repo-a", "Repo A", "backend", identity_key="local/repo-a")
            fx.manager.add_repository("repo-b", "Repo B", "frontend", identity_key="local/repo-b")
            with self.assertRaises(TUnderstandError) as raised:
                fx.manager.resolve()
            self.assertEqual("APP-BIND-002", raised.exception.code)
        finally:
            fx.close()

    def test_workspace_model_repository_count_is_enforced(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("only")
            fx.manager.initialize("application-a", "Application A", "multi-repo", "machine-a")
            fx.manager.add_repository("only", "Only", "backend", identity_key="local/only")
            fx.manager.bind_repository("only", repo)
            with self.assertRaises(TUnderstandError) as raised:
                fx.manager.resolve()
            self.assertEqual("APP-MODEL-003", raised.exception.code)
        finally:
            fx.close()

    def test_absolute_path_in_portable_manifest_is_rejected(self) -> None:
        fx = ApplicationFixture()
        try:
            fx.manager.initialize("application-a", "Application A", "single-repo", "machine-a")
            manifest = yaml.safe_load(fx.manager.manifest_path.read_text(encoding="utf-8"))
            manifest["application"]["description"] = "/tmp/source"
            fx.manager.manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            with self.assertRaises(TUnderstandError) as raised:
                fx.manager.load_manifest()
            self.assertEqual("APP-MANIFEST-003", raised.exception.code)
        finally:
            fx.close()

    def test_duplicate_bound_root_is_rejected(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("shared")
            fx.manager.initialize("application-a", "Application A", "multi-repo", "machine-a")
            fx.manager.add_repository("repo-a", "Repo A", "backend", identity_key="local/a")
            fx.manager.add_repository("repo-b", "Repo B", "frontend", identity_key="local/b")
            fx.manager.bind_repository("repo-a", repo)
            with self.assertRaises(TUnderstandError) as raised:
                fx.manager.bind_repository("repo-b", repo)
            self.assertEqual("APP-BOUNDARY-003", raised.exception.code)
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
