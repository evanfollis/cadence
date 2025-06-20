
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv

# One-time load
load_dotenv()

# Set up logger
logger = logging.getLogger("cadence.llm.client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Global default model configs
_DEFAULT_MODELS = {
    "reasoning": "o3-2025-04-16",
    "execution": "gpt-4.1",
    "efficiency": "o4-mini"
}

def get_env(key: str, required=True, default=None):
    val = os.getenv(key)
    if not val and required:
        raise RuntimeError(f"Environment variable {key} not set.")
    return val or default

# Centralized sync/async LLM client
class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        self.api_key = api_key or get_env('OPENAI_API_KEY')
        self.api_base = api_base or os.getenv('OPENAI_API_BASE', None)
        self.api_version = api_version or os.getenv('OPENAI_API_VERSION', None)
        self.default_model = default_model or _DEFAULT_MODELS["execution"]

        # Sync and Async clients
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_base)
        self._sync_client = OpenAI(api_key=self.api_key, base_url=self.api_base)

    def _resolve_model(self, model: Optional[str], agent_type: Optional[str]):
        if model:
            return model
        if agent_type and agent_type in _DEFAULT_MODELS:
            return _DEFAULT_MODELS[agent_type]
        return self.default_model

    def call(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        used_model = self._resolve_model(model, agent_type)
        msgs = messages.copy()
        if system_prompt and not any(m.get("role") == "system" for m in msgs):
            msgs.insert(0, {"role": "system", "content": system_prompt})

        logger.info(f"LLM sync call: model={used_model}, msgs_len={len(msgs)}")
        response = self._sync_client.chat.completions.create(
            model=used_model,
            messages=msgs,
            # max_tokens=max_tokens,
            **kwargs
        )
        content = response.choices[0].message.content.strip()
        logger.debug(f"LLM response: {content[:120]}...")
        return content

    async def acall(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        used_model = self._resolve_model(model, agent_type)
        msgs = messages.copy()
        if system_prompt and not any(m.get("role") == "system" for m in msgs):
            msgs.insert(0, {"role": "system", "content": system_prompt})

        logger.info(f"LLM async call: model={used_model}, msgs_len={len(msgs)}")
        response = await self._async_client.chat.completions.create(
            model=used_model,
            messages=msgs,
            max_tokens=max_tokens,
            **kwargs
        )
        content = response.choices[0].message.content.strip()
        logger.debug(f"LLM response: {content[:120]}...")
        return content

# Provide a default client getter for agents
def get_default_client() -> LLMClient:
    return _DEFAULT_CLIENT

_DEFAULT_CLIENT = LLMClient()
