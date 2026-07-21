from __future__ import annotations

import json
import unittest

from tests.discovery.common import DiscoveryFixture


class AdapterIntegrationTests(unittest.TestCase):
    def setUp(self): self.fx=DiscoveryFixture()
    def tearDown(self): self.fx.close()

    def _run(self):
        repo=self.fx.make_repo("repo-a",self.fx.sample_files()); self.fx.setup({"repo-a":repo})
        self.fx.snapshots.create_snapshot("SNAP_A",{},"foundation")
        self.fx.discovery.create("DISC_A","SNAP_A")
        return self.fx.adapters.run("EXTRACT_A","DISC_A")

    def test_adapter_run_is_snapshot_bound(self):
        doc=self._run()
        self.assertEqual(doc["snapshot_id"],"SNAP_A")
        self.assertGreater(doc["files_total"],0)
        self.assertEqual(self.fx.adapters.validate("EXTRACT_A")["status"],"PASS")

    def test_records_include_exact_file_hash(self):
        self._run(); records=[json.loads(x) for x in (self.fx.context/"extractions/EXTRACT_A/adapter-extractions.jsonl").read_text().splitlines()]
        java=next(x for x in records if x["path"].endswith("App.java"))
        self.assertEqual(java["adapter_id"],"java")
        self.assertRegex(java["file_sha256"],r"^[0-9a-f]{64}$")

    def test_duplicate_extraction_id_rejected(self):
        self._run()
        with self.assertRaises(Exception): self.fx.adapters.run("EXTRACT_A","DISC_A")

    def test_tamper_is_detected(self):
        self._run(); path=self.fx.context/"extractions/EXTRACT_A/adapter-extractions.jsonl"
        path.write_text(path.read_text()+"{}\n")
        self.assertEqual(self.fx.adapters.validate("EXTRACT_A")["status"],"FAIL")

if __name__ == '__main__': unittest.main()
