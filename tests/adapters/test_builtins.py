from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from tu_runtime.adapters import AdapterContext, AdapterRegistry

ROOT=Path(__file__).resolve().parents[2]

SAMPLES={
 "java":("App.java","package a; import java.util.List; public class App { public static void main(String[] a) {} }"),
 "javascript-typescript":("app.ts","import x from 'x'; export function run(){}; router.get('/x', run);"),
 "python":("app.py","import os\ndef run(): pass\nif __name__ == '__main__': run()\n"),
 "go":("main.go","package main\nimport \"fmt\"\nfunc main(){fmt.Println(1)}\n"),
 "rust":("main.rs","use std::io;\nfn main() {}\nstruct App;\n"),
 "dotnet":("Program.cs","using System; public class Program { static void Main(){} }"),
 "sql":("001.sql","create table orders(id bigint); create view active_orders as select * from orders;"),
 "bpmn-dmn":("flow.bpmn","<definitions xmlns='x'><process id='p' name='Process'><startEvent id='s'/><serviceTask id='t' name='Work'/></process></definitions>"),
 "openapi-asyncapi":("openapi.yaml","openapi: 3.0.0\ninfo: {title: API, version: '1'}\npaths: {/x: {get: {operationId: x}}}\n"),
 "infrastructure":("Dockerfile","FROM alpine:3\nEXPOSE 8080\nENTRYPOINT [\"x\"]\n"),
 "generic":("README.md","# Heading\ntext\n"),
}

class BuiltinAdapterTests(unittest.TestCase):
    def setUp(self): self.registry=AdapterRegistry(ROOT)

    def test_all_declared_adapters_select_and_validate(self):
        for expected,(path,text) in SAMPLES.items():
            data=text.encode(); ctx=AdapterContext("EXTRACT_TEST","SNAP_TEST","repo-a",path,hashlib.sha256(data).hexdigest())
            result=self.registry.extract(ctx,data,text)
            self.assertEqual(result["adapter_id"],expected,path)
            self.assertIn(result["status"],{"COMPLETE","PARTIAL","UNSUPPORTED"})

    def test_capability_matrix_has_eleven_adapters(self):
        matrix=self.registry.capability_matrix("2026-07-21T00:00:00Z")
        self.assertEqual(len(matrix["adapters"]),11)
        self.assertEqual([x["id"] for x in matrix["adapters"]],sorted(x["id"] for x in matrix["adapters"]))

    def test_python_syntax_error_is_partial(self):
        data=b"def broken(:\n"; ctx=AdapterContext("EXTRACT_TEST","SNAP_TEST","repo-a","bad.py",hashlib.sha256(data).hexdigest())
        result=self.registry.extract(ctx,data,data.decode())
        self.assertEqual(result["status"],"PARTIAL")
        self.assertTrue(result["limitations"])

    def test_generic_fallback_is_explicit(self):
        data=b"plain text"; ctx=AdapterContext("EXTRACT_TEST","SNAP_TEST","repo-a","notes.txt",hashlib.sha256(data).hexdigest())
        result=self.registry.extract(ctx,data,data.decode())
        self.assertEqual(result["adapter_id"],"generic")
        self.assertEqual(result["status"],"UNSUPPORTED")

    def test_selection_is_deterministic(self):
        data=SAMPLES["openapi-asyncapi"][1].encode()
        first=self.registry.select("openapi.yaml",data,data.decode()).id
        second=self.registry.select("openapi.yaml",data,data.decode()).id
        self.assertEqual(first,second)
        self.assertEqual(first,"openapi-asyncapi")


    def _extract(self, path: str, text: str):
        data=text.encode(); ctx=AdapterContext("EXTRACT_TEST","SNAP_TEST","repo-a",path,hashlib.sha256(data).hexdigest())
        return self.registry.extract(ctx,data,text)

    def test_openapi_and_asyncapi_subtypes(self):
        openapi=self._extract("openapi.yaml","openapi: 3.0.0\ninfo: {title: API, version: '1'}\npaths: {/x: {get: {operationId: getX}}}\n")
        asyncapi=self._extract("asyncapi.yaml","asyncapi: 3.0.0\ninfo: {title: Events, version: '1'}\nchannels: {orders: {address: orders}}\n")
        self.assertEqual(openapi["language"],"openapi")
        self.assertEqual(asyncapi["language"],"asyncapi")
        self.assertTrue(openapi["interfaces"]); self.assertTrue(asyncapi["interfaces"])

    def test_bpmn_and_dmn_subtypes(self):
        bpmn=self._extract("flow.bpmn","<definitions xmlns='x'><process id='p'><serviceTask id='t' name='Work'/></process></definitions>")
        dmn=self._extract("rules.dmn","<definitions xmlns='x'><decision id='d' name='Eligibility'/></definitions>")
        self.assertEqual(bpmn["language"],"bpmn")
        self.assertEqual(dmn["language"],"dmn")
        self.assertTrue(dmn["declarations"])

    def test_infrastructure_docker_kubernetes_and_terraform(self):
        docker=self._extract("Dockerfile","FROM alpine:3\nEXPOSE 8080\n")
        kube=self._extract("deployment.yaml","apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: orders}\n")
        terraform=self._extract("main.tf",'resource "aws_s3_bucket" "orders" {}\n')
        self.assertEqual(docker["language"],"dockerfile")
        self.assertEqual(kube["language"],"kubernetes")
        self.assertEqual(terraform["language"],"terraform")

    def test_dotnet_language_subtypes(self):
        cs=self._extract("Program.cs","using System; class Program { static void Main(){} }")
        fs=self._extract("Program.fs","module Program\n[<EntryPoint>]\nlet main argv = 0\n")
        vb=self._extract("Program.vb","Imports System\nModule Program\nSub Main()\nEnd Sub\nEnd Module\n")
        self.assertEqual([cs["language"],fs["language"],vb["language"]],["csharp","fsharp","visual-basic"])

    def test_interface_candidates_across_code_adapters(self):
        java=self._extract("Orders.java",'@Path("/orders") public class Orders {}')
        js=self._extract("orders.ts",'router.post("/orders", createOrder);')
        py=self._extract("orders.py",'@app.get("/orders")\ndef orders(): pass\n')
        go=self._extract("orders.go",'package orders\nfunc init(){ http.HandleFunc("/orders", handler) }\n')
        rust=self._extract("orders.rs",'#[get("/orders")]\nfn orders() {}\n')
        dotnet=self._extract("Orders.cs",'[HttpGet("/orders")] public class Orders {}')
        for result in (java,js,py,go,rust,dotnet): self.assertTrue(result["interfaces"],result["adapter_id"])

if __name__ == '__main__': unittest.main()
