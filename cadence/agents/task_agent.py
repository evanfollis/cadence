# cadence/agents/task_agent.py
"""
TaskAgent — Conversational design/code agent with episodic, task-centric context.

- Maintains a chat-style history (OpenAI format), with message[0] always the
  latest full snapshot of the codebase and docs (from tools/collect_code.py).
- Exposes API to reset context, append dialog, run LLM, and save/load history.
- Integrates with orchestrator to refresh code context and archive old dialog
  after each finalized task.
"""

from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from .base import Agent

DEFAULT_COLLECT_PATH = "tools/collect_code.py"
DEFAULT_COLLECT_ARGS = [
    "--root", "kairos",
    "--root", "docs",
    "--ext", ".py", ".md", ".cfg", ".toml", ".ini",
    "--max-bytes", "50000",
    "--out", "-"
]

class TaskAgent(Agent):
    def __init__(self):
        super().__init__()
        # These can be overridden for per-agent context
        self.collect_roots = ["docs", "kairos", "tools"]
        self.collect_ext = (".py", ".md")
        self.max_bytes = 50000

    def set_collect_code_args(self, roots, ext, max_bytes=None):
        self.collect_roots = list(roots)
        self.collect_ext = tuple(ext)
        if max_bytes is not None:
            self.max_bytes = max_bytes

    def _collect_code_snapshot(self) -> str:
        """Return a JSON string of the current codebase/docs snapshot."""
        args = ["--root"] + list(self.collect_roots)
        args += ["--ext"] + list(self.collect_ext)
        args += ["--max-bytes", str(self.max_bytes), "--out", "-"]
        try:
            result = subprocess.run(
                [sys.executable, DEFAULT_COLLECT_PATH, *args],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            print("ERROR: collect_code.py failed")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            raise
        return result.stdout

    def reset_context(self, system_prompt: Optional[str] = None):
        """
        Wipe conversation history and set messages[0] as latest snapshot.
        Optionally prepend a custom system prompt (as message[0]).
        """
        code_snapshot = self._collect_code_snapshot()
        self.messages = []
        if system_prompt:
            self.append_message("system", system_prompt)
        self.append_message(
            "user",
            f"Full codebase and docs snapshot as JSON:\n```json\n{code_snapshot}\n```"
        )
