
from .base import BaseAgent

class ExecutionAgent(BaseAgent):
    """
    Fast flagship agent (gpt-4.1): For code patching, deterministic tasks, tests.
    Minimal context by default.
    """
    def __init__(self, **kwargs):
        super().__init__(model="gpt-4.1", **kwargs)

    # If you want: override reset_context for extra lean, or leave as base.
