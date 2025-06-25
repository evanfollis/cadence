# src/cadence/dev/executor.py
"""
Cadence TaskExecutor
--------------------

Consumes *structured* ChangeSets in addition to raw diffs.  Priority:

    1. task["patch"]      – already-built diff (legacy)
    2. task["change_set"] – **preferred** structured path
    3. task["diff"]       – legacy single-file before/after dict

Always returns a unified diff string ready for `git apply`, so downstream
ShellRunner / Reviewer require **zero** changes.

2025-07-01 update
~~~~~~~~~~~~~~~~~
*   Detect the “already applied” case: if a generated diff is empty the task
    is considered a no-op.  We raise a `PatchBuildError("empty diff")`; the
    orchestrator can interpret this to auto-close the task instead of failing
    the cycle.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Dict, List

from .change_set import ChangeSet
from .patch_builder import PatchBuildError, build_patch


class TaskExecutorError(RuntimeError):
    """Generic executor failure."""


class TaskExecutor:
    def __init__(self, src_root: str | Path):
        self.src_root = Path(src_root).resolve()
        if not self.src_root.is_dir():
            raise ValueError(f"src_root '{src_root}' is not a directory.")

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def build_patch(self, task: Dict[str, Any]) -> str:
        """
        Build (or forward) a unified diff string.

        Accepted task keys (checked in this order):

        • ``patch``       – already-made diff → returned unchanged.
        • ``change_set``  – structured ChangeSet → converted via PatchBuilder.
        • ``diff``        – legacy before/after dict.

        Raises:
            TaskExecutorError — wrapped lower-level errors.
        """
        try:
            patch: str = ""

            # 1️⃣  already-built patch supplied -----------------------------
            raw = task.get("patch")
            if isinstance(raw, str):
                patch = raw

            # 2️⃣  structured ChangeSet path --------------------------------
            elif "change_set" in task:
                cs_obj = ChangeSet.from_dict(task["change_set"])
                patch = build_patch(cs_obj, Path("."))  # build relative to repo root

            # 3️⃣  legacy one-file diff path ---------------------------------
            else:
                patch = self._build_one_file_diff(task)

            # ---- common validation ----------------------------------------
            if not patch.strip():  # no textual change → probably already applied
                raise PatchBuildError("empty diff – change already present")

            return patch if patch.endswith("\n") else patch + "\n"

        except PatchBuildError as exc:
            raise TaskExecutorError(str(exc)) from exc
        except Exception as exc:
            raise TaskExecutorError(f"Failed to build patch: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Legacy helper – keep old diff path working
    # ------------------------------------------------------------------ #
    def _build_one_file_diff(self, task: Dict[str, Any]) -> str:
        diff_info = task.get("diff")
        if not diff_info:
            raise TaskExecutorError(
                "Task missing 'change_set', 'diff', or already-built 'patch'."
            )

        file_rel = diff_info.get("file", "")
        before = diff_info.get("before")
        after = diff_info.get("after")

        if not file_rel or before is None or after is None:
            raise TaskExecutorError(
                "diff dict must contain 'file', 'before', and 'after'."
            )

        # --- normalise line endings ------------------------------------- #
        if before and not before.endswith("\n"):
            before += "\n"
        if after and not after.endswith("\n"):
            after += "\n"

        before_lines: List[str] = before.splitlines(keepends=True) if before else []
        after_lines: List[str] = after.splitlines(keepends=True) if after else []

        new_file = len(before_lines) == 0 and len(after_lines) > 0
        delete_file = len(before_lines) > 0 and len(after_lines) == 0

        fromfile = "/dev/null" if new_file else f"a/{file_rel}"
        tofile = "/dev/null" if delete_file else f"b/{file_rel}"

        diff_lines = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=fromfile,
            tofile=tofile,
            lineterm="\n",
        )
        patch = "".join(diff_lines)
        if not patch.strip():
            raise PatchBuildError("empty diff – change already present")
        return patch if patch.endswith("\n") else patch + "\n"

    # ------------------------------------------------------------------ #
    # Post-commit helper – update remaining tasks with before_sha
    # ------------------------------------------------------------------ #
    def propagate_before_sha(self, file_shas: dict[str, str], backlog_mgr):
        """
        Update any **open** tasks whose ChangeSet edits touch files that have
        just been committed, filling in the ``before_sha`` field in-place.
        """
        for task in backlog_mgr.list_items("open"):
            cs = task.get("change_set")
            if not cs:
                continue
            touched = {e["path"] for e in cs["edits"]}
            if touched & file_shas.keys():
                for ed in cs["edits"]:
                    if ed["path"] in file_shas:
                        ed["before_sha"] = file_shas[ed["path"]]
                backlog_mgr.update_item(task["id"], {"change_set": cs})
