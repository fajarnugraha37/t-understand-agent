from __future__ import annotations
import argparse,contextlib,io,json,sys,os,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'runtime'),str(ROOT)]; warnings.simplefilter('ignore',ResourceWarning)
from tests.analysis.common import KnowledgeFixture
from tu_runtime.cli import main
p=argparse.ArgumentParser(); p.add_argument('--report',default=str(ROOT/'reports/documentation-cli-report.json')); a=p.parse_args(); checks=[]; errors=[]
fx=KnowledgeFixture()
def run(*args,ok=0):
    out=io.StringIO(); err=io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err): code=main(list(args))
    checks.append({'command':' '.join(args),'returncode':code})
    if code!=ok: errors.append({'command':args,'stdout':out.getvalue(),'stderr':err.getvalue(),'expected':ok,'actual':code})
    return out.getvalue()
try:
    r1=fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); } }'})
    r2=fx.make_repo('consumer',{'src/index.ts':'subscribe({topic:"orders.created"}); function x(){ post("/orders"); }'})
    fx.prepare({'producer':r1,'consumer':r2}); fx.analysis.run('ANL_A','EXT_A'); fx.graph.create('GRF_A','ANL_A'); fx.memory.build('MEM_A','GRF_A')
    base=['--context-root',str(fx.context)]
    run(*base,'model-build','--model-id','MODEL_A','--memory-id','MEM_A')
    run(*base,'model-validate','--model-id','MODEL_A')
    run(*base,'model-critique','--model-id','MODEL_A')
    run(*base,'model-artifact','--model-id','MODEL_A','--name','business-rules')
    run(*base,'model-reconcile','--reconciliation-id','RECON_A','--model-id','MODEL_B','--base-model-id','MODEL_A','--memory-id','MEM_A')
    run(*base,'documentation-generate','--docset-id','DOCS_A','--model-id','MODEL_A')
    run(*base,'documentation-validate','--docset-id','DOCS_A')
    run(*base,'documentation-critique','--docset-id','DOCS_A')
    run(*base,'export-create','--export-id','EXPORT_A','--docset-id','DOCS_A','--profile','mintlify-mdx')
    run(*base,'export-validate','--export-id','EXPORT_A')
    run('export-profiles')
    old_workspace=os.environ.get('T_UNDERSTAND_WORKSPACE')
    os.environ['T_UNDERSTAND_WORKSPACE']=str(r1)
    try:
        run('agent-bootstrap')
        out=run('model-list')
        if json.loads(out).get('versions') != []:
            errors.append({'command':['model-list'],'reason':'auto context should begin with no models','stdout':out})
    finally:
        if old_workspace is None: os.environ.pop('T_UNDERSTAND_WORKSPACE',None)
        else: os.environ['T_UNDERSTAND_WORKSPACE']=old_workspace
finally: fx.close()
r={'status':'PASS' if not errors else 'FAIL','checks':len(checks),'errors':errors,'commands':checks}; Path(a.report).write_text(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2)); sys.stdout.flush(); os._exit(0 if not errors else 1)
