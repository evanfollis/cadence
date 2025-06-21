# src/cadence/dev/record.py

"""
Cadence TaskRecord
------------------
Thread-safe, append-only persistence of task life-cycle history.

Key upgrades (2025-06-21)
• Replaced `threading.Lock` with **re-entrant** `threading.RLock` so
  nested mutator calls (e.g., save() → _persist()) never dead-lock.
• Every public mutator (save, append_iteration) and every private helper
  that writes to disk now acquires the lock.
"""

from __future__ import annotations

import os
import json
import threading
import copy
from typing import List, Dict, Optional
from datetime import datetime, UTC

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class TaskRecordError(Exception):
    """Custom error for task record issues."""


# --------------------------------------------------------------------------- #
# TaskRecord
# --------------------------------------------------------------------------- #
class TaskRecord:
    def __init__(self, record_file: str):
        self.record_file = record_file
        self._lock = threading.RLock()  # <-- upgraded to RLock
        self._records: List[Dict] = []
        self._idmap: Dict[str, Dict] = {}
        self._load()  # safe – _load() acquires the lock internally

    # ------------------------------------------------------------------ #
    # Public API – mutators
    # ------------------------------------------------------------------ #
    def save(self, task: dict, state: str, extra: dict | None = None) -> None:
        """
        Append a new state snapshot for the given task_id.
        """
        with self._lock:
            record = self._find_or_create_record(task)
            snapshot = {
                "state": state,
                "timestamp": self._now(),
                "task": copy.deepcopy(task),
                "extra": copy.deepcopy(extra) if extra else {},
            }
            record["history"].append(snapshot)
            self._sync_idmap()
            self._persist()

    def append_iteration(self, task_id: str, iteration: dict) -> None:
        """
        Append a fine-grained iteration step (e.g. reviewer notes).
        """
        with self._lock:
            record = self._find_record(task_id)
            if record is None:
                raise TaskRecordError(f"No record for task id={task_id}")
            iter_snapshot = {"timestamp": self._now(), **copy.deepcopy(iteration)}
            record.setdefault("iterations", []).append(iter_snapshot)
            self._persist()

    # ------------------------------------------------------------------ #
    # Public API – read-only
    # ------------------------------------------------------------------ #
    def load(self) -> List[Dict]:
        """Return a deep copy of all records."""
        with self._lock:
            return copy.deepcopy(self._records)

    # ------------------------------------------------------------------ #
    # Internal helpers (locking handled by callers)
    # ------------------------------------------------------------------ #
    def _find_or_create_record(self, task: dict) -> Dict:
        tid = self._get_task_id(task)
        rec = self._idmap.get(tid)
        if rec is None:
            rec = {
                "task_id": tid,
                "created_at": self._now(),
                "history": [],
                "iterations": [],
            }
            self._records.append(rec)
            self._idmap[tid] = rec
        return rec

    def _find_record(self, task_id: str) -> Optional[Dict]:
        return self._idmap.get(task_id)

    @staticmethod
    def _get_task_id(task: dict) -> str:
        tid = task.get("id")
        if not tid:
            raise TaskRecordError("Task dict missing 'id'. Cannot save record.")
        return tid

    # ------------------------------------------------------------------ #
    # Disk persistence & loading (always under lock)
    # ------------------------------------------------------------------ #
    def _persist(self) -> None:
        with self._lock:
            tmp = self.record_file + ".tmp"
            with open(tmp, "w", encoding="utf8") as f:
                json.dump(self._records, f, indent=2)
            os.replace(tmp, self.record_file)

    def _load(self) -> None:
        with self._lock:
            if not os.path.exists(self.record_file):
                self._records = []
                self._idmap = {}
                return
            with open(self.record_file, "r", encoding="utf8") as f:
                self._records = json.load(f)
            self._sync_idmap()

    def _sync_idmap(self):
        self._idmap = {rec["task_id"]: rec for rec in self._records}

    @staticmethod
    def _now():
        return datetime.now(UTC).isoformat()


# --------------------------------------------------------------------------- #
# Dev-only sanity CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    rec = TaskRecord("dev_record.json")
    tid = "a1b2c3"
    task = {"id": tid, "title": "Do something", "status": "open"}
    rec.save(task, state="patch_proposed", extra={"patch": "--- foo"})
    rec.append_iteration(tid, {"reviewer": "alice", "opinion": "looks good"})
    import pprint

    pprint.pp(rec.load())
