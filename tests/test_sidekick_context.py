from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if (PROJECT_ROOT / "src").exists():
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _stub_openai(monkeypatch):
    fake = types.SimpleNamespace(OpenAI=lambda *a, **k: None,
                                 AsyncOpenAI=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "openai", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    yield

def test_seed_context_resets(monkeypatch):
    from cadence.agents import sidekick as sk_mod
    from cadence.agents.reasoning import ReasoningAgent

    monkeypatch.setattr(ReasoningAgent, "gather_codebase_context", lambda self: "CTX")

    sk = sk_mod.Sidekick()
    # Initial seed on construction
    assert len(sk._agent.messages) == 2
    assert sk._agent.messages[0]["content"] == sk_mod._SIDEKICK_PROMPT
    assert "CTX" in sk._agent.messages[1]["content"]

    sk._agent.append_message("assistant", "hi")
    assert len(sk._agent.messages) == 3

    sk._inject_seed_context()
    assert len(sk._agent.messages) == 2
    assert sk._agent.messages[0]["content"] == sk_mod._SIDEKICK_PROMPT
    assert "CTX" in sk._agent.messages[1]["content"]