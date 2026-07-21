from __future__ import annotations
import shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.analysis.common import KnowledgeFixture,git
from tu_runtime.core.modeling import ModelManager
from tu_runtime.core.documentation import DocumentationManager,DOCUMENT_CATALOG
ROOT=Path(__file__).resolve().parents[2]

class DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=KnowledgeFixture(); a=cls.fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }'}); b=cls.fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'})
        cls.fx.prepare({'producer':a,'consumer':b}); cls.fx.analysis.run('ANL_A','EXT_A'); cls.fx.graph.create('GRF_A','ANL_A'); cls.fx.memory.build('MEM_A','GRF_A'); ModelManager(ROOT,cls.fx.context).build('MODEL_A','MEM_A')
    @classmethod
    def tearDownClass(cls): cls.fx.close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.context=Path(self.tmp.name)/'context'; shutil.copytree(self.fx.context,self.context); self.docs=DocumentationManager(ROOT,self.context)
    def tearDown(self): self.tmp.cleanup()
    def test_catalog_traceability_and_quality(self):
        m=self.docs.generate('DOCS_A','MODEL_A'); self.assertGreaterEqual(len(m['documents']),len(DOCUMENT_CATALOG)); self.assertEqual(m['quality']['catalog_coverage'],1.0); self.assertEqual(m['quality']['requirement_coverage'],1.0); self.assertEqual(m['quality']['model_record_coverage'],1.0); self.assertEqual(m['quality']['required_section_coverage'],1.0); self.assertEqual(m['quality']['repository_coverage'],1.0); self.assertEqual(m['quality']['flow_coverage'],1.0); self.assertEqual(m['quality']['section_traceability'],1.0); self.assertEqual(self.docs.validate('DOCS_A')['status'],'PASS'); self.assertEqual(self.docs.critique('DOCS_A')['status'],'PASS')
        for s in self.docs._jsonl('DOCS_A','sections.jsonl'):
            if s['classification'] not in {'LIMITATION','UNKNOWN_INTENT'}: self.assertTrue(s['claims'] and s['evidence'])
    def test_business_inference_is_disclosed(self):
        self.docs.generate('DOCS_A','MODEL_A'); business=[s for s in self.docs._jsonl('DOCS_A','sections.jsonl') if s['classification']=='BUSINESS_INFERENCE']; self.assertTrue(business); self.assertTrue(all(s['limitations'] for s in business))
    def test_document_invalidation_traces_changed_claims(self):
        fx=KnowledgeFixture()
        try:
            repo=fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }'}); other=fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'}); fx.prepare({'producer':repo,'consumer':other}); fx.analysis.run('ANL_A','EXT_A'); fx.graph.create('GRF_A','ANL_A'); fx.memory.build('MEM_A','GRF_A'); ModelManager(ROOT,fx.context).build('MODEL_A','MEM_A'); docs=DocumentationManager(ROOT,fx.context); docs.generate('DOCS_A','MODEL_A')
            (repo/'src/A.java').write_text('class A { void x(){ kafkaTemplate.send("changed","x"); } }'); git(repo,'add','.'); git(repo,'commit','-qm','change'); fx.snapshots.create_snapshot('SNAP_B',{},'foundation'); fx.discovery.create('DISC_B','SNAP_B'); fx.memory.invalidate('MEM_INV','MEM_A','DISC_B'); report=docs.invalidate('DOC_INV','DOCS_A','MEM_INV'); self.assertEqual(report['status'],'INVALIDATED'); self.assertTrue(report['affected_sections'])
        finally: fx.close()
    def test_failed_quality_gate_leaves_no_published_docset(self):
        with patch.object(self.docs,'critique',return_value={'status':'FAIL'}):
            with self.assertRaises(Exception): self.docs.generate('DOCS_A','MODEL_A')
        self.assertFalse(self.docs._dir('DOCS_A').exists())
    def test_tamper_is_detected(self):
        m=self.docs.generate('DOCS_A','MODEL_A'); p=self.docs._dir('DOCS_A')/m['documents'][0]['path']; p.write_text(p.read_text()+'tamper'); self.assertEqual(self.docs.validate('DOCS_A')['status'],'FAIL')
if __name__=='__main__': unittest.main()
