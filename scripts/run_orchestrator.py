# scripts/run_orchestrator.py
# ---------------------------------------------------------------------+
# Bootstrap: ensure repository ROOT (parent of this file’s directory)  +
# is on sys.path so that 'src.*' namespace packages resolve correctly  +
# ---------------------------------------------------------------------+
import pathlib, sys, os
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cadence.dev.orchestrator import DevOrchestrator

CONFIG = {
    "backlog_path": "dev_backlog.json",
    "template_file": None,
    "src_root": "src",          # <--- correct path
    "ruleset_file": None,
    "repo_dir": ".",
    "record_file": "dev_record.json",
}

if __name__ == "__main__":
    orch = DevOrchestrator(CONFIG)
    while True:
        result = orch.run_task_cycle(interactive=False)
        if not result.get("success"):
            break