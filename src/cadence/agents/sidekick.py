# src/cadence/agents/sidekick.py
"""
Persona agent that *delegates* to a ReasoningAgent but presents a
human-centric mentor/advisor interface.
"""
from __future__ import annotations

import json
from pathlib import Path

from .profile import AgentProfile, REASONING_PROFILE
from .reasoning import ReasoningAgent
from .base import BaseAgent


_SIDEKICK_PROMPT = """
You are an AI-enhanced co-developer and mentor. Your primary goal is to
extract the most creative, high-leverage ideas from the human user and
transform them into actionable improvements for the Cadence platform.
Avoid tactical implementation details unless asked; focus on vision,
architecture, and pragmatic next steps.
"""


class Sidekick:
    """
    Thin wrapper: exposes `run_interaction` but delegates work to an
    internal ReasoningAgent instance configured with a custom prompt.
    """

    def __init__(self):
        profile = AgentProfile(
            name="sidekick",
            role="advisor",
            model=REASONING_PROFILE.model,
            context_limit=REASONING_PROFILE.context_limit,
            review_policy=REASONING_PROFILE.review_policy,
            default_system_prompt=REASONING_PROFILE.default_system_prompt,
            extra=REASONING_PROFILE.extra.copy() if REASONING_PROFILE.extra else {},
        )
        self._agent = ReasoningAgent(profile=profile, system_prompt=_SIDEKICK_PROMPT)
        self._inject_seed_context()

    # ------------------------------------------------------------------ #
    # Public façade
    # ------------------------------------------------------------------ #
    def run_interaction(self, user_input: str, **kwargs) -> str:
        return self._agent.run_interaction(user_input, **kwargs)

    async def async_run_interaction(self, user_input: str, **kwargs) -> str:
        return await self._agent.async_run_interaction(user_input, **kwargs)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #
    def _inject_seed_context(self):
        """Reset the delegate agent and seed it with repo context."""
        BaseAgent.reset_context(self._agent)
        snapshot = self._agent.gather_codebase_context()
        self._agent.append_message("user", f"REFERENCE_DOCUMENTS:\\n{snapshot}\\n---\\nYou are cleared for deep reasoning.")