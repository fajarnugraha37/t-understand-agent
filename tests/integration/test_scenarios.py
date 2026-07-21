from __future__ import annotations
import subprocess,tempfile,time,unittest
from pathlib import Path
from tests.analysis.common import KnowledgeFixture
from tests.discovery.common import DiscoveryFixture,git
from tu_runtime.core.documentation import DocumentationManager
from tu_runtime.core.exporting import ExportManager
from tu_runtime.core.installation import InstallationManager
from tu_runtime.core.modeling import ModelManager
from tu_runtime.core.qna import QnAManager
from tu_runtime.core.qualification import QualificationManager
from tu_runtime.core.quality import QualityManager
from tu_runtime.core.reviewing import ReviewManager
ROOT=Path(__file__).resolve().parents[2]

def commit(repo:Path,msg='change'):
 subprocess.run(['git','-C',str(repo),'add','.'],check=True);subprocess.run(['git','-C',str(repo),'commit','-qm',msg],check=True)

class IntegrationScenarios(unittest.TestCase):
 def test_single_repo_complete_pipeline(self):
  fx=KnowledgeFixture()
  try:
   repo=fx.make_repo('service',{'src/App.java':'class App { void x(){ kafkaTemplate.send("orders.created","x"); } }\n','src/AppTest.java':'class AppTest {}\n'});fx.prepare({'service':repo});fx.analysis.run('ANL_A','EXT_A');fx.graph.create('GRF_A','ANL_A');fx.memory.build('MEM_A','GRF_A')
   ModelManager(ROOT,fx.context).build('MODEL_A','MEM_A');DocumentationManager(ROOT,fx.context).generate('DOCS_A','MODEL_A');ExportManager(ROOT,fx.context).create('EXP_A','DOCS_A','plain-markdown');QnAManager(ROOT,fx.context).ask('QNA-AA','MEM_A','Where is orders.created used?')
   fx.snapshots.create_review_target('STATIC_A','STATIC_AUDIT','SNAP_A');ReviewManager(ROOT,fx.context).run('RVW-AA','STATIC_A','audit')
   q=QualityManager(ROOT,fx.context).run('QLTY-A',['memory:MEM_A','model:MODEL_A','documentation:DOCS_A','export:EXP_A','qna:QNA-AA','review:RVW-AA'])
   self.assertEqual(q['status'],'PASS')
  finally:fx.close()
 def test_monorepo_module_coverage(self):
  fx=DiscoveryFixture()
  try:
   repo=fx.make_repo('mono',{'pom.xml':'<project/>','services/order/pom.xml':'<project/>','services/billing/package.json':'{"name":"billing"}'});fx.setup({'repo-a':repo},model='monorepo');fx.snapshots.create_snapshot('SNAP_M',{},'foundation');fx.discovery.create('DISC_M','SNAP_M');d=__import__('yaml').safe_load((fx.context/'discovery/DISC_M/repositories/repo-a.yaml').read_text());self.assertEqual(len(d['modules']),3)
  finally:fx.close()
 def test_multi_repo_contract_graph(self):
  fx=KnowledgeFixture()
  try:
   a=fx.make_repo('producer',{'src/A.java':'class A { void x(){ kafkaTemplate.send("orders.created","x"); } }'});b=fx.make_repo('consumer',{'src/a.ts':'subscribe({topic:"orders.created"});'});fx.prepare({'producer':a,'consumer':b});fx.analysis.run('ANL_A','EXT_A');g=fx.graph.create('GRF_A','ANL_A');self.assertGreater(g['coverage']['cross_relations'],0)
  finally:fx.close()
 def test_diff_review_matrix(self):
  fx=KnowledgeFixture()
  try:
   repo=fx.make_repo('service',{'src/App.java':'class App { void x(){} }','src/AppTest.java':'class AppTest {}'});fx.setup({'service':repo});fx.snapshots.create_snapshot('BASE',{},'review');(repo/'src/App.java').write_text('class App { boolean verify=false; }');commit(repo);fx.snapshots.create_snapshot('CAND',{},'review');fx.snapshots.create_review_target('TARGET','DIFF','CAND','BASE');r=ReviewManager(ROOT,fx.context).run('RVW-DIFF','TARGET','audit');self.assertIn(r['merge_gate'],{'WARN','BLOCK'})
  finally:fx.close()
 def test_freshness_invalidation_refresh(self):
  fx=KnowledgeFixture()
  try:
   repo=fx.make_repo('service',{'src/A.java':'class A { void x(){ kafkaTemplate.send("a","x"); } }'});fx.prepare({'service':repo});fx.analysis.run('ANL_A','EXT_A');fx.graph.create('GRF_A','ANL_A');fx.memory.build('MEM_A','GRF_A');(repo/'src/A.java').write_text('class A { void x(){ kafkaTemplate.send("b","x"); } }');commit(repo);fx.snapshots.create_snapshot('SNAP_B',{},'foundation');fx.discovery.create('DISC_B','SNAP_B');inv=fx.memory.invalidate('INV_A','MEM_A','DISC_B');self.assertEqual(inv['status'],'INVALIDATED')
  finally:fx.close()
 def test_platform_package_install_uninstall(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);context=base/'context';context.mkdir();m=InstallationManager(ROOT,context);m.package('INST-PKG','opencode');target=base/'config';m.install('INST-A','INST-PKG',target);self.assertEqual(m.doctor(target)['status'],'PASS');self.assertEqual(m.uninstall(target)['status'],'UNINSTALLED')
 def test_cheap_model_contract_qualification(self):
  with tempfile.TemporaryDirectory() as td:
   c=Path(td)/'context';c.mkdir();r=QualificationManager(ROOT,c).run('QUAL-A');self.assertEqual(r['status'],'PASS');self.assertTrue(all(not row['live_model_tested'] for row in r['matrix']))
