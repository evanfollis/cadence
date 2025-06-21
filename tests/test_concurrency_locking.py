# tests/test_concurrency_locking.py
"""
Concurrency / locking integration tests
=======================================

Objective
---------
Ensure that the new RLock-based protection in BacklogManager and TaskRecord
prevents race-condition corruption when many threads mutate the same
objects *simultaneously*.

The test intentionally shares a single instance across  multiple threads
to stress intra-process locking.  Cross-process safety (file-level
locking) is out-of-scope for this change-set.
"""

from __future__ import annotations
import json
import sys
import threading
import uuid
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# Helper – ensure the repo "src/" folder is importable inside the test run
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _ensure_importable(monkeypatch):
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if (PROJECT_ROOT / "src").exists():
        monkeypatch.syspath_prepend(str(PROJECT_ROOT))
    yield


# --------------------------------------------------------------------------- #
# BacklogManager concurrency test
# --------------------------------------------------------------------------- #
def test_backlog_thread_safety(tmp_path: Path):
    from src.cadence.dev.backlog import BacklogManager

    backlog_path = tmp_path / "backlog.json"
    mgr = BacklogManager(str(backlog_path))

    THREADS = 10
    TASKS_PER_THREAD = 100

    def _worker(tid: int):
        for i in range(TASKS_PER_THREAD):
            mgr.add_item(
                {
                    "title": f"task {tid}-{i}",
                    "type": "micro",
                    "status": "open",
                    "created_at": "2025-06-21T00:00:00Z",
                }
            )

    threads = [threading.Thread(target=_worker, args=(n,)) for n in range(THREADS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=10)
        assert not th.is_alive(), "thread hung – possible deadlock"

    # Validate in-memory state
    items = mgr.list_items(status="all")
    assert len(items) == THREADS * TASKS_PER_THREAD, "missing or duplicate tasks in memory"

    # Validate on-disk JSON integrity
    on_disk = json.loads(backlog_path.read_text())
    assert len(on_disk) == len(items), "disk state differs from memory state"


# --------------------------------------------------------------------------- #
# TaskRecord concurrency test
# --------------------------------------------------------------------------- #
def test_taskrecord_thread_safety(tmp_path: Path):
    from src.cadence.dev.record import TaskRecord

    record_path = tmp_path / "record.json"
    tr = TaskRecord(str(record_path))

    THREADS = 8
    SAVES_PER_THREAD = 75

    def _worker():
        for _ in range(SAVES_PER_THREAD):
            task_id = str(uuid.uuid4())
            task = {"id": task_id, "title": "concurrency", "status": "open"}
            tr.save(task, state="init")

    threads = [threading.Thread(target=_worker) for _ in range(THREADS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=10)
        assert not th.is_alive(), "thread hung – possible deadlock"

    # Verify integrity: unique task_id for each record
    data = tr.load()
    ids = [rec["task_id"] for rec in data]
    assert len(ids) == len(set(ids)), "duplicate task_id detected – race condition?"
    assert len(ids) == THREADS * SAVES_PER_THREAD, "missing records – some saves lost"
