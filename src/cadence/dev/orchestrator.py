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

import os
import sys
from typing import Any, Dict, Optional
from datetime import datetime, UTC
import uuid
import hashlib
from pathlib import Path
import tabulate  # noqa: F401 – needed by _format_backlog

from cadence.agents.registry import get_agent  # EfficiencyAgent
from .backlog import BacklogManager
from .change_set import ChangeSet
from .executor import PatchBuildError, TaskExecutor, TaskExecutorError
from .generator import TaskGenerator
from .record import TaskRecord, TaskRecordError
from .reviewer import TaskReviewer
from .shell import ShellRunner, ShellCommandError
from cadence.llm.json_call import LLMJsonCaller
from cadence.dev.schema import CHANGE_SET_V1, EFFICIENCY_REVIEW_V1
from cadence.context.provider import SnapshotContextProvider
from .failure_responder import FailureResponder

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
    def __init__(self, config: dict | None = None):
        if config is None:
            import json
            cfg_path = Path(__file__).resolve().parents[3] / "dev_config.json"
            config = json.loads(cfg_path.read_text())
            root = cfg_path.parent
            for key in ("backlog_path", "src_root", "repo_dir", "record_file", "template_file", "ruleset_file"):
                if key in config and config[key] is not None and not os.path.isabs(str(config[key])):
                    config[key] = str((root / config[key]).resolve())
        # Core collaborators -------------------------------------------------
        self.backlog = BacklogManager(config["backlog_path"])
        self.generator = TaskGenerator(config.get("template_file"))
        self.record = TaskRecord(config["record_file"])
        self.shell = ShellRunner(config["repo_dir"], task_record=self.record)
        self.executor = TaskExecutor(config["src_root"])
        self.reviewer = TaskReviewer(config.get("ruleset_file"))
        self.failure_responder = FailureResponder(config.get("backlog_path","dev_backlog.json"))

        # Agents -------------------------------------------------------------
        self.efficiency = get_agent("efficiency")
        self.planner = get_agent("reasoning")

        # JSON caller for blueprint → ChangeSet generation
        self._cs_json = LLMJsonCaller(schema=CHANGE_SET_V1)  # function-call mode
        # If we’re on-line (not stub-mode) prepare a structured-JSON caller
        self._eff_json: LLMJsonCaller | None = None
        if not getattr(self.efficiency.llm_client, "stub", False):
            self._eff_json = LLMJsonCaller(
                schema=EFFICIENCY_REVIEW_V1,
                function_name="efficiency_review",
            )

        self._enable_meta: bool = config.get("enable_meta", True)
        self.meta_agent: Optional[MetaAgent] = (
            MetaAgent(self.record) if self._enable_meta else None
        )

        # Behaviour toggles --------------------------------------------------
        self.backlog_autoreplenish_count: int = config.get(
            "backlog_autoreplenish_count", 3
        )

    # ------------------------------------------------------------------ #
    # Blueprint → micro-task expansion
    # ------------------------------------------------------------------ #
    def _expand_blueprint(self, bp: dict) -> list[dict]:
        # 0) always start with fresh context
        self.planner.reset_context()

        title = bp.get("title", "")
        desc  = bp.get("description", "")
        snapshot = SnapshotContextProvider().get_context(
            Path("src/cadence"), Path("docs"), Path("tools"), Path("tests"),
            exts=(".py", ".md", ".json", ".mermaid", ".txt", ".yaml", ".yml"),
        )

        sys_prompt = (
            "You are Cadence ReasoningAgent.  "
            "Convert the blueprint (title + description) into exactly ONE "
            "ChangeSet JSON object that follows the CadenceChangeSet schema.  "
            "Return JSON only—no markdown fencing."
        )
        user_prompt = (
            f"BLUEPRINT_TITLE:\n{title}\n\nBLUEPRINT_DESC:\n{desc}\n"
            "---\nCODE_SNAPSHOT:\n{snapshot}\n"
        )

        # ---------------------------------------------------------------
        # 2) Call the planner’s LLM client *through* the existing
        #    LLMJsonCaller so we keep schema validation & retry logic.
        #    We do this by cloning the caller and swapping its .llm
        #    attribute.
        # ---------------------------------------------------------------
        planner_caller = LLMJsonCaller(schema=CHANGE_SET_V1)
        planner_caller.llm = self.planner.llm_client

        obj   = planner_caller.ask(sys_prompt, user_prompt)
        cset  = ChangeSet.from_dict(obj)

        micro_task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "type": "micro",
            "status": "open",
            "created_at": datetime.now(UTC).isoformat(),
            "change_set": cset.to_dict(),
            "parent_id": bp["id"],
        }
        self.backlog.add_item(micro_task)
        return [micro_task]

    # ------------------------------------------------------------------ #
    # Back-log auto-replenishment
    # ------------------------------------------------------------------ #
    def _ensure_backlog(self, count: Optional[int] = None) -> None:
        """
        1)  Convert ANY high-level planning item ( blueprint | story | epic )
            that does *not* yet contain concrete patch material into **one**
            micro-task by delegating to _expand_blueprint().  After expansion
            the parent task is archived so the backlog never presents a
            non-executable item to the selector.

        2)  If the backlog is still empty after the conversions, fall back to
            automatic stub micro-task generation (old behaviour).
        """

        convertible = ("blueprint", "story", "epic")
        for bp in [
            t
            for t in self.backlog.list_items("open")
            if t.get("type") in convertible
            and not any(k in t for k in ("change_set", "diff", "patch"))
        ]:
            created = self._expand_blueprint(bp)
            self.backlog.update_item(bp["id"], {"status": "archived"})
            self.record.save(bp, state="blueprint_converted",
                             extra={"generated": [t["id"] for t in created]})

        # 2️⃣  if still no open tasks → auto-generate stub micro tasks
        if not self.backlog.list_items("open"):
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
        # Always start with an up-to-date context for every LLM agent
        for ag in (self.efficiency, self.planner):          # extend when more live agents appear
            try:
                ag.reset_context()
            except Exception:                  # noqa: BLE001 – never abort the run
                pass

        self._ensure_backlog()
        rollback_patch: str | None = None
        task: dict | None = None
        run_result: Dict[str, Any] | None = None

        try:
            # 1️⃣  Select task ------------------------------------------------
            open_tasks = self.backlog.list_items("open")

            # Only tasks that *actually* contain patch material are executable
            executable = [
                t for t in open_tasks
                if any(k in t for k in ("change_set", "diff", "patch"))
            ]

            if not executable:
                raise RuntimeError("No open tasks in backlog.")

            if select_id:
                task = next((t for t in open_tasks if t["id"] == select_id), None)
                if not task:
                    raise RuntimeError(f"Task id '{select_id}' not found.")
            elif interactive:
                print(self._format_backlog(executable))
                print("---")
                task = executable[self._prompt_pick(len(executable))]
            else:
                task = executable[0]

            print(f"\n[Selected task: {task['id'][:8]}] {task.get('title')}\n")
            self.shell.attach_task(task)  # allow ShellRunner to self-record

            # --- Branch isolation (NEW) ---------------------------------
            branch = f"task-{task['id'][:8]}"
            try:
                self.shell.git_checkout_branch(branch)
                # self._record(task, "branch_isolated", {"branch": branch})
            except ShellCommandError as ex:
                self._record(task, "failed_branch_isolation", {"error": str(ex)})
                return {"success": False, "stage": "branch_isolation", "error": str(ex)}

            # ── 2️⃣  Build patch ─────────────────────────────────────────────
            self._record(task, "build_patch")
            try:
                patch = self.executor.build_patch(task)

            except TaskExecutorError as ex:
                msg = str(ex).lower()

                # empty diff → treat as failure to ensure audit trail matches expectations
                if "empty diff" in msg:
                    self._record(task, "failed_build_patch", {"error": str(ex)})
                    print("[X] Patch build failed:", ex)
                    return {"success": False, "stage": "build_patch", "error": str(ex)}

                # change-set malformed  → block + fail
                if "after" in msg and "mode=modify" in msg:
                    self.backlog.update_item(task["id"], {"status": "blocked"})
                    self._record(task, "invalid_change_set", {"error": str(ex)})
                    print(f"[X] Invalid ChangeSet: {ex}")
                    return {
                        "success": False,
                        "stage": "change_set_validation",
                        "error": str(ex),
                    }

                # otherwise fail hard
                self._record(task, "failed_build_patch", {"error": str(ex)})
                print(f"[X] Patch build failed: {ex}")
                return {
                    "success": False,
                    "stage": "build_patch",
                    "error": str(ex),
                }

            except PatchBuildError as ex:
                self._record(task, "failed_build_patch", {"error": str(ex)})
                print(f"[X] Patch build failed: {ex}")
                return {
                    "success": False,
                    "stage": "build_patch",
                    "error": str(ex),
                }

            # success path
            rollback_patch = patch
            self._record(task, "patch_built", {"patch": patch})
            print("--- Patch built ---\n", patch)


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
            # phase flag for commit-guard
            self.shell._mark_phase(task["id"], "review_passed")

            # 4️⃣  Review #2 – Efficiency ------------------------------------
            # Skip hard-LLM step in stub-mode so CI remains offline-safe
            if getattr(self.efficiency.llm_client, "stub", False):
                eff_raw  = "LLM stub-mode: efficiency review skipped."
                eff_pass = True
                if eff_pass and hasattr(self.shell, "_mark_phase"):
                    self.shell._mark_phase(task["id"], "efficiency_passed")
            else:
                # -------- Structured JSON path ----------------------------------
                if self._eff_json:
                    sys_prompt = (
                        "You are the Cadence EfficiencyAgent.  "
                        "Return ONLY a JSON object matching the EfficiencyReview schema."
                    )
                    user_prompt = (
                        f"DIFF:\n{patch}\n\nTASK CONTEXT:\n{task}\n"
                        "If the diff should be accepted set pass_review=true, "
                        "otherwise false."
                    )
                    try:
                        eff_obj = self._eff_json.ask(sys_prompt, user_prompt)
                        eff_pass = bool(eff_obj["pass_review"])
                        eff_raw  = eff_obj["comments"]
                    except Exception as exc:      # JSON invalid → degrade gracefully
                        eff_raw  = f"[fallback-to-text] {exc}"
                        eff_pass = True
                else:
                    # -------- Legacy heuristic path (stub-mode) -----------------
                    eff_prompt = (
                        "You are the EfficiencyAgent for the Cadence workflow.\n"
                        "Review the diff below for best-practice, lint, and summarisation.\n"
                        f"DIFF:\n{patch}\n\nTASK CONTEXT:\n{task}"
                    )
                    eff_raw = self.efficiency.run_interaction(eff_prompt)

                    _block_tokens = ("[[fail]]", "rejected", "❌", "do not merge")
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
            
            # ---- hot-fix: update before_sha in remaining open tasks
            changed = {
                e["path"]
                for e in task.get("change_set", {}).get("edits", [])
            }
            file_shas = {}
            for p in changed:
                f = Path(self.executor.src_root) / p
                if f.exists():
                    file_shas[p] = hashlib.sha1(f.read_bytes()).hexdigest()
            self.executor.propagate_before_sha(file_shas, self.backlog)

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
    # Rollback helper – always records the outcome
    # ------------------------------------------------------------------ #
    def _attempt_rollback(
        self,
        task: dict | None = None,
        patch: str | None = None,
        *,
        src_stage: str = "manual",
        quiet: bool = False,
    ) -> None:
        """
        Revert the working tree to its pristine state after a failure in
        *src_stage*.  All outcomes are persisted to TaskRecord so the
        integration test can assert `"rollback_succeeded"` is present.
        """
        if task:
            self._record(task, "rollback_started", {"from_stage": src_stage})

        try:
            # Unstage & discard everything – no commit exists yet
            self.shell.git_reset_hard("HEAD")
            if task:
                self._record(task, "rollback_succeeded")
            if not quiet:
                print("[↩] Rollback successful – working tree restored.")

        except ShellCommandError as ex:
            if task:
                self._record(task, "rollback_failed", {"error": str(ex)})
            if not quiet:
                print(f"[X] Rollback FAILED: {ex}")
            if not quiet:
                raise

        # 🌱 auto-generate follow-up remediation tasks
        if task:
            try:
                self.failure_responder.handle_failure(task, src_stage)
            except Exception as fr_exc:  # pragma: no cover - best effort
                print(f"[FailureResponder-Error] {fr_exc}", file=sys.stderr)


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