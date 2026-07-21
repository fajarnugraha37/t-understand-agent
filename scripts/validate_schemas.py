from pathlib import Path
import json, yaml
from jsonschema import Draft202012Validator
root=Path(__file__).resolve().parents[1]
schema_count=0
for p in sorted((root/'schemas').glob('*.schema.json')):
    obj=json.loads(p.read_text())
    Draft202012Validator.check_schema(obj)
    if not obj.get('$id','').startswith('https://t-understand.dev/schemas/'):
        raise SystemExit(f'invalid schema id: {p}')
    schema_count+=1
validations=[]
def validate(instance_path,schema_path):
    instance=yaml.safe_load((root/instance_path).read_text()) if instance_path.suffix in ['.yaml','.yml'] else json.loads((root/instance_path).read_text())
    schema=json.loads((root/schema_path).read_text())
    errors=list(Draft202012Validator(schema).iter_errors(instance))
    validations.append({'instance':str(instance_path),'schema':str(schema_path),'errors':[e.message for e in errors]})
for inst,sch in [
 (Path('orchestrator/agent-registry.yaml'),Path('schemas/agent-registry.schema.json')),
 (Path('orchestrator/authority-matrix.yaml'),Path('schemas/authority-matrix.schema.json')),
 (Path('orchestrator/artifact-registry.yaml'),Path('schemas/artifact-registry.schema.json')),
 (Path('orchestrator/workflow-registry.yaml'),Path('schemas/workflow-registry.schema.json')),
]: validate(inst,sch)
for agent in sorted((root/'agents').glob('*/agent.yaml')):
    validate(agent.relative_to(root),Path('schemas/agent-manifest.schema.json'))
for adapter in sorted((root/'language-adapters').glob('*/adapter.yaml')):
    validate(adapter.relative_to(root),Path('schemas/adapter-manifest.schema.json'))
for inst,sch in [
 (Path('examples/application/application.yaml'),Path('schemas/application-manifest.schema.json')),
 (Path('examples/application/workspace.local.yaml'),Path('schemas/workspace-map.schema.json')),
 (Path('examples/application/workspace-resolution.yaml'),Path('schemas/workspace-resolution.schema.json')),
 (Path('examples/snapshot/repository-snapshot.yaml'),Path('schemas/repository-snapshot.schema.json')),
 (Path('examples/snapshot/application-snapshot.yaml'),Path('schemas/application-snapshot.schema.json')),
 (Path('examples/snapshot/snapshot-validation-report.yaml'),Path('schemas/snapshot-validation-report.schema.json')),
 (Path('examples/snapshot/snapshot-drift-report.yaml'),Path('schemas/snapshot-drift-report.schema.json')),
 (Path('examples/snapshot/review-target.yaml'),Path('schemas/review-target.schema.json')),
 (Path('examples/discovery/file-inventory-record.yaml'),Path('schemas/file-inventory-record.schema.json')),
 (Path('examples/discovery/repository-discovery.yaml'),Path('schemas/repository-discovery.schema.json')),
 (Path('examples/discovery/application-discovery.yaml'),Path('schemas/application-discovery.schema.json')),
 (Path('examples/adapters/adapter-extraction.yaml'),Path('schemas/adapter-extraction.schema.json')),
 (Path('examples/adapters/adapter-run.yaml'),Path('schemas/adapter-run.schema.json')),
 (Path('examples/adapters/capability-matrix.yaml'),Path('schemas/adapter-capability-matrix.schema.json')),
]: validate(inst,sch)
failed=[v for v in validations if v['errors']]
out={'status':'PASS' if not failed else 'FAIL','schemas':schema_count,'instances_validated':len(validations),'failures':failed}
print(json.dumps(out,indent=2))
raise SystemExit(0 if not failed else 1)
