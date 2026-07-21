from __future__ import annotations

import unittest

from tu_runtime.core.application import normalize_remote
from tu_runtime.core.errors import TUnderstandError
from tests.application.common import ApplicationFixture


class ApplicationUnitTests(unittest.TestCase):
    def test_remote_normalization_equivalence(self) -> None:
        values = [
            "https://github.com/Acme/order-service.git",
            "git@github.com:Acme/order-service.git",
            "ssh://git@github.com/Acme/order-service.git",
        ]
        identities = {normalize_remote(value)[0] for value in values}
        self.assertEqual({"github.com/Acme/order-service"}, identities)

    def test_credentials_in_https_remote_are_rejected(self) -> None:
        with self.assertRaises(TUnderstandError) as raised:
            normalize_remote("https://token@github.com/acme/repo.git")
        self.assertEqual("APP-REMOTE-006", raised.exception.code)

    def test_initialize_creates_portable_context_structure(self) -> None:
        fx = ApplicationFixture()
        try:
            result = fx.manager.initialize("application-a", "Application A", "multi-repo", "test-machine")
            self.assertEqual("INITIALIZED", result["status"])
            self.assertTrue((fx.context / "application.yaml").is_file())
            self.assertTrue((fx.context / "workspace.local.yaml").is_file())
            self.assertTrue((fx.context / "documentation" / "mintlify").is_dir())
            ignored = (fx.context / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("workspace.local.yaml", ignored)
            self.assertIn("runtime/", ignored)
        finally:
            fx.close()

    def test_repository_manifest_is_sorted_and_read_only(self) -> None:
        fx = ApplicationFixture()
        try:
            fx.manager.initialize("application-a", "Application A", "multi-repo", "test-machine")
            fx.manager.add_repository("repo-z", "Repo Z", "backend", identity_key="local/repo-z")
            fx.manager.add_repository("repo-a", "Repo A", "frontend", identity_key="local/repo-a")
            manifest = fx.manager.load_manifest()
            self.assertEqual(["repo-a", "repo-z"], [item["id"] for item in manifest["repositories"]])
            self.assertTrue(all(item["source_access"] == "READ_ONLY" for item in manifest["repositories"]))
            text = (fx.context / "application.yaml").read_text(encoding="utf-8")
            self.assertNotIn(str(fx.sources), text)
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
