"""# MODULE CONTEXT SUMMARY
filepath: cadence/agents/efficiency.py
purpose: ""
public_api: [
    'cadence.agents.efficiency.EfficiencyAgent',
]
depends_on: []
used_by: []
direct_imports: [
    'base',
]
related_schemas: []
context_window_expected: ""
escalation_review: ""
# END MODULE CONTEXT SUMMARY"""


from .base import BaseAgent

class EfficiencyAgent(BaseAgent):
    """
    Efficient/cost-optimized agent (o4-mini): For bulk, mid-level reasoning, vision.
    """
    def __init__(self, **kwargs):
        super().__init__(model="o4-mini", **kwargs)
