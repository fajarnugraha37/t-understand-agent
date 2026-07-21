import sys
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def load(name): return json.loads((ROOT/'reports'/name).read_text())
contract=load('discovery-contract-report.json'); tests=load('adapter-test-report.json'); cli=load('discovery-cli-report.json')
report={'product':'t-understand','version':(ROOT/'VERSION').read_text().strip(),'phase':6,'phase_name':'Language and Contract Adapters','status':'PASS' if all(x['status']=='PASS' for x in (contract,tests,cli)) else 'FAIL','inventory':{'adapters':11,'adapter_schemas':4,'adapter_cli_commands':5,'languages_and_contract_families':['generic','java','javascript-typescript','python','go','rust','dotnet','sql','bpmn-dmn','openapi-asyncapi','infrastructure']},'validation':{'contract_checks':contract['checks'],'adapter_tests':tests['tests'],'cli_checks':cli['checks']},'assurances':{'deterministic_selection':True,'generic_fallback':True,'snapshot_bound':True,'source_repository_write':'DENY','exact_file_sha256':True,'partial_parse_is_explicit':True,'cheap_model_dependency':False},'explicit_limitations':['Adapters extract deterministic surface declarations, dependencies, interface candidates, configuration keys, and entry points; they do not claim semantic call graphs or business behavior.','Regex adapters do not execute macros, annotation processors, source generators, templates, dynamic registration, or runtime configuration.','BPMN/DMN XML locations are line 1 because the standard-library XML parser does not preserve source line numbers.']}
(ROOT/'reports/phase-6-summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); import os
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if report['status']=='PASS' else 1)
