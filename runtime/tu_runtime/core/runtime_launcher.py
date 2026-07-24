from __future__ import annotations


_AGENT_RUNTIME_LAUNCHER = r'''from __future__ import annotations
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime"))
from tu_runtime.cli import main


def _documentation_heartbeat(stop: threading.Event) -> None:
    started = time.monotonic()
    print(
        "[t-understand] Documentation workflow started; repository analysis and validation may take several minutes.",
        file=sys.stderr,
        flush=True,
    )
    while not stop.wait(15.0):
        elapsed = int(time.monotonic() - started)
        print(
            f"[t-understand] Documentation workflow still running ({elapsed}s elapsed).",
            file=sys.stderr,
            flush=True,
        )


stop = threading.Event()
heartbeat = None
if "agent-document" in sys.argv[1:]:
    heartbeat = threading.Thread(
        target=_documentation_heartbeat,
        args=(stop,),
        name="t-understand-documentation-heartbeat",
        daemon=True,
    )
    heartbeat.start()

try:
    raise SystemExit(main())
finally:
    stop.set()
    if heartbeat is not None:
        heartbeat.join(timeout=1.0)
'''


def install_runtime_launcher_patch(installation_manager_type: type) -> None:
    """Install a heartbeat-enabled launcher without changing package contents.

    OpenCode's shell tool has a finite execution timeout. Deep documentation is
    intentionally synchronous and can exceed the host's default 120 seconds on
    real repositories. The heartbeat makes the active work visible on stderr;
    host instructions separately require a longer tool timeout.
    """

    if getattr(installation_manager_type, "_t_understand_launcher_patch", False):
        return
    original = installation_manager_type._engine_files

    def _engine_files(self):
        files = original(self)
        files["t-understand-engine/agent_runtime.py"] = _AGENT_RUNTIME_LAUNCHER.encode("utf-8")
        return files

    installation_manager_type._engine_files = _engine_files
    installation_manager_type._t_understand_launcher_patch = True
