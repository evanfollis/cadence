# Status: Archived. 
## Early prototype of my AI-native orchestration ideas. Superseded by synaplex and ai-native.”

# Cadence Development Loops

This repository contains Cadence, a prototype agent framework. Development is organised into numbered loops defined in `docs/next_steps.md`. Each loop represents a small, verifiable change set.

## Is the repo ready for Loop 0?

Yes. `src/cadence/dev/command_center.py` has been removed, there are no `streamlit` imports in the source tree and the legacy UI placeholder lives under `legacy/command_center.py`. The only missing step from Loop 0 is a short note in `docs/DEV_PROCESS.md` explaining that the Streamlit prototype is archived and a React GUI will replace it later.

## Running an orchestration cycle

1. Install dependencies and run the tests once:
   ```bash
   pip install -e .[dev]
   pytest -q
   ```
2. Start a task cycle with:
   ```bash
   python -m cadence.dev.orchestrator start
   ```
   Use `--disable-meta` to skip governance metrics when offline.

The orchestrator will load the backlog (`dev_backlog.json`), apply one task and record the result. After each cycle inspect `dev_record.json` for the summary.

## Executing loops

1. Read the next loop description in `docs/next_steps.md`.
2. Ensure your working tree is clean (`git status`).
3. Run `python -m cadence.dev.orchestrator start`.
   - If multiple open tasks exist the CLI will prompt you to pick one.
   - The agent will generate a patch, run tests and attempt to commit.
4. Review the commit and push to your fork.
5. Repeat until all tasks for the current loop are complete.

### Handling failures

- **Test failures**: the orchestrator automatically rolls back the patch. Fix the problem or mark the task as blocked.
- **Dirty repo**: if rollback fails the repo is left dirty. Clean the tree manually, then re-run the cycle.
- **Empty backlog**: a few placeholder micro tasks will be generated automatically. Edit `dev_backlog.json` to queue real work.

## Useful scripts

- `scripts/run_orchestrator.py` – non‑interactive loop runner.
- `tools/lint_docs.py` – checks that tables in `docs/` match the enums in code.
- `quick_start.py` – creates `docs/FILE_TREE.md`, a quick-start guide and a reset script.
