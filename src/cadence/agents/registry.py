# src/cadence/agents/registry.py
"""
Single place to obtain a Core Agent or Profile.

Avoids hard-coding classes throughout the codebase.
"""

from typing import Type

from .reasoning import ReasoningAgent
from .execution import ExecutionAgent
from .efficiency import EfficiencyAgent
from .profile import BUILTIN_PROFILES, AgentProfile

_CORE_AGENTS: dict[str, Type] = {
    "reasoning": ReasoningAgent,
    "execution": ExecutionAgent,
    "efficiency": EfficiencyAgent,
}


def get_agent(agent_type: str, **kwargs):
    """
    Instantiate a Core Agent by `agent_type`.

    Example:
        agent = get_agent("execution")
    """
    if agent_type not in _CORE_AGENTS:
        raise ValueError(f"Unknown agent_type '{agent_type}'. Valid: {list(_CORE_AGENTS)}")
    return _CORE_AGENTS[agent_type](**kwargs)


def get_profile(profile_name: str) -> AgentProfile:
    if profile_name not in BUILTIN_PROFILES:
        raise ValueError(f"Unknown profile '{profile_name}'. Valid: {list(BUILTIN_PROFILES)}")
    return BUILTIN_PROFILES[profile_name]