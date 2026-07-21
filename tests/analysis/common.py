from __future__ import annotations
import hashlib, json
from pathlib import Path
from tests.discovery.common import DiscoveryFixture, git
from tu_runtime.core.analysis import AnalysisManager
from tu_runtime.core.graph import GraphManager
from tu_runtime.core.memory import MemoryManager

PROJECT_ROOT=Path(__file__).resolve().parents[2]

def source_digest(root:Path)->str:
    h=hashlib.sha256()
    for path in sorted(x for x in root.rglob('*') if x.is_file() and '.git' not in x.parts):
        h.update(path.relative_to(root).as_posix().encode()); h.update(path.read_bytes())
    return h.hexdigest()

class KnowledgeFixture(DiscoveryFixture):
    def __init__(self):
        super().__init__(); self.analysis=AnalysisManager(PROJECT_ROOT,self.context); self.graph=GraphManager(PROJECT_ROOT,self.context); self.memory=MemoryManager(PROJECT_ROOT,self.context)
    def prepare(self,repos:dict[str,Path],suffix='A'):
        self.setup(repos)
        self.snapshots.create_snapshot(f'SNAP_{suffix}',{},'foundation')
        self.discovery.create(f'DISC_{suffix}',f'SNAP_{suffix}')
        self.adapters.run(f'EXT_{suffix}',f'DISC_{suffix}')
        return f'EXT_{suffix}'
    def semantic(self,analysis_id,name):
        values=[]
        for item in self.analysis._load_artifact(analysis_id,name):
            item={k:v for k,v in item.items() if k not in {'application_snapshot','captured_at','revision'}}
            values.append(json.dumps(item,sort_keys=True))
        return set(values)
