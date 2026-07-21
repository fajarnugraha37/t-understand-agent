from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from ..core.contracts import ContractValidator
from ..core.errors import TUnderstandError
from .base import AdapterContext, BaseAdapter
from .builtins import (
    BpmnDmnAdapter, DotNetAdapter, GenericAdapter, GoAdapter, InfrastructureAdapter,
    JavaAdapter, JavaScriptTypeScriptAdapter, OpenApiAsyncApiAdapter, PythonAdapter,
    RustAdapter, SqlAdapter,
)

_IMPLEMENTATIONS: dict[str, type[BaseAdapter]] = {
    "generic": GenericAdapter,
    "java": JavaAdapter,
    "javascript-typescript": JavaScriptTypeScriptAdapter,
    "python": PythonAdapter,
    "go": GoAdapter,
    "rust": RustAdapter,
    "dotnet": DotNetAdapter,
    "sql": SqlAdapter,
    "bpmn-dmn": BpmnDmnAdapter,
    "openapi-asyncapi": OpenApiAsyncApiAdapter,
    "infrastructure": InfrastructureAdapter,
}


class AdapterRegistry:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.contracts = ContractValidator(project_root)
        self.manifests: dict[str, dict[str, Any]] = {}
        self.adapters: dict[str, BaseAdapter] = {}
        for path in sorted((project_root / "language-adapters").glob("*/adapter.yaml")):
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.contracts.validate("adapter-manifest", manifest)
            adapter_id = manifest["id"]
            if adapter_id in self.manifests:
                raise TUnderstandError("ADAPTER-REGISTRY-001", f"Duplicate adapter id: {adapter_id}")
            implementation = _IMPLEMENTATIONS.get(adapter_id)
            if implementation is None:
                raise TUnderstandError("ADAPTER-REGISTRY-002", f"No built-in implementation for adapter: {adapter_id}")
            adapter = implementation()
            adapter.version = manifest["version"]
            self.manifests[adapter_id] = manifest
            self.adapters[adapter_id] = adapter
        fallback = [item["id"] for item in self.manifests.values() if item["fallback"]]
        if fallback != ["generic"]:
            raise TUnderstandError("ADAPTER-REGISTRY-003", "Exactly the generic adapter must be the fallback")

    def candidates(self, path: str, data: bytes, text: str | None) -> list[dict[str, Any]]:
        p = PurePosixPath(path)
        values=[]
        for adapter_id, adapter in self.adapters.items():
            score = int(adapter.detect(p, data, text))
            if score > 0:
                manifest=self.manifests[adapter_id]
                values.append({"id":adapter_id,"score":score,"priority":manifest["priority"]})
        return sorted(values,key=lambda value:(-value["score"],-value["priority"],value["id"]))

    def select(self, path: str, data: bytes, text: str | None) -> BaseAdapter:
        candidates=self.candidates(path,data,text)
        specialized=[value for value in candidates if value["id"]!="generic" and value["score"]>=50]
        selected=(specialized or candidates)
        return self.adapters[selected[0]["id"]] if selected else self.adapters["generic"]

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        result=self.select(context.path,data,text).extract(context,data,text)
        self.contracts.validate("adapter-extraction",result)
        return result

    def capability_matrix(self, generated_at: str) -> dict[str, Any]:
        matrix={
            "schema_id":"https://t-understand.dev/schemas/adapter-capability-matrix.schema.json",
            "schema_version":"1.0.0",
            "adapters":[{
                "id":m["id"],"version":m["version"],"priority":m["priority"],
                "languages":m["languages"],"capabilities":m["capabilities"],"fallback":m["fallback"],
            } for m in sorted(self.manifests.values(),key=lambda value:value["id"])],
            "generated_at":generated_at,
        }
        self.contracts.validate("adapter-capability-matrix",matrix)
        return matrix
