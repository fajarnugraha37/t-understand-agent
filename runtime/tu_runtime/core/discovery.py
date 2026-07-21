from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from ..adapters import AdapterContext, AdapterRegistry
from .application import ApplicationManager
from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_bytes, sha256_file, utc_now
from .snapshot import GitReader, SnapshotManager

DISCOVERY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")
MAX_TEXT_INSPECTION_BYTES = 2 * 1024 * 1024
MAX_INVENTORY_HASH_BYTES = 10 * 1024 * 1024

PROTECTED_NAMES = {".env", ".npmrc", ".pypirc", "credentials", "credentials.json", "id_rsa", "id_ed25519"}
PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
VENDORED_PARTS = {"node_modules", "vendor", ".venv", "venv", "third_party", "third-party", "externals"}
GENERATED_PARTS = {"dist", "build", "target", "out", ".gradle", ".next", "coverage", "generated", "gen", ".t-understand"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".jar", ".war", ".class", ".dll", ".exe", ".so", ".dylib", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi", ".bin"}

LANGUAGE_BY_SUFFIX = {
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".groovy": "groovy",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".py": "python", ".go": "go", ".rs": "rust",
    ".cs": "csharp", ".fs": "fsharp", ".vb": "visual-basic", ".sql": "sql",
    ".bpmn": "bpmn", ".dmn": "dmn", ".tf": "terraform", ".hcl": "hcl",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json", ".xml": "xml", ".toml": "toml",
    ".properties": "properties", ".sh": "shell", ".bash": "shell", ".ps1": "powershell",
    ".md": "markdown", ".mdx": "mdx", ".html": "html", ".css": "css", ".scss": "scss",
    ".proto": "protobuf", ".graphql": "graphql", ".gql": "graphql",
}

BUILD_MARKERS = {
    "pom.xml": "maven", "build.gradle": "gradle", "build.gradle.kts": "gradle-kotlin",
    "settings.gradle": "gradle", "settings.gradle.kts": "gradle-kotlin", "package.json": "npm",
    "pnpm-workspace.yaml": "pnpm-workspace", "yarn.lock": "yarn", "pyproject.toml": "python-project",
    "requirements.txt": "python-requirements", "go.mod": "go-modules", "Cargo.toml": "cargo",
    "global.json": "dotnet", "Directory.Build.props": "dotnet", "Makefile": "make",
}


def _canonical_digest(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(payload)


def _safe_relative(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or not path:
        raise TUnderstandError("DISC-PATH-001", f"Unsafe repository path: {path}")
    return pure.as_posix()


def _decode_text(data: bytes) -> str | None:
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _is_protected(path: str) -> bool:
    pure = PurePosixPath(path)
    lower_parts = [part.lower() for part in pure.parts]
    name = pure.name.lower()
    if name in PROTECTED_NAMES or pure.suffix.lower() in PROTECTED_SUFFIXES:
        return True
    if name.startswith(".env") or any(part in {"secrets", ".secrets", "credentials"} for part in lower_parts):
        return True
    return False


def _is_vendored(path: str) -> bool:
    return any(part.lower() in VENDORED_PARTS for part in PurePosixPath(path).parts)


def _is_generated(path: str) -> bool:
    pure = PurePosixPath(path)
    parts = {part.lower() for part in pure.parts}
    name = pure.name.lower()
    return bool(parts & GENERATED_PARTS) or name.endswith((".generated.java", ".g.cs", ".min.js", ".min.css"))


def _language(path: str) -> str | None:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"
    if name.endswith(".bpmn20.xml"):
        return "bpmn"
    return LANGUAGE_BY_SUFFIX.get(pure.suffix.lower())


def _classification(path: str, generated: bool, vendored: bool) -> str:
    pure = PurePosixPath(path)
    lower = path.lower()
    name = pure.name.lower()
    parts = [part.lower() for part in pure.parts]
    if vendored: return "vendored"
    if generated: return "generated"
    if name in {"readme.md", "contributing.md", "changelog.md", "license", "license.md"} or pure.suffix.lower() in {".md", ".mdx", ".adoc", ".rst"}: return "documentation"
    if ".github/workflows" in lower or name in {".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml", "buildkite.yml"}: return "ci"
    if name == "dockerfile" or name.startswith("dockerfile.") or pure.suffix.lower() == ".tf" or any(part in {"k8s", "kubernetes", "helm", "deploy", "deployment", "infra", "terraform"} for part in parts): return "deployment"
    if "migration" in lower or "migrations" in parts or "db/changelog" in lower or "db/migration" in lower: return "migration"
    if name in BUILD_MARKERS or pure.suffix.lower() in {".csproj", ".fsproj", ".vbproj", ".sln"}: return "build"
    if name.startswith(("openapi", "asyncapi")) or pure.suffix.lower() in {".bpmn", ".dmn", ".proto", ".graphql", ".gql"} or name.endswith(".bpmn20.xml"): return "contract"
    if "test" in parts or "tests" in parts or "__tests__" in parts or re.search(r"(?:^|[._-])(test|spec)(?:[._-]|$)", name): return "test"
    if pure.suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml"}: return "configuration"
    if _language(path) in {"java", "kotlin", "groovy", "javascript", "typescript", "python", "go", "rust", "csharp", "fsharp", "visual-basic", "sql", "shell", "powershell", "html", "css", "scss"}: return "source"
    if pure.suffix.lower() in BINARY_SUFFIXES: return "asset"
    return "unknown"


class RepositorySnapshotView:
    def __init__(self, source: Path, descriptor: dict[str, Any], snapshot_manager: SnapshotManager):
        self.source = source
        self.descriptor = descriptor
        self.git = GitReader(source)
        self.snapshot_manager = snapshot_manager
        self.target_type = descriptor["target"]["type"]
        if self.target_type in {"index", "worktree"}:
            report = snapshot_manager.drift(descriptor["snapshot_id"])
            if report["status"] != "UNCHANGED":
                raise TUnderstandError("DISC-DRIFT-001", f"Snapshot {descriptor['snapshot_id']} has drifted and cannot be discovered")

    def list_files(self) -> list[dict[str, Any]]:
        if self.target_type in {"branch", "tag", "commit", "head"}:
            return self._commit_files()
        if self.target_type == "index":
            return self._index_files()
        return self._worktree_files()

    def _commit_files(self) -> list[dict[str, Any]]:
        commit = self.descriptor["resolved"]["commit"]
        raw = self.git.bytes("ls-tree", "-r", "-z", "--long", commit) or b""
        result=[]
        for record in raw.split(b"\0"):
            if not record: continue
            header, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id, raw_size = header.decode("ascii").split()
            path = _safe_relative(raw_path.decode("utf-8", "surrogateescape"))
            if object_type != "blob" or mode == "160000":
                result.append({"path":path,"mode":mode,"object_id":object_id,"size":0,"tracked":True,"special":"submodule"})
                continue
            result.append({"path":path,"mode":mode,"object_id":object_id,"size":int(raw_size),"tracked":True})
        return sorted(result,key=lambda value:value["path"])

    def _index_files(self) -> list[dict[str, Any]]:
        raw = self.git.bytes("ls-files", "-s", "-z") or b""
        result=[]
        for record in raw.split(b"\0"):
            if not record: continue
            header, raw_path = record.split(b"\t",1)
            mode, object_id, stage = header.decode("ascii").split()
            if stage != "0":
                raise TUnderstandError("DISC-INDEX-001", "Unmerged index entries are not supported")
            path=_safe_relative(raw_path.decode("utf-8","surrogateescape"))
            if mode in {"120000","160000"}:
                result.append({"path":path,"mode":mode,"object_id":object_id,"size":0,"tracked":True,"special":"symlink" if mode=="120000" else "submodule"})
                continue
            size_text=self.git.text("cat-file","-s",object_id) or "0"
            result.append({"path":path,"mode":mode,"object_id":object_id,"size":int(size_text),"tracked":True})
        return sorted(result,key=lambda value:value["path"])

    def _worktree_files(self) -> list[dict[str, Any]]:
        tracked=set(self.git.nul_paths("ls-files","-z"))
        untracked=set(self.git.nul_paths("ls-files","--others","--exclude-standard","-z"))
        result=[]
        for path in sorted(tracked | untracked):
            safe=_safe_relative(path); target=(self.source / safe)
            if not target.exists() and not target.is_symlink():
                continue
            metadata=target.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                result.append({"path":safe,"mode":"120000","object_id":None,"size":0,"tracked":safe in tracked,"special":"symlink"})
            elif stat.S_ISREG(metadata.st_mode):
                result.append({"path":safe,"mode":oct(metadata.st_mode),"object_id":None,"size":metadata.st_size,"tracked":safe in tracked})
        return result

    def read(self, record: dict[str, Any]) -> bytes:
        path=record["path"]
        if record.get("special"):
            raise TUnderstandError("DISC-CONTENT-001", f"Special path content is not readable: {path}")
        if self.target_type in {"branch","tag","commit","head"}:
            data=self.git.bytes("cat-file","blob",record["object_id"])
            return data or b""
        if self.target_type == "index":
            data=self.git.bytes("show",f":{path}")
            return data or b""
        target=(self.source / path).resolve()
        try: target.relative_to(self.source.resolve())
        except ValueError as exc: raise TUnderstandError("DISC-PATH-002",f"Path escapes repository: {path}") from exc
        return target.read_bytes()


class DiscoveryManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root=project_root
        self.context_root=context_root.resolve()
        self.application=ApplicationManager(project_root,self.context_root)
        self.snapshots=SnapshotManager(project_root,self.context_root)
        self.contracts=ContractValidator(project_root)
        self.adapters=AdapterRegistry(project_root)

    @property
    def root(self) -> Path: return self.context_root / "discovery"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock=self.context_root / "runtime" / "locks" / "discovery.lock"
        lock.parent.mkdir(parents=True,exist_ok=True)
        try: lock.mkdir()
        except FileExistsError as exc: raise TUnderstandError("DISC-LOCK-001","Discovery mutation is already active") from exc
        try: yield
        finally: lock.rmdir()

    def _dir(self, discovery_id: str) -> Path:
        if not DISCOVERY_ID_RE.fullmatch(discovery_id): raise TUnderstandError("DISC-ID-001","discovery_id must match ^[A-Z][A-Z0-9_-]{2,63}$")
        return self.root / discovery_id

    def _workspace_sources(self) -> dict[str,Path]:
        resolution=load_yaml(self.application.resolution_path)
        self.contracts.validate("workspace-resolution",resolution)
        if resolution["status"]!="RESOLVED": raise TUnderstandError("DISC-WORKSPACE-001","Workspace resolution is not RESOLVED")
        return {item["repository_id"]:Path(item["git_root"]) for item in resolution["repositories"]}

    def create(self, discovery_id: str, snapshot_id: str) -> dict[str,Any]:
        final=self._dir(discovery_id)
        if final.exists(): raise TUnderstandError("DISC-ID-002",f"Discovery already exists: {discovery_id}")
        validation=self.snapshots.validate_snapshot(snapshot_id)
        if validation["status"]!="PASS": raise TUnderstandError("DISC-SNAPSHOT-001",f"Snapshot validation failed: {snapshot_id}")
        snapshot=self.snapshots.show_snapshot(snapshot_id)
        sources=self._workspace_sources()
        temp=self.root / f".{discovery_id}.{uuid.uuid4().hex}.tmp"
        with self.lock():
            if final.exists():
                raise TUnderstandError("DISC-ID-002", f"Discovery already exists: {discovery_id}")
            temp.mkdir(parents=True)
            try:
                refs=[]; total=Counter()
                for repo_ref in sorted(snapshot["repositories"],key=lambda value:value["repository_id"]):
                    repository_id=repo_ref["repository_id"]
                    descriptor=load_yaml(self.context_root/"snapshots"/snapshot_id/repo_ref["descriptor_path"])
                    source=sources.get(repository_id)
                    if source is None: raise TUnderstandError("DISC-WORKSPACE-002",f"Repository is not resolved locally: {repository_id}")
                    repo_doc, records=self._discover_repository(discovery_id,snapshot,descriptor,source,temp)
                    descriptor_path=temp/"repositories"/f"{repository_id}.yaml"
                    atomic_write_yaml(descriptor_path,repo_doc)
                    refs.append({"repository_id":repository_id,"descriptor_path":f"repositories/{repository_id}.yaml","descriptor_sha256":sha256_file(descriptor_path),"content_digest":repo_doc["content_digest"]})
                    total.update({"files_total":repo_doc["coverage"]["files_total"],"included":repo_doc["coverage"]["included"],"excluded":repo_doc["coverage"]["excluded"]})
                base={"schema_id":"https://t-understand.dev/schemas/application-discovery.schema.json","schema_version":"1.0.0","discovery_id":discovery_id,"application_id":snapshot["application_id"],"snapshot_id":snapshot_id,"snapshot_digest":snapshot["content_digest"],"status":"DISCOVERED","repositories":refs,"coverage":{"repositories_total":len(refs),"repositories_discovered":len(refs),"files_total":total["files_total"],"included":total["included"],"excluded":total["excluded"]},"generated_at":utc_now()}
                doc={**base,"content_digest":_canonical_digest(base)}
                self.contracts.validate("application-discovery",doc)
                atomic_write_yaml(temp/"application-discovery.yaml",doc)
                os.replace(temp,final)
            except Exception:
                shutil.rmtree(temp,ignore_errors=True); raise
        return self.show(discovery_id)

    def _discover_repository(self, discovery_id: str, snapshot: dict[str,Any], descriptor: dict[str,Any], source: Path, temp: Path) -> tuple[dict[str,Any],list[dict[str,Any]]]:
        view=RepositorySnapshotView(source,descriptor,self.snapshots)
        records=[]; language_counts=Counter(); exclusions=Counter(); bytes_total=0
        for source_record in view.list_files():
            path=source_record["path"]; size=int(source_record.get("size",0)); bytes_total+=size
            protected=_is_protected(path); vendored=_is_vendored(path); generated=_is_generated(path)
            special=source_record.get("special"); data:bytes|None=None; digest: str|None=None; text: str|None=None
            reason=None
            if special=="submodule": reason="submodule"
            elif special=="symlink": reason="symlink"
            elif protected: reason="protected"
            elif vendored: reason="vendored"
            elif generated: reason="generated"
            elif size>MAX_INVENTORY_HASH_BYTES: reason="oversized"
            else:
                data=view.read(source_record); digest=sha256_bytes(data)
                if PurePosixPath(path).suffix.lower() in BINARY_SUFFIXES or _decode_text(data) is None: reason="binary"
                else: text=_decode_text(data)
            classification=_classification(path,generated,vendored)
            language=_language(path)
            candidates=[]
            if reason is None and data is not None:
                candidates=[value["id"] for value in self.adapters.candidates(path,data,text)]
                if language: language_counts[language]+=1
            status="EXCLUDED" if reason else "INCLUDED"
            if reason: exclusions[reason]+=1
            record={"schema_id":"https://t-understand.dev/schemas/file-inventory-record.schema.json","schema_version":"1.0.0","snapshot_id":snapshot["snapshot_id"],"repository_id":descriptor["repository_id"],"path":path,"status":status,"classification":classification,"language":language,"size_bytes":size,"sha256":digest,"tracked":bool(source_record.get("tracked",True)),"binary":reason=="binary","generated":generated,"vendored":vendored,"protected":protected,"adapter_candidates":candidates}
            if reason: record["exclusion_reason"]=reason
            self.contracts.validate("file-inventory-record",record)
            records.append(record)
        repo_root=temp/"repositories"; repo_root.mkdir(parents=True,exist_ok=True)
        jsonl="".join(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n" for value in records)
        files_path=repo_root/f"{descriptor['repository_id']}.files.jsonl"; atomic_write_text(files_path,jsonl)
        included=[value for value in records if value["status"]=="INCLUDED"]
        paths=[value["path"] for value in records]
        build_systems=self._build_systems(paths); modules=self._modules(paths,build_systems)
        base={"schema_id":"https://t-understand.dev/schemas/repository-discovery.schema.json","schema_version":"1.0.0","discovery_id":discovery_id,"snapshot_id":snapshot["snapshot_id"],"repository_id":descriptor["repository_id"],"repository_snapshot_digest":descriptor["content_digest"],"status":"DISCOVERED","languages":[{"id":key,"files":value} for key,value in sorted(language_counts.items())],"build_systems":build_systems,"modules":modules,"entry_points":self._entry_points(paths),"contracts":self._contracts(paths),"deployment_assets":self._deployments(paths),"ci_assets":self._ci(paths),"migrations":self._migrations(paths),"coverage":{"files_total":len(records),"included":len(included),"excluded":len(records)-len(included),"by_exclusion_reason":dict(sorted(exclusions.items())),"bytes_total":bytes_total},"files_path":f"repositories/{descriptor['repository_id']}.files.jsonl","files_sha256":sha256_file(files_path),"generated_at":utc_now()}
        doc={**base,"content_digest":_canonical_digest(base)}
        self.contracts.validate("repository-discovery",doc)
        return doc,records

    def _build_systems(self,paths:list[str])->list[dict[str,str]]:
        result=[]
        for path in paths:
            pure=PurePosixPath(path); name=pure.name
            if name in BUILD_MARKERS: result.append({"path":path,"kind":BUILD_MARKERS[name]})
            elif pure.suffix.lower() in {".csproj",".fsproj",".vbproj"}: result.append({"path":path,"kind":"dotnet-project"})
            elif pure.suffix.lower()==".sln": result.append({"path":path,"kind":"dotnet-solution"})
        return sorted(result,key=lambda value:(value["path"],value["kind"]))

    def _modules(self,paths:list[str],markers:list[dict[str,str]])->list[dict[str,Any]]:
        grouped:dict[str,list[dict[str,str]]]={}
        for marker in markers:
            root=PurePosixPath(marker["path"]).parent.as_posix()
            root="." if root=="." else root
            grouped.setdefault(root,[]).append(marker)
        return [{"id":("root" if root=="." else re.sub(r"[^a-zA-Z0-9]+","-",root).strip("-").lower()) or "root","root":root,"kind":"build-module","markers":[m["path"] for m in sorted(values,key=lambda x:x["path"])]} for root,values in sorted(grouped.items())]

    def _entry_points(self,paths:list[str])->list[dict[str,str]]:
        result=[]
        for path in paths:
            pure=PurePosixPath(path); name=pure.name.lower(); lower=path.lower()
            kind=None
            if name in {"main.py","main.go","main.rs","program.cs","application.java","app.py","server.py","index.js","index.ts"}: kind="conventional-entry"
            elif "/cmd/" in f"/{lower}" and name=="main.go": kind="go-command"
            elif name=="dockerfile" or name.startswith("dockerfile."): kind="container-entry"
            if kind: result.append({"path":path,"kind":kind})
        return sorted(result,key=lambda value:value["path"])

    def _contracts(self,paths:list[str])->list[dict[str,str]]:
        result=[]
        for path in paths:
            pure=PurePosixPath(path); name=pure.name.lower(); suffix=pure.suffix.lower(); kind=None
            if name.startswith("openapi") or "openapi" in name: kind="openapi"
            elif name.startswith("asyncapi") or "asyncapi" in name: kind="asyncapi"
            elif suffix==".bpmn" or name.endswith(".bpmn20.xml"): kind="bpmn"
            elif suffix==".dmn": kind="dmn"
            elif suffix==".proto": kind="protobuf"
            elif suffix in {".graphql",".gql"}: kind="graphql"
            if kind: result.append({"path":path,"kind":kind})
        return sorted(result,key=lambda value:value["path"])

    def _deployments(self,paths:list[str])->list[dict[str,str]]:
        result=[]
        for path in paths:
            pure=PurePosixPath(path); name=pure.name.lower(); lower=path.lower(); kind=None
            if name=="dockerfile" or name.startswith("dockerfile."): kind="dockerfile"
            elif pure.suffix.lower()==".tf": kind="terraform"
            elif any(part.lower() in {"k8s","kubernetes","helm","deploy","deployment"} for part in pure.parts) and pure.suffix.lower() in {".yaml",".yml",".json"}: kind="deployment-manifest"
            if kind: result.append({"path":path,"kind":kind})
        return sorted(result,key=lambda value:value["path"])

    def _ci(self,paths:list[str])->list[dict[str,str]]:
        result=[]
        for path in paths:
            lower=path.lower(); name=PurePosixPath(path).name.lower(); kind=None
            if lower.startswith(".github/workflows/"): kind="github-actions"
            elif name==".gitlab-ci.yml": kind="gitlab-ci"
            elif name=="jenkinsfile": kind="jenkins"
            elif name=="azure-pipelines.yml": kind="azure-pipelines"
            if kind: result.append({"path":path,"kind":kind})
        return sorted(result,key=lambda value:value["path"])

    def _migrations(self,paths:list[str])->list[dict[str,str]]:
        result=[]
        for path in paths:
            lower=path.lower(); pure=PurePosixPath(path); kind=None
            if "db/migration" in lower or re.search(r"(?:^|/)v\d+.*__.*\.sql$",lower): kind="flyway"
            elif "db/changelog" in lower or "liquibase" in lower: kind="liquibase"
            elif "migration" in lower or "migrations" in [part.lower() for part in pure.parts]: kind="migration"
            if kind: result.append({"path":path,"kind":kind})
        return sorted(result,key=lambda value:value["path"])

    def show(self,discovery_id:str)->dict[str,Any]:
        return load_yaml(self._dir(discovery_id)/"application-discovery.yaml")

    def list(self)->dict[str,Any]:
        values=[]
        if self.root.exists():
            for path in sorted(self.root.glob("*/application-discovery.yaml")):
                doc=load_yaml(path); values.append({"discovery_id":doc["discovery_id"],"snapshot_id":doc["snapshot_id"],"status":doc["status"]})
        return {"discoveries":values}

    def validate(self,discovery_id:str)->dict[str,Any]:
        errors=[]; root=self._dir(discovery_id)
        try:
            app=load_yaml(root/"application-discovery.yaml"); self.contracts.validate("application-discovery",app)
            base={key:value for key,value in app.items() if key!="content_digest"}
            if _canonical_digest(base)!=app["content_digest"]: errors.append("application content_digest mismatch")
            for ref in app["repositories"]:
                descriptor_path=root/ref["descriptor_path"]
                if not descriptor_path.is_file(): errors.append(f"missing repository descriptor: {ref['descriptor_path']}"); continue
                if sha256_file(descriptor_path)!=ref["descriptor_sha256"]: errors.append(f"repository descriptor checksum mismatch: {ref['repository_id']}")
                repo=load_yaml(descriptor_path); self.contracts.validate("repository-discovery",repo)
                repo_base={key:value for key,value in repo.items() if key!="content_digest"}
                if _canonical_digest(repo_base)!=repo["content_digest"]: errors.append(f"repository content_digest mismatch: {ref['repository_id']}")
                files_path=root/repo["files_path"]
                if sha256_file(files_path)!=repo["files_sha256"]: errors.append(f"file inventory checksum mismatch: {ref['repository_id']}")
                count=0
                for line in files_path.read_text(encoding="utf-8").splitlines():
                    record=json.loads(line); self.contracts.validate("file-inventory-record",record); count+=1
                if count!=repo["coverage"]["files_total"]: errors.append(f"file inventory count mismatch: {ref['repository_id']}")
        except TUnderstandError as exc: errors.append(str(exc))
        except Exception as exc: errors.append(f"unexpected validation error: {exc}")
        report={"status":"PASS" if not errors else "FAIL","discovery_id":discovery_id,"errors":errors,"validated_at":utc_now()}
        atomic_write_yaml(root/"validation-report.yaml",report)
        return report

    def view(self,snapshot_id:str,repository_id:str)->RepositorySnapshotView:
        snapshot=self.snapshots.show_snapshot(snapshot_id); sources=self._workspace_sources()
        ref=next((value for value in snapshot["repositories"] if value["repository_id"]==repository_id),None)
        if ref is None: raise TUnderstandError("DISC-REPO-001",f"Repository not in snapshot: {repository_id}")
        descriptor=load_yaml(self.context_root/"snapshots"/snapshot_id/ref["descriptor_path"])
        return RepositorySnapshotView(sources[repository_id],descriptor,self.snapshots)


class AdapterManager:
    def __init__(self,project_root:Path,context_root:Path):
        self.project_root=project_root; self.context_root=context_root.resolve(); self.discovery=DiscoveryManager(project_root,context_root); self.registry=AdapterRegistry(project_root); self.contracts=ContractValidator(project_root)

    @property
    def root(self)->Path: return self.context_root/"extractions"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock=self.context_root / "runtime" / "locks" / "adapter.lock"
        lock.parent.mkdir(parents=True,exist_ok=True)
        try: lock.mkdir()
        except FileExistsError as exc: raise TUnderstandError("ADAPTER-LOCK-001","Adapter mutation is already active") from exc
        try: yield
        finally: lock.rmdir()

    def _dir(self,extraction_id:str)->Path:
        if not DISCOVERY_ID_RE.fullmatch(extraction_id): raise TUnderstandError("ADAPTER-ID-001","extraction_id must match ^[A-Z][A-Z0-9_-]{2,63}$")
        return self.root/extraction_id

    def run(self,extraction_id:str,discovery_id:str)->dict[str,Any]:
        final=self._dir(extraction_id)
        if final.exists(): raise TUnderstandError("ADAPTER-ID-002",f"Extraction already exists: {extraction_id}")
        validation=self.discovery.validate(discovery_id)
        if validation["status"]!="PASS": raise TUnderstandError("ADAPTER-DISC-001",f"Discovery validation failed: {discovery_id}")
        app=self.discovery.show(discovery_id); temp=self.root/f".{extraction_id}.{uuid.uuid4().hex}.tmp"
        with self.lock():
            if final.exists(): raise TUnderstandError("ADAPTER-ID-002",f"Extraction already exists: {extraction_id}")
            temp.mkdir(parents=True)
            try:
                records=[]; statuses=Counter(); usage=Counter()
                discovery_root=self.discovery._dir(discovery_id)
                for repo_ref in app["repositories"]:
                    repo=load_yaml(discovery_root/repo_ref["descriptor_path"]); view=self.discovery.view(app["snapshot_id"],repo["repository_id"])
                    source_records={record["path"]:record for record in view.list_files()}
                    for line in (discovery_root/repo["files_path"]).read_text(encoding="utf-8").splitlines():
                        inventory=json.loads(line)
                        if inventory["status"]!="INCLUDED":
                            continue
                        source_record=source_records.get(inventory["path"])
                        if source_record is None: raise TUnderstandError("ADAPTER-FILE-001",f"Snapshot file is unavailable: {inventory['path']}")
                        data=view.read(source_record)
                        if sha256_bytes(data)!=inventory["sha256"]: raise TUnderstandError("ADAPTER-HASH-001",f"File digest mismatch: {inventory['path']}")
                        text=_decode_text(data)
                        ctx=AdapterContext(extraction_id,app["snapshot_id"],repo["repository_id"],inventory["path"],inventory["sha256"])
                        result=self.registry.extract(ctx,data,text); records.append(result); statuses[result["status"].lower()]+=1; usage[result["adapter_id"]]+=1
                jsonl="".join(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n" for value in records)
                atomic_write_text(temp/"adapter-extractions.jsonl",jsonl)
                base={"schema_id":"https://t-understand.dev/schemas/adapter-run.schema.json","schema_version":"1.0.0","extraction_id":extraction_id,"discovery_id":discovery_id,"snapshot_id":app["snapshot_id"],"status":"EXTRACTED","files_total":len(records),"extracted":statuses["complete"],"partial":statuses["partial"],"unsupported":statuses["unsupported"],"skipped":statuses["skipped"],"records_path":"adapter-extractions.jsonl","records_sha256":sha256_file(temp/"adapter-extractions.jsonl"),"adapter_usage":dict(sorted(usage.items())),"generated_at":utc_now()}
                doc={**base,"content_digest":_canonical_digest(base)}; self.contracts.validate("adapter-run",doc); atomic_write_yaml(temp/"adapter-run.yaml",doc); os.replace(temp,final)
            except Exception:
                shutil.rmtree(temp,ignore_errors=True); raise
        return self.show(extraction_id)

    def show(self,extraction_id:str)->dict[str,Any]: return load_yaml(self._dir(extraction_id)/"adapter-run.yaml")
    def list(self)->dict[str,Any]:
        values=[]
        if self.root.exists():
            for path in sorted(self.root.glob("*/adapter-run.yaml")):
                doc=load_yaml(path); values.append({"extraction_id":doc["extraction_id"],"discovery_id":doc["discovery_id"],"status":doc["status"]})
        return {"extractions":values}
    def validate(self,extraction_id:str)->dict[str,Any]:
        errors=[]; root=self._dir(extraction_id)
        try:
            doc=load_yaml(root/"adapter-run.yaml"); self.contracts.validate("adapter-run",doc)
            base={key:value for key,value in doc.items() if key!="content_digest"}
            if _canonical_digest(base)!=doc["content_digest"]: errors.append("adapter run content_digest mismatch")
            records_path=root/doc["records_path"]
            if sha256_file(records_path)!=doc["records_sha256"]: errors.append("adapter records checksum mismatch")
            count=0
            for line in records_path.read_text(encoding="utf-8").splitlines(): self.contracts.validate("adapter-extraction",json.loads(line)); count+=1
            if count!=doc["files_total"]: errors.append("adapter record count mismatch")
        except Exception as exc: errors.append(str(exc))
        return {"status":"PASS" if not errors else "FAIL","extraction_id":extraction_id,"errors":errors,"validated_at":utc_now()}
    def capabilities(self)->dict[str,Any]: return self.registry.capability_matrix(utc_now())
