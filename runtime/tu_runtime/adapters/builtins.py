from __future__ import annotations

import ast
import json
import re
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from typing import Any

import yaml

from .base import AdapterContext, BaseAdapter, item, line_number


def _matches(pattern: str, text: str) -> list[re.Match[str]]:
    return list(re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE))


class GenericAdapter(BaseAdapter):
    id = "generic"
    language = None

    def detect(self, path: PurePosixPath, data: bytes, text: str | None) -> int:
        return 1 if text is not None else 0

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        if text is None:
            return self.result(context, "SKIPPED", [], [], [], [], [], ["Binary content is not parsed by the generic adapter."])
        headings = []
        for match in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
            headings.append(item("heading", match.group(2).strip(), line_number(text, match.start())))
        status = "PARTIAL" if headings else "UNSUPPORTED"
        limitations = ["Generic fallback records only obvious text headings; language semantics are not inferred."]
        return self.result(context, status, headings, [], [], [], [], limitations, "text")


class JavaAdapter(BaseAdapter):
    id = "java"
    language = "java"

    def detect(self, path: PurePosixPath, data: bytes, text: str | None) -> int:
        return 100 if path.suffix.lower() == ".java" and text is not None else 0

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        if text is None:
            return self.result(context, "SKIPPED", [], [], [], [], [], ["Java source was not decodable as text."])
        declarations=[]; dependencies=[]; interfaces=[]; configs=[]; entries=[]
        for m in _matches(r"^\s*package\s+([\w.]+)\s*;", text): declarations.append(item("package",m.group(1),line_number(text,m.start())))
        for m in _matches(r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", text): dependencies.append(item("import",m.group(1),line_number(text,m.start())))
        for m in _matches(r"\b(class|interface|enum|record|@interface)\s+([A-Za-z_$][\w$]*)", text): declarations.append(item(m.group(1).lower().replace('@','annotation'),m.group(2),line_number(text,m.start())))
        method_re=r"^[ \t]*(?:public|protected|private|static|final|synchronized|abstract|native|default|strictfp|\s)+[\w<>,.?\[\] @]+\s+([A-Za-z_$][\w$]*)\s*\(([^;{}]*)\)\s*(?:throws\s+[^\{]+)?\{"
        for m in _matches(method_re,text): declarations.append(item("method",m.group(1),line_number(text,m.start()),m.group(2).strip()))
        annotations=[]
        for m in _matches(r"@(Path|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*(?:\(([^)]*)\))?", text):
            name=m.group(1); detail=(m.group(2) or '').strip(); interfaces.append(item("http-mapping",name,line_number(text,m.start()),detail)); annotations.append(name)
        for m in _matches(r"@(?:Value|ConfigProperty)\s*\(\s*(?:name\s*=\s*)?[\"']([^\"']+)", text): configs.append(item("configuration-key",m.group(1),line_number(text,m.start())))
        for m in _matches(r"public\s+static\s+void\s+main\s*\(", text): entries.append(item("main",context.path,line_number(text,m.start())))
        limitations=["Regex surface extraction does not resolve overloads, generics, inherited annotations, generated code, or runtime framework registration."]
        return self.result(context,"COMPLETE",declarations,dependencies,interfaces,configs,entries,limitations)


class JavaScriptTypeScriptAdapter(BaseAdapter):
    id = "javascript-typescript"

    def detect(self, path: PurePosixPath, data: bytes, text: str | None) -> int:
        return 100 if path.suffix.lower() in {".js",".jsx",".mjs",".cjs",".ts",".tsx"} and text is not None else 0

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        if text is None: return self.result(context,"SKIPPED",[],[],[],[],[],["Source was not decodable as text."])
        language="typescript" if PurePosixPath(context.path).suffix.lower() in {".ts",".tsx"} else "javascript"
        declarations=[]; dependencies=[]; interfaces=[]; configs=[]; entries=[]
        for m in _matches(r"(?:import\s+(?:[^;]+?\s+from\s+)?|require\s*\()\s*[\"']([^\"']+)",text): dependencies.append(item("import",m.group(1),line_number(text,m.start())))
        for m in _matches(r"\b(?:export\s+)?(?:default\s+)?(class|interface|type|enum|function)\s+([A-Za-z_$][\w$]*)",text): declarations.append(item(m.group(1).lower(),m.group(2),line_number(text,m.start())))
        for m in _matches(r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",text): declarations.append(item("function",m.group(1),line_number(text,m.start())))
        for m in _matches(r"\b(?:app|router)\.(get|post|put|patch|delete|use)\s*\(\s*[\"']([^\"']+)",text): interfaces.append(item("http-route",m.group(2),line_number(text,m.start()),m.group(1).upper()))
        for m in _matches(r"\bprocess\.env\.([A-Z][A-Z0-9_]*)|\bprocess\.env\[['\"]([^'\"]+)",text): configs.append(item("environment-variable",m.group(1) or m.group(2),line_number(text,m.start())))
        if re.search(r"\b(?:main\s*\(|require\.main\s*===\s*module|import\.meta\.main)",text): entries.append(item("entry-point",context.path,1))
        limitations=["Surface extraction does not execute decorators, dynamic imports, framework plugins, metaprogramming, or route composition."]
        return self.result(context,"COMPLETE",declarations,dependencies,interfaces,configs,entries,limitations,language)


class PythonAdapter(BaseAdapter):
    id = "python"
    language = "python"

    def detect(self, path: PurePosixPath, data: bytes, text: str | None) -> int:
        return 100 if path.suffix.lower()==".py" and text is not None else 0

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        if text is None: return self.result(context,"SKIPPED",[],[],[],[],[],["Python source was not decodable as text."])
        declarations=[]; dependencies=[]; interfaces=[]; configs=[]; entries=[]; limitations=[]
        try:
            tree=ast.parse(text,filename=context.path)
        except SyntaxError as exc:
            return self.result(context,"PARTIAL",[],[],[],[],[],[f"Python AST parse failed at line {exc.lineno}: {exc.msg}"])
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): declarations.append(item("async-function" if isinstance(node,ast.AsyncFunctionDef) else "function",node.name,node.lineno))
            elif isinstance(node,ast.ClassDef): declarations.append(item("class",node.name,node.lineno))
            elif isinstance(node,ast.Import):
                for alias in node.names: dependencies.append(item("import",alias.name,node.lineno))
            elif isinstance(node,ast.ImportFrom): dependencies.append(item("import-from",node.module or ".",node.lineno))
            elif isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr.lower() in {"get","post","put","patch","delete","route","websocket"}:
                if node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str): interfaces.append(item("http-route",node.args[0].value,node.lineno,node.func.attr.upper()))
            elif isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {"getenv","get"} and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                root=node.func.value
                if isinstance(root,ast.Name) and root.id in {"environ","os"}: configs.append(item("environment-variable",node.args[0].value,node.lineno))
            elif isinstance(node,ast.If) and isinstance(node.test,ast.Compare):
                if "__name__" in ast.unparse(node.test) and "__main__" in ast.unparse(node.test): entries.append(item("main-guard",context.path,node.lineno))
        limitations.append("AST extraction does not import modules, execute decorators, or resolve dynamic registration.")
        return self.result(context,"COMPLETE",declarations,dependencies,interfaces,configs,entries,limitations)


