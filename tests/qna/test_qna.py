from __future__ import annotations
import shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.analysis.common import KnowledgeFixture, source_digest
from tu_runtime.core.qna import QnAManager

ROOT=Path(__file__).resolve().parents[2]

class QnATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=KnowledgeFixture()
        cls.repo_a=cls.fx.make_repo('producer',{'src/A.java':'class A { void send(){ kafkaTemplate.send("orders.created","x"); } }\n'})
        cls.repo_b=cls.fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"});\n'})
        cls.fx.prepare({'producer':cls.repo_a,'consumer':cls.repo_b}); cls.fx.analysis.run('ANL_A','EXT_A'); cls.fx.graph.create('GRF_A','ANL_A'); cls.fx.memory.build('MEM_A','GRF_A')
    @classmethod
    def tearDownClass(cls): cls.fx.close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.context=Path(self.tmp.name)/'context'; shutil.copytree(self.fx.context,self.context); self.manager=QnAManager(ROOT,self.context)
    def tearDown(self): self.tmp.cleanup()
    def test_answer_is_grounded_and_verified(self):
        before={p.name:source_digest(p) for p in (self.repo_a,self.repo_b)}
        manifest=self.manager.ask('QNA-ORDERS','MEM_A','Which repositories use orders.created?')
        self.assertEqual(manifest['status'],'ANSWERED'); self.assertGreater(manifest['quality']['verified_claims'],0)
        self.assertEqual(self.manager.validate('QNA-ORDERS')['status'],'PASS')
        answer=self.manager.answer('QNA-ORDERS'); self.assertTrue(answer['claims']); self.assertTrue(answer['citations'])
        self.assertEqual(before,{p.name:source_digest(p) for p in (self.repo_a,self.repo_b)})
    def test_unknown_answer_does_not_guess(self):
        self.manager.ask('QNA-UNKNOWN','MEM_A','Where is the lunar billing quantum reconciler?')
        answer=self.manager.answer('QNA-UNKNOWN'); self.assertEqual(answer['answer_status'],'unknown'); self.assertFalse(answer['claims']); self.assertTrue(answer['limitations'])
    def test_inference_is_disclosed(self):
        self.manager.ask('QNA-RELATION','MEM_A','How are producer and consumer related through orders.created?')
        answer=self.manager.answer('QNA-RELATION')
        if 'INFERENCE' in answer['direct_answer'] or any('INFERENCE' in x for x in answer['limitations']):
            self.assertTrue(answer['limitations'])
        self.assertEqual(self.manager.critique('QNA-RELATION')['status'],'PASS')
    def test_tamper_is_detected(self):
        self.manager.ask('QNA-TAMPER','MEM_A','What contains orders.created?')
        p=self.manager._dir('QNA-TAMPER')/'answer.md'; p.write_text(p.read_text()+'tamper\n')
        self.assertEqual(self.manager.validate('QNA-TAMPER')['status'],'FAIL')
    def test_failed_quality_gate_rolls_back(self):
        with patch.object(self.manager,'validate',return_value={'status':'FAIL'}):
            with self.assertRaises(Exception): self.manager.ask('QNA-FAIL','MEM_A','What contains orders.created?')
        self.assertFalse(self.manager._dir('QNA-FAIL').exists())

if __name__=='__main__': unittest.main()
