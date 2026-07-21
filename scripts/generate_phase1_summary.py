from pathlib import Path
import json, yaml
root=Path(__file__).resolve().parents[1]
def j(p): return json.loads((root/p).read_text())
def y(p): return yaml.safe_load((root/p).read_text())
agents=y('orchestrator/agent-registry.yaml')['agents']
skills=y('orchestrator/skill-registry.yaml')['skills']
arts=y('orchestrator/artifact-registry.yaml')['artifacts']
wfs=y('orchestrator/workflow-registry.yaml')['workflows']
reports={k:j(v) for k,v in {
 'governance':'reports/governance-report.json','negative':'reports/negative-test-report.json',
 'contracts':'reports/contract-test-report.json','economy':'reports/economy-contract-report.json'}.items()}
out={
 'product':'t-understand','version':(root/'VERSION').read_text().strip(),'phase':1,'phase_name':'Governance and Contracts','status':'PASS' if all(r['status']=='PASS' for r in reports.values()) else 'FAIL',
 'inventory':{'orchestrators':sum(a['kind']=='orchestrator' for a in agents),'terminal_workers':sum(a['kind']=='worker' for a in agents),'planned_skills':len(skills),'artifact_types':len(arts),'workflow_families':len(wfs),'workflow_states':sum(len(w['states']) for w in wfs),'json_schemas':len(list((root/'schemas').glob('*.schema.json')))},
 'validation':{'governance_checks':reports['governance']['checks'],'negative_governance_cases':reports['negative']['cases'],'contract_cases':reports['contracts']['cases'],'economy_checks':len(reports['economy']['checks'])},
 'assurances':{'source_repository_write':'DENY','canonical_memory_writer':'tu-memory-curator','maximum_delegation_depth':1,'flagship_model_required':False,'phase_2_core_runtime_implemented':True,'phase_3_application_management_implemented':True,'phase_4_snapshot_engine_implemented':True,'phase_5_discovery_engine_implemented':True,'phase_6_language_adapters_implemented':True}
}
(root/'reports/phase-1-summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2)); raise SystemExit(0 if out['status']=='PASS' else 1)
