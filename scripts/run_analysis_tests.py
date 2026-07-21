from __future__ import annotations
import argparse,json,sys,unittest,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/analysis-test-report.json')); args=p.parse_args()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/analysis'),pattern='test_*.py',top_level_dir=str(ROOT)); result=unittest.TextTestRunner(verbosity=2).run(suite)
report={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'categories':{'evidence_and_behavior':2,'scoped_and_incremental':2,'tamper':1}}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); sys.stdout.flush(); sys.stderr.flush(); os._exit(0 if result.wasSuccessful() else 1)
