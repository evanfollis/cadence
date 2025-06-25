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
