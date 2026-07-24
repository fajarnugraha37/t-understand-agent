from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


@dataclass(frozen=True)
class AdapterContext:
    extraction_id: str
    snapshot_id: str
    repository_id: str
    path: str
    file_sha256: str


class BaseAdapter:
    id = "base"
    version = "1.0.0"
    language: str | None = None

    def detect(self, path: PurePosixPath, data: bytes, text: str | None) -> int:
        return 0

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        return self.result(context, "UNSUPPORTED", [], [], [], [], [], ["No specialized extraction is available."])

    def result(
        self,
        context: AdapterContext,
        status: str,
        declarations: list[dict[str, Any]],
        dependencies: list[dict[str, Any]],
        interfaces: list[dict[str, Any]],
        configuration_keys: list[dict[str, Any]],
        entry_points: list[dict[str, Any]],
        limitations: list[str],
        language: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_id": "https://t-understand.dev/schemas/adapter-extraction.schema.json",
            "schema_version": "1.0.0",
            "extraction_id": context.extraction_id,
            "snapshot_id": context.snapshot_id,
            "repository_id": context.repository_id,
            "path": context.path,
            "file_sha256": context.file_sha256,
            "adapter_id": self.id,
            "adapter_version": self.version,
            "language": language if language is not None else self.language,
            "status": status,
            "declarations": _dedupe(declarations),
            "dependencies": _dedupe(dependencies),
            "interfaces": _dedupe(interfaces),
            "configuration_keys": _dedupe(configuration_keys),
            "entry_points": _dedupe(entry_points),
            "limitations": sorted(set(_as_text(value, 2000) for value in limitations)),
        }


def _as_text(value: Any, limit: int) -> str:
    """Render extractor values deterministically without assuming string input.

    Parsers often encounter mappings, lists, numbers, booleans, or nulls in
    structurally valid contracts. Adapter helpers must preserve them as bounded
    text instead of relying on string slicing and crashing the full workflow.
    """
    if isinstance(value, str):
        text = value
    elif value is None:
        text = ""
    else:
        try:
            text = json.dumps(
                value,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError, RecursionError):
            text = str(value)
    return text[:limit]


def item(kind: str, name: Any, line: int, detail: Any | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": _as_text(kind, 500),
        "name": _as_text(name, 500),
        "line": max(1, int(line)),
    }
    if detail is not None and _as_text(detail, 2000):
        result["detail"] = _as_text(detail, 2000)
    return result


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _dedupe(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for value in values:
        key = (value.get("kind"), value.get("name"), value.get("line"), value.get("detail"))
        unique[key] = value
    return sorted(unique.values(), key=lambda value: (value["line"], value["kind"], value["name"]))
