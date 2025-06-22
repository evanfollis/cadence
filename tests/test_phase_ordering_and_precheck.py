"""
Tests for ShellRunner: diff pre-check & phase-ordering
=====================================================

These tests verify that

1.  A patch whose *before* image does **not** match the working tree
    fails during the *pre-check* stage and records the correct snapshot.

2.  `git_commit` is refused unless both *patch_applied* **and**
    *tests_passed* phases are already recorded for the current task.

3.  When phases are executed in the correct order
    (apply → tests → commit) the commit succeeds and the *committed*
    phase flag is set.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Tuple

import pytest

# --------------------------------------------------------------------------- #
# Helper – fake in-memory TaskRecord
# --------------------------------------------------------------------------- #
class _FakeTaskRecord:
    def __init__(self) -> None:
        self.calls: List[dict] = []

    def save(self, task, state: str, extra: dict | None = None):
        self.calls.append({"task": task, "state": state, "extra": extra or {}})


# --------------------------------------------------------------------------- #
# Pytest fixtures / stubs
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _ensure_importable(monkeypatch):
    """
    Ensure ``src/`` is import-searchable regardless of the cwd that the
    test runner happens to use.
    """
    proj_root = Path(__file__).resolve().parents[1]
    if (proj_root / "src").exists():
        monkeypatch.syspath_prepend(str(proj_root))
    yield


def _proc(rc: int = 1, *, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Return a dummy CompletedProcess-like object."""
    return SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


def _patch_subprocess(monkeypatch, mapping: Dict[Tuple[str, str], SimpleNamespace]):
    """
    Monkey-patch ``subprocess.run`` so that the first two CLI tokens form a
    lookup key.  If the key exists in *mapping* we return that fake
    process; otherwise return a zero-exit stub.
    """

    def _fake_run(cmd, **_kwargs):
        key = tuple(cmd[:2])
        return mapping.get(key, _proc(rc=0))

    monkeypatch.setattr(subprocess, "run", _fake_run)


def _make_runner(tmp_path: Path, record: _FakeTaskRecord):
    """Return a (runner, repo_dir, task_id) triple."""
    from src.cadence.dev.shell import ShellRunner

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task = {"id": "task-xyz", "title": "demo", "status": "open"}
    runner = ShellRunner(repo_dir=str(repo_dir), task_record=record)
    runner.attach_task(task)
    return runner, repo_dir, task["id"]


# --------------------------------------------------------------------------- #
# Test 1 – diff pre-check failure
# --------------------------------------------------------------------------- #
def test_patch_precheck_failure(monkeypatch, tmp_path: Path):
    """
    git apply --check returns non-zero → ShellRunner must raise and record
    ``failed_git_apply`` without setting *patch_applied*.
    """
    from src.cadence.dev.shell import ShellCommandError

    record = _FakeTaskRecord()
    runner, _repo_dir, tid = _make_runner(tmp_path, record)

    # Pre-check fails
    _patch_subprocess(monkeypatch, {("git", "apply"): _proc(stderr="mismatch")})

    with pytest.raises(ShellCommandError):
        runner.git_apply("--- broken diff")

    # Snapshot written
    snap = record.calls[-1]
    assert snap["state"] == "failed_git_apply"
    assert "mismatch" in snap["extra"]["error"] or "mismatch" in snap["extra"].get(
        "output", ""
    )

    # Phase flag **not** set
    assert not runner._has_phase(tid, "patch_applied")  # pylint: disable=protected-access


# --------------------------------------------------------------------------- #
# Test 2 – commit refused when prerequisites are missing
# --------------------------------------------------------------------------- #
def test_commit_refused_without_prerequisites(monkeypatch, tmp_path: Path):
    from src.cadence.dev.shell import ShellCommandError

    record = _FakeTaskRecord()
    runner, _repo_dir, _tid = _make_runner(tmp_path, record)

    # Underlying git commands would *succeed* but the phase guard should
    # short-circuit first.
    _patch_subprocess(
        monkeypatch,
        {
            ("git", "add"): _proc(rc=0),
            ("git", "commit"): _proc(rc=0),  # never reached
        },
    )

    with pytest.raises(ShellCommandError) as exc:
        runner.git_commit("should fail")

    assert "missing prerequisite phase" in str(exc.value)
    snap = record.calls[-1]
    assert snap["state"] == "failed_git_commit"


# --------------------------------------------------------------------------- #
# Test 3 – happy-path: apply → tests → commit
# --------------------------------------------------------------------------- #
def test_full_success_flow(monkeypatch, tmp_path: Path):
    """
    Execute the correct phase sequence and assert that commit succeeds and
    the internal *committed* flag is set.
    """
    record = _FakeTaskRecord()
    runner, repo_dir, tid = _make_runner(tmp_path, record)

    # --- make an empty ./tests folder so ShellRunner.run_pytest() passes its
    #     early path-existence guard.
    (Path(repo_dir) / "tests").mkdir()

    sha = "abc123"

    _patch_subprocess(
        monkeypatch,
        {
            # Patch pre-check OK, apply OK
            ("git", "apply"): _proc(rc=0),
            # Pytest green
            ("pytest", "-q"): _proc(rc=0, stdout=""),
            # Git plumbing
            ("git", "add"): _proc(rc=0),
            ("git", "commit"): _proc(rc=0),
            ("git", "rev-parse"): _proc(rc=0, stdout=f"{sha}\n"),
        },
    )

    # 1. apply
    runner.git_apply("--- dummy diff")

    # 2. tests
    py_res = runner.run_pytest()
    assert py_res["success"] is True

    # 3. commit
    out_sha = runner.git_commit("commit msg")
    assert out_sha == sha
    assert runner._has_phase(tid, "committed")  # pylint: disable=protected-access