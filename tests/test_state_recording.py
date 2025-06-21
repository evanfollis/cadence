# tests/test_state_recording.py
"""
Integration test for TaskRecord integrity.

Runs DevOrchestrator.run_task_cycle twice:

1.  A green run where the patch fixes the bug and pytest passes.
2.  A red run where the patch is a no-op so pytest fails.

For each run we assert that:
    • mandatory state snapshots appear *in order* (allowing extra entries);
    • `task.status` matches the state for *done* → *archived*;
    • failure snapshots carry useful diagnostics.

The test is dependency-free: it stubs `openai` and `tabulate` before any
Cadence import so no network or extra wheels are required.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Global stubs – applied automatically by the autouse fixture
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _stub_external(monkeypatch):
    """Stub out optional / external deps so the test runs anywhere."""
    # Fake OpenAI client (LLM not used by DevOrchestrator path)
    fake_openai = sys.modules["openai"] = type(sys)("openai")
    fake_openai.AsyncOpenAI = lambda *a, **k: None  # type: ignore
    fake_openai.OpenAI = lambda *a, **k: None       # type: ignore

    # Fake tabulate to avoid CLI pretty-printer dependency
    fake_tabulate = sys.modules["tabulate"] = type(sys)("tabulate")
    fake_tabulate.tabulate = lambda *a, **k: ""

    # Env var so LLMClient constructor is happy
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")

    # --- critical fix: ensure real Cadence code is importable ---------------
    # We need the directory that CONTAINS the top-level “src/” package.
    if (PROJECT_ROOT / "src").exists():
        monkeypatch.syspath_prepend(str(PROJECT_ROOT))
    # ----------------------------------------------------------------------- #

    yield


# --------------------------------------------------------------------------- #
# Repo bootstrap helpers
# --------------------------------------------------------------------------- #
BAD_IMPL = "def add(x, y):\n    return x - 1 + y\n"
GOOD_IMPL = BAD_IMPL.replace("- 1 +", "+")


def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal Cadence project inside a temporary git repo."""
    repo = tmp_path

    # Source package
    pkg_root = repo / "src" / "cadence" / "utils"
    pkg_root.mkdir(parents=True, exist_ok=True)
    # PEP-420 implicit namespace would work, but an explicit file removes
    # any ambiguity on Py<3.10 or odd tooling.
    (repo / "src" / "__init__.py").write_text("")
    (repo / "src" / "cadence" / "__init__.py").write_text("")
    (pkg_root / "__init__.py").write_text("")
    (pkg_root / "add.py").write_text(BAD_IMPL)

    # Unit test that will pass only if GOOD_IMPL is in place
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_add.py").write_text(
        # Ensure repo/src is on import path _inside_ the pytest subprocess
        "import sys, pathlib, os\n"
        "sys.path.insert(0, os.fspath((pathlib.Path(__file__).resolve().parents[2] / 'src')))\n"
        "from cadence.utils.add import add\n"
        "\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )

    # Initial git commit so `git apply` has a base tree
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "CI"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)

    return repo


def _make_backlog(repo: Path, record_file: Path, *, fix_bug: bool) -> Path:
    """Write backlog.json containing exactly one task and return the path."""
    # For the “red” path we still need a *non-empty* diff so the run
    # proceeds through patch-apply and into pytest (where it will fail).
    # - Green run: after_code fixes the defect.
    # - Red  run: after_code == before_code  → diff is empty → PatchBuildError.
    after_code = GOOD_IMPL if fix_bug else BAD_IMPL
    task = {
        "id": "task-fix-add",
        "title": "Fix utils.add bug",
        "type": "micro",
        "status": "open",
        "created_at": datetime.now(UTC).isoformat(),
        "diff": {
            "file": "src/cadence/utils/add.py",
            "before": BAD_IMPL,
            "after":  after_code,
        },
    }
    backlog = repo / "backlog.json"
    backlog.write_text(json.dumps([task], indent=2))
    record_file.write_text("[]")   # empty initial record
    return backlog


def _orch_cfg(repo: Path, backlog: Path, record: Path) -> dict:
    """Return the minimal DevOrchestrator config dict."""
    return {
        "backlog_path": str(backlog),
        "template_file": None,
        "src_root": str(repo),
        "ruleset_file": None,
        "repo_dir": str(repo),
        "record_file": str(record),
    }


# --------------------------------------------------------------------------- #
# Parametrised integration test
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fix_bug", [True, False])
def test_task_record_snapshots(tmp_path: Path, fix_bug: bool):
    """
    Ensure TaskRecord snapshots are written after every mutator or failure.
    """
    repo = _init_repo(tmp_path)
    record_file = repo / "dev_record.json"
    backlog_file = _make_backlog(repo, record_file, fix_bug=fix_bug)

    from src.cadence.dev.orchestrator import DevOrchestrator

    orch = DevOrchestrator(_orch_cfg(repo, backlog_file, record_file))
    result = orch.run_task_cycle(select_id="task-fix-add", interactive=False)

    # ----------------- Inspect TaskRecord ----------------- #
    record: List[dict] = json.loads(record_file.read_text())
    assert len(record) == 1, "exactly one task record expected"
    history = record[0]["history"]
    states = [snap["state"] for snap in history]

    common = [
        "build_patch",
        "patch_built",
        "patch_reviewed",
        "patch_applied",
        "pytest_run",
    ]
    if fix_bug:
        expected_seq = common + ["committed", "status_done", "archived"]

        # Confirm green-path sequence
        it = iter(states)
        for label in expected_seq:
            assert label in it, f"missing or out-of-order state '{label}'"
    else:
        # Red path: must terminate with some `failed_…` snapshot
        assert not result["success"], "red run unexpectedly succeeded"
        assert states[-1].startswith("failed_"), "last snapshot must be a failure state"
        # And we still expect the initial 'build_patch' snapshot
        assert states[0] == "build_patch"

    # Semantic checks on snapshot contents
    if fix_bug:
        done_ix, arch_ix = states.index("status_done"), states.index("archived")
        assert history[done_ix]["task"]["status"] == "done"
        assert history[arch_ix]["task"]["status"] == "archived"
    else:
        extra = history[-1]["extra"]
        assert extra, "failure snapshot must include diagnostics"
        assert "error" in extra or "pytest" in extra