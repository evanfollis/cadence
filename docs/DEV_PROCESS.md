# CADENCE DEVELOPMENT PROCESS: ROLES, RESPONSIBILITIES, AND WORKFLOW

## Overview

The Cadence codebase is architected with a clear separation of concerns, assigning every major phase of the developer loop to a dedicated **role**. Each role is implemented as a class with a precise interface. In the future, these roles may be filled by “agents”—be they LLMs, microservices, or human collaborators—without fundamental changes to the orchestrator or workflow.

This process is summarized in the following policy, guard rails, and fail criteria.

---

## 1. **Core Agent/Class Roles**

| Role (Class/Agent) | Responsibility                               | Future agent?            | Critical Interface               |
|--------------------|----------------------------------------------|--------------------------|----------------------------------|
| `BacklogManager`   | Manage backlog: microtasks, stories, epics   | Yes                      | `list_items`, `add_item`, `remove_item`, `archive_completed` |
| `TaskGenerator`    | Propose new tasks (via LLM/rules/templates)  | Yes                      | `generate_tasks`, `overwrite_tasks`    |
| `TaskExecutor`     | Given a task description, produce code diff  | Yes                      | `build_patch`, `refine_patch`      |
| `TaskReviewer`     | Given a diff, adjudicate quality/pass/fail   | Yes                      | `review_patch`                   |
| `ShellRunner`      | Safely run local shell commands (git/tests)  | Maybe (for remote/CI)    | `git_apply`, `run_pytest`, `git_commit` |
| `TaskRecord`       | Persist task history throughout workflow     | Not directly             | `save`, `load`, `append_iteration` |
| `DevOrchestrator`  | Drives process, connects all roles           | Maybe (AI orchestrator)  | Main CLI/user interface          |

> **Note:** Each role is a future "swap point"—today a Python class, tomorrow a remote caller, LLM, or collaborative tool.

---

## 2. **Process and Expected Sequence**

### **A. Developer Workflow Loop**

| Phase            | Responsibility (role)         | Fail Criteria                      |
|------------------|------------------------------|------------------------------------|
| **Backlog**      | Select task from `BacklogManager` | If no items: Workflow blocks      |
| **Task Generation (optional)** | `TaskGenerator.generate_tasks`       | Tasks not well-formed/constrained  |
| **Patch Proposal**| `TaskExecutor.build_patch`     | Patch not produced or invalid      |
| **Patch Application** | `ShellRunner.git_apply`   | Patch does not apply cleanly       |
| **Testing**      | `ShellRunner.run_pytest`      | Tests fail or incomplete           |
| **Review**       | `TaskReviewer.review_patch`   | Diff fails hard rules or review    |
| **Iteration/Refinement** | `TaskExecutor.refine_patch` | Feedback not incorporated or endless loops |
| **Commit/Archive** | `ShellRunner.git_commit`, `TaskRecord.save` | Commit fails, state not saved   |

**Guard Rails**
- **No step may skip its predecessor.** E.g., cannot commit code that didn’t pass tests and review.
- **Every phase must expose clear, testable input/output (CLI, method, or file).**
- **All items, diffs, and outcomes are logged and auditable (via `TaskRecord`).**

---

## 3. **Key Expectations (What Is Success?)**

- Each role/class/agent does **only one job**.
- Inputs and outputs are strictly defined.
- Human, LLM, or other agents can be swapped for in any given role, provided they honor the contract.
- **Automation is always overridable** by a human, but never skipped without trace.
- The orchestrator is the **sole entity permitted to coordinate all roles**; all coordination flows through its interface.
- **Backlogs, history, and outcomes are always persistently logged.**

---

## 4. **Failure Criteria** *(When Is It a Bug or Policy Violation?)*

- Any class/agent does more than its prescribed role, or has unclear boundaries.
- Orchestration is hidden (implicit flows, tight coupling).
- Steps in the workflow are skipped or merged, process becomes opaque.
- Human/manual editing outside orchestrated flow (unless explicitly logged/recorded).
- Persistent record not up-to-date with reality (backlog drift, missed commits).
- Reviews (auto or manual) not enforced, or tasks proceeding after test/review fail.

---

## 5. **Reference Workflow Diagram**

```mermaid
flowchart LR
    subgraph Human/CLI
        Start
    end
    subgraph Orchestrator
        Orchestrator
    end
    subgraph Agents/Roles
        BacklogManager --> TaskExecutor
        TaskExecutor --> ShellRunner
        ShellRunner --> TaskReviewer
        TaskReviewer --> Orchestrator
        Orchestrator --> BacklogManager
        Orchestrator --> TaskGenerator
    end
    Start --> Orchestrator
    Orchestrator --> BacklogManager
    Orchestrator --> TaskExecutor
    Orchestrator --> ShellRunner
    Orchestrator --> TaskReviewer
    Orchestrator --> TaskGenerator
```

---

## 6. **Role Swapping: OOP ↔ Agentic (Future-Proofing Table)**

| Step            | Today (OOP/class)      | Tomorrow (Agent)              |
|-----------------|-----------------------|-------------------------------|
| Backlog         | Sync/backed by class/file | LLM, microservice, shared board |
| Patch Proposal  | LLM called from class  | External LLM or crowd agent   |
| Patch Apply     | Local GitShell class   | Remote shell, CI pipeline     |
| Test            | Local shell/pytest     | Kubernetes job, CI/CD web     |
| Review          | Class, LLM, or human   | AI copilot, human reviewers   |
| Orchestrate     | Python orchestrator    | Multi-agent conductor         |

---

## 7. **Canonical Example: End-to-End Flow**

```python
from cadence.dev.orchestrator import DevOrchestrator

orch = DevOrchestrator()
orch.view_backlog("micro")
orch.start_task("micro")      # Uses TaskExecutor, logs TaskRecord
# (inspect/modify code as needed, if dry_run: try without side effect)
orch.evaluate_task()          # shell/tests + review agent
orch.finalise_task("micro")   # archives task, updates records
```

---