# src/cadence/dev/patch_builder.py
"""
PatchBuilder – convert a `ChangeSet` into a canonical git diff.

Only this module *ever* constructs raw diff text; every other component deals
with structured `ChangeSet` objects.  The resulting patch is guaranteed to pass

    git apply --check -

before being handed to ShellRunner.
"""

from __future__ import annotations
import os
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
import subprocess
from typing import Optional

from .change_set import ChangeSet, FileEdit


class PatchBuildError(RuntimeError):
    """Bad ChangeSet → diff generation failed."""


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_patch(change_set: ChangeSet, repo_dir: str | Path) -> str:
    …
    repo_dir = Path(repo_dir).resolve()
    change_set.validate_against_repo(repo_dir)

    with TemporaryDirectory() as tmp:
        shadow = Path(tmp) / "shadow"
        copytree(repo_dir, shadow, dirs_exist_ok=True)

        for edit in change_set.edits:
            _apply_edit_to_shadow(edit, shadow)

        # ---- Git diff (run *inside* repo) --------------------------
        proc = subprocess.run(
            [
                "git",
                "diff",
                "--no-index",
                "--binary",
                "--relative",
                "--src-prefix=a/",
                "--dst-prefix=b/",
                "--",
                ".",                  # <- left side: current repo
                str(shadow),          #    right side: shadow copy
            ],
            cwd=repo_dir,             # <- KEY CHANGE
            capture_output=True,
            text=True,
        )

        if proc.returncode not in (0, 1):
            raise PatchBuildError(proc.stderr.strip())

        patch = _rewrite_shadow_paths(proc.stdout, shadow, repo_dir)
        if not patch.strip():
            raise PatchBuildError("ChangeSet produced an empty diff.")
        if not patch.endswith("\n"):
            patch += "\n"

        _ensure_patch_applies(patch, repo_dir)
        return patch
    
# -------------------------------------------------------------------
# Helper – strip absolute shadow prefix from +++ lines
# -------------------------------------------------------------------
def _rewrite_shadow_paths(raw: str, shadow_root: Path, repo_root: Path) -> str:
    """
    Convert
        --- a/src/foo.py
        +++ b/var/folders/…/shadow/src/foo.py
    into
        --- a/src/foo.py
        +++ b/src/foo.py
    """
    shadow_prefix = str(shadow_root) + os.sep
    fixed_lines = []
    for line in raw.splitlines():
        if line.startswith("+++ ") and shadow_prefix in line:
            head, _, tail = line.partition(shadow_prefix)
            fixed_lines.append("+++ b/" + tail)
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _apply_edit_to_shadow(edit: FileEdit, shadow_root: Path) -> None:
    target = shadow_root / edit.path

    if edit.mode == "delete":
        target.unlink(missing_ok=True)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    if edit.after is None:
        raise PatchBuildError(f"`after` content required for mode={edit.mode}")
    target.write_text(edit.after, encoding="utf-8")


def _ensure_patch_applies(patch: str, repo: Path) -> None:
    """Raise PatchBuildError if the patch would not apply cleanly."""
    proc = subprocess.run(
        ["git", "apply", "--check", "-"],
        input=patch,
        text=True,
        cwd=repo,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise PatchBuildError(f"Generated patch does not apply: {proc.stderr.strip()}")