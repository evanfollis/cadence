# tests/test_failed_rollback.py
"""
Regression-test — Atomic rollback on downstream failure
=======================================================

Purpose
-------
Verify that *any* failure after a patch is applied triggers a rollback that:
    • restores the working tree
    • writes the correct TaskRecord snapshots
    • leaves git status clean

The patch used here adds a deliberately failing test file.

Note: since Loop-5 the orchestrator may abort **earlier** at the
“patch_review_efficiency” stage (fail-closed).  The test therefore
accepts either failure stage.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest


# ───────────────────── global stubs ──────────────────────────────────────────
@pytest.fixture(autouse=True)
def _stub_external(monkeypatch):
    """Stub OpenAI + tabulate so the test is hermetic."""
    fake_openai = sys.modules["openai"] = type(sys)("openai")
    fake_openai.AsyncOpenAI = lambda *a, **k: None  # type: ignore
    fake_openai.OpenAI = lambda *a, **k: None       # type: ignore

    fake_tabulate = sys.modules["tabulate"] = type(sys)("tabulate")
    fake_tabulate.tabulate = lambda *a, **k: ""

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if (PROJECT_ROOT / "src").exists():
        monkeypatch.syspath_prepend(str(PROJECT_ROOT))
    yield


# ───────────────────── repo bootstrap helpers ────────────────────────────────
GOOD_IMPL = "def add(x, y):\n    return x + y\n"
FAILING_TEST = (
    "def test_intentional_failure():\n"
    "    assert False, 'This test is added by the patch and must fail'\n"
)

def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal Cadence project inside a temporary git repo."""
    repo = tmp_path
    pkg_root = repo / "src" / "cadence" / "utils"
    pkg_root.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "__init__.py").write_text("")
    (repo / "src" / "cadence" / "__init__.py").write_text("")
    (pkg_root / "__init__.py").write_text("")
    (pkg_root / "add.py").write_text(GOOD_IMPL)

    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_add.py").write_text(
        "import sys, pathlib, os\n"
        "sys.path.insert(0, os.fspath((pathlib.Path(__file__).resolve().parents[2] / 'src')))\n"
        "from cadence.utils.add import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )

    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "CI"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True,
                   stdout=subprocess.DEVNULL)
    return repo


def _make_backlog(repo: Path, record_file: Path) -> Path:
    """Write backlog.json with one task that *adds* a failing test."""
    task = {
        "id": "task-add-failing-test",
        "title": "Add failing test to trigger rollback",
        "type": "micro",
        "status": "open",
        "created_at": "2025-06-21T00:00:00Z",
        "diff": {
            "file": "tests/test_break.py",
            "before": "",
            "after":  FAILING_TEST,
        },
    }
    backlog_path = repo / "backlog.json"
    backlog_path.write_text(json.dumps([task], indent=2))
    record_file.write_text("[]")
    return backlog_path


def _orch_cfg(repo: Path, backlog: Path, record: Path) -> dict:
    return {
        "backlog_path": str(backlog),
        "template_file": None,
        "src_root": str(repo),
        "ruleset_file": None,
        "repo_dir": str(repo),
        "record_file": str(record),
    }


# ───────────────────── the actual test ───────────────────────────────────────
def test_atomic_rollback_on_failed_tests(tmp_path: Path):
    repo = _init_repo(tmp_path)
    record_file = repo / "dev_record.json"
    backlog_file = _make_backlog(repo, record_file)

    from src.cadence.dev.orchestrator import DevOrchestrator

    orch = DevOrchestrator(_orch_cfg(repo, backlog_file, record_file))
    result = orch.run_task_cycle(select_id="task-add-failing-test", interactive=False)

    # The run must fail, either at efficiency review or at the test stage.
    # ---- assertions -------------------------------------------------------
    assert result["success"] is False
    assert result["stage"] in {"patch_review_efficiency", "test"}

    # history must contain *some* failure state plus a rollback success
    history = json.loads(record_file.read_text())[0]["history"]
    states = {snap["state"] for snap in history}

    assert "rollback_succeeded" in states
    assert {"failed_patch_review_efficiency", "failed_test"} & states, (
        f"Expected a failure snapshot, got {states}"
    )

    # failing test file should be gone
    assert not (repo / "tests" / "test_break.py").exists()

    # working tree clean (ignore untracked)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    ).stdout.strip()
    tracked_changes = [l for l in status.splitlines() if not l.startswith("??")]
    assert tracked_changes == []

