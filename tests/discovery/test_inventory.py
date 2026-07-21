from __future__ import annotations

import json
import unittest

from .common import DiscoveryFixture, git


class InventoryTests(unittest.TestCase):
    def setUp(self): self.fx = DiscoveryFixture()
    def tearDown(self): self.fx.close()

    def _run(self):
        repo=self.fx.make_repo("repo-a",self.fx.sample_files()); self.fx.setup({"repo-a":repo})
        self.fx.snapshots.create_snapshot("SNAP_A",{},"foundation")
        return repo,self.fx.discovery.create("DISC_A","SNAP_A")

    def test_inventory_and_coverage(self):
        _,doc=self._run()
        self.assertEqual(doc["coverage"]["files_total"],11)
        self.assertEqual(doc["coverage"]["repositories_discovered"],1)
        self.assertEqual(self.fx.discovery.validate("DISC_A")["status"],"PASS")

    def test_protected_vendor_and_binary_are_excluded(self):
        self._run(); root=self.fx.context/"discovery"/"DISC_A"
        repo_doc=__import__('yaml').safe_load((root/"repositories/repo-a.yaml").read_text())
        records=[json.loads(line) for line in (root/repo_doc["files_path"]).read_text().splitlines()]
        by_path={r["path"]:r for r in records}
        self.assertEqual(by_path[".env"]["exclusion_reason"],"protected")
        self.assertIsNone(by_path[".env"]["sha256"])
        self.assertEqual(by_path["node_modules/pkg/index.js"]["exclusion_reason"],"vendored")
        self.assertEqual(by_path["assets/logo.png"]["exclusion_reason"],"binary")

    def test_build_modules_and_assets(self):
        self._run(); doc=__import__('yaml').safe_load((self.fx.context/"discovery/DISC_A/repositories/repo-a.yaml").read_text())
        self.assertIn("maven",[x["kind"] for x in doc["build_systems"]])
        self.assertIn("openapi",[x["kind"] for x in doc["contracts"]])
        self.assertIn("flyway",[x["kind"] for x in doc["migrations"]])
        self.assertIn("github-actions",[x["kind"] for x in doc["ci_assets"]])
        self.assertIn("dockerfile",[x["kind"] for x in doc["deployment_assets"]])

    def test_commit_snapshot_is_independent_from_later_worktree_change(self):
        repo,doc=self._run()
        (repo/"src/main/java/acme/App.java").write_text("changed but not committed",encoding="utf-8")
        shown=self.fx.discovery.show("DISC_A")
        self.assertEqual(shown["content_digest"],doc["content_digest"])
        self.assertEqual(self.fx.discovery.validate("DISC_A")["status"],"PASS")

    def test_multi_repo_order_is_deterministic(self):
        a=self.fx.make_repo("a",{"README.md":"# A\n"}); b=self.fx.make_repo("b",{"README.md":"# B\n"})
        self.fx.setup({"repo-b":b,"repo-a":a}); self.fx.snapshots.create_snapshot("SNAP_M",{},"foundation")
        doc=self.fx.discovery.create("DISC_M","SNAP_M")
        self.assertEqual([x["repository_id"] for x in doc["repositories"]],["repo-a","repo-b"])


    def test_monorepo_detects_multiple_module_roots(self):
        repo=self.fx.make_repo("mono",{
            "pom.xml":"<project/>",
            "services/order/pom.xml":"<project/>",
            "services/billing/package.json":"{\"name\":\"billing\"}",
        })
        self.fx.setup({"repo-a":repo},model="monorepo")
        self.fx.snapshots.create_snapshot("SNAP_MONO",{},"foundation")
        self.fx.discovery.create("DISC_MONO","SNAP_MONO")
        doc=__import__('yaml').safe_load((self.fx.context/"discovery/DISC_MONO/repositories/repo-a.yaml").read_text())
        self.assertEqual([m["root"] for m in doc["modules"]],[".","services/billing","services/order"])

    def test_output_is_portable_and_source_is_unchanged(self):
        import hashlib
        repo=self.fx.make_repo("repo-a",self.fx.sample_files()); self.fx.setup({"repo-a":repo})
        def digest():
            h=hashlib.sha256()
            for path in sorted(x for x in repo.rglob('*') if x.is_file() and '.git' not in x.parts):
                h.update(path.relative_to(repo).as_posix().encode()); h.update(path.read_bytes())
            return h.hexdigest()
        before=digest(); self.fx.snapshots.create_snapshot("SNAP_PORT",{},"foundation"); self.fx.discovery.create("DISC_PORT","SNAP_PORT"); after=digest()
        self.assertEqual(before,after)
        rendered=(self.fx.context/"discovery/DISC_PORT/application-discovery.yaml").read_text()
        self.assertNotIn(str(repo),rendered)

    def test_failed_discovery_does_not_publish_final_directory(self):
        repo=self.fx.make_repo("repo",{"app.py":"VALUE=1\n"}); self.fx.setup({"repo-a":repo})
        (repo/"app.py").write_text("VALUE=2\n",encoding="utf-8")
        self.fx.snapshots.create_snapshot("SNAP_DIRTY",{"repo-a":{"type":"worktree","ref":None}},"foundation")
        (repo/"app.py").write_text("VALUE=3\n",encoding="utf-8")
        with self.assertRaises(Exception): self.fx.discovery.create("DISC_FAIL","SNAP_DIRTY")
        self.assertFalse((self.fx.context/"discovery/DISC_FAIL").exists())

    def test_tamper_is_detected(self):
        self._run(); path=self.fx.context/"discovery/DISC_A/repositories/repo-a.files.jsonl"
        path.write_text(path.read_text()+"{}\n")
        self.assertEqual(self.fx.discovery.validate("DISC_A")["status"],"FAIL")

    def test_duplicate_discovery_id_rejected(self):
        self._run()
        with self.assertRaises(Exception): self.fx.discovery.create("DISC_A","SNAP_A")

if __name__ == '__main__': unittest.main()
