### Cadence — Delegation Packet for **Loop 0 · Streamlit quarantine**

*(hand this wholesale to the Reasoning Agent’s `run_interaction`; it converts each blueprint into a `ChangeSet` JSON that Execution Agent can implement)*

---

## 0.1  Global constraints the agent must respect

```text
• Use the CadenceChangeSet v1 schema (src/cadence/dev/schema.py).
• Touch ONLY the files listed under “Allowed Modules”; do not modify tests.
• Generated code must keep repo green ⇒ run `pytest -q` before commit.
• All added files end with a Unix newline.
• Remove Streamlit dependency entirely; future React GUI will live elsewhere.
```

---

## 0.2  Allowed Modules & Docs for context

```text
src/cadence/dev/command_center.py
src/cadence/dev/__init__.py
docs/DEV_PROCESS.md
pyproject.toml          # only if it contains a “streamlit” dependency
README.md               # optional badge cleanup
```

*(No other modules should be edited in this loop.)*

---

## 0.3  Blueprint task list

> **Blueprint 01 – Relocate legacy UI**

| Field           | Value                                                                                                                                                                                                                                                                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **title**       | “Move Streamlit Dev Center to legacy area”                                                                                                                                                                                                                                                                                           |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                            |
| **description** | <br>Move *src/cadence/dev/command\_center.py* and its associated Streamlit code to *legacy/command\_center.py* to freeze the prototype UI. Ensure nothing under `cadence.*` imports it. Add a comment header marking it deprecated. Update `src/cadence/dev/__init__.py` so the file is no longer exposed as part of the public API. |

<br>

> **Blueprint 02 – Remove Streamlit import trail**

| Field           | Value                                                                                                                                                                                                                                                |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Purge Streamlit dependency”                                                                                                                                                                                                                         |
| **type**        | blueprint                                                                                                                                                                                                                                            |
| **description** | <br>Search the entire codebase for `import streamlit` and delete or comment-gate any occurrences (there should be none after Blueprint 01). If *pyproject.toml* or *requirements.txt* lists `streamlit`, remove it. Ensure `pytest -q` still passes. |

<br>

> **Blueprint 03 – Update developer docs**

