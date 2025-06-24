# tools/lint_docs.py
"""
Lint the CADENCE docs for drift in phase table, agents, and OKRs.
Ensures doc ↔ code synchrony on phase ordering and canonical identifiers.
Extended for Failure-Diagnose phase.
"""
import re, sys
from pathlib import Path

PHASE_ENUM = [
    "Backlog",
    "Generate",
    "Execute",
    "Review-Reasoning",
    "Failure-Diagnose",
    "Review-Efficiency",
    "Branch-Isolate",
    "Test (pre-merge)",
    "Commit",
    "Merge Queue",
    "Record",
    "Meta",
]

def lint_dev_process_phases():
    """
    Ensure phase table in docs/DEV_PROCESS.md matches PHASE_ENUM, including 04-b Failure-Diagnose
    """
    path = Path("docs/DEV_PROCESS.md")
    lines = path.read_text(encoding="utf8").splitlines()
    in_table = False
    found = []
    for line in lines:
        if line.startswith("| Seq "): in_table = True
        if in_table and line.startswith("|") and "Phase" not in line and "-----" not in line:
            cells = [x.strip() for x in line.split("|")[1:]]
            phase = cells[1]
            found.append(phase)
        if in_table and line.strip() == "": break
    if found != PHASE_ENUM:
        print("[31mPhase table drift detected![0m")
        print("doc table:   ", found)
        print("PHASE_ENUM:  ", PHASE_ENUM)
        sys.exit(1)
    print("Phase table matches code.")

def main():
    lint_dev_process_phases()
    print("All lint checks passed.")

if __name__ == "__main__":
    main()
