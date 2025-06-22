# src/cadence/dev/shell.py
"""
Cadence ShellRunner
-------------------

Additions in this revision
~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **Phase-order enforcement**
   • `git_apply`, `run_pytest`, and `git_commit` now cooperate with a
     lightweight tracker that guarantees commits cannot occur unless a
     patch has been applied *and* the test suite has passed.
2. **Patch pre-check**
   • `git_apply` performs `git apply --check` before mutating the
     working tree, aborting early if the diff’s *before* image does not
     match the current file contents.

Enforced invariants
-------------------
• patch_applied   – set automatically after a successful `git_apply`
• tests_passed    – set automatically after a green `run_pytest`
• committed       – set after `git_commit`

Commit is refused (ShellCommandError) unless **both**
`patch_applied` *and* `tests_passed` are present for the task.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional, Dict, List, Set

from .record import TaskRecord
from .phase_guard import enforce_phase, PhaseOrderError


class ShellCommandError(Exception):
    """Raised when a shell/git/pytest command fails."""


class ShellRunner:
    """
    Wrapper around common git / pytest commands **with automatic failure
    persistence** *and* runtime phase-order guarantees.
    """

    # ------------------------------------------------------------------ #
    # Construction / context helpers
    # ------------------------------------------------------------------ #
    def __init__(self, repo_dir: str = ".", *, task_record: TaskRecord | None = None):
        self.repo_dir = os.path.abspath(repo_dir)
        if not os.path.isdir(self.repo_dir):
            raise ValueError(
                f"repo_dir '{self.repo_dir}' does not exist or is not a directory."
            )

        # Recording context (may be None for stand-alone usage)
        self._record: TaskRecord | None = task_record
        self._current_task: dict | None = None

        # Phase-tracking:  task_id → {phase labels}
        self._phase_flags: Dict[str, Set[str]] = {}

    # ---- phase-tracking helpers ---------------------------------------
    def _init_phase_tracking(self, task_id: str) -> None:
        self._phase_flags.setdefault(task_id, set())

    def _mark_phase(self, task_id: str, phase: str) -> None:
        self._phase_flags.setdefault(task_id, set()).add(phase)

    def _has_phase(self, task_id: str, phase: str) -> bool:
        return phase in self._phase_flags.get(task_id, set())

    # ------------------------------------------------------------------ #
    def attach_task(self, task: dict | None):
        """
        Attach the *current* task dict so that failures inside any shell
        call can be persisted and phase order can be enforced.
        """
        self._current_task = task
        if task:
            self._init_phase_tracking(task["id"])

    # ------------------------------------------------------------------ #
    # Internal helper – persist failure snapshot (best-effort)
    # ------------------------------------------------------------------ #
    def _record_failure(
        self,
        *,
        state: str,
        error: Exception | str,
        output: str = "",
        cmd: List[str] | None = None,
    ):
        if not (self._record and self._current_task):
            return  # runner used outside orchestrated flow
        extra = {"error": str(error)}
        if output:
            extra["output"] = output.strip()
        if cmd:
            extra["cmd"] = " ".join(cmd)
        try:
            self._record.save(self._current_task, state=state, extra=extra)
        except Exception:  # noqa: BLE001 – failure recording must not raise
            pass

    # ------------------------------------------------------------------ #
    # Git patch helpers
    # ------------------------------------------------------------------ #
    @enforce_phase(mark="patch_applied")
    def git_apply(self, patch: str, *, reverse: bool = False) -> bool:
        """
        Apply a unified diff to the working tree *after* ensuring the
        patch cleanly applies via `git apply --check`.
        """
        stage = "git_apply_reverse" if reverse else "git_apply"

        if not patch or not isinstance(patch, str):
            err = ShellCommandError("No patch supplied to apply.")
            self._record_failure(state=f"failed_{stage}", error=err)
            raise err

        # Write patch to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".patch", delete=False
        ) as tf:
            tf.write(patch)
            tf.flush()
            tf_path = tf.name

        # --- pre-check --------------------------------------------------
        check_cmd: List[str] = ["git", "apply", "--check"]
        if reverse:
            check_cmd.append("-R")
        check_cmd.append(tf_path)
        result = subprocess.run(
            check_cmd,
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            err = ShellCommandError(
                f"Patch pre-check failed: {result.stderr.strip() or result.stdout.strip()}"
            )
            self._record_failure(
                state=f"failed_{stage}",
                error=err,
                output=(result.stderr or result.stdout),
                cmd=check_cmd,
            )
            os.remove(tf_path)
            raise err

        # --- actual apply ----------------------------------------------
        cmd: List[str] = ["git", "apply"]
        if reverse:
            cmd.append("-R")
        cmd.append(tf_path)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )

            if result.returncode != 0:
                raise ShellCommandError(
                    f"git apply failed: {result.stderr.strip() or result.stdout.strip()}"
                )
            return True

        except Exception as ex:  # noqa: BLE001 – blanket to ensure capture
            output = ""
            if "result" in locals():
                output = (result.stdout or "") + "\n" + (result.stderr or "")
            self._record_failure(
                state=f"failed_{stage}",
                error=ex,
                output=output,
                cmd=cmd,
            )
            raise
        finally:
            os.remove(tf_path)

    # ------------------------------------------------------------------ #
    # Testing helpers
    # ------------------------------------------------------------------ #
    def run_pytest(self, test_path: Optional[str] = None) -> Dict:
        """
        Run pytest on the given path (default: ./tests).

        Success automatically marks the *tests_passed* phase.
        Returns {'success': bool, 'output': str}
        """
        stage = "pytest"
        path = test_path or os.path.join(self.repo_dir, "tests")
        if not os.path.exists(path):
            err = ShellCommandError(f"Tests path '{path}' does not exist.")
            self._record_failure(state=f"failed_{stage}", error=err)
            raise err

        cmd = ["pytest", "-q", path]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )
            passed = result.returncode == 0
            output = (result.stdout or "") + "\n" + (result.stderr or "")

            if passed and self._current_task:
                self._mark_phase(self._current_task["id"], "tests_passed")

            if not passed:
                # Persist *test* failure even though we don't raise here
                self._record_failure(
                    state="failed_pytest", error="pytest failed", output=output, cmd=cmd
                )
            return {"success": passed, "output": output.strip()}

        except Exception as ex:
            self._record_failure(state=f"failed_{stage}", error=ex)
            raise

    # ------------------------------------------------------------------ #
    # Commit helper
    # ------------------------------------------------------------------ #
    def git_commit(self, message: str) -> str:
        """
        Commit **all** staged/changed files with the given commit message.

        Phase-guard: refuses to commit unless *patch_applied* **and**
        *tests_passed* are recorded for the current task.
        Returns the new commit SHA string.
        """
        stage = "git_commit"

        # ---- phase-order enforcement -----------------------------------
        if self._current_task:
            tid = self._current_task["id"]
            missing: List[str] = []
            if not self._has_phase(tid, "patch_applied"):
                missing.append("patch_applied")
            if not self._has_phase(tid, "tests_passed"):
                missing.append("tests_passed")
            if missing:
                err = ShellCommandError(
                    f"Cannot commit – missing prerequisite phase(s): {', '.join(missing)}"
                )
                self._record_failure(state=f"failed_{stage}", error=err)
                raise err

        def _run(cmd: List[str]):
            return subprocess.run(
                cmd,
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )

        try:
            # Stage all changes
            add_cmd = ["git", "add", "-A"]
            result = _run(add_cmd)
            if result.returncode != 0:
                raise ShellCommandError(f"git add failed: {result.stderr.strip()}")

            # Commit
            commit_cmd = ["git", "commit", "-m", message]
            result = _run(commit_cmd)
            if result.returncode != 0:
                if "nothing to commit" in (result.stderr + result.stdout).lower():
                    raise ShellCommandError("git commit: nothing to commit.")
                raise ShellCommandError(f"git commit failed: {result.stderr.strip()}")

            # Retrieve last commit SHA
            sha_cmd = ["git", "rev-parse", "HEAD"]
            result = subprocess.run(
                sha_cmd,
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=True,
            )

            # Mark phase completed
            if self._current_task:
                self._mark_phase(self._current_task["id"], "committed")

            return result.stdout.strip()

        except Exception as ex:
            self._record_failure(
                state=f"failed_{stage}",
                error=ex,
                output=(result.stderr if "result" in locals() else ""),
            )
            raise


# --------------------------------------------------------------------------- #
# Dev-only sanity CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    runner = ShellRunner(".", task_record=None)  # no persistence
    print("ShellRunner loaded. No CLI demo.")