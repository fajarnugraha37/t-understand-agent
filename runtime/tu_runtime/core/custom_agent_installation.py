from __future__ import annotations

from pathlib import Path

from .io import atomic_write_bytes
from .managed_installation import remove_managed_block


_LEGACY_OPENCODE_BLOCK_ID = "t-understand-opencode"
_OPENCODE_CUSTOM_AGENT_NOTE = b"""

## OpenCode custom-agent activation

This agent is opt-in. It must run only when the human explicitly selects or invokes the `t-understand` custom agent. Never install or rely on global `AGENTS.md` auto-routing instructions.

When invoking `agent-document` through OpenCode's shell tool, set the tool timeout to at least `1800000` milliseconds. Do not use or inherit the default `120000` millisecond timeout. Heartbeat lines on stderr are liveness diagnostics; wait for the final JSON result on stdout.
"""


def _remove_legacy_global_agents_block(target_root: Path) -> None:
    """Remove only the old t-understand block from OpenCode's global AGENTS.md.

    Older releases installed auto-routing instructions globally. That made the
    t-understand agent influence unrelated OpenCode conversations. The custom
    agent under ``agents/t-understand.md`` is the only intended entry point.
    User-owned AGENTS.md content must remain untouched.
    """

    path = target_root / "AGENTS.md"
    if not path.is_file():
        return
    current = path.read_text(encoding="utf-8")
    cleaned = remove_managed_block(current, _LEGACY_OPENCODE_BLOCK_ID)
    if cleaned == current:
        return
    if cleaned.strip():
        atomic_write_bytes(path, cleaned.encode("utf-8"))
    else:
        path.unlink(missing_ok=True)


def install_custom_agent_only_patch(installation_manager_type: type) -> None:
    """Prevent global OpenCode instructions and clean legacy installations."""

    if getattr(installation_manager_type, "_t_understand_custom_agent_only_patch", False):
        return

    original_render_files = installation_manager_type._render_files
    original_install = installation_manager_type.install

    def _render_files(self, platform: str):
        files = original_render_files(self, platform)
        if platform == "opencode":
            files.pop("AGENTS.md", None)
            custom_agent = "agents/t-understand.md"
            if custom_agent in files:
                files[custom_agent] = files[custom_agent].rstrip() + _OPENCODE_CUSTOM_AGENT_NOTE
        return files

    def install(self, install_id, package_id, target_root, force=False):
        result = original_install(self, install_id, package_id, target_root, force)
        package = self.show_package(package_id)
        if package.get("platform") == "opencode":
            _remove_legacy_global_agents_block(Path(target_root).expanduser().resolve())
        return result

    installation_manager_type._render_files = _render_files
    installation_manager_type.install = install
    installation_manager_type._t_understand_custom_agent_only_patch = True
