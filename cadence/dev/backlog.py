
# cadence/dev/backlog.py

"""
Cadence BacklogManager
---------------------
Single Responsibility: CRUD on task backlog (no code/diffs). All file IO explicit, JSON-logged, and future agent-ready.
"""

import os
import json
import uuid
from typing import List, Dict, Optional

class BacklogEmptyError(Exception):
    """Raised if attempting to pop or select from an empty backlog."""
    pass

class TaskStructureError(Exception):
    """Raised if a task dict doesn't conform to required structure."""
    pass

class TaskNotFoundError(Exception):
    """Raised if a requested task_id is not in the backlog."""
    pass

REQUIRED_FIELDS = ("id", "title", "type", "status", "created_at")

class BacklogManager:
    """
    Manages Cadence backlog: microtasks, stories, and epics.
    - All tasks are plain dicts with mandatory fields.
    - Underlying store is a JSON file [{...}, ...].
    """

    def __init__(self, backlog_path: str):
        self.path = backlog_path
        self._items: List[Dict] = []
        self.load()

    def list_items(self, status: str = "open") -> List[Dict]:
        """
        Return a list of tasks filtered by status.
        status: "open", "in_progress", "done", or "all"
        """
        if status == "all":
            return list(self._items)
        return [item for item in self._items if item.get("status", "open") == status]

    def add_item(self, task: Dict) -> None:
        """
        Add a new task to backlog. Enforce structure and unique id.
        """
        task = self._normalize_task(task)
        if any(t["id"] == task["id"] for t in self._items):
            raise TaskStructureError(f"Duplicate task id: {task['id']}")
        self._items.append(task)
        self.save()

    def remove_item(self, task_id: str) -> None:
        """
        Mark a task as archived (status = 'archived').
        """
        idx = self._task_index(task_id)
        self._items[idx]["status"] = "archived"
        self.save()

    def archive_completed(self) -> None:
        """
        Mark all tasks with status 'done' as 'archived'.
        """
        n = 0
        for item in self._items:
            if item.get("status") == "done":
                item["status"] = "archived"
                n += 1
        if n:
            self.save()

    def save(self) -> None:
        """Persist backlog state to self.path as JSON (UTF-8, indent)."""
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf8") as f:
            json.dump(self._items, f, indent=2)
        os.replace(tmp_path, self.path)

    def load(self) -> None:
        """
        Reload backlog state from file. If the file does not exist, starts empty.
        """
        if not os.path.exists(self.path):
            self._items = []
            return
        with open(self.path, "r", encoding="utf8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Backlog JSON must be a list of tasks")
            self._items = [self._normalize_task(t) for t in data]

    def _normalize_task(self, task: Dict) -> Dict:
        """
        Ensure the dict has all required fields, fill missing, return new dict.
        """
        t = dict(task)  # copy
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
        # Sanity check: no harmful keys
        if not isinstance(t["id"], str):
            t["id"] = str(t["id"])
        return t

    def _task_index(self, task_id: str) -> int:
        """
        Internal: find list index of task by id or raise.
        """
        for ix, t in enumerate(self._items):
            if t["id"] == task_id:
                return ix
        raise TaskNotFoundError(f"No task found with id={task_id}")

    def get_item(self, task_id: str) -> Dict:
        """Retrieve a task by id."""
        idx = self._task_index(task_id)
        return self._items[idx]

    def update_item(self, task_id: str, updates: Dict) -> None:
        """
        Update arbitrary fields of a task (e.g. assign, progress, edit).
        """
        idx = self._task_index(task_id)
        self._items[idx].update(updates)
        self.save()

    def export(self) -> List[Dict]:
        """
        Return a (deep) copy of all backlog items.
        """
        import copy
        return copy.deepcopy(self._items)

    # Optional: friendly CLI/str output
    def __str__(self) -> str:
        from tabulate import tabulate
        if not self._items:
            return "(Backlog empty)"
        rows = [
            (t["id"][:8], t["title"], t["type"], t.get("status", "open"), t.get("created_at", ""))
            for t in self._items if t.get("status") != "archived"
        ]
        headers = ["id", "title", "type", "status", "created"]
        return tabulate(rows, headers, tablefmt="github")

# For direct module test/dev, NOT in prod code.
if __name__ == "__main__":
    # Example usage
    mgr = BacklogManager("dev_backlog.json")
    print(mgr)
    # To add: mgr.add_item({"title": "Test microtask", "type": "micro"})