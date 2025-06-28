Below is a **self-contained blueprint** for the backend-hardening sprint.
It captures *every* loop I proposed, the order of operations, and the artifacts each step must leave behind (code, tests, docs). You should be able to hand one loop at a time to Cadence itself (or work through manually) without me in the room.

---

## 1 · Guiding constraints

| Principle                                               | Implementation Guards                                           |
| ------------------------------------------------------- | --------------------------------------------------------------- |
| **Single Orchestrator** now; multi-process safety later | File-level mutex wraps backlog & record writes in Loop 1        |
| **ChangeSet = sole patch format**                       | Legacy `diff`/`patch` paths removed Loop 4                      |
| **Fail-closed** whenever JSON validation breaks         | Efficiency review strict-fail added Loop 5                      |
| **Docs ↔ Code ↔ Tests never drift**                     | Every loop patches dev docs + linter; new tests prove behaviour |

---

## 2 · Road-map table

| Loop  | Headline Deliverable                                                            | Key Modules Touched                                        | New Tests                        |
| ----- | ------------------------------------------------------------------------------- | ---------------------------------------------------------- | -------------------------------- |
| **0** | *Prep sweep* – delete Streamlit imports, archive legacy UI                      | `command_center.py` only (move to `legacy/`)               | n/a                              |
| **1** | `FileMutex` cross-process lock + integration                                    | `dev/locking.py`, `src/cadence/dev/backlog.py`, `src/cadence/dev/record.py`, `audit/*`     | `test_file_mutex.py`             |
| **2** | *Atomic rollback inside ShellRunner* + `dirty_repo` sentinel                    | `shell.py`, `orchestrator.py`                              | `test_failed_rollback.py` update |
| **3** | `PhaseTrackerMixin`; decorator on **all** ShellRunner mutators                  | `phase_guard.py`, `shell.py`                               | `test_phase_ordering.py`         |
| **4** | Deprecate `task["diff"]` & `task["patch"]` ; inject `before_sha` at backlog-add | `executor.py`, `src/cadence/dev/backlog.py`, delete fallback code in tests | `test_before_sha_validation.py`  |
| **5** | Efficiency review strict-fail on JSON parse/validation error                    | `orchestrator.py` review-2 block                           | `test_efficiency_review_gate.py` |

*(Loops 6+ reserved for patch-builder optimisation, snapshot caching, lint tooling.)*

---

## 3 · Detailed per-loop blueprint

### LOOP 0 – Streamlit code quarantine

* **Action**: move `src/cadence/dev/command_center.py` to `legacy/` and delete its import trail; adjust `__init__.py` exports.
* **Docs**: add note in `docs/DEV_PROCESS.md` that React GUI is future work; Streamlit frozen.
* **Tests**: none (pure relocation).

---

### LOOP 1 – Repository-wide mutex

**Changes**

| File                                                | Addition                                               |
| --------------------------------------------------- | ------------------------------------------------------ |
| `src/cadence/dev/locking.py`                        | `FileMutex` context-manager; `with FileMutex(path): …` |
| `src/cadence/dev/backlog.py`, `src/cadence/dev/record.py`                           | Wrap `save/load/_persist` with mutex                   |
| `audit/agent_event_log.py`, `audit/llm_call_log.py` | Replace optional *filelock* import with `FileMutex`    |

**Docs**

*DEV\_PROCESS.md* → Persistence bullet: “Backlog and TaskRecord writes use `FileMutex` (fcntl/msvcrt) to prevent multi-process clobber.”

**Tests**

`tests/test_file_mutex.py`:

1. Spawn two subprocesses writing distinct items to same backlog.
2. Assert final JSON valid and contains both items.

---

### LOOP 2 – Guaranteed rollback

**Changes**

| File              | Addition                                                                                  |
| ----------------- | ----------------------------------------------------------------------------------------- |
| `shell.py`        | `git_apply_reverse()` internal; `rollback(patch)` public; sets `dirty_repo` flag if fails |
| `orchestrator.py` | On any failure: `if self.shell.rollback(patch) is False: abort cycle early`               |

Edge behaviour: if `dirty_repo` true, next task cycle refuses to start until user (or agent) cleans workspace.

**Docs**

`DEV_PROCESS.md` → new fail-path diagram: *patch\_apply → test\_fail → rollback →* (dirty?) logic.

**Tests**

Update existing `tests/test_failed_rollback.py`:

* Simulate failing tests, ensure rollback succeeds and dirty flag is False.

---

### LOOP 3 – PhaseTrackerMixin

**Changes**

| File                         | Addition                                                                                                    |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `dev/phase_tracker.py` (new) | Mixin exposing `_init_phase` / `_mark_phase` / `_require_phase`                                             |
| `shell.py`                   | Inherit mixin; decorate `git_checkout_branch`, `run_pytest`, `git_commit`, `git_apply` with `enforce_phase` |
| `orchestrator.py`            | Remove manual flag manipulation where mixin now handles                                                     |

**Docs**

`DEV_PROCESS.md` → phase table gains explicit numeric IDs; mixin enforced order listed.

**Tests**

`tests/test_phase_ordering.py`: call ShellRunner methods out of order; expect `PhaseOrderError`.

---

### LOOP 4 – ChangeSet exclusive & SHA propagation

**Changes**

| File            | Action                                                                              |
| --------------- | ----------------------------------------------------------------------------------- |
| `executor.py`   | Delete legacy `_build_one_file_diff`; raise if `'change_set'` missing               |
| `dev/schema.py` | Remove `CHANGE_SET_V1` legacy alias fields (`changes`)                              |
| `src/cadence/dev/backlog.py`    | On `add_item`, for every `change_set` edit compute current SHA and set `before_sha` |
| Tests           | Remove fixtures that feed `diff`/`patch` tasks                                      |

**Docs**

*DEV\_PROCESS.md* & *DEV\_AGENTS.md* – “All tasks must supply `change_set` JSON; legacy formats removed.”

**Tests**

`tests/test_before_sha_validation.py`

1. Add task touching `src/foo.py`; ensure added SHA matches file state.
2. Mutate `foo.py` then attempt to apply stale task; expect SHA mismatch error.

---

### LOOP 5 – Fail-closed efficiency gate

**Changes**

| File              | Action                                                                                                                                                        |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `orchestrator.py` | In Efficiency review block, if `_eff_json` call raises *any* exception → `eff_pass=False`. Stub mode may be overridden by cmd-line `--force-efficiency-pass`. |
| `schema.py`       | No change                                                                                                                                                     |
| CLI               | Add `--force-efficiency-pass` flag for rare stub runs                                                                                                         |

**Docs**

*DEV\_PROCESS.md* – “JSON validation errors during efficiency review block merge.”

**Tests**

`tests/test_efficiency_review_gate.py`:

* Monkey-patch `_eff_json.ask` to raise; assert task cycle aborts at efficiency stage.

---

## 4 · Meta-work: onboarding & context reset

1. **File tree map** – auto-generated by `tools/collect_code.py --root src/cadence --out docs/FILE_TREE.md`.
2. **Quick-start.md** – step-by-step “clone → poetry install → pytest → start orchestrator” doc.
3. **Onboarding reset script** – `scripts/fresh_context.sh` deletes `.cadence_logs`, backlog, record, and re-initialises with a single blueprint task.

These live in `docs/ONBOARDING/` so you can wipe conversation history and boot a new chat with minimal prompt.

---

### Ready to execute?

If this plan looks right, we can dive into **Loop 1** and I’ll supply the granular NEXT\_ACTION / SUCCESS\_CRITERION / ROLLBACK diff list.
