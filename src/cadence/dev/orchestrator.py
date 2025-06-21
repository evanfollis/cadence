# src/cadence/dev/orchestrator.py
"""
Cadence DevOrchestrator
-----------------------
The *single* source of truth for phase-ordering in the development loop.

NEW FUNCTIONALITY (2025-06-21)
    • Atomic rollback: if any failure occurs **after** a patch is applied
      but **before** commit succeeds, we automatically revert the working
      tree to its pristine state using `git apply -R`.
"""

from __future__ import annotations

from .backlog import BacklogManager
from .generator import TaskGenerator
from .executor import TaskExecutor, PatchBuildError
from .reviewer import TaskReviewer
from .shell import ShellRunner, ShellCommandError
from .record import TaskRecord, TaskRecordError

import sys
from typing import Any, Dict


class DevOrchestrator:
    def __init__(self, config: dict):
        self.backlog = BacklogManager(config["backlog_path"])
        self.generator = TaskGenerator(config.get("template_file"))
        self.executor = TaskExecutor(config["src_root"])
        self.reviewer = TaskReviewer(config.get("ruleset_file"))
        self.shell = ShellRunner(config["repo_dir"])
        self.record = TaskRecord(config["record_file"])

    # ------------------------------------------------------------------ #
    # Internal helper – ALWAYS log, never raise
    # ------------------------------------------------------------------ #
    def _record(self, task: dict, state: str, extra: Dict[str, Any] | None = None) -> None:
        try:
            self.record.save(task, state=state, extra=extra or {})
        except TaskRecordError as e:
            print(f"[Record-Error] {e}", file=sys.stderr)

    # ------------------------------------------------------------------ #
    # Pretty-printing helpers
    # ------------------------------------------------------------------ #
    def show(self, status: str = "open", printout: bool = True):
        items = self.backlog.list_items(status)
        if printout:
            print(self._format_backlog(items))
        return items

    def _format_backlog(self, items):
        if not items:
            return "(Backlog empty)"
        from tabulate import tabulate

        rows = [
            (
                t["id"][:8],
                t.get("title", "")[:48],
                t.get("type", ""),
                t.get("status", ""),
                t.get("created_at", "")[:19],
            )
            for t in items
            if t.get("status") != "archived"
        ]
        headers = ["id", "title", "type", "status", "created"]
        return tabulate(rows, headers, tablefmt="github")

    # ------------------------------------------------------------------ #
    # Main workflow
    # ------------------------------------------------------------------ #
    def run_task_cycle(self, select_id: str | None = None, *, interactive: bool = True):
        """
        End-to-end flow for ONE micro-task.

        NEW BEHAVIOUR
            • Generates a reverse diff immediately after patch apply.
            • Any failure **before** commit triggers automatic rollback.
        """
        rollback_patch: str | None = None   # Will hold the *forward* patch
        task: dict | None = None            # current task for logging

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
                task = open_tasks[0]  # default: pick first open

            print(f"\n[Selected task: {task['id'][:8]}] {task.get('title')}\n")

            # 2. Build patch --------------------------------------------------
            self._record(task, "build_patch")
            try:
                patch = self.executor.build_patch(task)
                rollback_patch = patch  # Save for potential rollback
                self._record(task, "patch_built", {"patch": patch})
                print("--- Patch built ---\n", patch)
            except PatchBuildError as ex:
                self._record(task, "failed_build_patch", {"error": str(ex)})
                print(f"[X] Patch build failed: {ex}")
                return {"success": False, "stage": "build_patch", "error": str(ex)}

            # 3. Review -------------------------------------------------------
            review1 = self.reviewer.review_patch(patch, context=task)
            self._record(task, "patch_reviewed", {"review": review1})
            print("--- Review 1 ---")
            print(review1["comments"] or "(no comments)")
            if not review1["pass"]:
                self._record(task, "failed_patch_review", {"review": review1})
                print("[X] Patch failed review, aborting.")
                return {"success": False, "stage": "patch_review", "review": review1}

            # 4. Apply patch --------------------------------------------------
            try:
                self.shell.git_apply(patch)
                self._record(task, "patch_applied")
                print("[✔] Patch applied.")
            except ShellCommandError as ex:
                self._record(task, "failed_patch_apply", {"error": str(ex)})
                print(f"[X] git apply failed: {ex}")
                return {"success": False, "stage": "patch_apply", "error": str(ex)}

            # ------------------------------- #
            # --- CRITICAL SECTION BEGIN --- #
            # Any failure after this point MUST rollback before returning.
            # ------------------------------- #

            # 5. Run tests ----------------------------------------------------
            test_result = self.shell.run_pytest()
            self._record(task, "pytest_run", {"pytest": test_result})
            print("--- Pytest ---")
            print(test_result["output"])

            if not test_result["success"]:
                print("[X] Tests FAILED. Initiating rollback.")
                self._record(task, "failed_test", {"pytest": test_result})
                self._attempt_rollback(task, rollback_patch, src_stage="test")
                return {"success": False, "stage": "test", "test_result": test_result}

            # 6. (Optional) extra review could go here ------------------------

            # 7. Commit -------------------------------------------------------
            commit_msg = f"[Cadence] {task['id'][:8]} {task.get('title', '')}"
            try:
                sha = self.shell.git_commit(commit_msg)
                self._record(task, "committed", {"commit_sha": sha})
                print(f"[✔] Committed as {sha}")
            except ShellCommandError as ex:
                self._record(task, "failed_commit", {"error": str(ex)})
                print(f"[X] git commit failed: {ex}")
                # Commit failure ⇒ rollback
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
            # Catch-all safety net: attempt rollback if patch was applied
            if task and rollback_patch:
                self._attempt_rollback(task, rollback_patch, src_stage="unexpected", quiet=True)
            print(f"[X] Cycle failed: {ex}")
            return {"success": False, "error": str(ex)}

    # ------------------------------------------------------------------ #
    # Rollback helper
    # ------------------------------------------------------------------ #
    def _attempt_rollback(self, task: dict, patch: str | None, *, src_stage: str, quiet: bool = False):
        """
        Try to undo an applied patch.  Records outcome to TaskRecord.

        Args:
            task:       The current task dict (for logging).
            patch:      The *forward* patch previously applied.
            src_stage:  Where rollback was triggered (e.g., "test", "commit").
            quiet:      If True, suppress stdout noise (used in unexpected fail).
        """
        if not patch:
            # Defensive: nothing to rollback
            self._record(task, "rollback_skip_no_patch")
            return

        try:
            self.shell.git_apply(patch, reverse=True)
            self._record(task, f"failed_{src_stage}_and_rollback")
            if not quiet:
                print("[↩] Rollback successful – working tree restored.")
        except ShellCommandError as rb_ex:
            # CRITICAL: rollback failed – manual intervention required
            self._record(
                task,
                "critical_rollback_failure",
                {"trigger": src_stage, "rollback_error": str(rb_ex)},
            )
            print(f"[!!] Rollback FAILED – manual fix required: {rb_ex}")

    # ------------------------------------------------------------------ #
    # CLI dispatch helpers
    # ------------------------------------------------------------------ #
    def cli_entry(self, command: str, **kwargs):
        try:
            if command in ("backlog", "show"):
                return self.show(status=kwargs.get("status", "open"))
            if command == "start":
                return self.run_task_cycle(select_id=kwargs.get("id"))
            if command == "evaluate":
                return self.run_task_cycle(select_id=kwargs.get("id"))
            if command == "done":
                if "id" not in kwargs:
                    print("You must supply a task id for 'done'.")
                    return
                self.backlog.update_item(kwargs["id"], {"status": "done"})
                self.backlog.archive_completed()
                print(f"Task {kwargs['id']} marked as done and archived.")
                return
            print(f"Unknown command: {command}")
        except Exception as ex:
            print(f"[X] CLI command '{command}' failed: {ex}")

    # ------------------------------------------------------------------ #
    # Notebook / interactive helper
    # ------------------------------------------------------------------ #
    def _prompt_pick(self, n):
        while True:
            ans = input(f"Select task [0-{n-1}]: ")
            try:
                ix = int(ans)
                if 0 <= ix < n:
                    return ix
            except Exception:
                pass
            print("Invalid. Try again.")


# --------------------------------------------------------------------------- #
# Stand-alone execution (developer convenience)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    CONFIG = dict(
        backlog_path="dev_backlog.json",
        template_file="dev_templates.json",
        src_root="cadence",
        ruleset_file=None,
        repo_dir=".",
        record_file="dev_record.json",
    )
    orch = DevOrchestrator(CONFIG)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", help="show|start|evaluate|done")
    parser.add_argument("--id", default=None, help="Task id to use")
    args = parser.parse_args()

    orch.cli_entry(args.command or "show", id=args.id)