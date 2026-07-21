from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .errors import TUnderstandError


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TUnderstandError("RT-FILE-001", f"File does not exist: {path}") from exc
    except yaml.YAMLError as exc:
        raise TUnderstandError("RT-YAML-001", f"Invalid YAML in {path}: {exc}") from exc


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_yaml(path: Path, data: Any) -> None:
    atomic_write_text(path, dump_yaml(data))


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def ensure_relative_safe(path_value: str) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise TUnderstandError("RT-PATH-001", f"Path must be relative and contained: {path_value}")
    return candidate


def resolve_within(root: Path, path_value: str) -> Path:
    relative = ensure_relative_safe(path_value)
    root_resolved = root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise TUnderstandError("RT-PATH-002", f"Path escapes runtime root: {path_value}") from exc
    return resolved
