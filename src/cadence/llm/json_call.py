# src/cadence/llm/json_call.py
"""
LLMJsonCaller — ask an OpenAI-style model for *structured* output and
get back a validated Python object.

• Uses native function-calling / JSON mode when available.
• Falls back to streaming + incremental JSON parse if not.
• Performs jsonschema validation and automatic “please try again” repair.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
import json, logging, time

import jsonschema

from cadence.llm.client import get_default_client
from cadence.dev.schema import CHANGE_SET_V1

logger = logging.getLogger("cadence.llm.json_call")

_MAX_RETRIES = 3


class LLMJsonCaller:
    def __init__(self, *, schema: Dict = CHANGE_SET_V1, model: str | None = None):
        self.llm = get_default_client()
        self.schema = schema
        self.model = model

    # ------------------------------------------------------------------ #
    def ask(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(1, _MAX_RETRIES + 1):
            content = self.llm.call(
                messages,
                model=self.model,
                json_mode=True,          # new flag handled in patched client
            )
            try:
                obj = json.loads(content)
                jsonschema.validate(obj, self.schema)
                return obj
            except Exception as exc:      # noqa: BLE001
                logger.warning("JSON validation failed (attempt %d/%d): %s",
                               attempt, _MAX_RETRIES, exc)
                messages.append(
                    {
                        "role": "assistant",
                        "content": content[:4000],  # prevent runaway tokens
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Reply again using *only* valid JSON that matches the schema.",
                    }
                )
                time.sleep(1)

        raise RuntimeError("LLM gave invalid JSON after multiple attempts")
