"""# MODULE CONTEXT SUMMARY
filepath: cadence/agents/execution.py
purpose: ""
public_api: [
    'cadence.agents.execution.ExecutionAgent',
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

class ExecutionAgent(BaseAgent):
    """
    Fast flagship agent (gpt-4.1): For code patching, deterministic tasks, tests.
    Minimal context by default.
    """
    def __init__(self, **kwargs):
        super().__init__(model="gpt-4.1", **kwargs)

    # If you want: override reset_context for extra lean, or leave as base.
