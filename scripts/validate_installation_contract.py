import argparse,json,yaml
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--report',default='reports/installation-contract-report.json')
args=parser.parse_args()
errors=[]
checks=0
schema=json.loads((ROOT/'schemas/platform-adapter.schema.json').read_text())
validator=Draft202012Validator(schema)

for adapter_id in ('opencode','codex','claude-code','cursor'):
    document=yaml.safe_load((ROOT/f'adapters/{adapter_id}/adapter.yaml').read_text())
    checks+=1
    for error in validator.iter_errors(document):
        errors.append(f'{adapter_id}: {error.message}')

for skill in ROOT.joinpath('skills').rglob('SKILL.md'):
    checks+=2
    text=skill.read_text()
    if not skill.parent.name.startswith('tu-'):
        errors.append(f'non-namespaced skill directory {skill.parent.name}')
    if not text.startswith('---\n') or f'name: {skill.parent.name}\n' not in text:
        errors.append(f'invalid skill frontmatter {skill}')
    if skill.name!='SKILL.md':
        errors.append(f'invalid skill casing {skill}')

aggregate=ROOT/'adapters/codex/tu-understand/SKILL.md'
checks+=3
if not aggregate.exists():
    errors.append('missing Codex aggregate tu-understand skill')
else:
    if 'name: tu-understand\n' not in aggregate.read_text():
        errors.append('Codex aggregate skill is not tu-understand')
if (ROOT/'adapters/codex/t-understand').exists():
    errors.append('legacy non-namespaced Codex skill remains')

policy=ROOT/'orchestrator/tool-permission-policy.yaml'
checks+=1
if not policy.exists():
    errors.append('missing canonical tool permission policy')
else:
    data=yaml.safe_load(policy.read_text())
    requirements=' '.join(item['requirement'] for item in data.get('rules',[]))
    for expected in (
        'without per-action approval prompts',
        'GitHub CLI commands are denied',
        'read-only inspection commands',
        'fails closed',
    ):
        checks+=1
        if expected not in requirements:
            errors.append(f'missing permission requirement: {expected}')

source=(ROOT/'runtime/tu_runtime/core/installation.py').read_text()
for required in (
    'approval_policy = "never"',
    'sandbox_mode = "workspace-write"',
    'external_directory',
    'settings.json',
    'cli-config.json',
    'skills/tu-understand',
):
    checks+=1
    if required not in source:
        errors.append(f'installation runtime missing {required}')

for script in ('install.sh','doctor.sh','uninstall.sh','install.ps1','doctor.ps1','uninstall.ps1'):
    checks+=1
    if not (ROOT/'bin'/script).exists():
        errors.append(f'missing {script}')

install_ps=(ROOT/'bin/install.ps1').read_text()
install_sh=(ROOT/'bin/install.sh').read_text()
for expected in ('[string]$Target','[switch]$Force',"platform-install','--platform',$Target"):
    checks+=1
    if expected not in install_ps:errors.append(f'PowerShell installer missing {expected}')
checks+=1
if 'ContextRoot' in install_ps:errors.append('PowerShell installer still exposes ContextRoot')
for expected in ('[--force]','platform-install --platform'):
    checks+=1
    if expected not in install_sh:errors.append(f'shell installer missing {expected}')
checks+=1
if 'CONTEXT_ROOT' in install_sh:errors.append('shell installer still exposes CONTEXT_ROOT')

root_agent=(ROOT/'agents/t-understand/AGENT.md').read_text()
for expected in ('Human interaction contract','Never require the human','<workspace>/.t-understand/','Generate stable operation IDs automatically'):
    checks+=1
    if expected not in root_agent:errors.append(f'root agent missing agent-native rule: {expected}')

engine_source=(ROOT/'runtime/tu_runtime/core/installation.py').read_text()
for expected in ('def install_platform(', 't-understand-engine/agent_runtime.py', 'rerun with Force to replace it'):
    checks+=1
    if expected not in engine_source:errors.append(f'installer runtime missing {expected}')

result={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}
Path(args.report).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if not errors else 1)