| Field           | Value                                                                                                                                                                                                                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **title**       | “Annotate frozen UI in DEV\_PROCESS.md”                                                                                                                                                                                                                      |
| **type**        | blueprint                                                                                                                                                                                                                                                    |
| **description** | <br>Add a short bullet under **Future Work → Interface Layer** in *docs/DEV\_PROCESS.md*: “Streamlit prototype has been archived under *legacy/*. A new React GUI will supersede it.” Make sure the phase-table guard in *tools/lint\_docs.py* still passes. |

---

## 0.4  Impact notes for the agent

1. **No tests to add** in this loop. The suite should still run green.
2. `src/cadence/dev/__init__.py` is currently empty; removing the import means *no* new re-export is added.
3. Keep `legacy/` inside repository so SnapshotContextProvider can pick it up in historical analyses, but exclude it from future automated edits by adding a `# cadance-ignore` comment at top of the file.

---

## 0.5  Success criteria checklist (agent must satisfy)

* [ ] `pytest -q` returns 0 failures.
* [ ] Running `python -m cadence.dev.orchestrator show` no longer imports Streamlit.
* [ ] `grep -R "streamlit" src | wc -l` → returns 0.
* [ ] `docs/DEV_PROCESS.md` compiles and `python tools/lint_docs.py` passes.
* [ ] Git history shows **one** commit for each blueprint (or a single squash commit with a clear message).

---

### Hand-off

Paste the three blueprints above—unaltered—into the backlog with status `open`.
Then initiate an orchestrator run; ReasoningAgent will expand each blueprint into a `ChangeSet`, ExecutionAgent will implement, and ShellRunner will commit after tests pass.


---

### Cadence — Delegation Packet for **Loop 1 · Repository-wide mutex**

*(pass the whole packet to your Reasoning Agent; each blueprint is converted into a ChangeSet JSON; Execution Agent then implements & tests)*

---

## 1.0  Global constraints for this loop

```text
• Use CadenceChangeSet v1 schema only.
• Touch only the files listed under “Allowed Modules”.
• New code must run on Linux & Windows (use fcntl + msvcrt fallback).
• `pytest -q` must pass, including the new test.
• Keep every added file Unix-newline terminated.
• Docs/linter must stay green (`python tools/lint_docs.py`).
```

---

## 1.1  Allowed Modules & Docs

```text
# code
src/cadence/dev/locking.py          (new)
src/cadence/dev/backlog.py
src/cadence/dev/record.py
src/cadence/audit/agent_event_log.py
src/cadence/audit/llm_call_log.py

# docs
docs/DEV_PROCESS.md

# tests
tests/test_file_mutex.py            (new)
```

*(No other paths may be edited or added in this loop.)*

---

## 1.2  Blueprint task list

> **Blueprint 1 – Introduce FileMutex**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                      |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Create cross-process FileMutex helper”                                                                                                                                                                                                                                                                                                                    |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                  |
| **description** | <br>Implement *src/cadence/dev/locking.py* defining:<br>`class FileMutex:`<br>• Context-manager acquires exclusive lock on `<target_path>.lock`.<br>• POSIX: `fcntl.flock`, Windows: `msvcrt.locking`, otherwise no-op stub with warning.<br>• Exposes `.path` (lockfile) and `.acquired` boolean.<br>Add docstring with platform notes and example usage. |

---

> **Blueprint 2 – Integrate mutex into persistence layer**

| Field           | Value                                                                                                                                                                                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **title**       | “Guard backlog & record JSON writes with FileMutex”                                                                                                                                                                                                                      |
| **type**        | blueprint                                                                                                                                                                                                                                                                |
| **description** | <br>Edit `src/cadence/dev/backlog.py` and `src/cadence/dev/record.py`:<br>• Wrap *all* disk I/O (`save`, `load`, `_persist`) in `with FileMutex(self.path): …` **in addition** to existing `RLock`.<br>• Remove any redundant tmp-file rename race comments.<br>Preserve existing atomic-swap semantics. |

---

> **Blueprint 3 – Replace optional filelock usage in audit modules**

| Field           | Value                                                                                                                                                                                                                                                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Unify audit log locking via FileMutex”                                                                                                                                                                                                                                                                                                           |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                         |
| **description** | <br>In `src/cadence/audit/agent_event_log.py` and `audit/llm_call_log.py`:<br>• Delete the conditional `from filelock import FileLock` import.<br>• Import `FileMutex` and use it in place of `FileLock` (same semantics: `with FileMutex(jsonl_path):` ).<br>• If `FileMutex` is stub (no lock), behaviour matches old optional dependency path. |

---

> **Blueprint 4 – Update developer docs**

| Field           | Value                                                                                                                                                                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **title**       | “Document mutex in DEV\_PROCESS.md”                                                                                                                                                                          |
| **type**        | blueprint                                                                                                                                                                                                    |
| **description** | <br>Add bullet under **Persistence** subsection:<br>`• Backlog and TaskRecord writes are protected by FileMutex (fcntl/msvcrt) to prevent multi-process clobber.`<br>Ensure phase-table linter still passes. |

---

> **Blueprint 5 – Concurrency regression test**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Add test\_file\_mutex.py”                                                                                                                                                                                                                                                                                                                                                                                                |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **description** | <br>Create new test that:<br>1. Uses `tempfile.TemporaryDirectory()` as isolated repo.<br>2. Spawns **two** `python -c` subprocesses that each instantiate `BacklogManager` on the same JSON file and append a unique task (sleep 0.1 between writes).<br>3. Wait for both to finish; load JSON; assert len(list\_items) == 2 and file is valid.<br>Skip on Windows if `multiprocessing` spawn causes flake (mark xfail). |

---

## 1.3  Success checklist (agent must satisfy)

* [ ] `pytest -q` returns 0 failures including new test.
* [ ] `grep -R "filelock" src | wc -l` prints **0**.
* [ ] Running two orchestrators simultaneously (`python -m cadence.dev.orchestrator start & …`) produces no JSON decode errors.
* [ ] `python tools/lint_docs.py` passes.
* [ ] Git history for this loop is 4–5 commits (one per blueprint) *or* a single squash commit with a clear message “Loop 1: mutex integration”.

---

### Hand-off instructions

1. Insert the five blueprints above into the backlog (`status="open"`).
2. Trigger one `DevOrchestrator.run_task_cycle()` per blueprint, or let auto-selection pop them sequentially.
3. On green tests & commit, Loop 1 is complete.


---

### Cadence — Delegation Packet for **Loop 2 · Guaranteed rollback & dirty-repo sentinel**

*(hand this packet to the Reasoning Agent; each blueprint is converted to a ChangeSet JSON; Execution Agent then implements & tests)*

---

## 2.0  Global constraints for this loop

```text
• CadenceChangeSet v1 schema only.
• Edit only the files listed in “Allowed Modules”.
• New logic must keep all existing unit-tests green and pass the updated test suite.
• Git repo must never be left with unstaged changes after a failed task cycle.
• Docs/linter must stay green (`python tools/lint_docs.py`).
```

---

## 2.1  Allowed Modules & Docs

```text
# code
src/cadence/dev/shell.py
src/cadence/dev/orchestrator.py
src/cadence/dev/__init__.py      # only if it needs to re-export ShellRunner helper
src/cadence/dev/phase_guard.py   # read-only for context, no edits

# docs
docs/DEV_PROCESS.md              # fail-path update

# tests
tests/test_failed_rollback.py
```

*(No other paths may be edited in this loop.)*

---

## 2.2  Blueprint task list

> **Blueprint 1 – Extend ShellRunner with robust rollback**

| Field           | Value                                                                                                                                                                     |                                                                                                                                                                                                                                                                                                                                                                         |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Add rollback() + dirty\_repo flag to ShellRunner”                                                                                                                        |                                                                                                                                                                                                                                                                                                                                                                         |
| **type**        | blueprint                                                                                                                                                                 |                                                                                                                                                                                                                                                                                                                                                                         |
| **description** | <br>Enhance *src/cadence/dev/shell.py*:<br>1. Internal helper `_git_apply_reverse(patch)` (mirror of `git_apply` with `-R`).<br>2. Public \`def rollback(self, patch\:str | None) -> bool`which:<br>   • Returns **True** if reverse-apply succeeds.<br>   • On failure sets`self.dirty\_repo = True`, records `failed\_rollback`in TaskRecord, and returns **False**.<br>3.`self.dirty\_repo`defaults to **False** on instantiation and after every successful`git\_commit\`.<br>4. Mark phase ‘rollback\_done’ when rollback succeeds (optional). |

---

> **Blueprint 2 – Abort cycles when dirty\_repo is set**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Integrate dirty-repo guard in DevOrchestrator”                                                                                                                                                                                                                                                                                                                                                                                                       |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **description** | <br>Edit *src/cadence/dev/orchestrator.py*:<br>• At the very beginning of `run_task_cycle`, if `self.shell.dirty_repo` is **True**, log state `blocked_dirty_repo` and raise `RuntimeError("Repository dirty after failed rollback")`.<br>• Replace existing `_attempt_rollback()` logic with call to `self.shell.rollback(rollback_patch)`. If it returns **False**, abort cycle early with `success=False` payload containing `"dirty_repo": True`. |

---

> **Blueprint 3 – Update fail-path documentation**

| Field           | Value                                                                                                          |                                                                                                                                                                                               |
| --------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Document rollback & dirty-repo in DEV\_PROCESS.md”                                                            |                                                                                                                                                                                               |
| **type**        | blueprint                                                                                                      |                                                                                                                                                                                               |
| **description** | <br>Add small ASCII flow diagram under **Failure Handling**:<br>\`patch\_apply → test\_fail → rollback → \[ok] | \[rollback\_fail → dirty\_repo flag → block next loop]`<br>Describe manual/unblock options for developers (e.g. `git reset --hard`then`self.shell.dirty\_repo=False\`). Ensure linter passes. |

---

> **Blueprint 4 – Expand regression test**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Strengthen test\_failed\_rollback.py”                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **description** | <br>Update or create *tests/test\_failed\_rollback.py*:<br>1. Create tmp repo with two commits.<br>2. Forge a ChangeSet that intentionally fails tests (e.g. syntax error).<br>3. Run orchestrator cycle; assert: `result['success'] is False`, `result['stage'] == 'test'`, `shell.dirty_repo is False`.<br>4. Simulate rollback failure (e.g. corrupt patch) and assert `dirty_repo is True` and subsequent `run_task_cycle` immediately aborts with `blocked_dirty_repo`. Use `pytest.raises`. |

---

## 2.3  Success checklist

* [ ] `pytest -q` passes, including enhanced rollback test.
* [ ] Manual kill-switch: `shell.dirty_repo` is **False** after a clean cycle.
* [ ] When rollback fails, `.dirty_repo` flips to **True** and orchestrator refuses to start another cycle until flag cleared.
* [ ] `python tools/lint_docs.py` passes.
* [ ] No new un-tracked files in repo after failure simulation (`git status --porcelain` empty).
* [ ] Commits: ≤ 5, or one squash commit “Loop 2: rollback & dirty-repo sentinel”.

---

### Hand-off steps

1. Append the four blueprints above to the backlog (status **open**).
2. Trigger orchestrator cycles until all four are committed & archived.
3. Confirm success checklist; then mark Loop 2 complete.


---

### Cadence — Delegation Packet for **Loop 3 · Phase-ordering hard-guard**

*(give the full packet to the Reasoning Agent; it will emit a **ChangeSet** per blueprint, Execution Agent implements & tests)*

---

## 3.0  Global constraints

```text
• Use CadenceChangeSet v1 schema.
• Edit only files listed under “Allowed Modules”.
• Preserve all public APIs already used by Orchestrator (ShellRunner signatures stay stable).
• `pytest -q` + updated phase-ordering test must pass.
• Docs linter (`python tools/lint_docs.py`) must stay green.
```

---

## 3.1  Allowed Modules & Docs

```text
# code
src/cadence/dev/phase_tracker.py     (new)
src/cadence/dev/shell.py
src/cadence/dev/orchestrator.py
src/cadence/dev/phase_guard.py       (read-only for reference)

# docs
docs/DEV_PROCESS.md

# tests
tests/test_phase_ordering.py         (new)
```

---

## 3.2  Blueprint task list

> **Blueprint 1 – Introduce PhaseTrackerMixin**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Create PhaseTrackerMixin for phase flags”                                                                                                                                                                                                                                                                                                                                                                                                               |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **description** | <br>Add *src/cadence/dev/phase\_tracker.py* defining:<br>`class PhaseTrackerMixin:`<br>• `self._phase_flags: Dict[str, Set[str]]` internal.<br>• `_init_phase(task_id)`, `_mark_phase(task_id, phase)`, `_has_phase(task_id, phase)` helpers identical to pre-mix code.<br>• `_require_phase(task_id, *needed)` raises `PhaseOrderError` if any missing (wrapper for ad-hoc checks).<br>Docstring explains integration with `phase_guard.enforce_phase`. |

---

> **Blueprint 2 – Apply mixin & decorators to ShellRunner**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Refactor ShellRunner to use PhaseTrackerMixin”                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **description** | <br>In *src/cadence/dev/shell.py*:<br>1. `class ShellRunner(PhaseTrackerMixin):` (mixin first in MRO).<br>2. Remove now-duplicated phase-tracking code (`_phase_flags`, `_mark_phase`, etc.).<br>3. Decorate methods:<br>   • `git_checkout_branch` – `@enforce_phase(mark="branch_isolated")` (no prereqs).<br>   • `git_apply` – `@enforce_phase("branch_isolated", mark="patch_applied")`.<br>   • `run_pytest` – `@enforce_phase("patch_applied", mark="tests_passed")`.<br>   • `git_commit` – `@enforce_phase("tests_passed", mark="committed")`.<br>4. Internal logic that manually checked phase flags (e.g., in `git_commit`) is removed or replaced by `_require_phase`. |

---

> **Blueprint 3 – Remove ad-hoc flag manipulation in Orchestrator**

| Field           | Value                                                                                                                                                                                                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Clean Orchestrator manual phase‐flag hacks”                                                                                                                                                                                                                                       |
| **type**        | blueprint                                                                                                                                                                                                                                                                          |
| **description** | <br>Edit *src/cadence/dev/orchestrator.py*:<br>• Delete calls to `self.shell._mark_phase(...)` and the `_mark_phase` import note.<br>• Replace commit guard comments with “handled by PhaseTrackerMixin + enforce\_phase”.<br>No behaviour change expected; tests must still pass. |

---

> **Blueprint 4 – Update developer docs**

| Field           | Value                                                                                                                                                                                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **title**       | “Document numeric phase IDs & mixin”                                                                                                                                                                                                                   |
| **type**        | blueprint                                                                                                                                                                                                                                              |
| **description** | <br>In *docs/DEV\_PROCESS.md*:<br>• Convert phase table’s first column to explicit numeric order (1–10).<br>• Under **Runtime Enforcement** add bullet: “ShellRunner inherits PhaseTrackerMixin; `enforce_phase` decorator blocks out-of-order calls.” |

---

> **Blueprint 5 – Add phase-ordering regression test**

| Field           | Value                                                                                                                                                                                                                                                                                     |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Create tests/test\_phase\_ordering.py”                                                                                                                                                                                                                                                   |
| **type**        | blueprint                                                                                                                                                                                                                                                                                 |
| **description** | <br>New pytest that:<br>1. Instantiates `ShellRunner` in tmp repo.<br>2. Attaches dummy task `{"id": "ph001"}`.<br>3. Calls `run_pytest()` **before** `git_apply()` and expects `PhaseOrderError`.<br>4. Proper order path executes without error (use empty diff that passes pre-check). |

---

## 3.3  Success checklist

* [ ] `pytest -q` passes, including new phase-ordering test.
* [ ] Grep shows no remaining `_phase_flags` implementation in *shell.py* outside mixin import (`grep -n "_phase_flags" src/cadence/dev/shell.py` → 0).
* [ ] Manual run of `DevOrchestrator.run_task_cycle()` completes without PhaseOrderError when phases executed correctly.
* [ ] Docs linter passes; phase table shows numeric IDs.
* [ ] Commit history ≤ 5 commits or a single squash “Loop 3: PhaseTrackerMixin & strict ordering”.

---

### Hand-off

1. Insert the five blueprints above into backlog with `status="open"`.
2. Execute orchestrator cycles until all five are archived with green tests.
3. Confirm success checklist; Loop 3 is done.


---

### Cadence — Delegation Packet for **Loop 4 · ChangeSet-only pipeline & `before_sha` auto-fill**

*(give this packet to the Reasoning Agent; each blueprint becomes a ChangeSet JSON; Execution Agent implements & tests)*

---

## 4.0  Global constraints

```text
• CadenceChangeSet v1 schema is THE ONLY accepted task format after this loop.
• Any code path that still accepts 'diff' or 'patch' must be removed or hard-fail.
• Every new task inserted by BacklogManager must have correct before_sha on all edits.
• All existing unit-tests + new ones must pass (`pytest -q`).
• Docs linter (`python tools/lint_docs.py`) must stay green.
```

---

## 4.1  Allowed Modules & Docs

```text
# code
src/cadence/dev/executor.py
src/cadence/dev/backlog.py
src/cadence/dev/schema.py
src/cadence/llm/json_call.py      # only if alias-normaliser needs adjustment
src/cadence/dev/__init__.py       # (optional) re-export helpers
tests/                            # modify or add tests only under tests/

# docs
docs/DEV_PROCESS.md
docs/DEV_AGENTS.md
```

---

## 4.2  Blueprint task list

> **Blueprint 1 – Purge legacy patch paths from Executor**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Remove diff/patch fallbacks in TaskExecutor”                                                                                                                                                                                                                                                                                                                                         |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                             |
| **description** | <br>In *src/cadence/dev/executor.py*:<br>1. Delete `_build_one_file_diff` and its invocation.<br>2. `build_patch()` now:<br>   • Returns `task['patch']` **only** if key exists **and** is explicitly flagged `task['legacy']=True` (for emergency manual runs). Otherwise raise `TaskExecutorError('change_set required')` if `'change_set'` missing.<br>3. Remove import `difflib`. |

---

> **Blueprint 2 – Tighten ChangeSet schema & JSON caller**

| Field           | Value                                                                                                                                                                                                                                                                                                                               |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Lock schema: remove deprecated alias fields”                                                                                                                                                                                                                                                                                       |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                           |
| **description** | <br>Edit *src/cadence/dev/schema.py*:<br>1. In `CHANGE_SET_V1`, delete any mention of `"changes"` alias; `"edits"` is mandatory.<br>2. In *src/cadence/llm/json\_call.py* remove `_normalise_legacy()` call **or** have it raise `ValueError('legacy ChangeSet alias unsupported')` if it encounters `"changes"`. Update docstring. |

---

> **Blueprint 3 – Auto-populate before\_sha at backlog-add**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Inject before\_sha when task added”                                                                                                                                                                                                                                                                                                                                                    |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                               |
| **description** | <br>Edit *src/cadence/dev/backlog.py* `<add_item>`:<br>1. Detect `change_set` key.<br>2. For each `edit` where `before_sha` is null **and** `mode` ≠ "add": compute SHA-1 of the current file (`Path(edit['path'])` relative to repo root).<br>3. Mutate the incoming task dict in-place before saving.<br>4. If file missing, raise `TaskStructureError('cannot compute before_sha')`. |

---

> **Blueprint 4 – Update developer docs**

| Field           | Value                                                                                                                                                                                                                                                                                                            |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Document ChangeSet exclusivity”                                                                                                                                                                                                                                                                                 |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                        |
| **description** | <br>In *docs/DEV\_PROCESS.md* and *docs/DEV\_AGENTS.md*:<br>• Replace any reference to `diff`/`patch` fallback with “Every task **must** contain a `change_set` object”.<br>• Add sentence under **Persistence**: “BacklogManager auto-injects `before_sha` at task-creation time to guard against stale edits.” |

---

> **Blueprint 5 – Replace or add unit-tests**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Add test\_before\_sha\_validation.py and drop legacy fixtures”                                                                                                                                                                                                                                                                                                                                                                                    |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **description** | <br>1. Delete any test modules that feed `task['diff']` or `task['patch']`.<br>2. Create *tests/test\_before\_sha\_validation.py* with two cases:<br>   **case A** – Add task that modifies existing `src/foo.py`; assert BacklogManager wrote correct `before_sha`.<br>   **case B** – Manually tamper file then try `orchestrator.executor.build_patch(task)`; expect `PatchBuildError` due to SHA mismatch.<br> Skip on Windows if path issues. |

---

## 4.3  Success checklist

* [ ] `pytest -q` passes including new SHA test; no test imports `diff`/`patch` fixtures.
* [ ] `grep -R "['\"]diff['\"]" src/cadence/dev/executor.py` returns 0.
* [ ] Adding a task via CLI without `before_sha` populates it automatically.
* [ ] Attempting to submit legacy task (`diff`/`patch` only) raises `TaskExecutorError`.
* [ ] Docs linter passes; search for “diff path” phrase yields 0 hits in docs.
* [ ] Commit history ≤ 5 commits or one squash commit “Loop 4: ChangeSet-only & before\_sha”.

---

### Hand-off

1. Append the five blueprints to backlog (`status="open"`).
2. Run orchestrator cycles until all are archived & tests green.
3. Verify success checklist, then declare Loop 4 complete.


---

### Cadence — Delegation Packet for **Loop 5 · Fail-closed Efficiency Review**

*(deliver the entire packet to the Reasoning Agent; each blueprint becomes a ChangeSet JSON; Execution Agent implements & tests)*

---

## 5.0  Global constraints

```text
• CadenceChangeSet v1 schema only.
• Edit ONLY files listed in “Allowed Modules”.
• After this loop the pipeline must BLOCK any task whose efficiency-review JSON fails to parse or validate.
• A manual override is allowed via CLI flag --force-efficiency-pass.
• All tests old + new must pass (`pytest -q`).
• Docs linter (`python tools/lint_docs.py`) must stay green.
```

---

## 5.1  Allowed Modules & Docs

```text
# code
src/cadence/dev/orchestrator.py
src/cadence/dev/__init__.py        # (optional) expose CLI helper
docs/DEV_PROCESS.md
tests/test_efficiency_review_gate.py  (new)
```

*(No other files may be touched in this loop.)*

---

## 5.2  Blueprint task list

> **Blueprint 1 – Fail-closed logic inside Orchestrator**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Block merge on Efficiency JSON error”                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **description** | <br>In *src/cadence/dev/orchestrator.py* inside the “Review #2 – Efficiency” block:<br>1. Wrap `_eff_json.ask(...)` in `try/except`. On **any** exception (`Exception`):<br>   • `eff_raw = f"[failure:{type(e).__name__}] {e}"`<br>   • `eff_pass = False`<br>2. *If* CLI flag `self.force_efficiency_pass` is True, override to `eff_pass = True` with comment `# manual override`.<br>3. Abort task cycle exactly as today when `eff_pass is False` (stage=`"patch_review_efficiency"`). |

---

> **Blueprint 2 – CLI override flag**

| Field           | Value                                                                                                                                                                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Add --force-efficiency-pass flag to orchestrator CLI”                                                                                                                                                                                   |
| **type**        | blueprint                                                                                                                                                                                                                                |
| **description** | <br>In Orchestrator `__main__` section:<br>1. Add argparse flag `--force-efficiency-pass` (store\_true).<br>2. Store on instance: `self.force_efficiency_pass = args.force_efficiency_pass` (default False).<br>3. Document in `--help`. |

---

> **Blueprint 3 – Update developer docs**

| Field           | Value                                                                                                                                                                                                           |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Document fail-closed behaviour”                                                                                                                                                                                |
| **type**        | blueprint                                                                                                                                                                                                       |
| **description** | <br>Edit *docs/DEV\_PROCESS.md*:<br>• Under **Review-Efficiency** add bullet: “If JSON parse or validation fails the patch is rejected (fail-closed). Override during offline runs: `--force-efficiency-pass`.” |

---

> **Blueprint 4 – Regression test**

| Field           | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **title**       | “Add test\_efficiency\_review\_gate.py”                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **type**        | blueprint                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **description** | <br>Create test that:<br>1. Monkey-patch `DevOrchestrator._eff_json.ask` to raise `RuntimeError("mock failure")`.<br>2. Feed orchestrator a valid task with minimal ChangeSet; run `.run_task_cycle(select_id=task_id)`.<br>3. Assert returned dict has `success is False` **and** `stage == 'patch_review_efficiency'`.<br>4. Repeat with `orch.force_efficiency_pass=True`; assert cycle continues past efficiency review and reaches `"test"` stage. |

---

## 5.3  Success checklist

* [ ] `pytest -q` passes, including new efficiency gate test.
* [ ] Running orchestrator offline (stub LLM) without `--force-efficiency-pass` blocks at efficiency review.
* [ ] Same run **with** `--force-efficiency-pass` succeeds (tests still need to pass).
* [ ] Docs linter passes; docs mention the new fail-closed rule and override flag.
* [ ] Commit history ≤ 4 commits or single squash “Loop 5: fail-closed efficiency gate”.

---

### Hand-off

1. Add the four blueprints to the backlog (`status="open"`).
2. Execute orchestrator cycles until all four tasks are archived and tests green.
3. Verify the success checklist; Loop 5 is complete.

---
---
---

I’ve drafted all three onboarding artifacts and saved them in your repo:

| Artifact              | Purpose                                                                                           | Path                       |
| --------------------- | ------------------------------------------------------------------------------------------------- | -------------------------- |
| **FILE\_TREE.md**     | Auto-generated snapshot of the current `src/cadence` hierarchy.                                   | `docs/FILE_TREE.md`        |
| **Quick-start.md**    | One-pager: clone → install → run tests → start orchestrator (plus flags).                         | `docs/Quick-start.md`      |
| **fresh\_context.sh** | Shell script to wipe logs/backlog, seed a single blueprint, and prompt the next orchestrator run. | `scripts/fresh_context.sh` |

They’re now part of the repository; execute:

```bash
cat docs/Quick-start.md
bash scripts/fresh_context.sh   # to verify reset flow
```

Feel free to iterate further, but this gives you a clean onboarding/reset loop that matches the current Cadence architecture.
