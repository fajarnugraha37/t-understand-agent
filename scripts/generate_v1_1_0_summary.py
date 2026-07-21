from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name): return json.loads((ROOT/'reports'/name).read_text())
report_names=(
 'agent-native-test-report.json','agent-native-cli-report.json','model-test-report.json',
 'documentation-test-report.json','documentation-contract-report.json','installation-contract-report.json',
 'governance-report.json','negative-test-report.json','release-contract-report.json',
)
reports={name:load(name) for name in report_names}
report={
 'product':'t-understand','version':'1.1.0','status':'PASS' if all(r.get('status')=='PASS' for r in reports.values()) else 'FAIL',
 'changes':{
  'agent_native_multi_repository_discovery':True,
  'application_root_managed_state':True,
  'adaptive_requirements_driven_documentation':True,
  'mandatory_base_documents':41,
  'per_repository_documentation':True,
  'tier_1_deep_flow_documentation':True,
  'tier_2_standard_flow_documentation':True,
  'tier_3_catalog_coverage':True,
  'deep_business_modeling':True,
  'deep_domain_modeling':True,
  'multi_perspective_application_flows':True,
  'explicit_unknown_over_fabrication':True,
  'all_coverage_metrics_required_at_one':True,
 },
 'validation':reports,
 'limitations':[
  'Business goals, organizational ownership, and runtime behavior remain unknown unless authoritative evidence exists.',
  'External OpenCode, Codex, Claude Code, and Cursor executables are not invoked by the provider-neutral release harness.',
  'Repository builds and tests are not executed by documentation generation unless separately requested and evidenced.',
 ],
}
(ROOT/'reports/v1.1.0-multi-repo-deep-documentation-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2)); raise SystemExit(0 if report['status']=='PASS' else 1)
