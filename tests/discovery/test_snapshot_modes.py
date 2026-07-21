from __future__ import annotations

import json
import unittest

from .common import DiscoveryFixture, git


class SnapshotModeTests(unittest.TestCase):
    def setUp(self): self.fx=DiscoveryFixture()
    def tearDown(self): self.fx.close()

    def test_index_reads_staged_content(self):
        repo=self.fx.make_repo("repo",{"app.py":"VALUE = 'base'\n"}); self.fx.setup({"repo-a":repo})
        (repo/"app.py").write_text("VALUE = 'staged'\n",encoding="utf-8"); git(repo,"add","app.py"); (repo/"app.py").write_text("VALUE = 'unstaged'\n",encoding="utf-8")
        self.fx.snapshots.create_snapshot("SNAP_INDEX",{"repo-a":{"type":"index","ref":None}},"foundation")
        self.fx.discovery.create("DISC_INDEX","SNAP_INDEX")
        record=json.loads((self.fx.context/"discovery/DISC_INDEX/repositories/repo-a.files.jsonl").read_text().splitlines()[0])
        import hashlib
        self.assertEqual(record["sha256"],hashlib.sha256(b"VALUE = 'staged'\n").hexdigest())


    def test_unchanged_worktree_snapshot_is_discoverable(self):
        repo=self.fx.make_repo("repo",{"app.py":"VALUE = 1\n"}); self.fx.setup({"repo-a":repo})
        (repo/"app.py").write_text("VALUE = 2\n",encoding="utf-8")
        (repo/"new.py").write_text("NEW = True\n",encoding="utf-8")
        self.fx.snapshots.create_snapshot("SNAP_WORK",{"repo-a":{"type":"worktree","ref":None}},"foundation")
        doc=self.fx.discovery.create("DISC_WORK","SNAP_WORK")
        self.assertEqual(doc["status"],"DISCOVERED")
        import json
        records=[json.loads(line) for line in (self.fx.context/"discovery/DISC_WORK/repositories/repo-a.files.jsonl").read_text().splitlines()]
        self.assertIn("new.py",[r["path"] for r in records])

    def test_worktree_snapshot_rejects_drift(self):
        repo=self.fx.make_repo("repo",{"app.py":"VALUE = 1\n"}); self.fx.setup({"repo-a":repo})
        (repo/"app.py").write_text("VALUE = 2\n",encoding="utf-8")
        self.fx.snapshots.create_snapshot("SNAP_W",{"repo-a":{"type":"worktree","ref":None}},"foundation")
        (repo/"app.py").write_text("VALUE = 3\n",encoding="utf-8")
        with self.assertRaises(Exception): self.fx.discovery.create("DISC_W","SNAP_W")

if __name__ == '__main__': unittest.main()
