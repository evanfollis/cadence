
# CADENCE DEVELOPMENT PROCESS

*Last‑updated: 2025‑06‑20*

## 1 · Overview

One canonical document defines *what* must happen and *in what order*. All other docs reference this file to avoid drift.

## 2 · Core Workflow Phases

| Phase        | Role (Class)     | Critical Interfaces                           | Fail Criterion                 |
| ------------ | ---------------- | --------------------------------------------- | ------------------------------ |
| **Backlog**  | `BacklogManager` | `list_items`, `add_item`, `archive_completed` | Empty backlog blocks pipeline. |
| **Generate** | `TaskGenerator`  | `generate_tasks`, `overwrite_tasks`           | Ill‑formed tasks.              |
| **Execute**  | `TaskExecutor`   | `build_patch`, `refine_patch`                 | Patch invalid or cannot apply. |
| **Test**     | `ShellRunner`    | `run_pytest`, `git_apply`                     | Test suite fails.              |
| **Review**   | `TaskReviewer`   | `review_patch`                                | Review rejects diff.           |
| **Commit**   | `ShellRunner`    | `git_commit`                                  | Commit fails or skipped.       |
| **Record**   | `TaskRecord`     | `save`, `append_iteration`                    | State not persisted.           |
| **Meta**     | `MetaAgent`      | `analyse`, `alert`                            | Drift > policy threshold.      |

*Sequence is strict; no phase may be skipped or merged.*

## 3 · Guard Rails

* Tests **and** review must pass before commit.
* Overrides require explicit rationale and are logged.
* All artefacts (tasks, diffs, logs) are immutable once archived.

## 4 · Failure Criteria

* Roles perform multiple responsibilities.
* Orchestration happens outside `DevOrchestrator`.
* Silent state transitions or missing logs.
* Context injection exceeds model window constraints (see DEV\_AGENTS).

## 5 · Reference Architecture Diagram

See `docs/architecture.mmd` for the system flow.

### Context Selector (planned)
If repo snapshot > 50k tokens, ExecutionAgent must call
cadence.context.select.select_context() with a token budget set in
DEV_CONFIG.yaml.  The selector walks the module-import graph breadth-first
until the budget is reached.  Doc & code added in commit <SHA>.

---

*Change‑log:* 2025‑06‑20 — merged DEV\_WORKFLOW & DEV\_PROCESS; added strict phase table.
