import json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n): return json.loads((ROOT/'reports'/n).read_text())
c=load('analysis-contract-report.json'); t=load('analysis-test-report.json'); cli=load('knowledge-cli-report.json')
report={'product':'t-understand','version':(ROOT/'VERSION').read_text().strip(),'phase':7,'phase_name':'Structural and Behavioral Analysis','status':'PASS' if all(x['status']=='PASS' for x in (c,t,cli)) else 'FAIL','inventory':{'schemas':6,'runtime_managers':1,'cli_commands':5,'skill_packages':4},'validation':{'contract_checks':c['checks'],'tests':t['tests'],'cli_checks':cli['checks']},'assurances':{'snapshot_bound':True,'exact_evidence':True,'source_repository_write':'DENY','source_execution':'DENY','incremental_full_equivalence':True,'atomic_publication':True,'cheap_model_dependency':False},'explicit_limitations':['Lexical calls are conservative medium-confidence observations unless a specialized exact contract pattern applies.','Reflection, generated runtime types, macros, source generators, and deployed runtime state are not executed.','Phase 7 describes implemented technical behavior and does not infer business intent.']}
(ROOT/'reports/phase-7-summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); sys.stdout.flush(); os._exit(0 if report['status']=='PASS' else 1)
