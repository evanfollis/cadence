# src/cadence/llm/json_call.py
"""
LLMJsonCaller – ask the model for strictly-typed JSON via function-calling.
Retries automatically on validation failure and normalises legacy shapes.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict

import jsonschema

from cadence.llm.client import get_default_client
from cadence.dev.schema import CHANGE_SET_V1

logger = logging.getLogger("cadence.llm.json_call")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

_MAX_RETRIES = 3


class LLMJsonCaller:
    """
    Generic wrapper: validate any JSON object returned via the OpenAI
    *function-calling* pathway.

    Parameters
    ----------
    schema        – Draft-07 JSON-schema the assistant must satisfy.
    function_name – Name exposed to the OpenAI tools array (defaults to
                    “create_change_set” for backward-compat).
    """
    def __init__(
        self,
        *,
        schema: Dict = CHANGE_SET_V1,
        function_name: str = "create_change_set",
        model: str | None = None,
    ):
        self.schema = schema
        self.model = model
        self.llm = get_default_client()

        self.func_spec = [
            {
                "name": function_name,
                "description": "Return an object that satisfies the supplied schema",
                "parameters": self.schema,
            }
        ]

    # ------------------------------------------------------------------ #
    def ask(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        # Off-line / CI guard – bail out immediately
        if getattr(self.llm, "stub", False):
            raise RuntimeError("LLM unavailable — stub-mode")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(1, _MAX_RETRIES + 1):
            resp = self.llm.call(
                messages,
                model=self.model,
                json_mode=True,
                function_spec=self.func_spec,
            )

            try:
                # resp may be str *or* dict (when tool-call path chosen)
                obj = resp if isinstance(resp, dict) else _parse_json(resp)
                # Change-set helper no-op for other schemas
                if self.schema is CHANGE_SET_V1:
                    obj = _normalise_legacy(obj)
                jsonschema.validate(obj, self.schema)
                return obj

            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "JSON validation failed (%d/%d): %s", attempt, _MAX_RETRIES, exc
                )

                # When parsing/validation fails, fall back to the raw response
                assistant_output = (
                    resp if isinstance(resp, str) else json.dumps(resp)
                )[:4000]

                # Inject the invalid output so the model can self-correct
                messages.append({"role": "assistant", "content": assistant_output})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The JSON object is invalid. "
                            "Return ONLY a corrected JSON object."
                        ),
                    }
                )
                time.sleep(1)

        raise RuntimeError("LLM gave invalid JSON after multiple retries")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _parse_json(text: str) -> Dict[str, Any]:
    """
    If OpenAI response_format works, `text` is already pure JSON.
    Guard against accidental fencing.
    """
    if text.strip().startswith("```"):
        m = re.search(r"```json\s*([\s\S]*?)```", text, re.I)
        if not m:
            raise ValueError("Could not locate fenced JSON block")
        text = m.group(1)
    return json.loads(text)


def _normalise_legacy(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept LLM output that uses {"changes":[…]} instead of {"edits":[…]}.
    """
    if "changes" in obj and "edits" not in obj:
        obj["edits"] = [
            {
                "path": c.get("file") or c.get("path"),
                "mode": c.get("mode", "modify"),
                "after": c.get("after"),
                "before_sha": c.get("before_sha"),
            }
            for c in obj["changes"]
        ]
        obj.pop("changes")
    return obj