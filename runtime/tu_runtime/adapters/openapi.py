from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Iterable

import yaml

from .base import AdapterContext, BaseAdapter, item


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _server_records(servers: Any) -> Iterable[tuple[str, str | None]]:
    """Normalize OpenAPI and AsyncAPI server shapes without losing meaning.

    OpenAPI 3 uses a list of server objects. AsyncAPI uses a mapping from a
    logical server name to a server object. Swagger 2 normally uses host,
    basePath, and schemes instead of servers. Invalid-but-readable scalar
    values are retained as bounded evidence rather than crashing extraction.
    """
    if isinstance(servers, list):
        for index, server in enumerate(servers, start=1):
            if isinstance(server, dict):
                name = server.get("url") or server.get("host") or server.get("name")
                if not name:
                    name = f"server-{index}"
                detail = server.get("description") or server.get("protocol")
                yield str(name), str(detail) if detail is not None else None
            else:
                yield str(server), None
        return

    if isinstance(servers, dict):
        for logical_name, server in sorted(servers.items(), key=lambda pair: str(pair[0])):
            if isinstance(server, dict):
                detail_parts = []
                for key in ("url", "host", "protocol", "protocolVersion", "description"):
                    value = server.get(key)
                    if value not in (None, ""):
                        detail_parts.append(f"{key}={value}")
                yield str(logical_name), "; ".join(detail_parts) or None
            else:
                yield str(logical_name), str(server)
        return

    if servers not in (None, ""):
        yield str(servers), None


class OpenApiAsyncApiAdapter(BaseAdapter):
    id = "openapi-asyncapi"

    def detect(self, path, data, text):
        if text is None:
            return 0
        try:
            obj = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
        except Exception:
            return 0
        return 100 if isinstance(obj, dict) and any(key in obj for key in ("openapi", "asyncapi", "swagger")) else 0

    def extract(self, context: AdapterContext, data: bytes, text: str | None) -> dict[str, Any]:
        try:
            obj = (
                json.loads(text or "")
                if PurePosixPath(context.path).suffix.lower() == ".json"
                else yaml.safe_load(text or "")
            )
        except Exception as exc:
            return self.result(
                context,
                "PARTIAL",
                [],
                [],
                [],
                [],
                [],
                [f"Contract parse failed: {exc}"],
                "openapi-asyncapi",
            )

        declarations: list[dict[str, Any]] = []
        dependencies: list[dict[str, Any]] = []
        interfaces: list[dict[str, Any]] = []
        configuration_keys: list[dict[str, Any]] = []
        entry_points: list[dict[str, Any]] = []

        if not isinstance(obj, dict):
            return self.result(
                context,
                "UNSUPPORTED",
                declarations,
                dependencies,
                interfaces,
                configuration_keys,
                entry_points,
                ["Document root is not an object."],
                "openapi-asyncapi",
            )

        info = _mapping(obj.get("info"))
        if "openapi" in obj or "swagger" in obj:
            language = "openapi"
            entry_points.append(
                item(
                    "api-contract",
                    info.get("title", "OpenAPI"),
                    1,
                    obj.get("openapi") or obj.get("swagger"),
                )
            )
            paths = _mapping(obj.get("paths"))
            for route, methods in sorted(paths.items(), key=lambda pair: str(pair[0])):
                if not isinstance(methods, dict):
                    continue
                for method, operation in sorted(methods.items(), key=lambda pair: str(pair[0])):
                    if str(method).lower() not in {
                        "get",
                        "post",
                        "put",
                        "patch",
                        "delete",
                        "head",
                        "options",
                        "trace",
                    }:
                        continue
                    operation_id = _mapping(operation).get("operationId", "")
                    interfaces.append(
                        item(
                            "http-operation",
                            route,
                            1,
                            f"{str(method).upper()} {operation_id}".rstrip(),
                        )
                    )
        else:
            language = "asyncapi"
            entry_points.append(
                item(
                    "event-contract",
                    info.get("title", "AsyncAPI"),
                    1,
                    obj.get("asyncapi", ""),
                )
            )
            channels = _mapping(obj.get("channels"))
            for channel, value in sorted(channels.items(), key=lambda pair: str(pair[0])):
                operations = _mapping(value)
                supported = sorted(
                    str(key)
                    for key in operations
                    if str(key) in {"publish", "subscribe", "send", "receive"}
                )
                interfaces.append(item("channel", channel, 1, ",".join(supported)))

        components = _mapping(obj.get("components"))
        for section in ("schemas", "messages", "securitySchemes", "parameters"):
            values = _mapping(components.get(section))
            kind = section[:-1] if section.endswith("s") else section
            for name in sorted(values, key=str):
                declarations.append(item(kind, name, 1))

        for name, detail in _server_records(obj.get("servers")):
            dependencies.append(item("server", name, 1, detail))

        if "swagger" in obj and obj.get("host"):
            base_path = str(obj.get("basePath") or "")
            schemes = obj.get("schemes") or []
            scheme_text = ",".join(str(value) for value in schemes) if isinstance(schemes, list) else str(schemes)
            detail = "; ".join(value for value in (f"basePath={base_path}" if base_path else "", f"schemes={scheme_text}" if scheme_text else "") if value)
            dependencies.append(item("server", obj.get("host"), 1, detail or None))

        return self.result(
            context,
            "COMPLETE",
            declarations,
            dependencies,
            interfaces,
            configuration_keys,
            entry_points,
            [
                "References are inventoried but external $ref targets and overlays are not dereferenced in Phase 6."
            ],
            language,
        )
