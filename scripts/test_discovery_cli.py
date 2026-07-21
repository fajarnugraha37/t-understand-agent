from __future__ import annotations
import argparse, sys,contextlib,io,json,subprocess,sys,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.cli import main
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/discovery-cli-report.json')); args=p.parse_args()
checks=0; errors=[]
def run(*values,expect=0):
    global checks
    out=io.StringIO(); err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err): code=main(list(values))
    checks+=1
    if code!=expect: errors.append(f"{' '.join(values)} returned {code}, expected {expect}: {err.getvalue()}")
    text=out.getvalue().strip() or err.getvalue().strip()
    try:return json.loads(text)
    except Exception: errors.append(f'non-json output: {text}'); return {}
def git(path,*values): subprocess.run(['git','-C',str(path),*values],check=True,capture_output=True,text=True)
with tempfile.TemporaryDirectory() as temp:
    base=Path(temp); context=base/'context'; source=base/'source'; source.mkdir()
    git(source,'init','-q'); git(source,'config','user.email','cli@test'); git(source,'config','user.name','CLI')
    (source/'app.py').write_text("def main(): pass\n",encoding='utf-8'); (source/'openapi.yaml').write_text("openapi: 3.0.0\ninfo: {title: X, version: '1'}\npaths: {}\n")
    git(source,'add','.'); git(source,'commit','-qm','init')
    prefix=('--context-root',str(context))
    run(*prefix,'application-init','--application-id','cli-app','--name','CLI App','--workspace-model','single-repo','--machine-id','machine-a')
    run(*prefix,'repository-add','--repository-id','repo-a','--name','Repo A','--role','backend','--identity-key','local/repo-a')
    run(*prefix,'workspace-bind','--repository-id','repo-a','--path',str(source))
    run(*prefix,'snapshot-create','--snapshot-id','SNAP_CLI','--purpose','foundation')
    disc=run(*prefix,'discovery-run','--discovery-id','DISC_CLI','--snapshot-id','SNAP_CLI')
    if disc.get('status')!='DISCOVERED': errors.append('discovery-run did not complete')
    if run(*prefix,'discovery-validate','--discovery-id','DISC_CLI').get('status')!='PASS': errors.append('discovery validation failed')
    ext=run(*prefix,'adapter-run','--extraction-id','EXTRACT_CLI','--discovery-id','DISC_CLI')
    if ext.get('status')!='EXTRACTED': errors.append('adapter-run did not complete')
    if run(*prefix,'adapter-validate','--extraction-id','EXTRACT_CLI').get('status')!='PASS': errors.append('adapter validation failed')
    caps=run(*prefix,'adapter-capabilities')
    if len(caps.get('adapters',[]))!=11: errors.append('adapter capability matrix count mismatch')
    previous_workspace=os.environ.get('T_UNDERSTAND_WORKSPACE');os.environ['T_UNDERSTAND_WORKSPACE']=str(source)
    try:
        boot=run('agent-bootstrap')
        if boot.get('managed_state')!=str(source/'.t-understand'): errors.append('agent bootstrap did not select automatic discovery context')
        if run('discovery-list').get('discoveries')!=[]: errors.append('automatic discovery context should begin empty')
    finally:
        if previous_workspace is None: os.environ.pop('T_UNDERSTAND_WORKSPACE',None)
        else: os.environ['T_UNDERSTAND_WORKSPACE']=previous_workspace
report={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); import os
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if not errors else 1)
