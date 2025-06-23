# src/cadence/dev/patch_builder.py
"""
PatchBuilder – convert a ChangeSet into a git-compatible unified diff.

Guarantees:
• Only repository-relative paths (`a/<path>`, `b/<path>`).
• Trailing newline (git apply requirement).
• Patch passes `git apply --check`.

2025-06-24 fix
──────────────
Eliminate `/var/.../shadow/...` leakage and the `./` path prefix by
rewriting *all* header lines emitted by `git diff`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory

from .change_set import ChangeSet, FileEdit


class PatchBuildError(RuntimeError):
    """Bad ChangeSet → diff generation failed."""


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────
def build_patch(change_set: ChangeSet, repo_dir: str | Path) -> str:
    """
    Return a validated unified diff for *change_set* relative to *repo_dir*.
    """
    repo_dir = Path(repo_dir).resolve()
    change_set.validate_against_repo(repo_dir)

    with TemporaryDirectory() as tmp:
        shadow = Path(tmp) / "shadow"
        copytree(repo_dir, shadow, dirs_exist_ok=True)

        for edit in change_set.edits:
            _apply_edit_to_shadow(edit, shadow)

        # git diff runs inside repo → left side "." (no absolute path leakage)
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
                ".",          # ← repo root
                str(shadow),  # ← modified copy
            ],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )

        if proc.returncode not in (0, 1):  # 0 = identical, 1 = diff produced
            raise PatchBuildError(proc.stderr.strip())

        patch = _rewrite_headers(proc.stdout, shadow)

        if not patch.strip():
            raise PatchBuildError("ChangeSet produced an empty diff.")
        if not patch.endswith("\n"):
            patch += "\n"

        _ensure_patch_applies(patch, repo_dir)
        return patch


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────
def _apply_edit_to_shadow(edit: FileEdit, shadow_root: Path) -> None:
    target = shadow_root / edit.path
    if edit.mode == "delete":
        target.unlink(missing_ok=True)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    if edit.after is None:
        raise PatchBuildError(f"`after` content required for mode={edit.mode}")
    target.write_text(edit.after, encoding="utf-8")


def _rewrite_headers(raw: str, shadow_root: Path) -> str:
    """
    Fix header lines emitted by `git diff`:

        diff --git a/./src/foo.py b/<tmp>/shadow/src/foo.py
        --- a/./src/foo.py
        +++ b/<tmp>/shadow/src/foo.py

    becomes

        diff --git a/src/foo.py b/src/foo.py
        --- a/src/foo.py
        +++ b/src/foo.py
    """
    shadow_prefix = str(shadow_root) + os.sep
    fixed: list[str] = []

    for line in raw.splitlines():
        if line.startswith("diff --git "):
            _, _, paths = line.partition("diff --git ")
            left, right = paths.split(" ", maxsplit=1)
            left = left.replace("a/./", "a/")  # drop './'
            right = _strip_shadow(right, shadow_prefix)
            fixed.append(f"diff --git {left} {right}")
        elif line.startswith("--- "):
            fixed.append("".join(("--- ", line[4:].replace("a/./", "a/"))))
        elif line.startswith("+++ "):
            cleaned = line[4:]
            cleaned = cleaned.replace("b/./", "b/")
            cleaned = _strip_shadow(cleaned, shadow_prefix, prefix="b/")
            fixed.append("+++ " + cleaned)
        else:
            fixed.append(line)
    return "\n".join(fixed)


def _strip_shadow(path: str, shadow_prefix: str, *, prefix: str = "b/") -> str:
    """
    Normalise any header path that still contains the absolute TemporaryDirectory
    copy of the repo (the “…/shadow/…” component) so that **only repository-relative
    paths remain**::

         b/var/folders/.../shadow/src/foo.py  ->  b/src/foo.py
         a/var/folders/.../shadow/src/foo.py  ->  a/src/foo.py
    """
    # 1. Peel off the a/ or b/ token so the search is position-agnostic
    leading = ""
    rest = path
    if path.startswith(("a/", "b/")):
        leading, rest = path[:2], path[2:]        # keep 'a/' or 'b/' for later

    # 2. Find the *shadow* directory irrespective of how the tmp path is prefixed
    #    Examples that must all be normalised:
    #      var/folders/…/tmpabcd/shadow/src/foo.py
    #      private/var/…/tmpabcd/shadow/src/foo.py
    shadow_marker = f"{os.sep}shadow{os.sep}"

    if shadow_prefix in rest:
        _, _, tail = rest.partition(shadow_prefix)
    elif shadow_marker in rest:
        _, _, tail = rest.partition(shadow_marker)
    else:
        # Nothing to rewrite – re-attach original leading token and return
        return leading + rest

    # Drop any leading slash the partition may have preserved
    if tail.startswith(os.sep):
        tail = tail[len(os.sep):]

    new_prefix = prefix if leading == "b/" else "a/"
    return new_prefix + tail


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