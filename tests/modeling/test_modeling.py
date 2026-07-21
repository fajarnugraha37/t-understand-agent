from __future__ import annotations
import shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.analysis.common import KnowledgeFixture, source_digest
from tu_runtime.core.modeling import ModelManager, MODEL_TYPES

ROOT=Path(__file__).resolve().parents[2]

class ModelingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=KnowledgeFixture()
        cls.repo_a=cls.fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }','Dockerfile':'FROM eclipse-temurin:21\nEXPOSE 8080\n'})
        cls.repo_b=cls.fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'})
        cls.fx.prepare({'producer':cls.repo_a,'consumer':cls.repo_b}); cls.fx.analysis.run('ANL_A','EXT_A'); cls.fx.graph.create('GRF_A','ANL_A'); cls.fx.memory.build('MEM_A','GRF_A')
    @classmethod
    def tearDownClass(cls): cls.fx.close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.context=Path(self.tmp.name)/'context'; shutil.copytree(self.fx.context,self.context); self.manager=ModelManager(ROOT,self.context)
    def tearDown(self): self.tmp.cleanup()
    def test_complete_model_set_is_traceable_and_verified(self):
        before={p.name:source_digest(p) for p in (self.repo_a,self.repo_b)}; m=self.manager.build('MODEL_A','MEM_A'); self.assertEqual(before,{p.name:source_digest(p) for p in (self.repo_a,self.repo_b)})
        self.assertEqual(m['quality']['unsupported_records'],0); self.assertEqual(m['quality']['traceability_coverage'],1.0); self.assertEqual(set(MODEL_TYPES),set(k for k in m['artifacts'] if k!='traceability'))
        self.assertEqual(self.manager.validate('MODEL_A')['status'],'PASS'); self.assertEqual(self.manager.critique('MODEL_A')['status'],'PASS')
    def test_business_knowledge_is_not_promoted_to_fact(self):
        self.manager.build('MODEL_A','MEM_A')
        for name in ('business-capabilities','business-rules','actors'):
            for record in self.manager.artifact('MODEL_A',name)['records']: self.assertNotEqual(record['classification'],'FACT')
        self.assertEqual(self.manager.artifact('MODEL_A','business-rules')['records'][0]['classification'],'UNKNOWN')
    def test_conflicts_are_preserved(self):
        fx=KnowledgeFixture()
        try:
            a=fx.make_repo('repo-a',{'openapi.yaml':'openapi: 3.0.0\ninfo: {title: A, version: "1"}\npaths:\n  /same:\n    get: {operationId: a}\n'}); b=fx.make_repo('repo-b',{'openapi.yaml':'openapi: 3.0.0\ninfo: {title: B, version: "1"}\npaths:\n  /same:\n    get: {operationId: b}\n'})
            fx.prepare({'repo-a':a,'repo-b':b}); fx.analysis.run('ANL_A','EXT_A'); fx.graph.create('GRF_A','ANL_A'); fx.memory.build('MEM_A','GRF_A'); manager=ModelManager(ROOT,fx.context); m=manager.build('MODEL_A','MEM_A')
            self.assertEqual(m['status'],'CONFLICTED'); self.assertTrue(any(r['classification']=='CONFLICT' for r in manager.artifact('MODEL_A','architecture-model')['records']))
        finally: fx.close()
    def test_reconciliation_preserves_stable_record_identity(self):
        self.manager.build('MODEL_A','MEM_A'); report=self.manager.reconcile('RECON_A','MODEL_B','MODEL_A','MEM_A'); self.assertEqual(report['status'],'UNCHANGED'); self.assertTrue(report['unchanged']); self.assertFalse(report['added'] or report['removed'] or report['changed'])
    def test_failed_quality_gate_leaves_no_published_model(self):
        with patch.object(self.manager,'critique',return_value={'status':'FAIL'}):
            with self.assertRaises(Exception): self.manager.build('MODEL_A','MEM_A')
        self.assertFalse(self.manager._dir('MODEL_A').exists())
    def test_tamper_is_detected(self):
        self.manager.build('MODEL_A','MEM_A'); p=self.manager._dir('MODEL_A')/'application-model.yaml'; p.write_text(p.read_text()+'\n# tamper\n'); self.assertEqual(self.manager.validate('MODEL_A')['status'],'FAIL')
if __name__=='__main__': unittest.main()
