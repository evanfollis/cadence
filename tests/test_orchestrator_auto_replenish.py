"""
Smoke-test for DevOrchestrator._ensure_backlog()
"""

from __future__ import annotations
import pytest


class _DummyBacklog:
    def __init__(self):
        self.items = []

    def list_items(self, status="open"):
        return [t for t in self.items if t.get("status") == status]

    def add_item(self, task):
        self.items.append(dict(task))


class _DummyGenerator:
    def __init__(self):
        self.calls = []

    def generate_tasks(self, mode: str, count: int):
        assert mode == "micro"
        self.calls.append(count)
        return [
            {
                "id": f"gen-{i}",
                "title": f"auto-task {i}",
                "type": "micro",
                "status": "open",
                "created_at": "now",
            }
            for i in range(count)
        ]


class _DummyRecord:
    def __init__(self):
        self.snapshots = []

    def save(self, task, state, extra=None):
        self.snapshots.append(state)


@pytest.mark.parametrize("count", [1, 4])
def test_auto_replenish(count):
    from src.cadence.dev.orchestrator import DevOrchestrator

    orch = DevOrchestrator.__new__(DevOrchestrator)  # bypass __init__
    orch.backlog = _DummyBacklog()
    orch.generator = _DummyGenerator()
    orch.record = _DummyRecord()
    orch.backlog_autoreplenish_count = count
    orch._record = orch.record.save

    orch._ensure_backlog()
    assert len(orch.backlog.list_items("open")) == count
    assert "backlog_replenished" in orch.record.snapshots