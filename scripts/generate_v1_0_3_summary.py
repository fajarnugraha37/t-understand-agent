from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/'reports'/name).read_text())
reports={name:load(name) for name in ('agent-native-test-report.json','agent-native-cli-report.json','documentation-test-report.json','installation-contract-report.json','governance-report.json','negative-governance-report.json','release-contract-report.json')}
report={
 'product':'t-understand','version':'1.0.3','status':'PASS' if all(r.get('status')=='PASS' for r in reports.values()) else 'FAIL',
 'changes':{
  'capability_greeting':True,'substantive_task_overrides_greeting':True,'documentation_intent_precedence':True,
  'artifact_required_completion':True,'stable_documentation_output':'.t-understand/output/documentation/latest/',
  'chat_only_completion_denied':True,'private_reasoning_sanitation':True,'unexecuted_pass_claim_denied':True,
  'literal_prompt_regression':True,
 },
 'inventory':{'schemas':88,'skills':68,'canonical_artifacts':67,'private_cli_commands':111,'platform_adapters':4},
 'validation':reports,
 'limitations':['External host executables are structurally packaged but not invoked by this harness.','Repository builds and tests are not executed by documentation generation unless separately requested and evidenced.'],
}
(ROOT/'reports/v1.0.3-capability-documentation-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));raise SystemExit(0 if report['status']=='PASS' else 1)
