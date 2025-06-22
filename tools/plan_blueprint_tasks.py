#!/usr/bin/env python3
"""
Plan blueprint tasks → micro-tasks with ChangeSet.

Reads dev_backlog.json, finds any open task *without* “change_set”, calls the
LLMJsonCaller defined above to obtain one, validates it, and writes a new
micro-task back to the backlog.
"""

from __future__ import annotations
import argparse, uuid, datetime, json
from pathlib import Path

from cadence.dev.backlog import BacklogManager
from cadence.dev.change_set import ChangeSet
from cadence.llm.json_call import LLMJsonCaller

# tools/plan_blueprint_tasks.py  (top of file)

from pathlib import Path
import json, textwrap

CTX_DIR = Path("agent_context")
DOCS      = json.loads((CTX_DIR / "docs.json").read_text())     if (CTX_DIR / "docs.json").exists() else {}
MODULES   = json.loads((CTX_DIR / "module_contexts.json").read_text()) if (CTX_DIR / "module_contexts.json").exists() else {}
CODE_SNAP = json.loads((CTX_DIR / "code.json").read_text())     if (CTX_DIR / "code.json").exists() else {}

SYSTEM_PROMPT = textwrap.dedent(f"""
    You are **Cadence Planner** — a senior engineer inside an autonomous
    software-delivery platform.  Your job:

      1. Read the blueprint TITLE + DESCRIPTION supplied by the user.
      2. Inspect the *ground-truth* project context below.
      3. Produce EXACTLY ONE JSON object that satisfies the
         Cadence ChangeSet schema (provided implicitly by the function spec).

    ----------  PROJECT CONTEXT  ----------
    # High-level docs
    {json.dumps(DOCS, separators=(',', ':'))}

    # Module summaries
    {json.dumps(MODULES, separators=(',', ':'))}

    # Source snapshot (truncated)
    {json.dumps(CODE_SNAP, separators=(',', ':'))}
    ----------  END CONTEXT  ----------

    Output policy:
      • Use ONLY the JSON format requested by the function spec.
      • Do NOT wrap the object in Markdown fences.
      • After you emit the JSON, stop — no commentary.
""").strip()


def _plan(blueprint: dict) -> ChangeSet:
    caller = LLMJsonCaller()
    title = blueprint["title"]
    desc = blueprint.get("description", "")

    user_prompt = (
        f"Blueprint title:\n{title}\n\n"
        f"Blueprint description:\n{desc}\n\n"
        "Return a ChangeSet JSON that implements this task completely."
    )

    obj = caller.ask(SYSTEM_PROMPT, user_prompt)
    return ChangeSet.from_dict(obj)


# ---------------------------------------------------------------------- #
def ingest_blueprints(backlog_path: Path) -> None:
    bm = BacklogManager(backlog_path.as_posix())
    blueprints = [t for t in bm.list_items("open") if "change_set" not in t]

    if not blueprints:
        print("No blueprint tasks pending.")
        return

    for bp in blueprints:
        try:
            cs = _plan(bp)
        except Exception as exc:   # noqa: BLE001
            print(f"[FAIL] {bp['title']}: {exc}")
            continue

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
        bm.update_item(bp["id"], {"status": "archived"})
        print(f"[OK] micro-task {micro['id'][:8]} created for {bp['title']}")

    print("-- backlog snapshot --")
    print(bm)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backlog", default="dev_backlog.json")
    args = ap.parse_args()

    ingest_blueprints(Path(args.backlog))


if __name__ == "__main__":  # pragma: no cover
    main()