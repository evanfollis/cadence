# ./cadence/agents/efficiency.py
from __future__ import annotations

from .base import BaseAgent
from .profile import EFFICIENCY_PROFILE, AgentProfile


class EfficiencyAgent(BaseAgent):
    """
    Final class: fast, low-cost linting & summarisation.
    """

    def __init__(self, profile: AgentProfile = EFFICIENCY_PROFILE, **kwargs):
        super().__init__(profile, **kwargs)