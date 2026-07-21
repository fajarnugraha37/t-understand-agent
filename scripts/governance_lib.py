from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding='utf-8'))

def canonical_data():
    return {
        'agents': load_yaml('orchestrator/agent-registry.yaml'),
        'authority': load_yaml('orchestrator/authority-matrix.yaml'),
        'artifacts': load_yaml('orchestrator/artifact-registry.yaml'),
        'skills': load_yaml('orchestrator/skill-registry.yaml'),
        'workflows': load_yaml('orchestrator/workflow-registry.yaml'),
        'models': load_yaml('orchestrator/model-profiles.yaml'),
    }

def err(code, message, path=''):
    return {'code': code, 'message': message, 'path': path}

def audit(data=None):
    d = deepcopy(data or canonical_data())
    errors=[]; checks=0
    agents=d['agents']['agents']; roles=d['authority']['roles']; arts=d['artifacts']['artifacts']; skills=d['skills']['skills']; workflows=d['workflows']['workflows']
    agent_ids=[a['id'] for a in agents]; checks+=1
    if len(agent_ids)!=len(set(agent_ids)): errors.append(err('GOV-ID-001','Agent IDs must be unique','agent-registry'))
    if set(agent_ids)!=set(roles): errors.append(err('GOV-AUTH-001','Authority roles must exactly match agent registry','authority-matrix.roles'))
    checks+=1
    roots=[a for a in agents if a['kind']=='orchestrator']; workers=[a for a in agents if a['kind']=='worker']
    if [r['id'] for r in roots] != ['t-understand']: errors.append(err('GOV-ROOT-001','Exactly t-understand must be the sole orchestrator'))
    checks+=1
    for w in workers:
        checks+=1
        if w['can_delegate'] or w['max_delegation_depth'] != 0:
            errors.append(err('GOV-DELEGATE-001','Workers must be terminal and non-delegating',w['id']))
        if w['human_interaction']:
            errors.append(err('GOV-HUMAN-001','Workers may not interact with humans',w['id']))
    root=next(a for a in agents if a['id']=='t-understand'); checks+=1
    if not root['can_delegate'] or root['max_delegation_depth']!=1 or not root['human_interaction']:
        errors.append(err('GOV-ROOT-002','Root must be human-facing with delegation depth one','t-understand'))
    for rid,auth in roles.items():
        checks+=1
        if 'source_repository_write' not in auth['deny']:
            errors.append(err('GOV-SOURCE-001','Source repository write must be explicitly denied',rid))
        if rid!='t-understand' and 'workflow_state_transition' not in auth['deny']:
            errors.append(err('GOV-STATE-001','Workers must not transition workflow state',rid))
        if rid!='t-understand' and 'worker_delegation' not in auth['deny']:
            errors.append(err('GOV-DELEGATE-002','Workers must explicitly deny worker delegation',rid))
    checks+=1
    exclusive_authorities = {
        'canonical_memory_write': ['tu-memory-curator'],
        'model_artifact_write': ['tu-modeler'],
        'technical_document_write': ['tu-technical-writer'],
        'business_document_write': ['tu-business-writer'],
        'qna_answer_write': ['tu-answerer'],
        'review_finding_write': ['tu-reviewer'],
        'review_report_write': ['tu-reviewer'],
        'critique_artifact_write': ['tu-critic'],
        'verification_report_write': ['tu-verifier'],
        'workflow_state_transition': ['t-understand'],
        'record_human_decision': ['t-understand'],
    }
    for authority, expected in exclusive_authorities.items():
        checks += 1
        actual = [rid for rid, auth in roles.items() if authority in auth['allow']]
        if actual != expected:
            errors.append(err('GOV-EXCLUSIVE-001', f'Exclusive authority {authority} must belong only to {expected}', str(actual)))
    for rid, auth in roles.items():
        checks += 1
        if rid != 't-understand' and 'human_approval_fabrication' not in auth['deny']:
            errors.append(err('GOV-HUMAN-002','Workers must explicitly deny fabricated human approval',rid))
    checks+=1
    mem_writers=[rid for rid,a in roles.items() if 'canonical_memory_write' in a['allow']]
    if mem_writers!=['tu-memory-curator']:
        errors.append(err('GOV-MEMORY-001','tu-memory-curator must be the sole canonical memory writer',str(mem_writers)))
    checks+=1
    if 'apply_suggested_patch' not in roles['tu-reviewer']['deny']:
        errors.append(err('GOV-REVIEW-001','Reviewer must not apply suggested patches'))
    checks+=1
    artifact_ids=[a['id'] for a in arts]
    if len(artifact_ids)!=len(set(artifact_ids)): errors.append(err('GOV-ARTIFACT-001','Artifact IDs must be unique'))
    domain_authority = {
        'control': {'t-understand'}, 'approval': {'t-understand'},
        'discovery': {'tu-discoverer'}, 'snapshot': {'tu-discoverer'},
        'model': {'tu-modeler'}, 'memory': {'tu-memory-curator'},
        'critique': {'tu-critic'}, 'verification': {'tu-verifier'},
        'qna': {'tu-answerer'}, 'review': {'tu-reviewer'},
        'runtime': {'t-understand','assigned-worker'},
    }
    evidence_writers = {'tu-discoverer','tu-analyzer','tu-answerer'}
    documentation_writers = {'tu-technical-writer','tu-business-writer'}
    for a in arts:
        checks+=1
        writer=a['canonical_writer']
        if writer!='assigned-worker' and writer not in agent_ids:
            errors.append(err('GOV-ARTIFACT-002','Artifact writer must be registered',a['id']))
        if a.get('source_repository_write_required'):
            errors.append(err('GOV-ARTIFACT-003','No artifact may require source repository write',a['id']))
        allowed = evidence_writers if a['domain']=='evidence' else documentation_writers if a['domain']=='documentation' else domain_authority.get(a['domain'], set())
        if writer not in allowed:
            errors.append(err('GOV-ARTIFACT-004','Artifact writer is incompatible with artifact domain',f"{a['id']}:{writer}:{a['domain']}"))
    skill_ids=[s['id'] for s in skills]; checks+=1
    if len(skill_ids)!=len(set(skill_ids)): errors.append(err('GOV-SKILL-001','Skill IDs must be unique'))
    for s in skills:
        checks+=1
        if s['owner'] not in agent_ids: errors.append(err('GOV-SKILL-002','Skill owner must be registered',s['id']))
    workflow_ids=[w['id'] for w in workflows]; checks+=1
    if len(workflow_ids)!=len(set(workflow_ids)): errors.append(err('GOV-WORKFLOW-001','Workflow IDs must be unique'))
    for wf in workflows:
        state_ids=[s['id'] for s in wf['states']]
        checks+=1
        if wf['initial_state'] not in state_ids: errors.append(err('GOV-WORKFLOW-002','Initial state missing',wf['id']))
        for t in wf['terminal_states']:
            if t not in state_ids: errors.append(err('GOV-WORKFLOW-003','Terminal state missing',f"{wf['id']}:{t}"))
        for st in wf['states']:
            checks+=1
            if st['owner'] not in agent_ids: errors.append(err('GOV-STATE-002','State owner missing',f"{wf['id']}:{st['id']}"))
            if 'skill' in st and st['skill'] not in skill_ids: errors.append(err('GOV-STATE-003','State skill missing',f"{wf['id']}:{st['id']}"))
            for out in st.get('outputs',[]):
                if out not in artifact_ids: errors.append(err('GOV-STATE-004','State output artifact missing',f"{wf['id']}:{st['id']}:{out}"))
            for nxt in st.get('next_states',[]):
                if nxt not in state_ids: errors.append(err('GOV-STATE-005','Next state missing',f"{wf['id']}:{st['id']}:{nxt}"))
            if st.get('terminal') and st.get('next_states'): errors.append(err('GOV-STATE-006','Terminal state must not have next states',f"{wf['id']}:{st['id']}"))
    econ=d['models']['profiles']['economy']; checks+=8
    if econ['model']!='inherit': errors.append(err('GOV-ECON-001','Economy model must inherit'))
    if econ['flagship_required']: errors.append(err('GOV-ECON-002','Economy cannot require flagship'))
    if econ['parallelism'] is not False or econ['max_workers']!=1: errors.append(err('GOV-ECON-003','Economy must be sequential with one worker'))
    if econ['maximum_delegation_depth']!=1: errors.append(err('GOV-ECON-004','Economy depth must be one'))
    if not econ['structured_output_required'] or not econ['deterministic_verification_required']: errors.append(err('GOV-ECON-005','Economy requires structured output and deterministic verification'))
    if econ['silent_assumption']!='deny': errors.append(err('GOV-ECON-006','Economy must deny silent assumptions'))
    return {'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors}

def set_path(obj, path, value):
    parts=path.split('.')
    cur=obj
    for p in parts[:-1]:
        if p.isdigit(): cur=cur[int(p)]
        else: cur=cur[p]
    last=parts[-1]
    if last.isdigit(): cur[int(last)]=value
    else: cur[last]=value
