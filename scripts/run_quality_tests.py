import argparse,json,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/quality-test-report.json');a=p.parse_args();s=unittest.defaultTestLoader.discover('tests/quality');r=unittest.TextTestRunner(verbosity=2).run(s);d={'status':'PASS' if r.wasSuccessful() else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors)};Path(a.report).write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(0 if r.wasSuccessful() else 1)
