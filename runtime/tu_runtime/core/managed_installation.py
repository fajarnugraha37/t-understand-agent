from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .errors import TUnderstandError
from .installation import (
    MERGED_JSON_CONFIGS,
    PLATFORMS,
    InstallationManager as BaseInstallationManager,
    _deep_merge,
    _digest,
    default_target_root,
)
from .io import (
    atomic_write_bytes,
    atomic_write_yaml,
    load_yaml,
    sha256_file,
    utc_now,
)

MANAGED_TEXT_CONFIGS = {
    "opencode": {
        "AGENTS.md": "t-understand-opencode",
    },
}

_MANAGED_BLOCK_LABELS = {
    "t-understand-opencode": "opencode",
}


def _managed_markers(block_id: str) -> tuple[str, str]:
    label = _MANAGED_BLOCK_LABELS.get(block_id, block_id)
    return (
        f"<!-- BEGIN T-UNDERSTAND MANAGED BLOCK: {label} -->",
        f"<!-- END T-UNDERSTAND MANAGED BLOCK: {label} -->",
    )


def _newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _block_digest(block_content: str) -> str:
    normalized = _normalize_newlines(block_content).strip("\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_managed_block(
    text: str,
    block_id: str,
) -> tuple[int, int, str] | None:
    begin, end = _managed_markers(block_id)
    begin_count = text.count(begin)
    end_count = text.count(end)
    if begin_count == 0 and end_count == 0:
        return None
    if begin_count != 1 or end_count != 1:
        raise TUnderstandError(
            "INSTALL-MERGE-001",
            f"Managed block {block_id} is malformed or duplicated",
        )
    start = text.index(begin)
    end_start = text.index(end)
    if end_start < start:
        raise TUnderstandError(
            "INSTALL-MERGE-001",
            f"Managed block {block_id} has invalid marker ordering",
        )
    content_start = start + len(begin)
    raw_body = text[content_start:end_start]
    body = _normalize_newlines(raw_body).strip("\n")
    return start, end_start + len(end), body


def _render_managed_block(block_id: str, block_content: str, newline: str) -> str:
    begin, end = _managed_markers(block_id)
    normalized = _normalize_newlines(block_content).strip("\n")
    body = normalized.replace("\n", newline)
    return f"{begin}{newline}{body}{newline}{end}"


def merge_managed_block(
    existing: str,
    block_id: str,
    block_content: str,
) -> tuple[str, str]:
    newline = _newline_for(existing)
    rendered = _render_managed_block(block_id, block_content, newline)
    parsed = _parse_managed_block(existing, block_id)
    if parsed is None:
        if not existing:
            return rendered + newline, _block_digest(block_content)
        prefix = existing.rstrip("\r\n")
        return prefix + newline * 2 + rendered + newline, _block_digest(block_content)
    start, end, _ = parsed
    return existing[:start] + rendered + existing[end:], _block_digest(block_content)


def remove_managed_block(existing: str, block_id: str) -> str:
    parsed = _parse_managed_block(existing, block_id)
    if parsed is None:
        return existing
    start, end, _ = parsed
    newline = _newline_for(existing)
    prefix = existing[:start].rstrip("\r\n")
    suffix = existing[end:].lstrip("\r\n")
    if prefix and suffix:
        return prefix + newline * 2 + suffix
    if prefix:
        return prefix + newline
    return suffix


def validate_managed_block(
    existing: str,
    block_id: str,
    expected_digest: str,
) -> list[str]:
    try:
        parsed = _parse_managed_block(existing, block_id)
    except TUnderstandError as exc:
        return [str(exc)]
    if parsed is None:
        return [f"missing managed block: {block_id}"]
    _, _, body = parsed
    if _block_digest(body) != expected_digest:
        return [f"modified managed block: {block_id}"]
    return []


