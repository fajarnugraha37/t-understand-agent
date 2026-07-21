from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.core.contracts import SCHEMA_FILES
from tu_runtime.core.documentation import DOCUMENT_CATALOG
import yaml
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/documentation-contract-report.json')); a=p.parse_args(); errors=[]; checks=0
for x in ('documentation-section','documentation-manifest','document-plan','documentation-trace','coverage-ledger','documentation-critique','documentation-verification','document-invalidation'):
 checks+=1; errors += [] if x in SCHEMA_FILES else [f'missing {x}']
paths=[x[1] for x in DOCUMENT_CATALOG]; checks+=len(paths)
template=yaml.safe_load((ROOT/'templates/documentation/catalog.yaml').read_text()); checks+=1
tuple_catalog=tuple((x['id'],x['path'],x['audience'],x['source_models']) for x in template['documents'])
if tuple_catalog != DOCUMENT_CATALOG: errors.append('documentation template catalog differs from runtime catalog')
if len(paths)!=len(set(paths)): errors.append('duplicate catalog paths')
for f in ('orchestrator/documentation-generation-policy.yaml','runtime/tu_runtime/core/documentation.py','runtime/tu_runtime/core/conversation.py','orchestrator/capabilities.yaml'):
 checks+=1; errors += [] if (ROOT/f).exists() else [f'missing {f}']
policy=(ROOT/'orchestrator/documentation-generation-policy.yaml').read_text();runtime=(ROOT/'runtime/tu_runtime/core/documentation.py').read_text();conversation=(ROOT/'runtime/tu_runtime/core/conversation.py').read_text()
for expected,source in (
 ('chat_only_completion: deny',policy),('.t-understand/output/documentation/latest/',policy),('validate_user_view',runtime),('_publish_user_view',runtime),('DOCUMENTATION_GENERATION',conversation),('generate_documentation',conversation),('validate_response',conversation)):
 checks+=1
 if expected not in source:errors.append(f'missing artifact-first documentation contract: {expected}')
r={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'catalog_documents':len(paths)}; Path(a.report).write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); raise SystemExit(0 if not errors else 1)
