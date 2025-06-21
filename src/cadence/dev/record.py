
# src/cadence/dev/record.py

"""
Cadence TaskRecord
-----------------
Single Responsibility: Append/persist task processtates for full audit/repro. 
Write/read only here. 
File format: JSON list of dicts, one per unique task_id; each has history of states/iterations.
"""

import os
import json
import threading
import copy
from typing import List, Dict, Optional

class TaskRecordError(Exception):
    """Custom error for task record issues."""
    pass

class TaskRecord:
    def __init__(self, record_file: str):
        self.record_file = record_file
        self._lock = threading.Lock()
        # Always keep in-memory up to date with file
        self._records: List[Dict] = []
        self._idmap: Dict[str, Dict] = {}  # task_id -> record dict
        self._load()

    def save(self, task: dict, state: str, extra: dict = None) -> None:
        """
        Records a snapshot for given task_id and state (e.g. "patch_proposed", "patch_reviewed", etc).
        Extra provides arbitrary info (patch, review, commit_sha, test_results, etc).
        If task does not exist (task_id is new), creates new record.
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

    def load(self) -> List[Dict]:
        """
        Returns a (deep) copy of all records (full history).
        """
        with self._lock:
            return copy.deepcopy(self._records)

    def append_iteration(self, task_id: str, iteration: dict) -> None:
        """
        Appends a new step/edit/review (dict) to a task's record—usually finer-grained than save().
        """
        with self._lock:
            record = self._find_record(task_id)
            if record is None:
                raise TaskRecordError(f"No record for task id={task_id}")
            iter_snapshot = {
                "timestamp": self._now(),
                **copy.deepcopy(iteration)
            }
            record.setdefault("iterations", []).append(iter_snapshot)
            self._persist()

    # ========== Internal Below ==========

    def _find_or_create_record(self, task: dict) -> Dict:
        """
        Finds or creates a new record for given task.
        """
        tid = self._get_task_id(task)
        rec = self._idmap.get(tid)
        if rec is None:
            rec = {
                "task_id": tid,
                "created_at": self._now(),
                "history": [],
                "iterations": []
            }
            self._records.append(rec)
            self._idmap[tid] = rec
        return rec

    def _find_record(self, task_id: str) -> Optional[Dict]:
        return self._idmap.get(task_id)

    def _get_task_id(self, task: dict) -> str:
        tid = task.get("id")
        if not tid:
            raise TaskRecordError("Task dict missing 'id'. Cannot save record.")
        return tid

    def _persist(self) -> None:
        """
        Writes in-memory records to disk, atomic/overwrite (JSON).
        """
        tmp = self.record_file + ".tmp"
        with open(tmp, "w", encoding="utf8") as f:
            json.dump(self._records, f, indent=2)
        os.replace(tmp, self.record_file)

    def _load(self) -> None:
        """Loads file into memory iff exists. Otherwise, empty record."""
        if not os.path.exists(self.record_file):
            self._records = []
            self._idmap = {}
            return
        with open(self.record_file, "r", encoding="utf8") as f:
            self._records = json.load(f)
        self._sync_idmap()

    def _sync_idmap(self):
        """Ensures self._idmap is up to date with self._records."""
        self._idmap = {rec["task_id"]: rec for rec in self._records}

    def _now(self):
        from datetime import datetime
        return datetime.utcnow().isoformat()

# Example CLI/sanity use (not for prod)
if __name__ == "__main__":
    rec = TaskRecord("dev_record.json")
    tid = "a1b2c3"
    # Save new record
    task = {"id": tid, "title": "Do something", "status": "open"}
    rec.save(task, state="patch_proposed", extra={"patch": "--- foo"})
    # Append an iteration (e.g., reviewer comment)
    rec.append_iteration(tid, {"reviewer": "alice", "opinion": "looks good"})
    # Print record for tid
    print(json.dumps(rec.load(), indent=2))