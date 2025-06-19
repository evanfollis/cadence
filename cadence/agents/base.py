# cadence/agents/base.py
from typing import List, Dict, Any
from cadence.llm.client import _CLIENT as default_llm_client
from cadence.llm.client import _MODEL as default_model

class Agent:
    def __init__(self, llm_client: Any = default_llm_client, model: str = default_model):
        self.llm_client = llm_client
        self.model = model
        self.messages: List[Dict[str, Any]] = []

    def reset_context(self, *args, **kwargs):
        """Reset the agent's conversational context (override in subclass)."""
        self.messages = []

    def append_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def run_interaction(self, user_input: str, **llm_kwargs) -> str:
        """
        Add user_input, run the LLM, append the response, and return it.
        Assumes self.llm_client follows OpenAI client conventions.
        """
        self.append_message("user", user_input)
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            **llm_kwargs
        )
        assistant_msg = response.choices[0].message.content.strip()
        self.append_message("assistant", assistant_msg)
        return assistant_msg

    def save_history(self, path):
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, indent=2, ensure_ascii=False)

    def load_history(self, path):
        import json
        with open(path, "r", encoding="utf-8") as f:
            self.messages = json.load(f)
