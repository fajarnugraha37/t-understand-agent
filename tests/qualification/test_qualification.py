from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tu_runtime.core.qualification import QualificationManager
ROOT=Path(__file__).resolve().parents[2]
class QualificationTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.context=Path(self.tmp.name)/'context';self.context.mkdir();self.m=QualificationManager(ROOT,self.context)
 def tearDown(self):self.tmp.cleanup()
 def test_all_profiles_contract_qualified(self):
  r=self.m.run('QUAL-A');self.assertEqual(r['status'],'PASS');self.assertTrue(all(not x['live_model_tested'] for x in r['matrix']));self.assertEqual(self.m.validate('QUAL-A')['status'],'PASS')
 def test_claim_boundary_is_explicit(self):
  r=self.m.run('QUAL-B',profiles=['economy']);self.assertIn('no live',r['claim_boundary'].lower())
 def test_unknown_runner_rejected(self):
  with self.assertRaises(Exception):self.m.run('QUAL-C','unknown')
 def test_tamper_detected(self):
  self.m.run('QUAL-D');p=self.m._dir('QUAL-D')/'qualification-report.yaml';p.write_text(p.read_text()+'#tamper\n');self.assertEqual(self.m.validate('QUAL-D')['status'],'FAIL')
