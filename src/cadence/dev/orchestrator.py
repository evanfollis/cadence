# src/cadence/dev/orchestrator.py
"""
Cadence DevOrchestrator
-----------------------
Integrated union of all prior versions.

Key capabilities
~~~~~~~~~~~~~~~~
• Auto-replenishes an empty backlog with micro-tasks.  
• Persists *every* state transition to TaskRecord; ShellRunner
  self-records failures after `.attach_task()`.  
• Two-stage human-style review:
    1. **Reasoning** review via `TaskReviewer`.
    2. **Efficiency** review via `EfficiencyAgent` (LLM).  
• Safe patch application with automatic rollback on test/commit failure.  
• **MetaAgent** governance layer records post-cycle telemetry for audit /
  policy-checking (gated by `config['enable_meta']`, default =True).  
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

import tabulate  # noqa: F401 – needed by _format_backlog

from cadence.agents.registry import get_agent  # EfficiencyAgent
from .backlog import BacklogManager
from .executor import PatchBuildError, TaskExecutor, TaskExecutorError
from .generator import TaskGenerator
from .record import TaskRecord, TaskRecordError
from .reviewer import TaskReviewer
from .shell import ShellRunner, ShellCommandError

# --------------------------------------------------------------------------- #
# Meta-governance stub
# --------------------------------------------------------------------------- #
class MetaAgent:
    """Light-weight governance / analytics layer (MVP stub)."""

    def __init__(self, task_record: TaskRecord):
        self.task_record = task_record

    def analyse(self, run_summary: dict) -> dict:  # noqa: D401
        """Return minimal telemetry; insert richer checks later."""
        return {
            "telemetry": run_summary.copy(),
            "policy_check": "stub",
            "meta_ok": True,
        }


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class DevOrchestrator:
    def __init__(self, config: dict):
        # Core collaborators -------------------------------------------------
        self.backlog = BacklogManager(config["backlog_path"])
        self.generator = TaskGenerator(config.get("template_file"))
        self.record = TaskRecord(config["record_file"])
        self.shell = ShellRunner(config["repo_dir"], task_record=self.record)
        self.executor = TaskExecutor(config["src_root"])
        self.reviewer = TaskReviewer(config.get("ruleset_file"))

        # Agents -------------------------------------------------------------
        self.efficiency = get_agent("efficiency")
        self._enable_meta: bool = config.get("enable_meta", True)
        self.meta_agent: Optional[MetaAgent] = (
            MetaAgent(self.record) if self._enable_meta else None
        )

        # Behaviour toggles --------------------------------------------------
        self.backlog_autoreplenish_count: int = config.get(
            "backlog_autoreplenish_count", 3
        )

    # ------------------------------------------------------------------ #
    # Back-log auto-replenishment
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
    # Record helper – ALWAYS log, never raise
    # ------------------------------------------------------------------ #
    def _record(
        self, task: dict, state: str, extra: Dict[str, Any] | None = None
    ) -> None:
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
        return tabulate.tabulate(rows, headers, tablefmt="github")

    # ------------------------------------------------------------------ #
    # Main workflow
    # ------------------------------------------------------------------ #
    def run_task_cycle(
        self, select_id: str | None = None, *, interactive: bool = False
    ):
        """
        Run **one** micro-task end-to-end with:

        • auto-replenish ⟶ dual Reasoning+Efficiency reviews ⟶ tests ⟶ commit  
        • auto-rollback on failure  
        • MetaAgent post-run analysis (non-blocking)  
        """
        self._ensure_backlog()
        rollback_patch: str | None = None
        task: dict | None = None
        run_result: Dict[str, Any] | None = None

        try:
            # 1️⃣  Select task ------------------------------------------------
            open_tasks = self.backlog.list_items("open")
            if not open_tasks:
                raise RuntimeError("No open tasks in backlog.")

            if select_id:
                task = next((t for t in open_tasks if t["id"] == select_id), None)
                if not task:
                    raise RuntimeError(f"Task id '{select_id}' not found.")
            elif interactive:
                print(self._format_backlog(open_tasks))
                print("---")
                task = open_tasks[self._prompt_pick(len(open_tasks))]
            else:
                task = open_tasks[0]

            print(f"\n[Selected task: {task['id'][:8]}] {task.get('title')}\n")
            self.shell.attach_task(task)  # allow ShellRunner to self-record

            # 2️⃣  Build patch -----------------------------------------------
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

            # 3️⃣  Review #1 – Reasoning ------------------------------------
            review1 = self.reviewer.review_patch(patch, context=task)
            # keep legacy state for the test-suite
            self._record(task, "patch_reviewed",             {"review": review1})
            self._record(task, "patch_reviewed_reasoning",   {"review": review1})
            print("--- Review 1 (Reasoning) ---")
            print(review1["comments"] or "(no comments)")
            if not review1["pass"]:
                self._record(task, "failed_patch_review_reasoning", {"review": review1})
                print("[X] Patch failed REASONING review, aborting.")
                return {
                    "success": False,
                    "stage": "patch_review_reasoning",
                    "review": review1,
                }

            # 4️⃣  Review #2 – Efficiency ------------------------------------
            # Skip hard-LLM step in stub-mode so CI remains offline-safe
            if getattr(self.efficiency.llm_client, "stub", False):
                eff_raw  = "LLM stub-mode: efficiency review skipped."
                eff_pass = True
                if eff_pass and hasattr(self.shell, "_mark_phase"):
                    self.shell._mark_phase(task["id"], "efficiency_passed")
            else:
                eff_prompt = (
                    "You are the EfficiencyAgent for the Cadence workflow.\n"
                    "Review the diff below for best-practice, lint, and summarisation.\n"
                    f"DIFF:\n{patch}\n\nTASK CONTEXT:\n{task}"
                )
                eff_raw = self.efficiency.run_interaction(eff_prompt)

                # Treat review as FAILED only when the assistant gives an
                # explicit block / reject marker. A mere occurrence of the
                # word “fail” in prose should not veto the patch.
                _block_tokens = ("[[fail]]", "block", "rejected", "❌", "do not merge")
                eff_pass = not any(tok in eff_raw.lower() for tok in _block_tokens)

            # Record flag for downstream phase-guards
            if eff_pass and hasattr(self.shell, "_mark_phase") and task.get("id"):
                self.shell._mark_phase(task["id"], "efficiency_passed")
            eff_review = {"pass": eff_pass, "comments": eff_raw}
            self._record(task, "patch_reviewed_efficiency", {"review": eff_review})
            print("--- Review 2 (Efficiency) ---")
            print(eff_review["comments"] or "(no comments)")
            if not eff_pass:
                self._record(task, "failed_patch_review_efficiency", {"review": eff_review})
                print("[X] Patch failed EFFICIENCY review, aborting.")
                return {
                    "success": False,
                    "stage": "patch_review_efficiency",
                    "review": eff_review,
                }

            # # Optional phase marker for advanced ShellRunner integrations ----
            # if hasattr(self.shell, "_mark_phase") and task.get("id"):
            #     self.shell._mark_phase(task["id"], "efficiency_passed")

            # 5️⃣  Apply patch -----------------------------------------------
            try:
                self.shell.git_apply(patch)
                self._record(task, "patch_applied")
                print("[✔] Patch applied.")
            except ShellCommandError as ex:
                self._record(task, "failed_patch_apply", {"error": str(ex)})
                print(f"[X] git apply failed: {ex}")
                return {"success": False, "stage": "patch_apply", "error": str(ex)}

            # 6️⃣  Run tests --------------------------------------------------
            test_result = self.shell.run_pytest()
            self._record(task, "pytest_run", {"pytest": test_result})
            print("--- Pytest ---")
            print(test_result["output"])
            if not test_result["success"]:
                print("[X] Tests FAILED. Initiating rollback.")
                self._record(task, "failed_test", {"pytest": test_result})
                self._attempt_rollback(task, rollback_patch, src_stage="test")
                return {"success": False, "stage": "test", "test_result": test_result}

            # 7️⃣  Commit -----------------------------------------------------
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

            # 8️⃣  Mark done & archive ---------------------------------------
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

        # ------------------------------------------------------------------ #
        # MetaAgent post-cycle analysis (non-blocking)
        # ------------------------------------------------------------------ #
        finally:
            if self._enable_meta and self.meta_agent and task:
                try:
                    meta_result = self.meta_agent.analyse(run_result or {})
                    # append_iteration keeps the last history entry untouched
                    self.record.append_iteration(task["id"],
                                                {"phase": "meta_analysis",
                                                "payload": meta_result})
                except Exception as meta_ex:   # pragma: no cover
                    print(f"[MetaAgent-Error] {meta_ex}", file=sys.stderr)

    # ------------------------------------------------------------------ #
    # Rollback helper
    # ------------------------------------------------------------------ #
    def _attempt_rollback(
        self, task: dict, patch: str | None, *, src_stage: str, quiet: bool = False
    ):
        if not patch:
            self._record(task, "rollback_skip_no_patch")
            return
        try:
            self.shell.git_apply(patch, reverse=True)
            self._record(task, f"failed_{src_stage}_and_rollback")
            if not quiet:
                print("[↩] Rollback successful – working tree restored.")
        except ShellCommandError as rb_ex:
            self._record(
                task,
                "critical_rollback_failure",
                {"trigger": src_stage, "rollback_error": str(rb_ex)},
            )
            print(f"[!!] Rollback FAILED – manual fix required: {rb_ex}")

    # ------------------------------------------------------------------ #
    # CLI helpers
    # ------------------------------------------------------------------ #
    def cli_entry(self, command: str, **kwargs):
        try:
            if command in ("backlog", "show"):
                return self.show(status=kwargs.get("status", "open"))
            if command in ("start", "evaluate"):
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

    def _prompt_pick(self, n: int) -> int:
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
# Stand-alone execution helper
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    CONFIG = dict(
        backlog_path="dev_backlog.json",
        template_file="dev_templates.json",
        src_root="cadence",
        ruleset_file=None,
        repo_dir=".",
        record_file="dev_record.json",
        enable_meta=True,
        backlog_autoreplenish_count=3,
    )
    orch = DevOrchestrator(CONFIG)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", help="show|start|evaluate|done")
    parser.add_argument("--id", default=None, help="Task id to use")
    parser.add_argument(
        "--backlog-autoreplenish-count",
        type=int,
        default=3,
        help="Number of micro-tasks to auto-generate when backlog is empty.",
    )
    parser.add_argument(
        "--disable-meta",
        action="store_true",
        help="Disable MetaAgent execution for this session.",
    )
    args = parser.parse_args()

    orch.backlog_autoreplenish_count = args.backlog_autoreplenish_count
    if args.disable_meta:
        orch._enable_meta = False
        orch.meta_agent = None

    orch.cli_entry(args.command or "show", id=args.id)
