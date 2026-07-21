import argparse, json, yaml
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(); p.add_argument('--report',default='reports/economy-contract-report.json'); args=p.parse_args()
m=yaml.safe_load((root/'orchestrator/model-profiles.yaml').read_text()); e=m['profiles']['economy']
checks={
 'model_inherited':e['model']=='inherit',
 'no_flagship_dependency':e['flagship_required'] is False,
 'sequential':e['parallelism'] is False and e['max_workers']==1,
 'depth_one':e['maximum_delegation_depth']==1,
 'evidence_slices':e['context_strategy']=='evidence-slices',
 'single_objective':e['one_primary_objective'] is True,
 'structured_output':e['structured_output_required'] is True,
 'deterministic_verification':e['deterministic_verification_required'] is True,
 'silent_assumption_denied':e['silent_assumption']=='deny',
 'material_critique':all(x in e['critic_required_for'] for x in ['system-model','technical-document','business-document','qna-answer','major-review-finding'])
}
status='PASS' if all(checks.values()) else 'FAIL'; out={'status':status,'checks':checks}
Path(args.report).parent.mkdir(parents=True,exist_ok=True); Path(args.report).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2)); raise SystemExit(0 if status=='PASS' else 1)