class GoAdapter(BaseAdapter):
    id="go"; language="go"
    def detect(self,path,data,text): return 100 if path.suffix.lower()==".go" and text is not None else 0
    def extract(self,context,data,text):
        if text is None: return self.result(context,"SKIPPED",[],[],[],[],[],["Go source was not decodable as text."])
        d=[]; deps=[]; inter=[]; entries=[]
        for m in _matches(r"^\s*package\s+([A-Za-z_][\w]*)",text): d.append(item("package",m.group(1),line_number(text,m.start())))
        for m in _matches(r"(?:^\s*import\s+|^\s*)[\"`]([^\"`]+)[\"`]",text): deps.append(item("import",m.group(1),line_number(text,m.start())))
        for m in _matches(r"^\s*type\s+([A-Za-z_][\w]*)\s+(struct|interface)\b",text): d.append(item(m.group(2),m.group(1),line_number(text,m.start())))
        for m in _matches(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)\s*\(",text): d.append(item("function",m.group(1),line_number(text,m.start())))
        for m in _matches(r"\b(?:HandleFunc|Handle)\s*\(\s*[\"`]([^\"`]+)",text): inter.append(item("http-route",m.group(1),line_number(text,m.start())))
        if re.search(r"^\s*package\s+main\b",text,re.MULTILINE) and re.search(r"^\s*func\s+main\s*\(",text,re.MULTILINE): entries.append(item("main",context.path,1))
        return self.result(context,"COMPLETE",d,deps,inter,[],entries,["Surface extraction does not resolve build tags, generated interfaces, reflection, or framework route composition."])


class RustAdapter(BaseAdapter):
    id="rust"; language="rust"
    def detect(self,path,data,text): return 100 if path.suffix.lower()==".rs" and text is not None else 0
    def extract(self,context,data,text):
        if text is None: return self.result(context,"SKIPPED",[],[],[],[],[],["Rust source was not decodable as text."])
        d=[]; deps=[]; inter=[]; entries=[]
        for m in _matches(r"^\s*(?:pub\s+)?(?:async\s+)?(fn|struct|enum|trait|type|const|static|mod)\s+([A-Za-z_][\w]*)",text): d.append(item(m.group(1),m.group(2),line_number(text,m.start())))
        for m in _matches(r"^\s*(?:pub\s+)?use\s+([^;]+);",text): deps.append(item("use",m.group(1).strip(),line_number(text,m.start())))
        for m in _matches(r"#\[(?:get|post|put|patch|delete)\s*\(\s*[\"']([^\"']+)",text): inter.append(item("http-route",m.group(1),line_number(text,m.start())))
        if re.search(r"^\s*fn\s+main\s*\(",text,re.MULTILINE): entries.append(item("main",context.path,1))
        return self.result(context,"COMPLETE",d,deps,inter,[],entries,["Macro expansion, cfg evaluation, trait resolution, and generated code are not executed."])


class DotNetAdapter(BaseAdapter):
    id="dotnet"
    def detect(self,path,data,text): return 100 if path.suffix.lower() in {".cs",".fs",".vb"} and text is not None else 0
    def extract(self,context,data,text):
        if text is None: return self.result(context,"SKIPPED",[],[],[],[],[],[".NET source was not decodable as text."])
        suffix=PurePosixPath(context.path).suffix.lower(); language={".cs":"csharp",".fs":"fsharp",".vb":"visual-basic"}[suffix]
        d=[]; deps=[]; inter=[]; configs=[]; entries=[]
        if suffix==".cs":
            for m in _matches(r"^\s*using\s+([\w.]+)\s*;",text): deps.append(item("using",m.group(1),line_number(text,m.start())))
            for m in _matches(r"\b(class|interface|record|struct|enum|delegate)\s+([A-Za-z_][\w]*)",text): d.append(item(m.group(1),m.group(2),line_number(text,m.start())))
            for m in _matches(r"\[(HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete|Route)\s*(?:\(([^)]*)\))?\]",text): inter.append(item("http-mapping",m.group(1),line_number(text,m.start()),(m.group(2) or '').strip()))
            for m in _matches(r"Configuration\s*\[\s*[\"']([^\"']+)",text): configs.append(item("configuration-key",m.group(1),line_number(text,m.start())))
            if re.search(r"\bstatic\s+(?:async\s+)?(?:void|Task(?:<int>)?|int)\s+Main\s*\(",text): entries.append(item("main",context.path,1))
        elif suffix==".fs":
            for m in _matches(r"^\s*(?:module|namespace|type|let)\s+(?:rec\s+)?([A-Za-z_][\w.]*)",text): d.append(item("declaration",m.group(1),line_number(text,m.start())))
            for m in _matches(r"^\s*open\s+([\w.]+)",text): deps.append(item("open",m.group(1),line_number(text,m.start())))
            if "[<EntryPoint>]" in text: entries.append(item("entry-point",context.path,1))
        else:
            for m in _matches(r"^\s*Imports\s+([\w.]+)",text): deps.append(item("imports",m.group(1),line_number(text,m.start())))
            for m in _matches(r"\b(Class|Interface|Structure|Enum|Module)\s+([A-Za-z_][\w]*)",text): d.append(item(m.group(1).lower(),m.group(2),line_number(text,m.start())))
            if re.search(r"\bSub\s+Main\s*\(",text,re.IGNORECASE): entries.append(item("main",context.path,1))
        return self.result(context,"COMPLETE",d,deps,inter,configs,entries,["Surface extraction does not resolve partial types, source generators, attributes inherited at runtime, or framework conventions."],language)


class SqlAdapter(BaseAdapter):
    id="sql"; language="sql"
    def detect(self,path,data,text): return 100 if path.suffix.lower()==".sql" and text is not None else 0
    def extract(self,context,data,text):
        if text is None: return self.result(context,"SKIPPED",[],[],[],[],[],["SQL source was not decodable as text."])
        d=[]; inter=[]
        pattern=r"\bcreate\s+(?:or\s+replace\s+)?(table|view|materialized\s+view|index|function|procedure|trigger|type|sequence|schema)\s+(?:if\s+not\s+exists\s+)?([\w.\"`\[\]-]+)"
        for m in _matches(pattern,text): d.append(item(m.group(1).lower(),m.group(2).strip('"`[]'),line_number(text,m.start())))
        for m in _matches(r"\b(?:alter|drop)\s+(table|view|index|function|procedure|trigger|type|sequence)\s+(?:if\s+exists\s+)?([\w.\"`\[\]-]+)",text): inter.append(item(f"{m.group(1).lower()}-mutation",m.group(2).strip('"`[]'),line_number(text,m.start()),m.group(0).split()[0].upper()))
        return self.result(context,"COMPLETE",d,[],inter,[],[],["SQL dialect, dynamic SQL, search_path resolution, and procedural bodies are not semantically evaluated."])


class BpmnDmnAdapter(BaseAdapter):
    id="bpmn-dmn"
    def detect(self,path,data,text):
        name=path.name.lower(); suffix=path.suffix.lower()
        if suffix==".dmn" or suffix==".bpmn" or name.endswith(".bpmn20.xml"): return 100
        if text and ("<bpmn:" in text or "<definitions" in text and "decision" in text): return 80
        return 0
    def extract(self,context,data,text):
        try: root=ET.fromstring(data)
        except ET.ParseError as exc: return self.result(context,"PARTIAL",[],[],[],[],[],[f"XML parse failed: {exc}"],"bpmn-dmn")
        d=[]; deps=[]; inter=[]; configs=[]; entries=[]
        for element in root.iter():
            tag=element.tag.rsplit('}',1)[-1]; eid=element.attrib.get('id'); name=element.attrib.get('name') or eid
            if not name: continue
            if tag in {"process","collaboration","decision","decisionService","inputData","businessKnowledgeModel"}: d.append(item(tag,name,1,eid or ''))
            elif tag.endswith("Task") or tag in {"startEvent","endEvent","intermediateCatchEvent","intermediateThrowEvent","exclusiveGateway","parallelGateway","inclusiveGateway","eventBasedGateway","callActivity","subProcess"}: inter.append(item(tag,name,1,eid or ''))
            if tag in {"calledElement","calledDecision"}: deps.append(item(tag,name,1))
            for key in ("calledElement","decisionRef","messageRef","signalRef","errorRef","escalationRef"):
                if key in element.attrib: deps.append(item(key,element.attrib[key],1,eid or ''))
            if tag in {"process","decisionService"}: entries.append(item("entry-definition",name,1,eid or ''))
        return self.result(context,"COMPLETE",d,deps,inter,configs,entries,["XML line locations are reported as line 1 because the standard library parser does not preserve source lines; expression semantics are not evaluated."],"dmn" if PurePosixPath(context.path).suffix.lower()==".dmn" else "bpmn")


class OpenApiAsyncApiAdapter(BaseAdapter):
    id="openapi-asyncapi"
    def detect(self,path,data,text):
        if text is None: return 0
        try: obj=json.loads(text) if path.suffix.lower()==".json" else yaml.safe_load(text)
        except Exception: return 0
        return 100 if isinstance(obj,dict) and ("openapi" in obj or "asyncapi" in obj or "swagger" in obj) else 0
    def extract(self,context,data,text):
        try: obj=json.loads(text or "") if PurePosixPath(context.path).suffix.lower()==".json" else yaml.safe_load(text or "")
        except Exception as exc: return self.result(context,"PARTIAL",[],[],[],[],[],[f"Contract parse failed: {exc}"],"openapi-asyncapi")
        d=[]; deps=[]; inter=[]; configs=[]; entries=[]
        if not isinstance(obj,dict): return self.result(context,"UNSUPPORTED",[],[],[],[],[],["Document root is not an object."],"openapi-asyncapi")
        if "openapi" in obj or "swagger" in obj:
            language="openapi"; entries.append(item("api-contract",str(obj.get("info",{}).get("title","OpenAPI")),1,str(obj.get("openapi") or obj.get("swagger"))))
            for path, methods in sorted((obj.get("paths") or {}).items()):
                if isinstance(methods,dict):
                    for method, operation in sorted(methods.items()):
                        if method.lower() in {"get","post","put","patch","delete","head","options","trace"}: inter.append(item("http-operation",path,1,method.upper()+" "+str((operation or {}).get("operationId",''))))
        else:
            language="asyncapi"; entries.append(item("event-contract",str(obj.get("info",{}).get("title","AsyncAPI")),1,str(obj.get("asyncapi",""))))
            for channel, value in sorted((obj.get("channels") or {}).items()): inter.append(item("channel",channel,1,",".join(sorted(k for k in (value or {}) if k in {"publish","subscribe","send","receive"}))))
        components=obj.get("components") or {}
        for section in ("schemas","messages","securitySchemes","parameters"):
            for name in sorted((components.get(section) or {})): d.append(item(section[:-1] if section.endswith('s') else section,name,1))
        for server in sorted((obj.get("servers") or {})): deps.append(item("server",server,1))
        return self.result(context,"COMPLETE",d,deps,inter,configs,entries,["References are inventoried but external $ref targets and overlays are not dereferenced in Phase 6."],language)


class InfrastructureAdapter(BaseAdapter):
    id="infrastructure"
    def detect(self,path,data,text):
        if text is None: return 0
        name=path.name.lower()
        if name=="dockerfile" or name.startswith("dockerfile."): return 100
        if path.suffix.lower()==".tf": return 100
        if path.suffix.lower() in {".yaml",".yml"}:
            try:
                docs=list(yaml.safe_load_all(text))
            except Exception: return 0
            if any(isinstance(doc,dict) and "apiVersion" in doc and "kind" in doc for doc in docs): return 95
        return 0
    def extract(self,context,data,text):
        path=PurePosixPath(context.path); d=[]; deps=[]; inter=[]; configs=[]; entries=[]; language="infrastructure"
        if path.name.lower()=="dockerfile" or path.name.lower().startswith("dockerfile."):
            language="dockerfile"
            for m in _matches(r"^\s*FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?",text or ''): deps.append(item("base-image",m.group(1),line_number(text or '',m.start()),m.group(2) or ''))
            for m in _matches(r"^\s*EXPOSE\s+(.+)$",text or ''): inter.append(item("exposed-port",m.group(1).strip(),line_number(text or '',m.start())))
            for m in _matches(r"^\s*(ENTRYPOINT|CMD)\s+(.+)$",text or ''): entries.append(item(m.group(1).lower(),m.group(2).strip(),line_number(text or '',m.start())))
            for m in _matches(r"^\s*(?:ARG|ENV)\s+([A-Za-z_][A-Za-z0-9_]*)",text or ''): configs.append(item("build-or-environment-key",m.group(1),line_number(text or '',m.start())))
        elif path.suffix.lower()==".tf":
            language="terraform"
            for m in _matches(r"^\s*(resource|data|module|variable|output|provider|terraform)\s+[\"']([^\"']+)[\"'](?:\s+[\"']([^\"']+)[\"'])?",text or ''): d.append(item(m.group(1),m.group(3) or m.group(2),line_number(text or '',m.start()),m.group(2)))
            for m in _matches(r"^\s*source\s*=\s*[\"']([^\"']+)",text or ''): deps.append(item("module-source",m.group(1),line_number(text or '',m.start())))
        else:
            language="kubernetes"
            try: docs=list(yaml.safe_load_all(text or ''))
            except Exception as exc: return self.result(context,"PARTIAL",[],[],[],[],[],[f"YAML parse failed: {exc}"],language)
            for doc in docs:
                if not isinstance(doc,dict) or "kind" not in doc: continue
                metadata=doc.get("metadata") or {}; name=str(metadata.get("name","<unnamed>")); kind=str(doc.get("kind"))
                d.append(item(kind,name,1,str(doc.get("apiVersion",""))))
                if kind in {"Deployment","StatefulSet","DaemonSet","Job","CronJob","Pod"}: entries.append(item("workload",name,1,kind))
                if kind in {"Service","Ingress","Gateway","HTTPRoute"}: inter.append(item("network-interface",name,1,kind))
                if kind in {"ConfigMap","Secret"}: configs.append(item("configuration-resource",name,1,kind))
        return self.result(context,"COMPLETE",d,deps,inter,configs,entries,["Templates, Helm/Kustomize overlays, Terraform evaluation, admission mutation, and runtime cluster state are not rendered in Phase 6."],language)
