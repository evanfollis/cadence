# scripts/auto_generate_patches.py
"""
Bridge between a plain-English backlog task and a fully-formed “diff”
task that DevOrchestrator can execute autonomously.
"""
from pathlib import Path
import json, textwrap, os, sys

from cadence.agents.registry import get_agent            # Core agents
from cadence.dev.backlog import BacklogManager
from cadence.dev.generator import TaskGenerator

EXEC_AGENT = get_agent("execution")      # gpt-4.1 context-aware generator
BACKLOG_PATH = os.getenv("CADENCE_BACKLOG", "dev_backlog.json")

def _build_prompt(task: dict) -> str:
    instruct = textwrap.dedent(f"""
        You are an ExecutionAgent inside the Cadence platform.
        Produce a UNIFIED DIFF that implements exactly this task:

        {json.dumps(task, indent=2)}

        • The diff must apply cleanly to the CURRENT repo root.
        • Finish your answer with a Markdown ```diff fenced block ONLY.
    """)
    return instruct.strip()

def main():
    backlog = BacklogManager(BACKLOG_PATH)
    untranslated = [t for t in backlog.list_items("open") if "diff" not in t]

    if not untranslated:
        print("No tasks need patch generation.")
        return

    for t in untranslated:
        diff = EXEC_AGENT.run_interaction(_build_prompt(t))
        # Strip markdown fence if ExecutionAgent wrapped it
        diff = diff.split("```diff")[-1].split("```")[0].strip()
        before_path = Path(t["diff_file_guess"]) if "diff_file_guess" in t else None
        if before_path and before_path.exists():
            before_text = before_path.read_text()
        else:
            before_text = ""   # new file

        t["diff"] = {
            "file": str(before_path) if before_path else "<TBD>",
            "before": before_text,
            "after": ""  # will be reconstructed by TaskExecutor.build_patch
        }
        t["generated_patch"] = diff        # hang onto raw diff for record
        backlog.update_item(t["id"], t)    # persist

    print(f"Generated patches for {len(untranslated)} task(s).")

if __name__ == "__main__":
    main()