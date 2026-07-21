from __future__ import annotations
import unittest
from tests.analysis.common import KnowledgeFixture

class GraphTests(unittest.TestCase):
    def setUp(self): self.fx=KnowledgeFixture()
    def tearDown(self): self.fx.close()
    def _build(self,consumer=True):
        a=self.fx.make_repo('producer',{'src/A.java':'class A { @PostMapping("/orders") void x(){ kafkaTemplate.send("orders.created","x"); String q="insert into orders values(1)"; } }'})
        btext='subscribe({topic:"orders.created"}); function x(){ post("/orders"); const q="select * from orders"; }' if consumer else 'function x(){}'
        b=self.fx.make_repo('consumer',{'src/index.ts':btext})
        self.fx.prepare({'producer':a,'consumer':b}); self.fx.analysis.run('ANL_A','EXT_A'); return self.fx.graph.create('GRF_A','ANL_A')
    def test_exact_cross_repository_links(self):
        doc=self._build(); self.assertEqual(self.fx.graph.validate('GRF_A')['status'],'PASS')
        rels=self.fx.graph._load_artifact('GRF_A','cross_relations'); types={x['type'] for x in rels}
        self.assertTrue({'PRODUCES_FOR','CALLS','SHARES_DATA_WITH'} <= types)
        self.assertTrue(all(len(x['evidence'])>=2 for x in rels))
        self.assertTrue(all(x['source_repository']!=x['target_repository'] for x in rels))
    def test_one_sided_contract_remains_candidate(self):
        doc=self._build(False); self.assertGreater(doc['coverage']['unresolved_candidates'],0)
    def test_same_repository_is_not_cross_linked(self):
        repo=self.fx.make_repo('repo-a',{'src/A.java':'class A { void x(){ kafkaTemplate.send("t","x"); } @KafkaListener(topics="t") void y(){} }'})
        self.fx.prepare({'repo-a':repo}); self.fx.analysis.run('ANL_A','EXT_A'); doc=self.fx.graph.create('GRF_A','ANL_A'); self.assertEqual(doc['coverage']['cross_relations'],0)
    def test_ambiguous_http_providers_are_not_promoted(self):
        p1=self.fx.make_repo('provider-one',{'openapi.yaml':'openapi: 3.0.0\ninfo: {title: P1, version: "1"}\npaths:\n  /same:\n    get: {operationId: one}\n'})
        p2=self.fx.make_repo('provider-two',{'openapi.yaml':'openapi: 3.0.0\ninfo: {title: P2, version: "1"}\npaths:\n  /same:\n    get: {operationId: two}\n'})
        c=self.fx.make_repo('consumer',{'src/index.ts':'function x(){ get("/same"); }'})
        self.fx.prepare({'provider-one':p1,'provider-two':p2,'consumer':c}); self.fx.analysis.run('ANL_A','EXT_A'); doc=self.fx.graph.create('GRF_A','ANL_A')
        calls=[x for x in self.fx.graph._load_artifact('GRF_A','cross_relations') if x['type']=='CALLS' and x['contract_key']=='http:GET:/same']
        self.assertEqual(calls,[]); self.assertGreater(doc['coverage']['unresolved_candidates'],0)
    def test_tamper_is_detected(self):
        self._build(); p=self.fx.context/'graphs/GRF_A/cross-relations.jsonl'; p.write_text(p.read_text()+'{}\n'); self.assertEqual(self.fx.graph.validate('GRF_A')['status'],'FAIL')
if __name__=='__main__': unittest.main()
