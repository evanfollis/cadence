# CADENCE DEVELOPMENT PROCESS (v2 — 2025-06-23)

## Phase Table — **MUST NOT DRIFT**  

| Seq | Phase            | Responsible Class / Service         | Fail Criterion                       |
|-----|------------------|--------------------------------------|--------------------------------------|
| 01  | Backlog          | BacklogManager                       | Empty backlog                        |
| 02  | Generate         | TaskGenerator                        | Malformed task                       |
| 03  | Execute          | TaskExecutor                         | Patch invalid                        |
| 04  | Review-Reasoning | TaskReviewer                         | Review rejects diff                  |
| 05  | Review-Efficiency| `EfficiencyAgent` (LLM)              | Lint or metric failure               |
| 06  | Branch-Isolate   | ShellRunner.git_checkout_branch      | Branch creation fails                |
| 07  | Test (pre-merge) | ShellRunner.run_pytest               | Tests fail                           |
| 08  | Commit           | ShellRunner.git_commit               | Phase guard missing flags            |
| 09  | Merge Queue      | MergeCoordinator (new)               | Conflicts or post-merge test fail    |
| 10  | Record           | TaskRecord                           | State not persisted                  |
| 11  | Meta             | MetaAgent                            | Drift > policy threshold             |

*Phase sequencing validated at runtime by `phase_guard.enforce_phase()` and at doc-time by `tools/lint_docs.py`.*

## Guard Rails
* Commit blocked unless phases 01-07 succeed **and** flags `review_passed`, `efficiency_passed`, `branch_isolated`, `tests_passed` are present.
* Merge blocked unless branch fast-forwards and post-merge tests pass.