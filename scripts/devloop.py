#!/usr/bin/env python3
"""
Cadence one-shot loop
====================

Combines:

1. `scripts/update_backlog.py`
2. a backlog dry-run validator (catches empty / bad diffs)
3. `scripts/run_orchestrator.py`

Usage
-----

    # one normal cycle
    python scripts/loop.py

    # pass flags straight through to run_orchestrator.py
    python scripts/loop.py --id 955710ac

    # delete invalid tasks instead of aborting
    python scripts/loop.py --auto-purge

    # validate only (no orchestrator run)
    python scripts/loop.py --validate-only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────
def _run(cmd: List[str], label: str) -> None:
    print(f"\n🔸 {label}: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"❌ '{label}' failed (exit {exc.returncode})")
        sys.exit(exc.returncode)


def _validate_backlog(backlog_path: Path) -> Tuple[List[str], List[str]]:
    """
    Returns (bad_ids, error_messages).
    """
    from src.cadence.dev.backlog import BacklogManager
    from src.cadence.dev.executor import TaskExecutor, TaskExecutorError

    bl = BacklogManager(backlog_path)
    executor = TaskExecutor("cadence")

    bad: List[str] = []
    errs: List[str] = []

    for t in bl.list_items("open"):
        try:
            executor.build_patch(t)
        except TaskExecutorError as exc:
            bad.append(t["id"])
            errs.append(f"{t['id'][:8]} → {exc}")

    return bad, errs


def _purge_tasks(backlog_path: Path, task_ids: List[str]) -> None:
    from src.cadence.dev.backlog import BacklogManager

    bl = BacklogManager(backlog_path)
    for tid in task_ids:
        bl.remove_item(tid)
    print(f"🧹 purged {len(task_ids)} invalid task(s) from backlog")


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Cadence single-cycle helper")
    parser.add_argument(
        "--backlog",
        default="dev_backlog.json",
        help="Path to dev_backlog.json (default: %(default)s)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run backlog validation but skip orchestrator",
    )
    parser.add_argument(
        "--auto-purge",
        action="store_true",
        help="Delete any task that fails dry-run validation",
    )
    # capture *all* unknown flags to forward to run_orchestrator.py
    args, passthrough = parser.parse_known_args()

    backlog_path = Path(args.backlog)

    # 1) refresh backlog
    _run(["python", "scripts/update_backlog.py"], "refresh backlog")

    # 2) dry-run validate
    bad_ids, msgs = _validate_backlog(backlog_path)
    if bad_ids:
        print("❌ invalid tasks detected:\n  " + "\n  ".join(msgs))
        if args.auto_purge:
            _purge_tasks(backlog_path, bad_ids)
        else:
            sys.exit(66)  # EX_DATAERR

    print("✅ backlog validation passed")

    if args.validate_only:
        return

    # 3) orchestrator
    _run(["python", "scripts/run_orchestrator.py", *passthrough], "orchestrator")


if __name__ == "__main__":  # pragma: no cover
    main()
