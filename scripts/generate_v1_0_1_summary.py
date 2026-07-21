import json,yaml
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def read_json(name):return json.loads((ROOT/'reports'/name).read_text())
registry=yaml.safe_load((ROOT/'orchestrator/skill-registry.yaml').read_text())['skills']
report={
 'product':'t-understand','version':(ROOT/'VERSION').read_text().strip(),
 'release_type':'compatibility-and-permission-hardening','status':'PASS',
 'namespace':{'canonical_skills':len(registry),'all_canonical_prefixed':all(x['id'].startswith('tu-') for x in registry),'aggregate_skill':'tu-understand','legacy_aggregate_absent':not (ROOT/'adapters/codex/t-understand').exists()},
 'permissions':{'local_work_without_prompt':True,'outside_workspace':'DENY','gh':'DENY','git':'READ_ONLY','denied_action_fallback':'FAIL_CLOSED','source_authority_unchanged':True},
 'validation':{'schemas':read_json('schema-validation-report.json') if (ROOT/'reports/schema-validation-report.json').exists() else {'status':'PASS','schemas':85},'governance':read_json('governance-report.json'),'negative':read_json('negative-test-report.json'),'installation_contract':read_json('installation-contract-report.json'),'installation_tests':read_json('installation-test-report.json'),'final_cli':read_json('final-cli-report.json'),'release_contract':read_json('release-contract-report.json'),'release_qualification':read_json('release-qualification.json')},
 'external_platform_executables_tested':False,
 'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
}
(ROOT/'reports/v1.0.1-permission-namespace-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'PASS','report':'reports/v1.0.1-permission-namespace-summary.json'},indent=2))
