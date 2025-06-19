# cadence/agents/chat/agent_registry.py
from cadence.agents.task_agent import TaskAgent

class AgentRegistry:
    def __init__(self):
        self._agents = {}

    def get_or_create(self, name, roots, ext=(".py", ".md"), system_prompt=None):
        if name not in self._agents:
            agent = TaskAgent()
            agent.set_collect_code_args(roots=roots, ext=ext)
            agent.reset_context(system_prompt=system_prompt)
            self._agents[name] = agent
        return self._agents[name]

    def list_agents(self):
        return list(self._agents.keys())

    def reset_agent(self, name, roots, ext=(".py", ".md"), system_prompt=None):
        agent = TaskAgent()
        agent.set_collect_code_args(roots=roots, ext=ext)
        agent.reset_context(system_prompt=system_prompt)
        self._agents[name] = agent
        return agent
