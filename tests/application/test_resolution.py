from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from tests.application.common import ApplicationFixture


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".git" not in item.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class ApplicationResolutionTests(unittest.TestCase):
    def test_single_repo_resolution(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("service", "git@github.com:acme/service.git")
            before = source_digest(repo)
            fx.manager.initialize("service-app", "Service App", "single-repo", "machine-a")
            fx.manager.add_repository("service", "Service", "backend-service", remote="https://github.com/acme/service.git")
            fx.manager.bind_repository("service", repo)
            result = fx.manager.resolve()
            self.assertEqual("RESOLVED", result["status"])
            self.assertEqual("MATCH", result["repositories"][0]["identity_status"])
            self.assertEqual(before, source_digest(repo))
            self.assertTrue(fx.manager.resolution_path.is_file())
        finally:
            fx.close()

    def test_monorepo_resolution(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("platform", "https://github.com/acme/platform.git", {
                "services/api/README.md": "api\n",
                "apps/web/README.md": "web\n",
                "infra/k8s.yaml": "kind: List\n",
            })
            fx.manager.initialize("platform-app", "Platform", "monorepo", "machine-a")
            fx.manager.add_repository("platform", "Platform Monorepo", "application-monorepo", remote="git@github.com:acme/platform.git")
            fx.manager.bind_repository("platform", repo)
            result = fx.manager.resolve()
            self.assertEqual("monorepo", result["workspace_model"])
            self.assertEqual(1, len(result["repositories"]))
        finally:
            fx.close()

    def test_multi_repo_resolution(self) -> None:
        fx = ApplicationFixture()
        try:
            api = fx.make_repo("api", "https://github.com/acme/api.git")
            web = fx.make_repo("web", "https://github.com/acme/web.git")
            fx.manager.initialize("application-a", "Application A", "multi-repo", "machine-a")
            fx.manager.add_repository("api", "API", "backend-service", remote="git@github.com:acme/api.git")
            fx.manager.add_repository("web", "Web", "frontend", remote="git@github.com:acme/web.git")
            fx.manager.bind_repository("api", api)
            fx.manager.bind_repository("web", web)
            result = fx.manager.resolve()
            self.assertEqual(["api", "web"], [item["repository_id"] for item in result["repositories"]])
            validation = fx.manager.validate(inspect_workspace=True)
            self.assertEqual("PASS", validation["status"], validation)
        finally:
            fx.close()

    def test_explicit_identity_supports_repository_without_origin(self) -> None:
        fx = ApplicationFixture()
        try:
            repo = fx.make_repo("private-local")
            fx.manager.initialize("local-app", "Local App", "single-repo", "machine-a")
            fx.manager.add_repository("local-repo", "Local Repo", "prototype", identity_key="company/local-repo")
            fx.manager.bind_repository("local-repo", repo)
            result = fx.manager.resolve()
            self.assertEqual("EXPLICIT", result["repositories"][0]["identity_status"])
            self.assertIsNone(result["repositories"][0]["actual_identity"])
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
