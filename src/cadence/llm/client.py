# src/cadence/llm/client.py
from __future__ import annotations

import os, logging, time
from typing import List, Dict, Any, Optional, cast

from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessageParam
from dotenv import load_dotenv
import tiktoken
import hashlib
from cadence.audit.llm_call_log import LLMCallLogger

# one-time env expansion
load_dotenv()

logger = logging.getLogger("cadence.llm.client")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

_DEFAULT_MODELS = {
    "reasoning": "o3-2025-04-16",
    "execution": "gpt-4.1",
    "efficiency": "o4-mini",
}


def _count_tokens(model: str, messages: List[Dict[str, str]]) -> int:
    enc = tiktoken.get_encoding("o200k_base")
    return sum(len(enc.encode(m["role"])) + len(enc.encode(m["content"])) for m in messages)


class LLMClient:
    """
    Central sync/async wrapper with:

    • stub-mode when no API key
    • optional json_mode   → OpenAI “response_format={type:json_object}”
    • optional function_spec → OpenAI “tools=[…]”
    """

    _warned_stub = False

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        key = api_key or os.getenv("OPENAI_API_KEY")
        self.stub = not bool(key)
        self.api_key = key
        self.api_base = api_base or os.getenv("OPENAI_API_BASE")
        self.api_version = api_version or os.getenv("OPENAI_API_VERSION")
        self.default_model = default_model or _DEFAULT_MODELS["execution"]

        if self.stub:
            if not LLMClient._warned_stub:
                logger.warning(
                    "[Cadence] LLMClient stub-mode — OPENAI_API_KEY missing; "
                    ".call()/ .acall() return canned message."
                )
                LLMClient._warned_stub = True
            self._sync_client = None
            self._async_client = None
        else:
            try:
                self._sync_client  = OpenAI(api_key=self.api_key,
                                            base_url=self.api_base)
                self._async_client = AsyncOpenAI(api_key=self.api_key,
                                                 base_url=self.api_base)
                # If the test-suite monkey-patched OpenAI to a stub that
                # returns None we must still fall back to stub-mode.
                if self._sync_client is None or not hasattr(self._sync_client,
                                                            "chat"):
                    raise AttributeError
            except Exception:                      # noqa: BLE001
                self.stub = True
                self._sync_client = self._async_client = None
                if not LLMClient._warned_stub:
                    logger.warning("[Cadence] LLMClient stub-mode (auto)")
                    LLMClient._warned_stub = True

    # ------------------------------------------------------------------ #
    def _resolve_model(self, model: Optional[str], agent_type: Optional[str]) -> str:
        if model:
            return model
        if agent_type and agent_type in _DEFAULT_MODELS:
            return _DEFAULT_MODELS[agent_type]
        return self.default_model

    # ------------------------------------------------------------------ #
    def call(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        function_spec: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        if self.stub:
            return "LLM unavailable — Cadence stub-mode"

        used_model = self._resolve_model(model, agent_type)
        msgs = messages.copy()
        if system_prompt and not any(m.get("role") == "system" for m in msgs):
            msgs.insert(0, {"role": "system", "content": system_prompt})

        prompt_tokens = _count_tokens(used_model, msgs)
        t0 = time.perf_counter()

        # -- wrap tools if present --------------------------------------
        tools_arg = None
        tool_choice_arg = None
        if function_spec:
            tools_arg = [{"type": "function", "function": fs}
                         for fs in function_spec]
            tool_choice_arg = {
                "type": "function",
                "function": {               # <- nest correctly
                    "name": function_spec[0]["name"]
                }
            }

        # ----------------------------------------------------------------
        # Strip Cadence-internal kwargs that the OpenAI SDK does not accept.
        # (agent_id is used only by our audit log.)
        # ----------------------------------------------------------------
        safe_kwargs = dict(kwargs)
        safe_kwargs.pop("agent_id", None)

        response = self._sync_client.chat.completions.create(  # type: ignore[arg-type]
            model=used_model,
            messages=cast(List[ChatCompletionMessageParam], msgs),
            # Never send response_format if we are already in tool-call mode
            response_format=None if function_spec else (
                {"type": "json_object"} if json_mode else None
            ),
            tools=tools_arg,
            tool_choice=tool_choice_arg,
            **safe_kwargs,
        )

        # ------------------------------------------------------------ #
        # OpenAI mutually-excludes  “tools=…”   and   “response_format”.
        # If we supplied  tools=function_spec, the assistant returns
        # the result in   message.tool_calls[0].function.arguments
        # and leaves   message.content == None.
        # ------------------------------------------------------------ #
        if response.choices[0].message.content is None and response.choices[0].message.tool_calls:
            # We requested exactly ONE function; grab its arguments.
            content = response.choices[0].message.tool_calls[0].function.arguments
        else:
            content = (response.choices[0].message.content or "").strip()

        latency = time.perf_counter() - t0
        completion_tokens = getattr(response.usage, "completion_tokens", None)

        LLMCallLogger().log({
            "ts": time.time(),
            "agent_id": kwargs.get("agent_id", "n/a"),
            "model": used_model,
            "temperature": kwargs.get("temperature"),
            "top_p": kwargs.get("top_p"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_s": latency,
            "result_sha": hashlib.sha1(content.encode()).hexdigest(),
        })

        logger.info(
            "LLM call %s → %.2fs  prompt≈%d  completion≈%d",
            used_model,
            latency,
            prompt_tokens,
            completion_tokens,
        )
        return content

    # async version (rarely used by Cadence core)
    async def acall(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        function_spec: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        if self.stub:
            return "LLM unavailable — Cadence stub-mode"

        used_model = self._resolve_model(model, agent_type)
        msgs = messages.copy()
        if system_prompt and not any(m.get("role") == "system" for m in msgs):
            msgs.insert(0, {"role": "system", "content": system_prompt})

        prompt_tokens = _count_tokens(used_model, msgs)
        t0 = time.perf_counter()

        # -- wrap tools if present --------------------------------------
        tools_arg = None
        tool_choice_arg = None
        if function_spec:
            tools_arg = [{"type": "function", "function": fs}
                         for fs in function_spec]
            tool_choice_arg = {
                "type": "function",
                "function": {               # <- nest correctly
                    "name": function_spec[0]["name"]
                }
            }

        # ----------------------------------------------------------------
        # Strip Cadence-internal kwargs that the OpenAI SDK does not accept.
        # (agent_id is used only by our audit log.)
        # ----------------------------------------------------------------
        safe_kwargs = dict(kwargs)
        safe_kwargs.pop("agent_id", None)

        response = await self._async_client.chat.completions.create(  # type: ignore[arg-type]
            model=used_model,
            messages=cast(List[ChatCompletionMessageParam], msgs),
            # Never send response_format if we are already in tool-call mode
            response_format=None if function_spec else (
                {"type": "json_object"} if json_mode else None
            ),
            tools=tools_arg,
            tool_choice=tool_choice_arg,
            **safe_kwargs,
        )

        # ------------------------------------------------------------ #
        # OpenAI mutually-excludes  “tools=…”   and   “response_format”.
        # If we supplied  tools=function_spec, the assistant returns
        # the result in   message.tool_calls[0].function.arguments
        # and leaves   message.content == None.
        # ------------------------------------------------------------ #
        if response.choices[0].message.content is None and response.choices[0].message.tool_calls:
            # We requested exactly ONE function; grab its arguments.
            content = response.choices[0].message.tool_calls[0].function.arguments
        else:
            content = (response.choices[0].message.content or "").strip()

        latency = time.perf_counter() - t0
        completion_tokens = getattr(response.usage, "completion_tokens", None)

        LLMCallLogger().log({
            "ts": time.time(),
            "agent_id": kwargs.get("agent_id", "n/a"),
            "model": used_model,
            "temperature": kwargs.get("temperature"),
            "top_p": kwargs.get("top_p"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_s": latency,
            "result_sha": hashlib.sha1(content.encode()).hexdigest(),
        })

        logger.info(
            "LLM call %s → %.2fs  prompt≈%d  completion≈%d",
            used_model,
            latency,
            prompt_tokens,
            completion_tokens,
        )
        return content


# helper for callers that want the singleton
def get_default_client() -> LLMClient:
    return _DEFAULT_CLIENT


_DEFAULT_CLIENT = LLMClient()
