# src/cadence/agents/reasoning.py
from __future__ import annotations

from .base import BaseAgent
from .profile import REASONING_PROFILE, AgentProfile


class ReasoningAgent(BaseAgent):
    """
    Final class: provides deep, chain-of-thought reasoning and architectural review.
    """

    def __init__(self, profile: AgentProfile = REASONING_PROFILE, **kwargs):
        super().__init__(profile, **kwargs)

    # Automatically inject a fresh code snapshot on each reset
    def reset_context(self, system_prompt: str | None = None):
        super().reset_context(system_prompt)
        docs = self.gather_codebase_context(
            root=("docs",),
            ext=(".md", ".mermaid", ".json"),
        )
        self.append_message("user", f"REFERENCE_DOCUMENTS:\n{docs}\n---\nYou are cleared for deep reasoning.")