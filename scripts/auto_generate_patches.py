#!/usr/bin/env python3
"""
Generate executable before/after diffs (or raw `patch`) for every open
task in dev_backlog.json.

Run with --force to overwrite existing diff/patch blocks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from cadence.agents.registry import get_agent
from cadence.dev.backlog import BacklogManager

# --------------------------------------------------------------------- #
# Config paths
# --------------------------------------------------------------------- #
BACKLOG_PATH = Path(os.getenv("CADENCE_BACKLOG", "dev_backlog.json"))

PROMPT_TPL   = Path("agent_context/base_execution_prompt.txt")
DOCS_JSON    = Path("agent_context/docs.json")
CODE_JSON    = Path("agent_context/code.json")
MODULES_JSON = Path("agent_context/module_contexts.json")

# --------------------------------------------------------------------- #
# Rich system-prompt (≈30 k tokens once!)
# --------------------------------------------------------------------- #
base_prompt = (
    PROMPT_TPL.read_text()
    if PROMPT_TPL.exists()
    else "You are Cadence ExecutionAgent.  Produce git-apply-able unified diffs."
)

def _make_agent():
    # Each task gets a fresh ExecutionAgent with the same big prompt
    return get_agent("execution", system_prompt=base_prompt)

# --------------------------------------------------------------------- #
# Task-specific user prompt
# --------------------------------------------------------------------- #
def _build_prompt(task: dict) -> str:
    return (
        "You are an ExecutionAgent inside the Cadence platform.\n"
        "Produce a UNIFIED DIFF that implements exactly this task:\n\n"
        f"{json.dumps(task, indent=2)}\n\n"
        "STRICT REQUIREMENTS:\n"
        "• The diff MUST contain `--- a/<path>` and `+++ b/<path>` header lines.\n"
        "• Hunks must begin with @@, context lines with ' '.\n"
        "• It must apply with `git apply -p0` at repo root without error.\n"
        "• Return *only* one fenced  ```diff  code block – no explanation.\n"
    ).strip()

# --------------------------------------------------------------------- #
def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true",
                   help="Regenerate even if task already has diff or patch.")
    return p.parse_args()

# --------------------------------------------------------------------- #
def main() -> None:
    args = _cli()
    bm   = BacklogManager(str(BACKLOG_PATH))

    candidates = [
        t for t in bm.list_items("open")
        if args.force or ("diff" not in t and "patch" not in t)
    ]
    if not candidates:
        print("No tasks need patch generation.")
        return

    for task in candidates:
        agent = _make_agent()
        agent.append_message("user", _build_prompt(task))
        llm_reply = agent.run_interaction("")

        # ---------------- extract fenced diff ---------------------------
        fence = re.search(r"```diff\s*([\s\S]*?)```", llm_reply)
        patch = (fence.group(1) if fence else llm_reply).strip()

        if not patch:
            print(f"[WARN] Empty patch for '{task['title']}', skipping.")
            continue

        # ---------------- try to compute after-text ---------------------
        file_match = re.search(r"^[+-]{3}\s+(?:a/|b/)?(.+)$", patch, re.M)
        if not file_match:
            print(f"[WARN] No file header found in patch for '{task['title']}', "
                  f"storing raw patch only.")
            task["patch"] = patch
            bm.update_item(task["id"], task)
            continue

        file_rel = file_match.group(1).strip()
        before   = Path(file_rel).read_text(encoding="utf8") if Path(file_rel).exists() else ""

        try:
            with tempfile.TemporaryDirectory() as td:
                tmp_root = Path(td)
                tmp_file = tmp_root / file_rel
                tmp_file.parent.mkdir(parents=True, exist_ok=True)
                tmp_file.write_text(before, encoding="utf8")

                subprocess.run(                         # may raise
                    ["git", "apply", "-p0", "-"],
                    input=patch, text=True, cwd=tmp_root, check=True
                )
                after = tmp_file.read_text(encoding="utf8")

        except subprocess.CalledProcessError as exc:
            print(f"[WARN] git apply failed for '{task['title']}'. "
                  f"Storing raw patch. First 20 lines:\n"
                  f"{patch.splitlines()[:20]}\n---")
            task["patch"] = patch
            bm.update_item(task["id"], task)
            continue

        # -------------- success → store structured diff ----------------
        task["diff"] = {"file": file_rel, "before": before, "after": after}
        task.pop("patch", None)
        bm.update_item(task["id"], task)
        print(f"[OK] Diff attached for '{task['title']}' → {file_rel}")

    print(f"Updated {len(candidates)} task(s).")

if __name__ == "__main__":
    main()