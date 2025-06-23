# tests/backlog_blocked_filtering.py
from src.cadence.dev.backlog import BacklogManager, TaskStructureError
import os, uuid

def test_blocked_tasks_are_filtered():
    path = f".test_backlog_{uuid.uuid4().hex}.json"
    try:
        mgr = BacklogManager(path)
        # Add an open task
        t1 = {"title": "Task open", "type": "micro", "status": "open", "created_at": "2024-07-01T12:00", "id": "T1"}
        mgr.add_item(t1)
        # Add a blocked task
        t2 = {"title": "Task blocked", "type": "micro", "status": "blocked", "created_at": "2024-07-01T12:01", "id": "T2"}
        mgr.add_item(t2)
        # Add another open task
        t3 = {"title": "Task open2", "type": "micro", "status": "open", "created_at": "2024-07-01T12:02", "id": "T3"}
        mgr.add_item(t3)
        open_tasks = mgr.list_items("open")
        ids = {t["id"] for t in open_tasks}
        assert "T2" not in ids, "Blocked tasks must not appear in open list"
        assert "T1" in ids and "T3" in ids
        # Also test list_items("all")
        all_tasks = mgr.list_items("all")
        all_ids = {t["id"] for t in all_tasks}
        assert "T2" in all_ids
    finally:
        if os.path.exists(path):
            os.remove(path)

def test_invalid_status_rejected():
    path = f".test_backlog_{uuid.uuid4().hex}.json"
    try:
        mgr = BacklogManager(path)
        bad_task = {"title": "Bad status", "type": "micro", "status": "nonsense", "created_at": "2024-07-01T12:03", "id": "T4"}
        try:
            mgr.add_item(bad_task)
            assert False, "TaskStructureError should have been raised for invalid status"
        except TaskStructureError:
            pass
    finally:
        if os.path.exists(path):
            os.remove(path)
