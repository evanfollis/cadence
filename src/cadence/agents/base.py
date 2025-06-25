# src/cadence/agents/base.py
from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from cadence.llm.client import LLMClient, get_default_client
from cadence.context.provider import ContextProvider, SnapshotContextProvider
from cadence.audit.agent_event_log import AgentEventLogger
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

        # ---- audit logger  ---------------------------------------
        _alog = AgentEventLogger()
        self._agent_id = _alog.register_agent(
            self.profile.name,
            self.system_prompt or "",
            context_digest=self._context_digest(),
        )
        self._alog = _alog

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
        try:
            self._alog.log_message(self._agent_id, "user", user_input)
        except Exception:
            pass
        response = self.llm_client.call(
            self.messages,
            model=self.profile.model,
            system_prompt=None,  # already injected
            agent_id=self._agent_id,
            **llm_kwargs,
        )
        self.append_message("assistant", response)
        try:
            self._alog.log_message(self._agent_id, "assistant", response)
        except Exception:
            pass
        return response

    async def async_run_interaction(self, user_input: str, **llm_kwargs) -> str:
        self.append_message("user", user_input)
        try:
            self._alog.log_message(self._agent_id, "user", user_input)
        except Exception:
            pass
        response = await self.llm_client.acall(
            self.messages,
            model=self.profile.model,
            system_prompt=None,
            agent_id=self._agent_id,
            **llm_kwargs,
        )
        self.append_message("assistant", response)
        try:
            self._alog.log_message(self._agent_id, "assistant", response)
        except Exception:
            pass
        return response
    
    # ---------------- internal helper -------------------------------
    def _context_digest(self) -> str:
        """
        Quick SHA-1 fingerprint of the reference docs that were injected
        on reset(); helps you prove later that the agent saw *fresh*
        context when the conversation started.
        """
        import hashlib, json
        if self.messages and self.messages[-1]["role"] == "user" \
           and self.messages[-1]["content"].startswith("REFERENCE_DOCUMENTS:"):
            payload = self.messages[-1]["content"]
            return hashlib.sha1(payload.encode()).hexdigest()
        return hashlib.sha1(json.dumps(self.messages[:1]).encode()).hexdigest()

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
        root: Tuple[str, ...] | None = None,
        ext: Tuple[str, ...] = (".py", ".md", ".json", ".mermaid", ".txt", ".yaml", ".yml"),
        **kwargs,
    ) -> str:
        """Return repo/docs snapshot via the injected ContextProvider."""
        # ---------- resolve roots -------------------------------------
        # Prefer the real package path  src/cadence/  if it exists; fall back to
        # legacy  cadence/  (used by older notebooks or when the repo is
        # checked out directly inside PYTHONPATH).
        if root is None:
            candidates = ("src/cadence", "tests", "tools", "docs", "scripts")
        else:
            candidates = root

        paths = [Path(p) for p in candidates if Path(p).exists()]
        if not paths:                       # nothing found → empty string
            return ""

        return self.context_provider.get_context(*paths, exts=ext, **kwargs)
