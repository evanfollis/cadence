# src/cadence/dev/patch_builder.py
"""
PatchBuilder – convert a `ChangeSet` into a canonical git diff.

Only this module *ever* constructs raw diff text; every other component deals
with structured `ChangeSet` objects.  The resulting patch is guaranteed to pass

    git apply --check -

before being handed to ShellRunner.
"""

from __future__ import annotations

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
    """
    Return a validated unified diff for *change_set* relative to *repo_dir*.

    • Enforces relative paths.
    • Guarantees trailing newline required by git.
    • Uses `--binary` so images & line-ending changes survive intact.
    """
    repo_dir = Path(repo_dir).resolve()
    change_set.validate_against_repo(repo_dir)  # SHA-guard (no-op if not provided)

    with TemporaryDirectory() as tmp:
        shadow = Path(tmp) / "shadow"
        copytree(repo_dir, shadow, dirs_exist_ok=True)

        for edit in change_set.edits:
            _apply_edit_to_shadow(edit, shadow)

        # git diff --no-index produces exit-code 1 when a diff exists.
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
                str(repo_dir),
                str(shadow),
            ],
            capture_output=True,
            text=True,
        )

        if proc.returncode not in (0, 1):  # 0=same, 1=diff produced
            raise PatchBuildError(proc.stderr.strip())

        patch = proc.stdout
        if not patch.strip():
            raise PatchBuildError("ChangeSet produced an empty diff.")

        if not patch.endswith("\n"):
            patch += "\n"

        # Final safety-check
        _ensure_patch_applies(patch, repo_dir)

        return patch


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