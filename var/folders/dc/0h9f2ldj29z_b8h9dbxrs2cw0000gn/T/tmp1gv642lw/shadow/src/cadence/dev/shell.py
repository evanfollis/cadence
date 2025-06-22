# src/cadence/dev/shell.py
"""
Cadence ShellRunner
-------------------
Now requires 'efficiency_passed' phase before allowing commit.
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
    # ... [unchanged constructors and helpers] ...

    # ... [other code unchanged] ...

    # ------------------------------------------------------------------ #
    # Commit helper
    # ------------------------------------------------------------------ #
    def git_commit(self, message: str) -> str:
        """
        Commit **all** staged/changed files with the given commit message.
        Phase-guard: refuses to commit unless *patch_applied*, *tests_passed*, and *efficiency_passed* are recorded for the current task.
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
            if not self._has_phase(tid, "efficiency_passed"):
                missing.append("efficiency_passed")
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
    # ... [remaining methods unchanged] ...
