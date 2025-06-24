from __future__ import annotations
import json, time, os
from pathlib import Path
from threading import RLock
from contextlib import nullcontext
try:
    from filelock import FileLock
except ImportError:
    FileLock = None  # pragma: no cover

ROOT = Path(os.getenv("CADENCE_AGENT_LOG_DIR", ".cadence_logs"))
ROOT.mkdir(parents=True, exist_ok=True)
_MAX = 50 * 1024 * 1024                   # 50 MB rotate

class LLMCallLogger:
    _inst: "LLMCallLogger|None" = None
    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
            cls._inst._init()
        return cls._inst
    def _init(self):
        ts = time.strftime("%Y%m%d-%H%M%S")
        self._file = ROOT / f"llm-{ts}.jsonl"
        self._lock = RLock()
        self._flock = FileLock(str(self._file)+".lock") if FileLock else None
    # ------------------------------------------------------------------
    def log(self, rec: dict):
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        ctx = self._flock if self._flock else nullcontext()
        with ctx, self._lock:
            with self._file.open("a", encoding="utf-8") as fh:
                fh.write(line)
        if self._file.stat().st_size > _MAX:
            ts = time.strftime("%Y%m%d-%H%M%S")
            self._file.rename(self._file.with_name(f"llm-{ts}.jsonl"))