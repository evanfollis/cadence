# src/cadence/dev/failure_responder.py
"""
FailureResponder: Phase-2

Responds agentically to failed tasks during workflow execution.

- Holds a ReasoningAgent (LLM or stub) for sub-task breakdown after failure.
- Receives {failed_task, stage, error, diff, test_output} in handle_failure().
- Prompts agent (JSON mode) for a breakdown into sub-tasks (for retry/repair).
- Injects sub-tasks into BacklogManager (status=open, parent_id=<failed>).
- Marks failed task as status="blocked".
- Depth-limited via max_depth (default=2) to prevent recursive fanout.
"""
from __future__ import annotations
import json
from typing import Optional, Any, Callable

from cadence.agents.registry import get_agent
from cadence.dev.backlog import BacklogManager, TaskStructureError

class FailureResponder:
    def __init__(self, backlog: BacklogManager, *, max_depth: int =2, agent_factory: Optional[Callable]=None):
        self.backlog = backlog
        self.max_depth = max_depth
        if agent_factory is not None:
            self.agent = agent_factory()
        else:
            self.agent = get_agent("reasoning")

    def handle_failure(self, *,
                      failed_task: dict,
                      stage: str,
                      error: Any,
                      diff: Optional[str]=None,
                      test_output: Optional[str]=None,
                      depth: int=0) -> Optional[list]:
        if depth >= self.max_depth:
            return None
        prompt = self._build_prompt(failed_task, stage, error, diff, test_output)
        try:
            agent_resp = self.agent.run_interaction(prompt, json_mode=True)
            if isinstance(agent_resp, str):
                subtask_list = json.loads(agent_resp)
            else:
                subtask_list = agent_resp
            # Validate: must be list of dicts, each dict is a task blueprint
            if not (isinstance(subtask_list, list) and all(isinstance(x, dict) for x in subtask_list)):
                raise ValueError("Agent did not return list[dict] for sub-tasks.")
        except Exception as ex:
            # Fallback: log/skip
            return None
        parent_id = failed_task.get("id")
        for t in subtask_list:
            t = dict(t)
            t.setdefault("status", "open")
            t["parent_id"] = parent_id
            try:
                self.backlog.add_item(t)
            except TaskStructureError:
                continue  # skip malformed
        self.backlog.update_item(parent_id, {"status": "blocked"})
        return subtask_list

    def _build_prompt(self, failed_task, stage, error, diff, test_output):
        prompt = (
            "A task in the Cadence agentic workflow has failed. "
            "Your job: return up to three sub-tasks (JSON list of dicts). "
            "Each dict should contain at minimum 'title', 'type', 'description'. "
            "Maintain enough granularity that other agents (or humans) can retry or repair the failure.\n\n"
            f"Failed task id: {failed_task.get('id')}\nTitle: {failed_task.get('title')}\nStage: {stage}\nError: {error}"
        )
        if diff:
            prompt += f"\nDiff:\n{diff.strip()[:1200]}"
        if test_output:
            prompt += f"\nTest output:\n{test_output.strip()[:1200]}"
        prompt += "\nReturn ONLY a JSON array (list of task dicts)."
        return prompt

# Test stub for offline/CI
class StubLLM:
    def call(self, messages, **kwargs):
        # Always returns two sub-tasks for testing
        return json.dumps([
          {"title": "Diagnose error", "type": "micro", "description": "Analyze failure in stage."},
          {"title": "Attempt automated repair", "type": "micro", "description": "Propose fix for root cause."}
        ])

# Simple unit test to ensure CI does not require LLM
if __name__ == "__main__":
    from cadence.dev.backlog import BacklogManager
    import tempfile, os
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("[]")
        tf.flush()
        backlog = BacklogManager(tf.name)
        responder = FailureResponder(backlog, agent_factory=lambda: type("StubAgent", (), {"run_interaction": lambda s, prompt, **kw: StubLLM().call([])})())
        failed_task = {"id": "fail001", "title": "Patch step failed"}
        out = responder.handle_failure(failed_task=failed_task, stage="patch", error="patch_apply error")
        assert isinstance(out, list) and len(out) == 2
        assert backlog.list_items("open")
        assert backlog.get_item("fail001")["status"] == "blocked"
        os.unlink(tf.name)
