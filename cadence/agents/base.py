"""# MODULE CONTEXT SUMMARY
filepath: cadence/agents/base.py
purpose: ""
public_api: [
    'cadence.agents.base.BaseAgent',
]
depends_on: [
    'cadence.llm.client',
]
used_by: []
direct_imports: [
    'cadence',
    'json',
    'typing',
]
related_schemas: []
context_window_expected: ""
escalation_review: ""
# END MODULE CONTEXT SUMMARY"""


from typing import List, Dict, Any, Optional
from cadence.llm.client import LLMClient, get_default_client

class BaseAgent:
    """Abstract LLM-backed agent: stateful message stack, universal interface."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        self.llm_client = llm_client or get_default_client()
        self.model = model
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, Any]] = []

    def reset_context(self, system_prompt: Optional[str] = None):
        """Clear history, optionally (re)set system prompt."""
        self.messages = []
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            self.append_message("system", sys_prompt)

    def append_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def run_interaction(self, user_input: str, **llm_kwargs) -> str:
        self.append_message("user", user_input)
        response = self.llm_client.call(
            self.messages,
            model=self.model,
            system_prompt=self.system_prompt,
            **llm_kwargs
        )
        self.append_message("assistant", response)
        return response

    async def async_run_interaction(self, user_input: str, **llm_kwargs) -> str:
        self.append_message("user", user_input)
        response = await self.llm_client.acall(
            self.messages,
            model=self.model,
            system_prompt=self.system_prompt,
            **llm_kwargs
        )
        self.append_message("assistant", response)
        return response

    def save_history(self, path: str):
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, indent=2, ensure_ascii=False)

    def load_history(self, path: str):
        import json
        with open(path, "r", encoding="utf-8") as f:
            self.messages = json.load(f)
