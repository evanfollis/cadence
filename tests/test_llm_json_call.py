"""
tests/test_llm_json_call.py
===========================

Regression tests for cadence.llm.json_call.LLMJsonCaller

The stubbed client means no real network traffic is made.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, List

import pytest

# ------------------------------------------------------------------------- #
# ensure  src/  is importable from any working dir
# ------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if (PROJECT_ROOT / "src").exists():
    sys.path.insert(0, str(PROJECT_ROOT))

from cadence.llm.json_call import LLMJsonCaller
from cadence.dev.schema import CHANGE_SET_V1


# ------------------------------------------------------------------------- #
# helpers
# ------------------------------------------------------------------------- #
def _minimal_changeset() -> dict[str, Any]:
    """Return the smallest ChangeSet that validates against CHANGE_SET_V1."""
    return {
        "message": "demo",
        "edits": [
            {
                "path": "foo.py",
                "mode": "add",
                "after": "print('hi')",
                "before_sha": None,
            }
        ],
        "author": "",
        "meta": {},
    }


class _StubLLM:
    """
    Very small stand-in for cadence.llm.client.LLMClient.

    • pops predefined responses off a queue;
    • counts how many times .call() is invoked.
    """

    def __init__(self, responses: List[Any]):
        self._queue = list(responses)
        self.call_count = 0
        self.stub = False  # important – LLMJsonCaller checks this

    # signature compatible with real .call()
    def call(self, *_a, **_kw):
        self.call_count += 1
        if not self._queue:
            raise RuntimeError("StubLLM queue exhausted")
        return self._queue.pop(0)

    # async variant (unused here, but keeps interface parity)
    async def acall(self, *_a, **_kw):
        return self.call()


# ------------------------------------------------------------------------- #
# pytest fixture that patches get_default_client() for each test
# ------------------------------------------------------------------------- #
@pytest.fixture
def _patch_llm(monkeypatch):
    """
    Provide a helper that installs a fresh StubLLM for the current test.
    """

    def _install(responses: List[Any]) -> _StubLLM:
        from cadence.llm import json_call as _jc_mod

        stub = _StubLLM(responses)
        monkeypatch.setattr(_jc_mod, "get_default_client", lambda: stub)
        return stub

    return _install


# ------------------------------------------------------------------------- #
# test-cases
# ------------------------------------------------------------------------- #
def test_plain_json_string(_patch_llm):
    """Happy-path: assistant returns plain JSON text."""
    payload = _minimal_changeset()
    _patch_llm([json.dumps(payload)])

    caller = LLMJsonCaller(schema=CHANGE_SET_V1)
    obj = caller.ask("sys", "user")
    assert obj == payload


def test_tool_call_dict_return(_patch_llm):
    """
    Tool-call path: LLMClient.call() returns the parsed dict directly,
    so LLMJsonCaller must accept the object unchanged.
    """
    payload = _minimal_changeset()
    _patch_llm([payload])  # already-parsed dict

    caller = LLMJsonCaller(schema=CHANGE_SET_V1)
    obj = caller.ask("system", "user")
    assert obj == payload


def test_retry_then_success(_patch_llm, monkeypatch):
    """
    First response is invalid → LLMJsonCaller retries and
    succeeds on the second round.
    """
    bad = "NOT-JSON"
    good = _minimal_changeset()
    stub = _patch_llm([bad, json.dumps(good), json.dumps(good)])  # queue len ≥ _MAX_RETRIES

    # Skip real waiting during retries
    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_kw: None)

    caller = LLMJsonCaller(schema=CHANGE_SET_V1)
    obj = caller.ask("sys", "usr")
    assert obj == good

    # One bad + one good response must have been consumed
    assert stub.call_count == 2
    assert len(stub._queue) == 1