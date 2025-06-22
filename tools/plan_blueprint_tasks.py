#!/usr/bin/env python3
"""
tools/plan_blueprint_tasks.py

Turn high-level blueprint tasks into executable micro-tasks
that contain `change_set` payloads.
"""

from __future__ import annotations
import argparse, json, uuid, datetime, sys
from pathlib import Path

from cadence.dev.backlog import BacklogManager
from cadence.dev.change_set import ChangeSet
from cadence.agents.registry import get_agent    # NEW

def _plan_to_changeset(title: str, description: str) -> ChangeSet:
    """
    Ask the ExecutionAgent to return a **ChangeSet JSON block**.
    The agent prompt can be as sophisticated as you like; the only
    requirement is that it answers with a fenced ```json block that
    matches ChangeSet.from_json().
    """
    agent = get_agent("execution")                     # Core ExecutionAgent
    prompt = (
        "You are Cadence Planner.  Convert the following blueprint task\n"
        "into a compact ChangeSet JSON.  One ChangeSet must implement the\n"
        "task completely.  No prose, ONLY a fenced ```json block.\n\n"
        f"TITLE:\n{title}\n\nDESCRIPTION:\n{description}"
    )
    reply = agent.run_interaction(prompt)
    import re, json
    m = re.search(r"```json\\s*([\\s\\S]*?)```", reply, re.I)
    if not m:
        raise RuntimeError("Agent reply did not contain a JSON block.")

    cs = ChangeSet.from_dict(json.loads(m.group(1)))
    return cs

# ------------------------------------------------------------------ #
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backlog", default="dev_backlog.json")
    args = p.parse_args()

    bm = BacklogManager(args.backlog)
    blueprints = [t for t in bm.list_items("open") if "change_set" not in t]

    if not blueprints:
        print("No blueprint tasks without change_set — nothing to do.")
        return

    for bp in blueprints:
        cs = _plan_to_changeset(bp["title"], bp.get("description", ""))
        micro = {
            "id": str(uuid.uuid4()),
            "title": bp["title"],
            "type": "micro",
            "status": "open",
            "created_at": datetime.datetime.utcnow().isoformat(),
            "change_set": cs.to_dict(),
            "parent_id": bp["id"],
        }
        bm.add_item(micro)
        print(f"[OK] seeded micro-task {micro['id'][:8]} for “{bp['title']}”")

        # mark the blueprint as done/archived so it won't be reprocessed
        bm.update_item(bp["id"], {"status": "archived"})

    print("Backlog after planning:")
    print(bm)

if __name__ == "__main__":
    main()