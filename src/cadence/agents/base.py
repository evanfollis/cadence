# src/cadence/agents/base.py
from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from src.cadence.llm.client import LLMClient, get_default_client
from src.cadence.context.provider import ContextProvider, SnapshotContextProvider
from .profile import AgentProfile


class BaseAgent:
    """
    The one true superclass for *all* Cadence agents.

    An agent = (profile) + (conversation state) + (LLM client) [+ optional helpers]

    Subclasses SHOULD NOT hard-code models; they inherit that from the supplied
    `AgentProfile`.  Core agents (Reasoning / Execution / Efficiency) simply
    pass the canonical profile; personas may inject a custom one.
    """

    def __init__(
        self,
        profile: AgentProfile,
        *,
        llm_client: Optional[LLMClient] = None,
        system_prompt: Optional[str] = None,
        context_provider: Optional[ContextProvider] = None,
    ):
        self.profile = profile
        self.llm_client = llm_client or get_default_client()
        self.system_prompt = system_prompt or profile.default_system_prompt
        self.context_provider = context_provider or SnapshotContextProvider()
        self.messages: List[Dict[str, Any]] = []
        self.reset_context()

    # --------------------------------------------------------------------- #
    # Conversation helpers
    # --------------------------------------------------------------------- #
    def reset_context(self, system_prompt: Optional[str] = None):
        """Clear history and (re)set the system prompt."""
        self.messages = []
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            self.append_message("system", sys_prompt)

    def append_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    # --------------------------------------------------------------------- #
    # LLM calls
    # --------------------------------------------------------------------- #
    def run_interaction(self, user_input: str, **llm_kwargs) -> str:
        self.append_message("user", user_input)
        response = self.llm_client.call(
            self.messages,
            model=self.profile.model,
            system_prompt=None,  # already injected
            **llm_kwargs,
        )
        self.append_message("assistant", response)
        return response

    async def async_run_interaction(self, user_input: str, **llm_kwargs) -> str:
        self.append_message("user", user_input)
        response = await self.llm_client.acall(
            self.messages,
            model=self.profile.model,
            system_prompt=None,
            **llm_kwargs,
        )
        self.append_message("assistant", response)
        return response

    # --------------------------------------------------------------------- #
    # Persistence
    # --------------------------------------------------------------------- #
    def save_history(self, path: str):
        import json
        Path(path).write_text(json.dumps(self.messages, indent=2, ensure_ascii=False))

    def load_history(self, path: str):
        import json
        self.messages = json.loads(Path(path).read_text())

    # --------------------------------------------------------------------- #
    # Context helpers
    # --------------------------------------------------------------------- #
    def gather_codebase_context(
        self,
        root: Tuple[str, ...] = ("cadence", "docs"),
        ext: Tuple[str, ...] = (".py", ".md", ".json", ".mermaid"),
        **kwargs,
    ) -> str:
        """Return repo/docs snapshot via the injected ContextProvider."""
        return self.context_provider.get_context(*(Path(r) for r in root), exts=ext, **kwargs)
