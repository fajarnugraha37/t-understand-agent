from __future__ import annotations
import json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.analysis.common import KnowledgeFixture
from tu_runtime.core.modeling import ModelManager
from tu_runtime.core.documentation import DocumentationManager
from tu_runtime.core.exporting import ExportManager,PROFILES
ROOT=Path(__file__).resolve().parents[2]

class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=KnowledgeFixture(); a=cls.fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }'}); b=cls.fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'})
        cls.fx.prepare({'producer':a,'consumer':b}); cls.fx.analysis.run('ANL_A','EXT_A'); cls.fx.graph.create('GRF_A','ANL_A'); cls.fx.memory.build('MEM_A','GRF_A'); ModelManager(ROOT,cls.fx.context).build('MODEL_A','MEM_A'); DocumentationManager(ROOT,cls.fx.context).generate('DOCS_A','MODEL_A')
    @classmethod
    def tearDownClass(cls): cls.fx.close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.context=Path(self.tmp.name)/'context'; shutil.copytree(self.fx.context,self.context); self.docs=DocumentationManager(ROOT,self.context); self.exports=ExportManager(ROOT,self.context)
    def tearDown(self): self.tmp.cleanup()
    def test_all_profiles_are_created_and_validated(self):
        for i,profile in enumerate(PROFILES):
            eid=f'EXPORT_{i}'; m=self.exports.create(eid,'DOCS_A',profile); self.assertEqual(m['status'],'VALID'); self.assertEqual(self.exports.validate(eid)['status'],'PASS')
    def test_profile_configuration_files(self):
        expectations={'plain-markdown':'SUMMARY.md','github-markdown':'README.md','mintlify-mdx':'docs.json','docusaurus-mdx':'sidebars.js','mkdocs-markdown':'mkdocs.yml'}
        for i,(profile,name) in enumerate(expectations.items()):
            eid=f'EXPORT_{i}'; self.exports.create(eid,'DOCS_A',profile); self.assertTrue((self.exports._dir(eid)/'site'/name).exists())
        self.assertIn('navigation',json.loads((self.exports._dir('EXPORT_2')/'site/docs.json').read_text()))
    def test_semantic_traceability_stays_canonical(self):
        self.exports.create('EXPORT_A','DOCS_A','mintlify-mdx'); self.assertEqual(self.exports.show('EXPORT_A')['docset_id'],'DOCS_A'); self.assertTrue((self.docs._dir('DOCS_A')/'traceability.jsonl').exists())
    def test_failed_validation_leaves_no_published_export(self):
        with patch.object(self.exports,'validate',return_value={'status':'FAIL'}):
            with self.assertRaises(Exception): self.exports.create('EXPORT_A','DOCS_A','plain-markdown')
        self.assertFalse(self.exports._dir('EXPORT_A').exists())
    def test_tamper_is_detected(self):
        m=self.exports.create('EXPORT_A','DOCS_A','plain-markdown'); p=self.exports._dir('EXPORT_A')/m['files'][0]['path']; p.write_text(p.read_text()+'tamper'); self.assertEqual(self.exports.validate('EXPORT_A')['status'],'FAIL')
if __name__=='__main__': unittest.main()
