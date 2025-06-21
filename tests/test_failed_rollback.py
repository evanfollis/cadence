"""
Regression-test — Atomic rollback on downstream failure
=======================================================

Purpose
-------
Verify that *any* failure **after** a patch is applied but **before**
commit triggers an automatic rollback that restores a pristine working
tree **and** writes the correct snapshots to TaskRecord.

Strategy
--------
1.  Start with a clean repo where utils.add() is *correct* and all tests
    pass.

2.  Backlog contains a task whose patch **adds a brand-new failing test
    file** – this guarantees pytest will fail *if* the patch is applied,
    regardless of implementation details.

3.  Run a full `DevOrchestrator` cycle (non-interactive).

4.  Assert:
        ─ orchestrator reports failure at the *test* stage;
        ─ TaskRecord contains both `"failed_test"` **and**
          `"failed_test_and_rollback"` snapshots;
        ─ the failing test file is gone (working tree restored);
        ─ original tests pass again and git status is clean.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest


# --------------------------------------------------------------------------- #
# Global stubs – applied automatically
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _stub_external(monkeypatch):
    """Stub out optional / external deps so the test is hermetic."""
    # Fake OpenAI client (LLM not used by this path)
    fake_openai = sys.modules["openai"] = type(sys)("openai")
    fake_openai.AsyncOpenAI = lambda *a, **k: None  # type: ignore
    fake_openai.OpenAI = lambda *a, **k: None       # type: ignore

    # Fake tabulate (pretty-printer)
    fake_tabulate = sys.modules["tabulate"] = type(sys)("tabulate")
    fake_tabulate.tabulate = lambda *a, **k: ""

    # Satisfy LLMClient env check
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    # Ensure repository *parent* (containing “src/”) is importable
    PROJ_ROOT = Path(__file__).resolve().parents[1]
    if (PROJ_ROOT / "src").exists():
        monkeypatch.syspath_prepend(str(PROJ_ROOT))

    yield


# --------------------------------------------------------------------------- #
# Repo bootstrap helpers
# --------------------------------------------------------------------------- #
GOOD_IMPL = "def add(x, y):\n    return x + y\n"
FAILING_TEST = (
    "def test_intentional_failure():\n"
    "    assert False, 'This test is added by the patch and must fail'\n"
)


def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal Cadence project inside a temporary git repo."""
    repo = tmp_path

    # --- source package ----------------------------------------------------
    pkg_root = repo / "src" / "cadence" / "utils"
    pkg_root.mkdir(parents=True, exist_ok=True)
    (repo / "src" / "__init__.py").write_text("")
    (repo / "src" / "cadence" / "__init__.py").write_text("")
    (pkg_root / "__init__.py").write_text("")
    (pkg_root / "add.py").write_text(GOOD_IMPL)

    # --- baseline passing test --------------------------------------------
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_add.py").write_text(
        "import sys, pathlib, os\n"
        "sys.path.insert(0, os.fspath((pathlib.Path(__file__).resolve().parents[2] / 'src')))\n"
        "from cadence.utils.add import add\n"
        "\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )

    # --- git init ----------------------------------------------------------
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "CI"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial good implementation"],
        cwd=repo,
        check=True,
        stdout=subprocess.DEVNULL,
    )
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
            # New file relative to repo root
            "file": "tests/test_break.py",
            "before": "",                 # new file → empty 'before'
            "after":  FAILING_TEST,
        },
    }
    backlog_path = repo / "backlog.json"
    backlog_path.write_text(json.dumps([task], indent=2))
    record_file.write_text("[]")  # fresh record
    return backlog_path


def _orch_cfg(repo: Path, backlog: Path, record: Path) -> dict:
    """Return minimal DevOrchestrator config."""
    return {
        "backlog_path": str(backlog),
        "template_file": None,
        "src_root": str(repo),
        "ruleset_file": None,
        "repo_dir": str(repo),
        "record_file": str(record),
    }


# --------------------------------------------------------------------------- #
# The actual test
# --------------------------------------------------------------------------- #
def test_atomic_rollback_on_failed_tests(tmp_path: Path):
    """
    Full DevOrchestrator run — must:
        • fail at test phase,
        • rollback applied patch,
        • leave working tree clean.
    """
    repo = _init_repo(tmp_path)
    record_file = repo / "dev_record.json"
    backlog_file = _make_backlog(repo, record_file)

    # Import *after* stubs are in place
    from src.cadence.dev.orchestrator import DevOrchestrator

    orch = DevOrchestrator(_orch_cfg(repo, backlog_file, record_file))
    result = orch.run_task_cycle(select_id="task-add-failing-test", interactive=False)

    # ---- orchestrator result ---------------------------------------------
    assert result["success"] is False
    assert result["stage"] == "test"

    # ---- TaskRecord snapshots --------------------------------------------
    history: List[dict] = json.loads(record_file.read_text())[0]["history"]
    states = [snap["state"] for snap in history]
    assert "failed_test" in states, "failure snapshot missing"
    assert "failed_test_and_rollback" in states, "rollback snapshot missing"

    # ---- Working tree validation -----------------------------------------
    # 1. The intentionally failing test must be *gone*
    assert not (repo / "tests" / "test_break.py").exists(), "rollback did not remove new file"

    # 2. Original add() implementation still correct
    sys.path.insert(0, str(repo / "src"))
    from cadence.utils.add import add  # noqa: E402  (delayed import)

    assert add(2, 3) == 5

    # 3. Git working tree clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        stdout=subprocess.PIPE,
        encoding="utf-8",
        check=True,
    ).stdout.strip()
    assert status == "", f"working tree dirty after rollback:\n{status}"