# ./cadence/agents/execution.py
from __future__ import annotations

from .base import BaseAgent
from .profile import EXECUTION_PROFILE, AgentProfile


class ExecutionAgent(BaseAgent):
    """
    Final class: generates or refactors significant portions of the codebase.
    """

    def __init__(self, profile: AgentProfile = EXECUTION_PROFILE, **kwargs):
        super().__init__(profile, **kwargs)