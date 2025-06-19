# cadence/dev/orchestrator.py

"""
Cadence DevOrchestrator
----------------------
Coordinated, single-point-of-control workflow runner
across backlog, generation, patching, review, shell, and record roles.
No cross-cutting, no skipped steps. 
Agent/extensible. Ready for CLI or notebook invocation.
"""

from .backlog import BacklogManager
from .generator import TaskGenerator
from .executor import TaskExecutor, PatchBuildError
from .reviewer import TaskReviewer
from .shell import ShellRunner, ShellCommandError
from .record import TaskRecord, TaskRecordError

import sys

class DevOrchestrator:
    def __init__(self, config: dict):
        self.backlog = BacklogManager(config["backlog_path"])
        self.generator = TaskGenerator(config.get("template_file"))
        self.executor = TaskExecutor(config["src_root"])
        self.reviewer = TaskReviewer(config.get("ruleset_file"))
        self.shell = ShellRunner(config["repo_dir"])
        self.record = TaskRecord(config["record_file"])

    # ----- Backlog overview -----
    def show(self, status: str = "open", printout: bool = True):
        """Print or return backlog overview."""
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
                t["id"][:8], t.get("title", "")[:48], t.get("type", ""),
                t.get("status", ""), t.get("created_at", "")[:19]
            )
            for t in items if t.get("status") != "archived"
        ]
        headers = ["id", "title", "type", "status", "created"]
        return tabulate(rows, headers, tablefmt="github")
    
    # ----- Main workflow -----
    def run_task_cycle(self, select_id: str = None, interactive: bool = True):
        """
        Full end-to-end workflow for one microtask:
        1. Select task
        2. Build patch
        3. Reviewer check
        4. Apply patch (git)
        5. Run pytest
        6. Reviewer final check (optional)
        7. git commit if passes; record everything
        8. Mark task done/archived if complete

        Args:
            select_id: If provided, pick directly; else let user pick interactively
            interactive: If True, allow prompts for selection/confirmation.
        Returns summary dict for the cycle.
        """
        try:
            # 1. Select Task
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

            # 2. Build a patch from executor
            self.record.save(task, state="build_patch")
            patch = self.executor.build_patch(task)
            self.record.save(task, state="patch_built", extra={"patch": patch})
            print("--- Patch built ---\n", patch)

            # 3. Reviewer initial check
            review1 = self.reviewer.review_patch(patch, context=task)
            self.record.save(task, state="patch_reviewed", extra={"review": review1})
            print("--- Review 1 ---")
            print(review1["comments"])
            if not review1["pass"]:
                print(f"[X] Patch failed review, aborting (state recorded).")
                return {"success": False, "stage": "patch_review", "review": review1}

            # 4. Apply patch via shell/git (never apply if review failed)
            applied = self.shell.git_apply(patch)
            self.record.save(task, state="patch_applied", extra={})
            print("[✔] Patch applied.")

            # 5. Run tests (pytest, whole repo or tests path)
            test_result = self.shell.run_pytest()
            self.record.save(task, state="pytest_run", extra={"pytest": test_result})
            print("--- Pytest ---")
            print(test_result["output"])
            if not test_result["success"]:
                print(f"[X] Tests FAILED, aborting before commit (state recorded).")
                return {"success": False, "stage": "test", "test_result": test_result}

            # 6. Final review (optional): can trigger another review step here
            # (out-of-scope for MVP—extend as needed for LLM/human gating)

            # 7. git commit, record commit SHA
            commit_msg = f"[Cadence] {task['id'][:8]} {task.get('title', '')}"
            sha = self.shell.git_commit(commit_msg)
            self.record.save(task, state="committed", extra={"commit_sha": sha})
            print(f"[✔] Committed as {sha}")

            # 8. Mark task done in backlog and archive
            self.backlog.update_item(task["id"], {"status": "done"})
            self.backlog.archive_completed()
            self.record.save(task, state="archived", extra={})
            print("[✔] Task marked done and archived.")

            return {"success": True, "commit": sha, "task_id": task["id"]}

        except Exception as ex:
            print(f"[X] Cycle failed: {ex}")
            return {"success": False, "error": str(ex)}

    # ----- CLI entry point -----
    def cli_entry(self, command: str, **kwargs):
        """
        Unified CLI dispatch. Supported commands: 'backlog', 'start', 'evaluate', 'done'
        """
        try:
            if command in ("backlog", "show"):
                return self.show(status=kwargs.get("status", "open"))
            elif command == "start":
                return self.run_task_cycle(select_id=kwargs.get("id"))
            elif command == "evaluate":  # could hook for custom test/review pipeline
                return self.run_task_cycle(select_id=kwargs.get("id"))
            elif command == "done":
                # Mark a task done and archive
                if "id" not in kwargs:
                    print("You must supply a task id for 'done'.")
                    return
                self.backlog.update_item(kwargs["id"], {"status": "done"})
                self.backlog.archive_completed()
                print(f"Task {kwargs['id']} marked as done and archived.")
                return
            else:
                print(f"Unknown command: {command}")
        except Exception as ex:
            print(f"[X] CLI command '{command}' failed: {ex}")

    # ----- Notebook-friendly -----
    # Provide direct API for notebook use:
    # e.g., orch.show(), orch.run_task_cycle(), ...

    # Helper for CLI interactive selection
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

# Example main/dev use:
if __name__ == "__main__":
    # Example config; adjust as needed per environment
    CONFIG = dict(
        backlog_path="dev_backlog.json",
        template_file="dev_templates.json",
        src_root="cadence",
        ruleset_file=None,
        repo_dir=".",
        record_file="dev_record.json"
    )
    orch = DevOrchestrator(CONFIG)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", help="show|start|evaluate|done")
    parser.add_argument("--id", default=None, help="Task id to use")
    args = parser.parse_args()
    orch.cli_entry(args.command or "show", id=args.id)