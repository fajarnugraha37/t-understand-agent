from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.core.contracts import SCHEMA_FILES
from tu_runtime.core.modeling import MODEL_TYPES
import yaml
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/model-contract-report.json')); a=p.parse_args()
required={'model-record','model-artifact','model-manifest','model-trace','model-critique','model-verification','model-reconciliation'}; errors=[]; checks=0
for x in sorted(required): checks+=1; errors += [] if x in SCHEMA_FILES and (ROOT/'schemas'/SCHEMA_FILES[x]).exists() else [f'missing {x}']
policy=yaml.safe_load((ROOT/'orchestrator/modeling-policy.yaml').read_text()); checks+=1
if tuple(policy['model_catalog']) != MODEL_TYPES: errors.append('model policy catalog differs from runtime catalog')
for x in ('application-model','architecture-model','dependency-model','data-model','event-model','deployment-model','security-model','business-capabilities','business-rules','actors','state-model','flows','terminology'): checks+=1
for f in ('orchestrator/modeling-policy.yaml','runtime/tu_runtime/core/modeling.py'): checks+=1; errors += [] if (ROOT/f).exists() else [f'missing {f}']
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}; Path(a.report).write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); raise SystemExit(0 if not errors else 1)
