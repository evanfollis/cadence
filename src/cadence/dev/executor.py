# src/cadence/dev/executor.py
"""
Cadence TaskExecutor
--------------------
Now guarantees every generated patch ends with a final newline, fixing the
`git apply` “corrupt patch” error that occurred on some modified-file
diffs containing trailing context lines.
"""

from __future__ import annotations

import os
import difflib
from typing import Dict, List

class PatchBuildError(Exception):
    pass


class TaskExecutor:
    def __init__(self, src_root: str):
        if not os.path.isdir(src_root):
            raise ValueError(f"src_root '{src_root}' is not a directory.")
        self.src_root = os.path.abspath(src_root)

    # ------------------------------------------------------------------ #
    def build_patch(self, task: Dict) -> str:
        # >>> NEW: accept a pre-computed raw patch <<<
        raw = task.get("patch")
        if isinstance(raw, str) and raw.strip():
            return raw.strip() + ("\n" if not raw.endswith("\n") else "")
        try:
            diff_info = task.get("diff")
            if not diff_info:
                raise PatchBuildError("Task missing 'diff' key.")

            file_rel = diff_info.get("file", "")
            before   = diff_info.get("before")
            after    = diff_info.get("after")
            if not file_rel or before is None or after is None:
                raise PatchBuildError("Diff dict must contain 'file', 'before', 'after'.")

            # --- normalise line endings -----------------------------------
            if before and not before.endswith("\n"):
                before += "\n"
            if after and not after.endswith("\n"):
                after += "\n"

            before_lines: List[str] = before.splitlines(keepends=True) if before else []
            after_lines:  List[str] = after.splitlines(keepends=True)  if after  else []

            new_file    = len(before_lines) == 0 and len(after_lines) > 0
            delete_file = len(before_lines) > 0 and len(after_lines) == 0

            fromfile = "/dev/null" if new_file else f"a/{file_rel}"
            tofile   = "/dev/null" if delete_file else f"b/{file_rel}"

            diff_lines = list(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=fromfile,
                    tofile=tofile,
                    # default lineterm="\n"
                )
            )

            patch = "".join(diff_lines)
            # Ensure the patch ends with *exactly* one \n ─ git is picky.
            if not patch.endswith("\n"):
                patch += "\n"

            if not patch.strip():
                raise PatchBuildError("Generated patch is empty.")

            return patch

        except Exception as e:
            raise PatchBuildError(f"Failed to build patch: {e}")

    # unchanged helpers …
    def refine_patch(self, task: Dict, feedback: str) -> str:
        raise NotImplementedError

    def validate_patch(self, patch: str) -> bool:
        return bool(patch and patch.startswith(("---", "diff ", "@@")))


# --------------------------------------------------------------------------- #
# Quick manual demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    executor = TaskExecutor(src_root=".")
    print(
        executor.build_patch(
            {
                "diff": {
                    "file": "demo.txt",
                    "before": "",
                    "after": "hello\nworld\n",
                }
            }
        )
    )