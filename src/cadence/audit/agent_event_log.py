from __future__ import annotations

import json, os, time, uuid
from pathlib import Path
from threading import RLock
from typing import Dict, Any
from contextlib import nullcontext

try:
    from filelock import FileLock            # optional, but recommended
except ImportError:                          # pragma: no cover
    FileLock = None                          # type: ignore

# configurable via env-vars, but sane defaults for CI & dev shells
# Resolve to an absolute path so later ``chdir`` calls do not break logging
LOG_ROOT   = Path(os.getenv("CADENCE_AGENT_LOG_DIR", ".cadence_logs")).resolve()
MAX_BYTES  = int(os.getenv("CADENCE_AGENT_LOG_ROLL_MB", "50")) * 1024 * 1024
LOG_ROOT.mkdir(parents=True, exist_ok=True)


class AgentEventLogger:
    """
    Append-only JSON-Lines audit log.
    Each write = one *event* dict:
        {ts, event, agent, role?, content?, profile?, context_digest?}
    """

    _instance: "AgentEventLogger|None" = None

    # ---------------- singleton boiler-plate -------------------------
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        ts = time.strftime("%Y%m%d-%H%M%S")
        self._file = LOG_ROOT / f"events-{ts}.jsonl"
        self._lock = RLock()
        self._flock = FileLock(str(self._file)+".lock") if FileLock else None

    # ---------------- public helpers --------------------------------
    def register_agent(self, profile: str,
                       system_prompt: str,
                       context_digest: str | None = None) -> str:
        aid = f"{profile}-{uuid.uuid4().hex[:8]}"
        self._write({
            "ts": time.time(),
            "event": "agent_init",
            "agent": aid,
            "profile": profile,
            "context_digest": context_digest,
            "system_prompt": system_prompt,
        })
        return aid

    def log_message(self, aid: str, role: str, content: str) -> None:
        self._write({
            "ts": time.time(),
            "event": "msg",
            "agent": aid,
            "role": role,
            "content": content,
        })

    # ---------------- internals -------------------------------------
    def _write(self, obj: Dict[str, Any]) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        ctx = self._flock if self._flock else nullcontext()
        with ctx, self._lock:
            with self._file.open("a", encoding="utf-8") as fh:
                fh.write(line)

        # rotate if the file gets too big
        if self._file.stat().st_size > MAX_BYTES:
            ts = time.strftime("%Y%m%d-%H%M%S")
            self._file.rename(self._file.with_name(f"events-{ts}.jsonl"))
            # new empty file will be created automatically on next write