class InstallationManager(BaseInstallationManager):
    """Installer with partial ownership for shared host instruction files."""

    @staticmethod
    def _management_mode(entry: dict[str, Any]) -> str:
        return entry.get("management_mode", "owned_file")

    def install(
        self,
        install_id: str,
        package_id: str,
        target_root: Path,
        force: bool = False,
    ) -> dict[str, Any]:
        self._check_id(install_id)
        target = self._ensure_safe_target(target_root)
        package = self.show_package(package_id)
        if self.validate_package(package_id)["status"] != "PASS":
            raise TUnderstandError(
                "INSTALL-PACKAGE-002", "Package validation failed"
            )
        metadata_root = self._install_meta(target)
        manifest_path = metadata_root / "install-manifest.yaml"
        if manifest_path.exists():
            current = load_yaml(manifest_path)
            if (
                current["install_id"] == install_id
                and current.get("package_id") == package_id
                and self.doctor(target)["status"] == "PASS"
                and not force
            ):
                return current
            if not force:
                raise TUnderstandError(
                    "INSTALL-CONFLICT-001",
                    "Target already has a managed t-understand installation; rerun with Force to replace it",
                )
            self.uninstall(target, force=True)

        payload = self.package_root / package_id / "payload"
        target.mkdir(parents=True, exist_ok=True)
        backup_root = metadata_root / "backups" / install_id
        installed: list[dict[str, Any]] = []
        backups: list[dict[str, str]] = []

        with self.lock():
            try:
                for package_entry in package["files"]:
                    relative = Path(package_entry["path"])
                    relative_key = relative.as_posix()
                    source = payload / relative
                    destination = target / relative
                    merge_json = (
                        relative_key
                        in MERGED_JSON_CONFIGS.get(package["platform"], set())
                    )
                    block_id = MANAGED_TEXT_CONFIGS.get(
                        package["platform"], {}
                    ).get(relative_key)
                    existed_before = destination.exists()
                    existing_json: Any = {}

                    if existed_before:
                        backup = backup_root / relative
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(destination, backup)
                        backups.append(
                            {
                                "path": relative_key,
                                "sha256": sha256_file(backup),
                            }
                        )
                        if merge_json:
                            try:
                                existing_json = json.loads(
                                    destination.read_text(encoding="utf-8")
                                )
                            except Exception as exc:
                                if not force:
                                    raise TUnderstandError(
                                        "INSTALL-CONFLICT-003",
                                        f"Existing managed JSON is invalid: {relative}",
                                    ) from exc
                                existing_json = {}
                        elif block_id is None and not force:
                            raise TUnderstandError(
                                "INSTALL-CONFLICT-002",
                                f"Unmanaged destination exists: {relative}",
                            )

                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if merge_json:
                        overlay = json.loads(source.read_text(encoding="utf-8"))
                        merged = _deep_merge(existing_json, overlay)
                        atomic_write_bytes(
                            destination,
                            (
                                json.dumps(merged, indent=2, sort_keys=True) + "\n"
                            ).encode("utf-8"),
                        )
                        installed.append(
                            {
                                "path": relative_key,
                                "sha256": sha256_file(destination),
                                "management_mode": "json_merge",
                            }
                        )
                    elif block_id is not None:
                        existing_text = (
                            destination.read_bytes().decode("utf-8")
                            if existed_before
                            else ""
                        )
                        merged_text, block_sha256 = merge_managed_block(
                            existing_text,
                            block_id,
                            source.read_text(encoding="utf-8"),
                        )
                        atomic_write_bytes(
                            destination,
                            merged_text.encode("utf-8"),
                        )
                        installed.append(
                            {
                                "path": relative_key,
                                "sha256": block_sha256,
                                "management_mode": "managed_block",
                                "block_id": block_id,
                                "file_created_by_installer": not existed_before,
                            }
                        )
                    else:
                        shutil.copy2(source, destination)
                        installed.append(
                            {
                                "path": relative_key,
                                "sha256": sha256_file(destination),
                                "management_mode": "owned_file",
                            }
                        )

                base = {
                    "schema_id": "https://t-understand.dev/schemas/install-manifest.schema.json",
                    "schema_version": "1.1.0",
                    "install_id": install_id,
                    "package_id": package_id,
                    "platform": package["platform"],
                    "target_root": str(target),
                    "status": "INSTALLED",
                    "files": installed,
                    "backups": backups,
                    "installed_at": utc_now(),
                }
                manifest = {**base, "content_digest": _digest(base)}
                self.contracts.validate("install-manifest", manifest)
                atomic_write_yaml(manifest_path, manifest)
                if self.doctor(target)["status"] != "PASS":
                    raise TUnderstandError(
                        "INSTALL-VERIFY-001", "Post-install doctor failed"
                    )
            except Exception:
                for item in reversed(installed):
                    (target / item["path"]).unlink(missing_ok=True)
                for item in backups:
                    backup = backup_root / item["path"]
                    destination = target / item["path"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, destination)
                shutil.rmtree(metadata_root, ignore_errors=True)
                raise
        return load_yaml(manifest_path)

    def doctor(self, target_root: Path) -> dict[str, Any]:
        target = target_root.expanduser().resolve()
        errors: list[str] = []
        checks = 0
        try:
            manifest = load_yaml(
                self._install_meta(target) / "install-manifest.yaml"
            )
            checks += 1
            self.contracts.validate("install-manifest", manifest)
            checks += 1
            if Path(manifest["target_root"]).resolve() != target:
                errors.append("target root mismatch")

            for entry in manifest["files"]:
                checks += 1
                path = target / entry["path"]
                mode = self._management_mode(entry)
                if mode == "managed_block":
                    if not path.is_file():
                        errors.append(f"missing: {entry['path']}")
                        continue
                    errors.extend(
                        validate_managed_block(
                            path.read_bytes().decode("utf-8"),
                            entry["block_id"],
                            entry["sha256"],
                        )
                    )
                elif not path.is_file() or sha256_file(path) != entry["sha256"]:
                    errors.append(f"missing or modified: {entry['path']}")

            checks += 1
            if (
                _digest(
                    {
                        key: value
                        for key, value in manifest.items()
                        if key != "content_digest"
                    }
                )
                != manifest["content_digest"]
            ):
                errors.append("install manifest digest mismatch")
        except Exception as exc:
            errors.append(str(exc))
        return {
            "status": "PASS" if not errors else "FAIL",
            "target_root": str(target),
            "checks": checks,
            "errors": errors,
            "generated_at": utc_now(),
        }

    def uninstall(self, target_root: Path, force: bool = False) -> dict[str, Any]:
        target = target_root.expanduser().resolve()
        metadata_root = self._install_meta(target)
        manifest = load_yaml(metadata_root / "install-manifest.yaml")
        modified: list[str] = []

        for entry in manifest["files"]:
            path = target / entry["path"]
            mode = self._management_mode(entry)
            if mode == "managed_block":
                if not path.exists():
                    continue
                block_errors = validate_managed_block(
                    path.read_bytes().decode("utf-8"),
                    entry["block_id"],
                    entry["sha256"],
                )
                if block_errors and not force:
                    modified.append(entry["path"])
            elif path.exists() and sha256_file(path) != entry["sha256"] and not force:
                modified.append(entry["path"])

        if modified:
            raise TUnderstandError(
                "INSTALL-UNINSTALL-001",
                f"Managed files were modified: {', '.join(modified)}",
            )

        legacy_manifest = not any(
            "management_mode" in entry for entry in manifest["files"]
        )
        for entry in sorted(
            manifest["files"],
            key=lambda item: len(Path(item["path"]).parts),
            reverse=True,
        ):
            path = target / entry["path"]
            mode = self._management_mode(entry)
            if mode != "managed_block":
                path.unlink(missing_ok=True)
                continue
            if not path.exists():
                continue
            current = path.read_bytes().decode("utf-8")
            try:
                cleaned = remove_managed_block(current, entry["block_id"])
            except TUnderstandError:
                raise TUnderstandError(
                    "INSTALL-MERGE-002",
                    f"Cannot safely remove malformed managed block from {entry['path']}",
                )
            if not cleaned.strip() and entry.get("file_created_by_installer", False):
                path.unlink(missing_ok=True)
            else:
                atomic_write_bytes(path, cleaned.encode("utf-8"))

        backup_root = metadata_root / "backups" / manifest["install_id"]
        if legacy_manifest:
            for entry in manifest["backups"]:
                source = backup_root / entry["path"]
                destination = target / entry["path"]
                if source.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)

        shutil.rmtree(metadata_root, ignore_errors=True)
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        return {
            "status": "UNINSTALLED",
            "install_id": manifest["install_id"],
            "target_root": str(target),
            "restored_backups": len(manifest["backups"]) if legacy_manifest else 0,
            "generated_at": utc_now(),
        }


__all__ = [
    "InstallationManager",
    "PLATFORMS",
    "default_target_root",
    "merge_managed_block",
    "remove_managed_block",
    "validate_managed_block",
]
