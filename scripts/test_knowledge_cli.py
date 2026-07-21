from __future__ import annotations
import argparse,contextlib,io,json,subprocess,sys,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]
from tu_runtime.cli import main
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/knowledge-cli-report.json')); args=p.parse_args()
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
def make_repo(base,name,files):
    source=base/name; source.mkdir(); git(source,'init','-q'); git(source,'config','user.email','knowledge@test'); git(source,'config','user.name','Knowledge CLI')
    for rel,content in files.items():
        target=source/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content,encoding='utf-8')
    git(source,'add','.'); git(source,'commit','-qm','init'); return source
with tempfile.TemporaryDirectory() as temp:
    base=Path(temp); context=base/'context'
    producer=make_repo(base,'producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }'})
    consumer=make_repo(base,'consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'})
    prefix=('--context-root',str(context))
    run(*prefix,'application-init','--application-id','cli-app','--name','CLI App','--workspace-model','multi-repo','--machine-id','machine-a')
    for rid,path in [('producer',producer),('consumer',consumer)]:
        run(*prefix,'repository-add','--repository-id',rid,'--name',rid,'--role','service','--identity-key',f'local/{rid}')
        run(*prefix,'workspace-bind','--repository-id',rid,'--path',str(path))
    run(*prefix,'snapshot-create','--snapshot-id','SNAP_CLI','--purpose','foundation')
    run(*prefix,'discovery-run','--discovery-id','DISC_CLI','--snapshot-id','SNAP_CLI')
    run(*prefix,'adapter-run','--extraction-id','EXT_CLI','--discovery-id','DISC_CLI')
    analysis=run(*prefix,'analysis-run','--analysis-id','ANL_CLI','--extraction-id','EXT_CLI')
    if analysis.get('status')!='ANALYZED': errors.append('analysis-run did not complete')
    if run(*prefix,'analysis-validate','--analysis-id','ANL_CLI').get('status')!='PASS': errors.append('analysis validation failed')
    graph=run(*prefix,'graph-create','--graph-id','GRF_CLI','--analysis-id','ANL_CLI')
    if graph.get('coverage',{}).get('cross_relations',0)<2: errors.append('graph did not produce expected cross-repository links')
    if run(*prefix,'graph-validate','--graph-id','GRF_CLI').get('status')!='PASS': errors.append('graph validation failed')
    memory=run(*prefix,'memory-build','--memory-id','MEM_CLI','--graph-id','GRF_CLI')
    if memory.get('status')!='CURRENT': errors.append('memory-build did not produce current memory')
    if run(*prefix,'memory-validate','--memory-id','MEM_CLI').get('status')!='PASS': errors.append('memory validation failed')
    if run(*prefix,'memory-critique','--memory-id','MEM_CLI').get('status')!='PASS': errors.append('memory critique failed')
    if run(*prefix,'memory-freshness','--memory-id','MEM_CLI','--snapshot-id','SNAP_CLI').get('status')!='CURRENT': errors.append('freshness assessment failed')
    if not run(*prefix,'memory-search','--memory-id','MEM_CLI','--query','orders').get('results'): errors.append('memory search returned no results')
    if not run(*prefix,'analysis-list').get('analyses'): errors.append('analysis list empty')
    if not run(*prefix,'graph-list').get('graphs'): errors.append('graph list empty')
    if not run(*prefix,'memory-list').get('versions'): errors.append('memory list empty')
    previous_workspace=os.environ.get('T_UNDERSTAND_WORKSPACE');os.environ['T_UNDERSTAND_WORKSPACE']=str(producer)
    try:
        boot=run('agent-bootstrap')
        if boot.get('managed_state')!=str(producer/'.t-understand'): errors.append('agent bootstrap did not select automatic knowledge context')
        if run('analysis-list').get('analyses')!=[]: errors.append('automatic analysis context should begin empty')
    finally:
        if previous_workspace is None: os.environ.pop('T_UNDERSTAND_WORKSPACE',None)
        else: os.environ['T_UNDERSTAND_WORKSPACE']=previous_workspace
report={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}
Path(args.report).write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); sys.stdout.flush(); sys.stderr.flush(); os._exit(0 if not errors else 1)
