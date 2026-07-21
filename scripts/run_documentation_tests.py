from __future__ import annotations
import argparse,json,sys,unittest,os,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]; warnings.simplefilter('ignore',ResourceWarning)
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/documentation-test-report.json')); a=p.parse_args()
s=unittest.defaultTestLoader.discover(str(ROOT/'tests/documentation'),pattern='test_*.py',top_level_dir=str(ROOT)); r=unittest.TextTestRunner(verbosity=2).run(s); d={'status':'PASS' if r.wasSuccessful() else 'FAIL','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'categories':{'catalog_traceability':1,'business_disclosure':1,'invalidation':1,'atomic_rollback':1,'tamper':1}}; Path(a.report).write_text(json.dumps(d,indent=2)+'\n'); print(json.dumps(d,indent=2)); sys.stdout.flush(); os._exit(0 if r.wasSuccessful() else 1)
