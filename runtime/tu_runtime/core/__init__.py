"""Core lifecycle, routing, persistence, and validation primitives."""

# Shared host instruction files such as OpenCode's AGENTS.md require partial
# ownership. Load the managed installer as the public InstallationManager while
# keeping the original implementation available as its backward-compatible base.
from . import installation as _installation
from .managed_installation import InstallationManager as _ManagedInstallationManager
from .runtime_launcher import install_runtime_launcher_patch

install_runtime_launcher_patch(_ManagedInstallationManager)
_installation.InstallationManager = _ManagedInstallationManager
