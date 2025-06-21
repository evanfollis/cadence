
# src/cadence/dev/shell.py

"""
Cadence ShellRunner
-------------------
Single Responsibility: Isolated safe shell/git/pytest operations, *never* creates code/diffs.
Never does role boundaries' work. All subprocesses run in isolated, safe manner.
"""

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

    def git_apply(self, patch: str) -> bool:
        """
        Applies patch to working tree using 'git apply'.
        Returns True if successful.
        Raises ShellCommandError if fail.
        """
        if not patch or not isinstance(patch, str):
            raise ShellCommandError("No patch supplied to apply.")
        # Write patch to a temp file to apply
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".patch", delete=False) as tf:
            tf.write(patch)
            tf.flush()
            tf_path = tf.name
        try:
            result = subprocess.run(
                ["git", "apply", tf_path],
                cwd=self.repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=False
            )
            if result.returncode != 0:
                raise ShellCommandError(f"git apply failed: {result.stderr.strip()}")
            return True
        finally:
            os.remove(tf_path)

    def run_pytest(self, test_path: Optional[str] = None) -> Dict:
        """
        Runs pytest on the given path (default: repo_dir or ./tests).
        Returns summary dict: {'success': bool, 'output': str}
        Raises ShellCommandError if pytest is not found.
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
                check=False
            )
            passed = (result.returncode == 0)
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            return {"success": passed, "output": output.strip()}
        except FileNotFoundError as e:
            raise ShellCommandError("pytest is not installed or not in PATH.") from e

    def git_commit(self, message: str) -> str:
        """
        Commits all staged/changed files with given commit message in repo_dir.
        Returns commit SHA string.
        Raises ShellCommandError on fail.
        """
        # Stage all (for MVP); fine-grained logic can be added if needed.
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False
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
            check=False
        )
        if result.returncode != 0:
            if "nothing to commit" in (result.stderr + result.stdout).lower():
                raise ShellCommandError("git commit: nothing to commit.")
            else:
                raise ShellCommandError(f"git commit failed: {result.stderr.strip()}")
        # Get last commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=True
        )
        sha = result.stdout.strip()
        return sha

# Example CLI/dev use
if __name__ == "__main__":
    runner = ShellRunner(".")
    # runner.git_apply('--- a/foo.py\n+++ b/foo.py\n...')  # Patch string
    # print(runner.run_pytest())
    # print(runner.git_commit("Demo commit"))