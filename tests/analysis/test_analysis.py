from __future__ import annotations
import unittest
from tests.analysis.common import KnowledgeFixture, git, source_digest

class AnalysisTests(unittest.TestCase):
    def setUp(self): self.fx=KnowledgeFixture()
    def tearDown(self): self.fx.close()
    def test_structural_and_behavioral_outputs_are_evidence_bound(self):
        repo=self.fx.make_repo('repo-a',{'src/A.java':'class A { @Transactional void x(){ kafkaTemplate.send("orders.created","x"); String q="insert into orders values(1)"; throw new IllegalStateException(); } }'})
        self.fx.prepare({'repo-a':repo}); doc=self.fx.analysis.run('ANL_A','EXT_A')
        self.assertEqual(self.fx.analysis.validate('ANL_A')['status'],'PASS')
        self.assertGreater(doc['coverage']['observations'],0)
        rels=self.fx.analysis._load_artifact('ANL_A','relations')
        self.assertTrue({'PRODUCES','WRITES','TRANSACTION_BOUNDARY','THROWS'} <= {x['type'] for x in rels})
        self.assertTrue(all(x['evidence'] for x in rels))
    def test_analysis_does_not_mutate_source(self):
        repo=self.fx.make_repo('repo-a',{'src/a.py':'def run():\n  raise ValueError()\n'})
        self.fx.prepare({'repo-a':repo}); before=source_digest(repo); self.fx.analysis.run('ANL_A','EXT_A'); self.assertEqual(before,source_digest(repo))
    def test_scoped_analysis_is_explicit(self):
        repo=self.fx.make_repo('repo-a',{'src/a.py':'def a(): pass\n','src/b.py':'def b(): pass\n'})
        self.fx.prepare({'repo-a':repo}); doc=self.fx.analysis.run('ANL_A','EXT_A',['repo-a:src/a.py'])
        self.assertEqual(doc['mode'],'scoped'); self.assertEqual(doc['coverage']['files_analyzed'],1); self.assertGreater(doc['coverage']['files_skipped'],0)
    def test_incremental_is_semantically_equivalent_to_full(self):
        repo=self.fx.make_repo('repo-a',{'src/A.java':'class A { void x(){ kafkaTemplate.send("a","x"); } }','README.md':'# A'})
        self.fx.prepare({'repo-a':repo},'1'); self.fx.analysis.run('ANL_1','EXT_1')
        (repo/'src/A.java').write_text('class A { void x(){ kafkaTemplate.send("b","x"); } }'); (repo/'src/B.java').write_text('class B {}'); git(repo,'add','.'); git(repo,'commit','-qm','change')
        self.fx.snapshots.create_snapshot('SNAP_2',{},'foundation'); self.fx.discovery.create('DISC_2','SNAP_2'); self.fx.adapters.run('EXT_2','DISC_2')
        inc=self.fx.analysis.refresh('ANL_INC','ANL_1','EXT_2'); self.fx.analysis.run('ANL_FULL','EXT_2')
        self.assertEqual(inc['mode'],'incremental'); self.assertGreater(inc['coverage']['files_reused'],0)
        for name in ('evidence','entities','relations','observations'): self.assertEqual(self.fx.semantic('ANL_INC',name),self.fx.semantic('ANL_FULL',name))
    def test_tamper_is_detected(self):
        repo=self.fx.make_repo('repo-a',{'src/a.py':'def a(): pass\n'}); self.fx.prepare({'repo-a':repo}); self.fx.analysis.run('ANL_A','EXT_A')
        p=self.fx.context/'analysis/ANL_A/entities.jsonl'; p.write_text(p.read_text()+'{}\n'); self.assertEqual(self.fx.analysis.validate('ANL_A')['status'],'FAIL')
if __name__=='__main__': unittest.main()
