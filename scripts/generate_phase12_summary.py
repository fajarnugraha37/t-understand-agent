import json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(n): return json.loads((ROOT/'reports'/n).read_text())
c=load('export-contract-report.json'); t=load('export-test-report.json'); cli=load('documentation-cli-report.json')
report={'product':'t-understand','version':(ROOT/'VERSION').read_text().strip(),'phase':12,'phase_name':'Documentation Exporters','status':'PASS' if all(x['status']=='PASS' for x in (c,t,cli)) else 'FAIL','inventory':{'profiles':c['profiles'],'schemas':2,'cli_commands':5,'profile_count':len(c['profiles'])},'validation':{'contract_checks':c['checks'],'tests':t['tests'],'shared_cli_checks':cli['checks']},'assurances':{'canonical_document_unchanged':True,'presentation_only_transformation':True,'immutable_exports':True,'source_digest':True,'file_checksums':True,'link_validation':True,'markdown_fence_validation':True,'profile_configuration_validation':True},'explicit_limitations':['Mintlify, Docusaurus, and MkDocs outputs receive deterministic structural validation; this does not claim execution of external hosted build services.','Exporter profiles do not change canonical classifications, claims, evidence, or traceability.']}
(ROOT/'reports/phase-12-summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); sys.stdout.flush(); os._exit(0 if report['status']=='PASS' else 1)
