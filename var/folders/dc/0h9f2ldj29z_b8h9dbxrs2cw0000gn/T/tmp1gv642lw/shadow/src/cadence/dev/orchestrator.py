# src/cadence/dev/orchestrator.py
"""
Cadence DevOrchestrator
-----------------------
Now wires ShellRunner with TaskRecord and attaches the *current* task
before any shell operation so that ShellRunner can persist failures.
"""

from __future__ import annotations

from .backlog import BacklogManager
from .generator import TaskGenerator
from .executor import TaskExecutor, PatchBuildError, TaskExecutorError
from .reviewer import TaskReviewer
from .shell import ShellRunner, ShellCommandError
from .record import TaskRecord, TaskRecordError
from cadence.agents.registry import get_agent  # <---- NEW IMPORT
import sys
from typing import Any, Dict, Optional
import tabulate


class DevOrchestrator:
    def __init__(self, config: dict):
        self.backlog = BacklogManager(config["backlog_path"])
        self.generator = TaskGenerator(config.get("template_file"))
        self.record = TaskRecord(config["record_file"])
        # ShellRunner now receives TaskRecord so it can self-record failures
        self.shell = ShellRunner(config["repo_dir"], task_record=self.record)
        self.executor = TaskExecutor(config["src_root"])
        self.reviewer = TaskReviewer(config.get("ruleset_file"))
        self.efficiency = get_agent("efficiency")  # <---- ADDED: mandatory second review
        self.backlog_autoreplenish_count: int = config.get(
            "backlog_autoreplenish_count", 3
        )
        
    # ------------------------------------------------------------------ #
    # Back-log auto-replenishment  (unchanged)
    # ------------------------------------------------------------------ #
    def _ensure_backlog(self, count: Optional[int] = None) -> None:
        if self.backlog.list_items("open"):
            return
        n = count if count is not None else self.backlog_autoreplenish_count
        for t in self.generator.generate_tasks(mode="micro", count=n):
            self.backlog.add_item(t)
        self._record(
            {"id": "auto-backlog-replenish", "title": "Auto-replenish"},
            state="backlog_replenished",
            extra={"count": n},
        )

    # ------------------------------------------------------------------ #
    # Internal helper – ALWAYS log, never raise  (unchanged)
    # ------------------------------------------------------------------ #
    def _record(self, task: dict, state: str, extra: Dict[str, Any] | None = None) -> None:
        try:
            self.record.save(task, state=state, extra=extra or {})
        except TaskRecordError as e:
            print(f"[Record-Error] {e}", file=sys.stderr)

    # ... [show, _format_backlog unchanged] ...

    # ------------------------------------------------------------------ #
    # Main workflow
    # ------------------------------------------------------------------ #
    def run_task_cycle(self, select_id: str | None = None, *, interactive: bool = True):
        """
        End-to-end flow for ONE micro-task with auto-rollback on failure.
        Now requires both Reasoning and Efficiency review to pass before commit.
        """
        self._ensure_backlog()
        rollback_patch: str | None = None
        task: dict | None = None

        try:
            # 1. Select Task --------------------------------------------------
            open_tasks = self.backlog.list_items(status="open")
            if not open_tasks:
                raise RuntimeError("No open tasks in backlog.")
            if select_id:
                task = next((t for t in open_tasks if t["id"] == select_id), None)
                if not task:
                    raise RuntimeError(f"Task id '{select_id}' not found in open backlog.")
            elif interactive:
                print(self._format_backlog(open_tasks))
                print("---")
                idx = self._prompt_pick(len(open_tasks))
                task = open_tasks[idx]
            else:
                task = open_tasks[0]
            print(f"\n[Selected task: {task['id'][:8]}] {task.get('title')}\n")
            self.shell.attach_task(task)
            # 2. Build patch --------------------------------------------------
            self._record(task, "build_patch")
            try:
                patch = self.executor.build_patch(task)
                rollback_patch = patch
                self._record(task, "patch_built", {"patch": patch})
                print("--- Patch built ---\n", patch)
            except (PatchBuildError, TaskExecutorError) as ex:
                self._record(task, "failed_build_patch", {"error": str(ex)})
                print(f"[X] Patch build failed: {ex}")
                return {"success": False, "stage": "build_patch", "error": str(ex)}

            # 3. Review #1 (Reasoning/TaskReviewer) --------------------------
            review1 = self.reviewer.review_patch(patch, context=task)
            self._record(task, "patch_reviewed_reasoning", {"review": review1})
            print("--- Review 1 (Reasoning) ---")
            print(review1["comments"] or "(no comments)")
            if not review1["pass"]:
                self._record(task, "failed_patch_review_reasoning", {"review": review1})
                print("[X] Patch failed REASONING review, aborting.")
                return {"success": False, "stage": "patch_review_reasoning", "review": review1}

            # 4. Review #2 (EfficiencyAgent) ----------------------------------
            efficiency_prompt = (
                "You are the EfficiencyAgent for the Cadence workflow. "
                "Please review the following code diff for best-practice, lint, and summarisation requirements.\n"
                f"DIFF:\n\n{patch}\n\nTASK CONTEXT:\n{task}"
            )
            eff_review_raw = self.efficiency.run_interaction(efficiency_prompt)
            eff_review = {"pass": ("pass" in eff_review_raw.lower() and not "fail" in eff_review_raw.lower()), "comments": eff_review_raw}
            self._record(task, "patch_reviewed_efficiency", {"review": eff_review})
            print("--- Review 2 (Efficiency) ---")
            print(eff_review["comments"] or "(no comments)")
            if not eff_review["pass"]:
                self._record(task, "failed_patch_review_efficiency", {"review": eff_review})
                print("[X] Patch failed EFFICIENCY review, aborting.")
                return {"success": False, "stage": "patch_review_efficiency", "review": eff_review}
            # Pass flags so ShellRunner knows both review stages passed
            if hasattr(self.shell, "_mark_phase") and task.get("id"):
                self.shell._mark_phase(task["id"], "efficiency_passed")

            # 5. Apply patch --------------------------------------------------
            try:
                self.shell.git_apply(patch)
                self._record(task, "patch_applied")
                print("[✔] Patch applied.")
            except ShellCommandError as ex:
                self._record(task, "failed_patch_apply", {"error": str(ex)})
                print(f"[X] git apply failed: {ex}")
                return {"success": False, "stage": "patch_apply", "error": str(ex)}

            # ------- CRITICAL SECTION BEGIN --------
            # 6. Run tests ----------------------------------------------------
            test_result = self.shell.run_pytest()
            self._record(task, "pytest_run", {"pytest": test_result})
            print("--- Pytest ---")
            print(test_result["output"])
            if not test_result["success"]:
                print("[X] Tests FAILED. Initiating rollback.")
                self._record(task, "failed_test", {"pytest": test_result})
                self._attempt_rollback(task, rollback_patch, src_stage="test")
                return {"success": False, "stage": "test", "test_result": test_result}

            # 7. Commit -------------------------------------------------------
            commit_msg = f"[Cadence] {task['id'][:8]} {task.get('title', '')}"
            try:
                sha = self.shell.git_commit(commit_msg)
                self._record(task, "committed", {"commit_sha": sha})
                print(f"[✔] Committed as {sha}")
            except ShellCommandError as ex:
                self._record(task, "failed_commit", {"error": str(ex)})
                print(f"[X] git commit failed: {ex}")
                self._attempt_rollback(task, rollback_patch, src_stage="commit")
                return {"success": False, "stage": "commit", "error": str(ex)}

            # 8. Mark task done + archive ------------------------------------
            self.backlog.update_item(task["id"], {"status": "done"})
            task = self.backlog.get_item(task["id"])
            self._record(task, "status_done")
            self.backlog.archive_completed()
            task = self.backlog.get_item(task["id"])
            self._record(task, "archived")
            print("[✔] Task marked done and archived.")
            return {"success": True, "commit": sha, "task_id": task["id"]}
        except Exception as ex:
            if task and rollback_patch:
                self._attempt_rollback(task, rollback_patch, src_stage="unexpected", quiet=True)
            print(f"[X] Cycle failed: {ex}")
            return {"success": False, "error": str(ex)}
    # ... [other unchanged methods: _attempt_rollback, cli_entry, _prompt_pick] ...
