import argparse,json,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--report',default='reports/final-cli-report.json');a=p.parse_args();ROOT=Path(__file__).resolve().parents[1];cli=ROOT/'bin/t-understand';checks=[]
def run(args,ok=True,timeout=60,cwd=None):
 r=subprocess.run([str(cli),*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,cwd=cwd);checks.append({'args':args,'returncode':r.returncode});
 if ok and r.returncode!=0:raise RuntimeError(r.stderr)
 if not ok and r.returncode==0:raise RuntimeError('expected failure')
 return r
with tempfile.TemporaryDirectory() as td:
 root=Path(td);c=root/'installer-state';c.mkdir();target=root/'opencode';workspace=root/'workspace';workspace.mkdir();subprocess.run(['git','-C',str(workspace),'init','-q'],check=True)
 run(['--context-root',str(c),'qualification-matrix'])
 run(['--context-root',str(c),'platforms'])
 run(['integration-matrix'])
 run(['agent-bootstrap'],cwd=workspace)
 if not (workspace/'.t-understand/application.yaml').is_file():raise RuntimeError('agent bootstrap did not create managed workspace state')
 run(['--context-root',str(c),'platform-install','--platform','opencode','--target-root',str(target)],timeout=120)
 # An identical healthy install is idempotent.
 run(['--context-root',str(c),'platform-install','--platform','opencode','--target-root',str(target)],timeout=120)
 (target/'AGENTS.md').write_text('tampered')
 run(['--context-root',str(c),'platform-install','--platform','opencode','--target-root',str(target)],False,timeout=120)
 run(['--context-root',str(c),'platform-install','--platform','opencode','--target-root',str(target),'--force'],timeout=120)
 run(['--context-root',str(c),'platform-doctor','--platform','opencode','--target-root',str(target)])
 run(['--context-root',str(c),'platform-uninstall','--platform','opencode','--target-root',str(target)])
r={'status':'PASS','checks':len(checks),'cases':checks};Path(a.report).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
