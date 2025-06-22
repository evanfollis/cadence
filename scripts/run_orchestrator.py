# scripts/run_orchestrator.py
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