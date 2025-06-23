# src/cadence/dev/backlog.py

"""
Cadence BacklogManager
---------------------
Thread-safe CRUD on the task backlog.

Key changes (2025-06-21)
• Introduced a process-local re-entrant lock (`threading.RLock`) named
  `_lock`.  ALL public mutators and any internal helpers that touch shared
  state or disk are now executed under `with self._lock: …`.
• Read helpers (`list_items`, `get_item`, `export`, `__str__`) also acquire
  the lock to guarantee a coherent snapshot even while writers operate.
• Nested calls (e.g. `archive_completed()` → `save()`) are safe because
  RLock is re-entrant.
"""

from __future__ import annotations

import os
import json
import uuid
import threading
import copy
from typing import List, Dict, Optional

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class BacklogEmptyError(Exception):
    """Raised if attempting to pop or select from an empty backlog."""


class TaskStructureError(Exception):
    """Raised if a task dict doesn't conform to required structure."""


class TaskNotFoundError(Exception):
    """Raised if a requested task_id is not in the backlog."""


# --------------------------------------------------------------------------- #
# Constants / helpers
# --------------------------------------------------------------------------- #
REQUIRED_FIELDS = ("id", "title", "type", "status", "created_at")

VALID_STATUSES = ("open", "in_progress", "done", "archived", "blocked")

# --------------------------------------------------------------------------- #
# BacklogManager
# --------------------------------------------------------------------------- #
class BacklogManager:
    """
    Manages Cadence backlog: micro-tasks, stories, and epics.
    State is persisted to JSON.  All mutating operations are guarded
    by an *instance-local* RLock to avoid intra-process race conditions.
    """

    # ------------------------------- #
    # Construction / loading
    # ------------------------------- #
    def __init__(self, backlog_path: str):
        self.path = backlog_path
        self._lock = threading.RLock()
        self._items: List[Dict] = []
        # load() already acquires the lock – safe to call here
        self.load()

    # ------------------------------- #
    # Public API – READ
    # ------------------------------- #
    def list_items(self, status: str = "open") -> List[Dict]:
        """
        Return a list of tasks filtered by status.
        status: "open", "in_progress", "done", "archived" or "all"
        * Items with status "blocked" are never included in list_items("open")
        """
        with self._lock:
            if status == "open":
                data = [item for item in self._items if item.get("status", "open") == "open"]
                # explicit: blocked tasks are NOT returned for "open":
                data = [item for item in data if item.get("status") != "blocked"]
            elif status == "all":
                data = list(self._items)
            else:
                data = [item for item in self._items if item.get("status", "open") == status]
            # Shallow-copy so caller cannot mutate our internal state.
            return [dict(item) for item in data]

    def get_item(self, task_id: str) -> Dict:
        """Retrieve a single task by id (defensive copy)."""
        with self._lock:
            idx = self._task_index(task_id)
            return dict(self._items[idx])

    def export(self) -> List[Dict]:
        """Return a deep copy of *all* backlog items."""
        with self._lock:
            return copy.deepcopy(self._items)

    # ------------------------------- #
    # Public API – WRITE / MUTATE
    # ------------------------------- #
    def add_item(self, task: Dict) -> None:
        """Add a new task to backlog (enforces structure & unique id)."""
        with self._lock:
            task = self._normalize_task(task)
            if any(t["id"] == task["id"] for t in self._items):
                raise TaskStructureError(f"Duplicate task id: {task['id']}")
            self._items.append(task)
            self.save()

    def remove_item(self, task_id: str) -> None:
        """Soft-delete: mark a task as archived."""
        with self._lock:
            idx = self._task_index(task_id)
            self._items[idx]["status"] = "archived"
            self.save()

    def update_item(self, task_id: str, updates: Dict) -> None:
        """Update arbitrary fields of a task (e.g. assign, progress)."""
        with self._lock:
            idx = self._task_index(task_id)
            self._items[idx].update(updates)
            self.save()

    def archive_completed(self) -> None:
        """Mark all tasks with status 'done' as 'archived'."""
        with self._lock:
            changed = False
            for item in self._items:
                if item.get("status") == "done":
                    item["status"] = "archived"
                    changed = True
            if changed:
                self.save()

    # ------------------------------- #
    # Disk persistence (internal)
    # ------------------------------- #
    def save(self) -> None:
        """Persist backlog state atomically (under lock)."""
        with self._lock:
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w", encoding="utf8") as f:
                json.dump(self._items, f, indent=2)
            os.replace(tmp_path, self.path)

    def load(self) -> None:
        """Load backlog state from disk (gracefully handles missing file)."""
        with self._lock:
            if not os.path.exists(self.path):
                self._items = []
                return
            with open(self.path, "r", encoding="utf8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Backlog JSON must be a list of tasks")
            self._items = [self._normalize_task(t) for t in data]

    # ------------------------------- #
    # Internal helpers
    # ------------------------------- #
    def _task_index(self, task_id: str) -> int:
        for ix, t in enumerate(self._items):
            if t["id"] == task_id:
                return ix
        raise TaskNotFoundError(f"No task found with id={task_id}")

    @staticmethod
    def _normalize_task(task: Dict) -> Dict:
        """Ensure mandatory fields are present; fill sensible defaults."""
        t = dict(task)  # shallow copy
        for field in REQUIRED_FIELDS:
            if field not in t:
                if field == "id":
                    t["id"] = str(uuid.uuid4())
                elif field == "created_at":
                    import datetime

                    t["created_at"] = datetime.datetime.utcnow().isoformat()
                elif field == "status":
                    t["status"] = "open"
                elif field == "type":
                    t["type"] = "micro"
                else:
                    raise TaskStructureError(f"Missing required field: {field}")
        if not isinstance(t["id"], str):
            t["id"] = str(t["id"])
        # Validate status field:
        if t["status"] not in VALID_STATUSES:
            raise TaskStructureError(f"Invalid status: {t['status']}. Valid: {VALID_STATUSES}")
        return t

    # ------------------------------- #
    # Convenience string representation
    # ------------------------------- #
    def __str__(self) -> str:
        from tabulate import tabulate

        with self._lock:
            if not self._items:
                return "(Backlog empty)"
            rows = [
                (t["id"][:8], t["title"], t["type"], t.get("status", "open"), t.get("created_at", ""))
                for t in self._items
                if t.get("status") != "archived"
            ]
            headers = ["id", "title", "type", "status", "created"]
            return tabulate(rows, headers, tablefmt="github")


# --------------------------------------------------------------------------- #
# Development-only smoke-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    mgr = BacklogManager("dev_backlog.json")
    print(mgr)
