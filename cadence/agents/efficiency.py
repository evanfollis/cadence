
from .base import BaseAgent

class EfficiencyAgent(BaseAgent):
    """
    Efficient/cost-optimized agent (o4-mini): For bulk, mid-level reasoning, vision.
    """
    def __init__(self, **kwargs):
        super().__init__(model="o4-mini", **kwargs)
