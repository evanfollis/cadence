# Cadence Solo-Developer Workflow (v0.2)

This file is executable documentation: follow it line-by-line for each
micro-task.

## Shell aliases (one-time)

```bash
alias ktests='pytest -q'
alias kprompt='python tools/gen_prompt.py --code-root cadence --docs-dir docs'
```

---

## Cadence OOP/Agentic Workflow (2025+)

| Phase    | Module/Class    | Responsibility                  | Error/Fault Handling                    |
|----------|----------------|----------------------------------|-----------------------------------------|
| **MVP-Safe** | `mvp_loop.py` | *Single script* collapses Generate→Test loop using in-memory patching only | Auto-rollback on failure, 3-try circuit |
| Backlog  | BacklogManager | Presents task list/selection     | Empty: process halts; log required      |
| Generate | TaskGenerator  | Produces new tasks (LLM/options) | Failed output: abort                    |
| Diff     | TaskExecutor   | Produces/appplies patch          | Invalid/unapplicable: reject/abort      |
| Test     | ShellRunner    | Runs tests on patch code         | Test fail: loop refinement              |
| Review   | TaskReviewer   | Review diff for pass/fail        | Fail = loop back to Diff                |
| Commit   | ShellRunner    | Git commit/record/close loop     | Commit fail: halt/error/log             |
| Record   | TaskRecord     | Archive full state/history       | Always must succeed (blocking)          |

> OOP classes handle each role, but can be swapped for specialized “agents” in a future distributed or multi-member system. All phases are explicit and logged.

### Guard Rails & Fail Criteria

- No step is automatic; all input/output must be logged.
- No phase may be skipped or short-circuited (bypass is a policy violation).
- Any deviation from prescribed interface is a bug.
- All logs and state must remain audit-ready and reconstructable.

---

# **Adopt this foundation for all future Cadence projects.**
- Keep roles single-responsibility, explicit, and logged.
- Upgrade to agentic/distributed team as needs grow – code and docs are ready for growth.
- Use these docs as onboarding and review materials for any collaborators.

---