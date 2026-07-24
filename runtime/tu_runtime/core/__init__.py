"""Core lifecycle, routing, persistence, and validation primitives."""

# Shared host instruction files such as OpenCode's AGENTS.md require partial
# ownership. Load the managed installer as the public InstallationManager while
# keeping the original implementation available as its backward-compatible base.
from . import installation as _installation
from .managed_installation import InstallationManager as _ManagedInstallationManager

_installation.InstallationManager = _ManagedInstallationManager

# Agent-native documentation is user-facing. Unexpected implementation errors
# must be converted into the normal structured error contract so host agents do
# not leak Python tracebacks into conversation output.
from . import conversation as _conversation
from .errors import TUnderstandError


class _SafeAgentConversationManager(_conversation.AgentConversationManager):
    def generate_documentation(self, prompt: str):
        try:
            return super().generate_documentation(prompt)
        except TUnderstandError:
            raise
        except Exception as exc:
            raise TUnderstandError(
                "AGENT-DOC-INTERNAL-001",
                "Documentation generation encountered an unexpected repository-analysis error: "
                f"{type(exc).__name__}: {str(exc)[:500]}",
            ) from None


_conversation.AgentConversationManager = _SafeAgentConversationManager
