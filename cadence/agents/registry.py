
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
