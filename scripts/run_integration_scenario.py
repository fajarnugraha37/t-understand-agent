import argparse,json,time,unittest
from pathlib import Path
from tu_runtime.core.integration import SCENARIOS
p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--output-dir',default='reports/integration-scenarios');a=p.parse_args()
ids=[x['id'] for x in SCENARIOS]
if a.case not in ids:raise SystemExit(f'unknown case {a.case}')
method='test_'+a.case.replace('-','_')
name=f'tests.integration.test_scenarios.IntegrationScenarios.{method}'
start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromName(name);r=unittest.TextTestRunner(verbosity=2).run(suite);ms=int((time.monotonic()-start)*1000)
d={'id':a.case,'status':'PASS' if r.wasSuccessful() else 'FAIL','assertions':max(1,r.testsRun),'duration_ms':ms,'failures':[str(x[1]) for x in r.failures+r.errors]}
out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);(out/f'{a.case}.json').write_text(json.dumps(d,indent=2)+'\n');raise SystemExit(0 if r.wasSuccessful() else 1)
