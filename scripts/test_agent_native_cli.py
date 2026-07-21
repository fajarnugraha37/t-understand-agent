from __future__ import annotations
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--report',default=str(ROOT/'reports/agent-native-cli-report.json'));args=parser.parse_args()
checks=[];errors=[]

def run(cwd:Path,*argv:str,input_text:str|None=None):
 env={**os.environ,'PYTHONPATH':str(ROOT/'runtime'),'T_UNDERSTAND_WORKSPACE':str(cwd)}
 cp=subprocess.run([sys.executable,'-m','tu_runtime.cli',*argv],cwd=cwd,env=env,text=True,input=input_text,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 return cp

with tempfile.TemporaryDirectory() as td:
 base=Path(td); repo=base/'repo';repo.mkdir()
 subprocess.run(['git','-C',str(repo),'init','-q'],check=True);subprocess.run(['git','-C',str(repo),'config','user.email','test@example.com'],check=True);subprocess.run(['git','-C',str(repo),'config','user.name','Test'],check=True)
 (repo/'src').mkdir();(repo/'src/index.ts').write_text('export const value = 1;\n');(repo/'README.md').write_text('# Repo\n');(repo/'package.json').write_text('{"name":"repo"}\n')
 subprocess.run(['git','-C',str(repo),'add','.'],check=True);subprocess.run(['git','-C',str(repo),'commit','-qm','init'],check=True)
 cp=run(repo,'agent-plan','--prompt','hi');checks.append('greeting-plan');
 if cp.returncode or json.loads(cp.stdout).get('intent')!='GREETING':errors.append(f'greeting plan failed {cp.stderr}')
 literal='Understand this repository deeply, precisely and write comprehensive, detailed, deep, sensible documentation'
 cp=run(repo,'agent-plan','--prompt',literal);checks.append('documentation-plan');d=json.loads(cp.stdout) if cp.returncode==0 else {}
 if cp.returncode or d.get('intent')!='DOCUMENTATION_GENERATION' or not d.get('artifact_required'):errors.append(f'documentation plan failed {cp.stderr}')
 cp=run(repo,'agent-document','--prompt',literal);checks.append('documentation-run');completion=json.loads(cp.stdout) if cp.returncode==0 else {}
 if cp.returncode or completion.get('status')!='PASS' or completion.get('documents',0)<5:errors.append(f'documentation run failed {cp.stderr}')
 latest=repo/'.t-understand/output/documentation/latest';checks.append('stable-output')
 if not (latest/'index.md').is_file() or not (latest/'_meta/manifest.yaml').is_file():errors.append('stable documentation output missing')
 response=base/'response.txt';response.write_text(completion.get('chat_response',''))
 cp=run(repo,'agent-response-validate','--prompt',literal,'--response-file',str(response));checks.append('response-validation')
 if cp.returncode or json.loads(cp.stdout).get('status')!='PASS':errors.append(f'response validation failed {cp.stderr}')
 bad=base/'bad.txt';bad.write_text('# Todos\nThought: secret\n')
 cp=run(repo,'agent-response-validate','--prompt',literal,'--response-file',str(bad));checks.append('leakage-rejection')
 if cp.returncode==0:errors.append('private reasoning leakage was accepted')
report={'status':'PASS' if not errors else 'FAIL','checks':len(checks),'check_names':checks,'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if not errors else 1)
