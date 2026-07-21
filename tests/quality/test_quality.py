from __future__ import annotations
import shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.analysis.common import KnowledgeFixture
from tu_runtime.core.qna import QnAManager
from tu_runtime.core.quality import QualityManager

ROOT=Path(__file__).resolve().parents[2]
class QualityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fx=KnowledgeFixture();repo=cls.fx.make_repo('service',{'src/A.java':'class A { void send(){ kafkaTemplate.send("orders.created","x"); } }\n'});cls.fx.prepare({'service':repo});cls.fx.analysis.run('ANL_A','EXT_A');cls.fx.graph.create('GRF_A','ANL_A');cls.fx.memory.build('MEM_A','GRF_A');QnAManager(ROOT,cls.fx.context).ask('QNA-AA','MEM_A','Where is orders.created used?')
 @classmethod
 def tearDownClass(cls):cls.fx.close()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.context=Path(self.tmp.name)/'context';shutil.copytree(self.fx.context,self.context);self.m=QualityManager(ROOT,self.context)
 def tearDown(self):self.tmp.cleanup()
 def test_consolidated_quality_passes(self):
  r=self.m.run('QLTY-A',['memory:MEM_A','qna:QNA-AA']);self.assertEqual(r['status'],'PASS');self.assertEqual(self.m.validate('QLTY-A')['status'],'PASS')
 def test_invalid_target_fails_closed(self):
  with self.assertRaises(Exception):self.m.run('QLTY-B',['qna:MISSING'])
 def test_tamper_is_detected(self):
  self.m.run('QLTY-C',['memory:MEM_A']);p=self.m._dir('QLTY-C')/'quality-report.yaml';p.write_text(p.read_text()+'#tamper\n');self.assertEqual(self.m.validate('QLTY-C')['status'],'FAIL')
 def test_failed_post_validation_rolls_back(self):
  with patch.object(self.m,'validate',return_value={'status':'FAIL'}):
   with self.assertRaises(Exception):self.m.run('QLTY-D',['memory:MEM_A'])
  self.assertFalse(self.m._dir('QLTY-D').exists())
