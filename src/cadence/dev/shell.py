# src/cadence/dev/shell.py
"""
Cadence ShellRunner
-------------------
Single Responsibility
    • Provide *safe*, auditable wrappers around git / pytest / shell
      commands.  
    • **NEW** – Support reverse-applying a patch (rollback) via the same
      entry-point by passing `reverse=True`.

Never creates code or diffs; only executes them.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional, Dict


class ShellCommandError(Exception):
    """Raised when a shell/git/pytest command fails."""
    pass


class ShellRunner:
    def __init__(self, repo_dir: str = "."):
        self.repo_dir = os.path.abspath(repo_dir)
        if not os.path.isdir(self.repo_dir):
            raise ValueError(f"repo_dir '{self.repo_dir}' does not exist or is not a directory.")

    # ------------------------------------------------------------------ #
    # Git patch helpers
    # ------------------------------------------------------------------ #
    def git_apply(self, patch: str, *, reverse: bool = False) -> bool:
        """
        Apply a unified diff to the working tree.

        Args:
            patch:   Unified diff string (UTF-8).
            reverse: If True, apply the patch in *reverse* (equivalent to
                     `git apply -R`) – used for automatic rollback.

        Returns:
            True on success.

        Raises:
            ShellCommandError on any git failure or invalid patch input.
        """
        if not patch or not isinstance(patch, str):
            raise ShellCommandError("No patch supplied to apply.")

        # Write patch to a temporary file so git can consume it.
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".patch", delete=False) as tf:
            tf.write(patch)
            tf.flush()
            tf_path = tf.name

        try:
            cmd = ["git", "apply"]
            if reverse:
                cmd.append("-R")
            cmd.append(tf_path)

            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )
            if result.returncode != 0:
                direction = "reverse " if reverse else ""
                raise ShellCommandError(
                    f"git {direction}apply failed: {result.stderr.strip() or result.stdout.strip()}"
                )
            return True
        finally:
            os.remove(tf_path)

    # ------------------------------------------------------------------ #
    # Testing helpers
    # ------------------------------------------------------------------ #
    def run_pytest(self, test_path: Optional[str] = None) -> Dict:
        """
        Run pytest on the given path (default: ./tests).

        Returns:
            {'success': bool, 'output': str}
        """
        path = test_path or os.path.join(self.repo_dir, "tests")
        if not os.path.exists(path):
            raise ShellCommandError(f"Tests path '{path}' does not exist.")

        try:
            result = subprocess.run(
                ["pytest", "-q", path],
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )
            passed = result.returncode == 0
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            return {"success": passed, "output": output.strip()}
        except FileNotFoundError as e:
            raise ShellCommandError("pytest is not installed or not in PATH.") from e

    # ------------------------------------------------------------------ #
    # Commit helper
    # ------------------------------------------------------------------ #
    def git_commit(self, message: str) -> str:
        """
        Commit **all** staged/changed files with the given commit message.

        Returns:
            The new commit SHA string.

        Raises:
            ShellCommandError on failure (e.g., nothing to commit).
        """
        # Stage all changes (MVP behaviour)
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            raise ShellCommandError(f"git add failed: {result.stderr.strip()}")

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            if "nothing to commit" in (result.stderr + result.stdout).lower():
                raise ShellCommandError("git commit: nothing to commit.")
            raise ShellCommandError(f"git commit failed: {result.stderr.strip()}")

        # Retrieve last commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=True,
        )
        return result.stdout.strip()


# --------------------------------------------------------------------------- #
# Dev-only sanity CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    runner = ShellRunner(".")
    # Example usage:
    # runner.git_apply(patch_string)
    # runner.git_apply(patch_string, reverse=True)  # rollback