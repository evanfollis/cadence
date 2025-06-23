from __future__ import annotations
import subprocess, uuid, textwrap
from pathlib import Path
from cadence.dev.change_set import ChangeSet, FileEdit
from cadence.dev.patch_builder import build_patch

def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one python file."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    target = repo / "src" / "demo.py"
    target.write_text("def foo():\n    return 1\n", encoding="utf8")

    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "CI"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    return repo

def test_patch_builder_generates_relative_paths(tmp_path: Path):
    repo = _init_repo(tmp_path)

    # Build a ChangeSet that modifies src/demo.py
    new_code = "def foo():\n    return 42\n"
    cs = ChangeSet(
        edits=[
            FileEdit(
                path="src/demo.py",
                mode="modify",
                after=new_code,
            )
        ],
        message="change return value",
    )

    patch = build_patch(cs, repo)

    # --- Assertions -------------------------------------------------
    # 1. No absolute /var/…/shadow path left in the diff
    assert "/shadow/" not in patch, "shadow path still present in patch"

    # 2. Headers are repository-relative
    assert patch.startswith("--- a/src/demo.py"), "unexpected from-file header"
    assert "\n+++ b/src/demo.py" in patch, "unexpected to-file header"

    # 3. Patch applies cleanly to the working tree
    subprocess.run(["git", "apply", "--check", "-"], cwd=repo, input=patch,
                   text=True, check=True)