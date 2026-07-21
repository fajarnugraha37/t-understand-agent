import sys
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def load(name): return json.loads((ROOT/'reports'/name).read_text())
contract=load('discovery-contract-report.json'); tests=load('discovery-test-report.json'); cli=load('discovery-cli-report.json')
report={'product':'t-understand','version':(ROOT/'VERSION').read_text().strip(),'phase':5,'phase_name':'Repository Discovery Engine','status':'PASS' if all(x['status']=='PASS' for x in (contract,tests,cli)) else 'FAIL','inventory':{'discovery_schemas':3,'discovery_cli_commands':4,'classification_types':13,'supported_snapshot_modes':6},'validation':{'contract_checks':contract['checks'],'tests':tests['tests'],'cli_checks':cli['checks']},'assurances':{'source_repository_access':'READ_ONLY','snapshot_bound':True,'portable_outputs':True,'protected_content_read':'DENY','ignored_content_read':'DENY','coverage_ledgers':True,'deterministic_ordering':True,'single_monorepo_multi_repo':True},'explicit_limitations':['Phase 5 inventories repository shape and candidate assets but does not construct semantic call graphs or runtime behavior models.','Generated, vendored, protected, binary, symlink, submodule, and oversized contents are excluded with explicit ledger entries.']}
(ROOT/'reports/phase-5-summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); import os
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if report['status']=='PASS' else 1)
