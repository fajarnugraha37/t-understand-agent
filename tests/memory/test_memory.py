from __future__ import annotations
import unittest
from tests.analysis.common import KnowledgeFixture, git

class MemoryTests(unittest.TestCase):
    def setUp(self): self.fx=KnowledgeFixture()
    def tearDown(self): self.fx.close()
    def _build(self):
        a=self.fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }'})
        b=self.fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'})
        self.fx.prepare({'producer':a,'consumer':b}); self.fx.analysis.run('ANL_A','EXT_A'); self.fx.graph.create('GRF_A','ANL_A'); return self.fx.memory.build('MEM_A','GRF_A'),a,b
    def test_memory_is_verified_and_searchable(self):
        doc,_,_=self._build(); self.assertGreater(doc['counts']['claims'],0); self.assertEqual(self.fx.memory.validate('MEM_A')['status'],'PASS'); self.assertEqual(self.fx.memory.critique('MEM_A')['status'],'PASS'); self.assertTrue(self.fx.memory.search('MEM_A','orders')['results'])
    def test_freshness_is_snapshot_aware(self):
        self._build(); self.assertEqual(self.fx.memory.freshness('MEM_A','SNAP_A')['status'],'CURRENT'); self.assertEqual(self.fx.memory.freshness('MEM_A','MISSING')['status'],'UNKNOWN')
    def test_invalidation_propagates(self):
        _,repo,_=self._build(); (repo/'src/A.java').write_text('class A { void x(){ kafkaTemplate.send("changed","x"); } }'); git(repo,'add','.'); git(repo,'commit','-qm','change')
        self.fx.snapshots.create_snapshot('SNAP_B',{},'foundation'); self.fx.discovery.create('DISC_B','SNAP_B')
        report=self.fx.memory.invalidate('INV_A','MEM_A','DISC_B'); self.assertEqual(report['status'],'INVALIDATED'); self.assertTrue(report['invalidated_evidence']); self.assertTrue(report['affected_claims'])
    def test_duplicate_http_provider_is_conflict_not_arbitrary_fact(self):
        a=self.fx.make_repo('repo-a',{'openapi.yaml':'openapi: 3.0.0\ninfo: {title: A, version: "1"}\npaths:\n  /same:\n    get: {operationId: a}\n'})
        b=self.fx.make_repo('repo-b',{'openapi.yaml':'openapi: 3.0.0\ninfo: {title: B, version: "1"}\npaths:\n  /same:\n    get: {operationId: b}\n'})
        self.fx.prepare({'repo-a':a,'repo-b':b}); self.fx.analysis.run('ANL_A','EXT_A'); self.fx.graph.create('GRF_A','ANL_A'); doc=self.fx.memory.build('MEM_A','GRF_A')
        self.assertEqual(doc['status'],'CONFLICTED'); self.assertGreater(doc['counts']['conflicts'],0); self.assertEqual(self.fx.memory.freshness('MEM_A','SNAP_A')['status'],'STALE')
    def test_tamper_is_detected(self):
        self._build(); p=self.fx.context/'memory/versions/MEM_A/claims.jsonl'; p.write_text(p.read_text()+'{}\n'); self.assertEqual(self.fx.memory.validate('MEM_A')['status'],'FAIL')
if __name__=='__main__': unittest.main()
