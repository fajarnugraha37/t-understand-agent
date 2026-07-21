import argparse,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
p=argparse.ArgumentParser();p.add_argument('--report',default=str(ROOT/'reports/agent-native-test-report.json'));a=p.parse_args()
s=unittest.defaultTestLoader.discover(str(ROOT/'tests/agent_native'),pattern='test_*.py',top_level_dir=str(ROOT));r=unittest.TextTestRunner(verbosity=2).run(s)
d={'status':'PASS' if r.wasSuccessful() else 'FAIL','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'categories':{'greeting':1,'intent_precedence':2,'artifact_documentation':1,'response_sanitation':1,'multi_repository_discovery':1,'multi_repository_documentation':1}}
Path(a.report).write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2));sys.stdout.flush();os._exit(0 if r.wasSuccessful() else 1)
