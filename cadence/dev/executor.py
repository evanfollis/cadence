# cadence/dev/executor.py

"""
Cadence TaskExecutor
-------------------
Single Responsibility: Given a task, produce a code/text patch (unapplied). Never applies, commits, or tests.
Extensible: can be subclassed or composed with LLM/crowd agents for codegen/refinement.
"""

import os
import difflib
import tempfile
from typing import Dict, Optional, List

class PatchBuildError(Exception):
    """Raised if patch/diff cannot be produced."""
    pass


class TaskExecutor:
    def __init__(self, src_root: str):
        if not os.path.isdir(src_root):
            raise ValueError(f"src_root '{src_root}' is not a directory.")
        self.src_root = os.path.abspath(src_root)

    def build_patch(self, task: Dict) -> str:
        """
        Given selected task (dict), produce diff/patch string.
        - For simplicity, expects 'file', 'before', 'after' in task['diff'].
        - Never applies patch.
        - Returns unified diff as UTF-8 str.
        """
        try:
            diff_info = task.get('diff')
            if not diff_info:
                raise PatchBuildError("Task missing 'diff' key. Task must include code diff directives.")

            file_rel = diff_info.get('file')
            before = diff_info.get('before')
            after = diff_info.get('after')
            if not file_rel or before is None or after is None:
                raise PatchBuildError("Diff dict must have 'file', 'before', and 'after' (as strings).")

            file_abs = os.path.join(self.src_root, file_rel)
            # Optionally validate file paths
            before_lines = before.splitlines(keepends=True)
            after_lines = after.splitlines(keepends=True)

            diff_lines = list(difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=file_rel,
                tofile=file_rel,
                lineterm=''
            ))
            patch = "".join(line + '\n' for line in diff_lines)
            if not patch.strip():
                raise PatchBuildError("Generated patch is empty.")

            # Logically, do NOT write/apply - that's ShellRunner's responsibility.
            return patch
        except Exception as e:
            raise PatchBuildError(f"Failed to build patch: {e}")

    def refine_patch(self, task: Dict, feedback: str) -> str:
        """
        Propose a revised patch, given task and feedback (from reviewer/human).
        Here, we're stubbed for simplicity - can be extended to call LLM/code agent.
        - Returns new diff/patch string.
        """
        # In a future agentic system, call out to LLM or microservice here with context.
        # Example hook: (pseudo) agent.generate_patch(task, feedback)
        # For now, just raise if not implemented.
        raise NotImplementedError("Patch refinement requires agent integration or human intervention.")

    # Optionally: you can add utility for validating a patch (not apply!).
    def validate_patch(self, patch: str) -> bool:
        """
        Returns True if patch is nontrivial and properly formatted.
        (Simple heuristic only; actual application/testing is ShellRunner's job.)
        """
        return bool(patch and patch.startswith('---'))

# Example CLI/dev usage
if __name__ == "__main__":
    # Example simulated task:
    executor = TaskExecutor(src_root="cadence")
    sample_task = {
        "id": "testid",
        "diff": {
            "file": "sample_module.py",
            "before": "# Old code\nprint('Hello')\n",
            "after":  "# Old code\nprint('Hello, world!')\n"
        }
    }
    patch = executor.build_patch(sample_task)
    print("--- PATCH OUTPUT ---")
    print(patch)