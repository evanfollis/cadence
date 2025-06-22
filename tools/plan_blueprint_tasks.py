#!/usr/bin/env python3
"""
Convert blueprint tasks in dev_backlog.json into micro-tasks with validated
ChangeSets.  Uses function-calling JSON mode and full project context.
"""

from __future__ import annotations
import argparse, uuid, datetime, json, textwrap
from pathlib import Path

from cadence.dev.backlog import BacklogManager
from cadence.dev.change_set import ChangeSet
from cadence.llm.json_call import LLMJsonCaller

# ------------------------------------------------------------------ #
# Load project context snapshots
# ------------------------------------------------------------------ #
CTX_DIR = Path("agent_context")
DOCS      = json.loads((CTX_DIR / "docs.json").read_text())             if (CTX_DIR / "docs.json").exists() else {}
MODULES   = json.loads((CTX_DIR / "module_contexts.json").read_text())  if (CTX_DIR / "module_contexts.json").exists() else {}
CODE_SNAP = json.loads((CTX_DIR / "code.json").read_text())             if (CTX_DIR / "code.json").exists() else {}

_SYSTEM_CONTEXT = textwrap.dedent(
    f"""
    ----------  PROJECT CONTEXT (truncated) ----------
    ## Docs
    {json.dumps(DOCS, separators=(",", ":"), ensure_ascii=False)[:100000]}

    ## Module summaries
    {json.dumps(MODULES, separators=(",", ":"), ensure_ascii=False)[:100000]}

    ## Source snapshot
    {json.dumps(CODE_SNAP, separators=(",", ":"), ensure_ascii=False)[:100000]}
    --------------------------------------------------
    """
).strip()

SYSTEM_PROMPT = (
    "You are Cadence Planner.  Given a blueprint TITLE and DESCRIPTION, "
    "generate a *single* JSON object that conforms to the Cadence "
    "ChangeSet schema.  Use the project context for accuracy.  "
    "Do NOT return markdown, only JSON."
    "\n\n" + _SYSTEM_CONTEXT
)

caller = LLMJsonCaller()  # singleton


def _plan(blueprint: dict) -> ChangeSet:
    title = blueprint["title"]
    desc = blueprint.get("description", "")
    user_prompt = (
        f"BLUEPRINT TITLE:\n{title}\n\n"
        f"BLUEPRINT DESCRIPTION:\n{desc}\n\n"
        "Return the ChangeSet JSON now."
    )
    obj = caller.ask(SYSTEM_PROMPT, user_prompt)
    return ChangeSet.from_dict(obj)


# ------------------------------------------------------------------ #
def ingest_blueprints(backlog_path: Path) -> None:
    bm = BacklogManager(backlog_path.as_posix())
    blueprints = [t for t in bm.list_items("open") if "change_set" not in t]

    if not blueprints:
        print("No blueprint tasks pending.")
        return

    for bp in blueprints:
        try:
            cs = _plan(bp)
        except Exception as exc:  # noqa: BLE001
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
        print(f"[OK] {micro['id'][:8]} — ChangeSet generated")

    print("\nBacklog snapshot:")
    print(bm)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backlog", default="dev_backlog.json")
    args = ap.parse_args()
    ingest_blueprints(Path(args.backlog))


if __name__ == "__main__":  # pragma: no cover
    main()