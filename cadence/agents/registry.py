"""# MODULE CONTEXT SUMMARY
filepath: cadence/agents/registry.py
purpose: ""
public_api: [
    'cadence.agents.registry.get_agent',
]
depends_on: []
used_by: []
direct_imports: [
    'efficiency',
    'execution',
    'reasoning',
]
related_schemas: []
context_window_expected: ""
escalation_review: ""
# END MODULE CONTEXT SUMMARY"""


from .reasoning import ReasoningAgent
from .execution import ExecutionAgent
from .efficiency import EfficiencyAgent

AGENT_TYPES = {
    "reasoning": ReasoningAgent,
    "execution": ExecutionAgent,
    "efficiency": EfficiencyAgent,
}

def get_agent(agent_type: str, **kwargs):
    """
    Retrieve an agent instance by type. Extra kwargs passed to constructor.
    """
    if agent_type not in AGENT_TYPES:
        raise ValueError(f"Unknown agent_type '{agent_type}'. Valid: {list(AGENT_TYPES.keys())}")
    return AGENT_TYPES[agent_type](**kwargs)
