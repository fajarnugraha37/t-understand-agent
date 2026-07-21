from __future__ import annotations
import shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.analysis.common import KnowledgeFixture, source_digest
from tu_runtime.core.reviewing import ReviewManager,ReviewExportManager,EXPORT_PROFILES

ROOT=Path(__file__).resolve().parents[2]

def commit(repo:Path,msg='change'):
    subprocess.run(['git','-C',str(repo),'add','.'],check=True)
    subprocess.run(['git','-C',str(repo),'commit','-m',msg],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=KnowledgeFixture()
        cls.repo=cls.fx.make_repo('service',{'src/App.java':'class App { void run(){} }\n','src/AppTest.java':'class AppTest {}\n'})
        cls.fx.setup({'service':cls.repo}); cls.fx.snapshots.create_snapshot('BASE',{},'review')
        (cls.repo/'src/App.java').write_text('class App { void run(){ try{} catch(Exception e){} } boolean verify=false; }\n')
        commit(cls.repo)
        cls.fx.snapshots.create_snapshot('CAND',{},'review'); cls.fx.snapshots.create_review_target('TARGET','DIFF','CAND','BASE')
    @classmethod
    def tearDownClass(cls): cls.fx.close()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.context=Path(self.tmp.name)/'context'; shutil.copytree(self.fx.context,self.context); self.manager=ReviewManager(ROOT,self.context)
    def tearDown(self): self.tmp.cleanup()
    def test_diff_review_detects_exact_risks_and_test_gap(self):
        before=source_digest(self.repo); m=self.manager.run('RVW-DIFF','TARGET','audit')
        self.assertEqual(m['merge_gate'],'BLOCK'); findings=self.manager.findings('RVW-DIFF')
        self.assertTrue(any(f['type']=='SECURITY' and f['severity']=='CRITICAL' for f in findings))
        self.assertTrue(any(f['type']=='RELIABILITY' for f in findings))
        self.assertTrue(any(f['type']=='TEST_GAP' for f in findings))
        self.assertEqual(self.manager.validate('RVW-DIFF')['status'],'PASS'); self.assertEqual(before,source_digest(self.repo))
    def test_static_audit_and_critical_profile(self):
        self.manager.snapshots.create_review_target('STATIC','STATIC_AUDIT','CAND')
        m=self.manager.run('RVW-STATIC','STATIC','critical-only'); findings=self.manager.findings('RVW-STATIC')
        self.assertTrue(findings); self.assertTrue(all(f['severity'] in {'BLOCKER','CRITICAL'} for f in findings)); self.assertEqual(m['profile'],'critical-only')
    def test_tamper_is_detected(self):
        self.manager.run('RVW-TAMPER','TARGET','balanced'); p=self.manager._dir('RVW-TAMPER')/'findings.md'; p.write_text(p.read_text()+'tamper\n')
        self.assertEqual(self.manager.validate('RVW-TAMPER')['status'],'FAIL')
    def test_failed_verification_rolls_back(self):
        with patch.object(self.manager,'validate',return_value={'status':'FAIL'}):
            with self.assertRaises(Exception): self.manager.run('RVW-FAIL','TARGET','balanced')
        self.assertFalse(self.manager._dir('RVW-FAIL').exists())

class ReviewExportTests(unittest.TestCase):
    def setUp(self):
        self.fx=KnowledgeFixture(); self.repo=self.fx.make_repo('service',{'src/App.java':'class App { boolean verify=false; }\n'}); self.fx.setup({'service':self.repo}); self.fx.snapshots.create_snapshot('CAND',{},'review'); self.fx.snapshots.create_review_target('STATIC','STATIC_AUDIT','CAND'); self.reviews=ReviewManager(ROOT,self.fx.context); self.reviews.run('RVW-EXPORT','STATIC','audit'); self.exports=ReviewExportManager(ROOT,self.fx.context)
    def tearDown(self): self.fx.close()
    def test_all_export_profiles(self):
        for idx,profile in enumerate(EXPORT_PROFILES):
            doc=self.exports.create(f'RVX-{idx}A','RVW-EXPORT',profile); self.assertEqual(doc['profile'],profile); self.assertEqual(self.exports.validate(doc['export_id'])['status'],'PASS')
    def test_source_review_tamper_invalidates_export(self):
        self.exports.create('RVX-TAMPER','RVW-EXPORT','github'); p=self.reviews._dir('RVW-EXPORT')/'review-summary.md'; p.write_text(p.read_text()+'tamper\n')
        # source manifest itself remains intact, but canonical review validation fails and future export is blocked
        self.assertEqual(self.reviews.validate('RVW-EXPORT')['status'],'FAIL')
        with self.assertRaises(Exception): self.exports.create('RVX-BLOCKED','RVW-EXPORT','json')

if __name__=='__main__': unittest.main()
