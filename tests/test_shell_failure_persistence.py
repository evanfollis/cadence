"""
Regression tests — Shell failure persistence
============================================

Goal
----
Assert that *every* failing shell operation executed through
`cadence.dev.shell.ShellRunner` writes an explicit `failed_<stage>`
snapshot to the provided `TaskRecord` **before** the error propagates.

We stub `subprocess.run` so the tests are hermetic (no real git/pytest
invocations) and execute in milliseconds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import List, Tuple

import pytest


# --------------------------------------------------------------------------- #
# Helpers / stubs
# --------------------------------------------------------------------------- #
class _FakeTaskRecord:
    """Minimal in-memory stand-in for cadence.dev.record.TaskRecord."""

    def __init__(self) -> None:
        self.calls: List[dict] = []

    # Signature matches real .save()
    def save(self, task, state: str, extra: dict | None = None):
        self.calls.append({"task": task, "state": state, "extra": extra or {}})


@pytest.fixture(autouse=True)
def _ensure_importable(monkeypatch):
    """
    Make the repository root (containing ``src/``) importable **everywhere**
    so the tests run from any working directory or CI container.
    """
    proj_root = Path(__file__).resolve().parents[1]
    if (proj_root / "src").exists():
        monkeypatch.syspath_prepend(str(proj_root))
    yield


def _proc(rc=1, *, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """Return a dummy CompletedProcess-like object."""
    return SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


def _patch_subprocess(monkeypatch, mapping: dict[Tuple[str, str], SimpleNamespace]):
    """
    Replace ``subprocess.run`` so that:

        key = tuple(cmd[:2])   # e.g. (“git”, “apply”)

    If *key* is in *mapping* → return that DummyProcess.
    Otherwise → succeed (rc=0).
    """

    def _fake_run(cmd, **_kwargs):
        key = tuple(cmd[:2])
        return mapping.get(key, _proc(rc=0))

    monkeypatch.setattr(subprocess, "run", _fake_run)


def _make_runner(tmp_path: Path, record: _FakeTaskRecord):
    """Set up a ShellRunner pointed at an empty temp repo dir."""
    from src.cadence.dev.shell import ShellRunner

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    runner = ShellRunner(repo_dir=str(repo_dir), task_record=record)
    runner.attach_task({"id": "task-1", "title": "demo", "status": "open"})
    return runner, repo_dir


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_git_apply_failure_persists(monkeypatch, tmp_path: Path):
    from src.cadence.dev.shell import ShellCommandError

    record = _FakeTaskRecord()
    runner, _ = _make_runner(tmp_path, record)

    # Simulate `git apply` failing
    _patch_subprocess(
        monkeypatch,
        {("git", "apply"): _proc(stderr="boom")},
    )

    with pytest.raises(ShellCommandError):
        runner.git_apply("--- broken diff")

    assert record.calls, "TaskRecord.save was not called on failure"
    snapshot = record.calls[-1]
    assert snapshot["state"] == "failed_git_apply"
    assert "boom" in snapshot["extra"].get("error", "") or "boom" in snapshot["extra"].get(
        "output", ""
    )


def test_pytest_failure_persists(monkeypatch, tmp_path: Path):
    record = _FakeTaskRecord()
    runner, repo_dir = _make_runner(tmp_path, record)

    # Ensure ./tests exists so run_pytest() doesn't raise path-missing error
    (repo_dir / "tests").mkdir()

    _patch_subprocess(
        monkeypatch,
        {("pytest", "-q"): _proc(stdout="F..", stderr="1 failed")},
    )

    result = runner.run_pytest()
    assert result["success"] is False, "stubbed pytest should fail"

    snapshot = record.calls[-1]
    assert snapshot["state"] == "failed_pytest"
    assert "1 failed" in snapshot["extra"]["output"]


def test_git_commit_failure_persists(monkeypatch, tmp_path: Path):
    """
    Commit may now fail **either** because prerequisites were not met
    (*phase-guard short-circuit*) **or** because `git commit` itself
    returns a non-zero exit code.  Both paths must record a snapshot
    with state ``failed_git_commit``.
    """
    from src.cadence.dev.shell import ShellCommandError

    record = _FakeTaskRecord()
    runner, _ = _make_runner(tmp_path, record)

    # `git add` succeeds, `git commit` fails with "nothing to commit"
    mapping = {
        ("git", "add"): _proc(rc=0),
        ("git", "commit"): _proc(rc=1, stderr="nothing to commit"),
    }
    _patch_subprocess(monkeypatch, mapping)

    with pytest.raises(ShellCommandError):
        runner.git_commit("empty commit")

    snapshot = record.calls[-1]
    assert snapshot["state"] == "failed_git_commit"
    # Accept either the original git-level error or the new phase-guard msg
    err_msg = snapshot["extra"]["error"]
    assert (
        "nothing to commit" in err_msg
        or "missing prerequisite phase" in err_msg
        or "missing prerequisite phase(s)" in err_msg
    )