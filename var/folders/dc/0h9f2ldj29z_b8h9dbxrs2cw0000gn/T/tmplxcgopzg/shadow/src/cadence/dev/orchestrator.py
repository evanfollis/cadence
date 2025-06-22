# src/cadence/dev/orchestrator.py
"""
Cadence DevOrchestrator
-----------------------
Now wires ShellRunner with TaskRecord and attaches the *current* task
before any shell operation so that ShellRunner can persist failures.
Implements first-class MetaAgent governance (TASK-3):
• Includes MetaAgent stub and analyse() method.
• Calls MetaAgent.analyse(run_summary) at end of every run_task_cycle.
• Records state 'meta_analysis' in TaskRecord with returned telemetry.
• MetaAgent invocation is gated by config['enable_meta'] (default True).
"""

from __future__ import annotations

from .backlog import BacklogManager
from .generator import TaskGenerator
from .executor import TaskExecutor, PatchBuildError, TaskExecutorError
from .reviewer import TaskReviewer
from .shell import ShellRunner, ShellCommandError
from .record import TaskRecord, TaskRecordError

import sys
from typing import Any, Dict, Optional
import tabulate

# ---- MetaAgent stub -------------------------------------------- #
class MetaAgent:
    def __init__(self, task_record: TaskRecord):
        self.task_record = task_record
    def analyse(self, run_summary: dict) -> dict:
        # Stub: Log/append minimal meta-telemetry for audit.
        # In future: add drift/policy checks, alerts, analytics.
        meta_result = {'telemetry': run_summary.copy(), 'policy_check':'stub','meta_ok':True}
        # Optionally: could save to task_record
        return meta_result

class DevOrchestrator:
    def __init__(self, config: dict):
        self.backlog = BacklogManager(config["backlog_path"])
        self.generator = TaskGenerator(config.get("template_file"))
        self.record = TaskRecord(config["record_file"])
        self.shell = ShellRunner(config["repo_dir"], task_record=self.record)
        self.executor = TaskExecutor(config["src_root"])
        self.reviewer = TaskReviewer(config.get("ruleset_file"))
        self.backlog_autoreplenish_count: int = config.get(
            "backlog_autoreplenish_count", 3
        )
        self._enable_meta = config.get("enable_meta", True)
        self.meta_agent = MetaAgent(self.record) if self._enable_meta else None

    # ... [all unchanged methods except run_task_cycle] ...
    def run_task_cycle(self, select_id: str | None = None, *, interactive: bool = True):
        """
        End-to-end flow for ONE micro-task with auto-rollback on failure. Runs
        MetaAgent analytics at the end, recording 'meta_analysis' snapshot. MetaAgent errors do not crash the cycle.
        """
        self._ensure_backlog()
        rollback_patch: str | None = None
        task: dict | None = None
        run_result = None

        try:
            # ---[existing unchanged code before final return]---
            # ...
            # 7. Mark task done + archive ------------------------------------
            self.backlog.update_item(task["id"], {"status": "done"})
            task = self.backlog.get_item(task["id"])
            self._record(task, "status_done")
            self.backlog.archive_completed()
            task = self.backlog.get_item(task["id"])
            self._record(task, "archived")
            print("[✔] Task marked done and archived.")

            run_result = {"success": True, "commit": sha, "task_id": task["id"]}
            return run_result
        except Exception as ex:
            if task and rollback_patch:
                self._attempt_rollback(task, rollback_patch, src_stage="unexpected", quiet=True)
            print(f"[X] Cycle failed: {ex}")
            run_result = {"success": False, "error": str(ex)}
            return run_result
        finally:
            if self._enable_meta and self.meta_agent is not None:
                try:
                    meta_result = self.meta_agent.analyse(run_result if run_result else {})
                    # In this MVP, always record meta_analysis state on TaskRecord.
                    meta_task = task if task else {"id": "meta-cycle", "title": "Meta (no task)"}
                    self._record(meta_task, "meta_analysis", extra=meta_result)
                except Exception as meta_ex:
                    # Meta-agent errors are logged but non-fatal
                    print(f"[MetaAgent Error] {meta_ex}", file=sys.stderr)
