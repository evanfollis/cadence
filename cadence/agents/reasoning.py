"""# MODULE CONTEXT SUMMARY
filepath: cadence/agents/reasoning.py
purpose: ""
public_api: [
    'cadence.agents.reasoning.ReasoningAgent',
]
depends_on: []
used_by: []
direct_imports: [
    'base',
    'subprocess',
    'sys',
    'typing',
]
related_schemas: []
context_window_expected: ""
escalation_review: ""
# END MODULE CONTEXT SUMMARY"""


from typing import Optional
from .base import BaseAgent
import sys
import subprocess

class ReasoningAgent(BaseAgent):
    """
    High-reasoning agent (o3 model): For meta, multi-step, chain-of-thought.
    Injects codebase/docs context at reset.
    """

    def __init__(self, **kwargs):
        super().__init__(model="o3-2025-04-16", **kwargs)

    def reset_context(self, system_prompt: Optional[str] = None):
        """Wipe, inject code snapshot, optionally set prompt."""
        code_snapshot = self.collect_code_snapshot()
        self.messages = []
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            self.append_message("system", sys_prompt)
        self.append_message(
            "user",
            f"Full codebase and docs snapshot as JSON:\n```json\n{code_snapshot}\n```"
        )

    def collect_code_snapshot(self) -> str:
        """Call tools/collect_code.py for the latest codebase/docs snapshot."""
        args = [
            sys.executable, "tools/collect_code.py",
            "--root", "cadence", "--root", "docs",
            "--ext", ".py", ".md", ".cfg", ".toml", ".ini",
            "--max-bytes", "50000", "--out", "-"
        ]
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print("ERROR: collect_code.py failed")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            raise
        return result.stdout
