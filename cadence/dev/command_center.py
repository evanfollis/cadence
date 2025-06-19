# Cadence/dev/command_center.py

import streamlit as st

# You may need to adjust the import path according to your setup
from cadence.dev.orchestrator import DevOrchestrator

# ---- Basic Config (map to your dev environment) ----
CONFIG = dict(
    backlog_path="dev_backlog.json",
    template_file="dev_templates.json",
    src_root="cadence",
    ruleset_file=None,
    repo_dir=".",
    record_file="dev_record.json"
)
orch = DevOrchestrator(CONFIG)

# ---- Session State Initialization ----
if "selected_task_id" not in st.session_state:
    st.session_state["selected_task_id"] = None
if "phase" not in st.session_state:
    st.session_state["phase"] = "Backlog"

# ---- Sidebar: Phase Navigation ----
st.sidebar.title("Cadence Dev Center")
phase = st.sidebar.radio(
    "Workflow phase",
    ["Backlog", "Task Detail", "Patch Review", "Run Test", "Archive"],
    index=["Backlog", "Task Detail", "Patch Review", "Run Test", "Archive"].index(st.session_state["phase"])
)
st.session_state["phase"] = phase

# ---- Main: Backlog View ----
if phase == "Backlog":
    st.title("Task Backlog")
    open_tasks = orch.backlog.list_items(status="open")
    if not open_tasks:
        st.info("No open tasks! Add tasks via CLI/Notebook.")
    else:
        import pandas as pd
        df = pd.DataFrame(open_tasks)
        st.dataframe(df[["id", "title", "type", "status", "created_at"]])
        selected = st.selectbox(
            "Select a task to work on",
            options=[t["id"] for t in open_tasks],
            format_func=lambda tid: f'{tid[:8]}: {next(t["title"] for t in open_tasks if t["id"] == tid)}'
        )
        if st.button("Continue to task detail"):
            st.session_state["selected_task_id"] = selected
            st.session_state["phase"] = "Task Detail"
            st.experimental_rerun()

# ---- Task Detail View ----
elif phase == "Task Detail":
    st.title("Task Details")
    task_id = st.session_state.get("selected_task_id")
    if not task_id:
        st.warning("No task selected.")
        st.stop()
    task = orch.backlog.get_item(task_id)
    st.markdown(f"**Title:** {task['title']}\n\n**Type:** {task['type']}\n\n**Status:** {task['status']}\n\n**Created:** {task['created_at']}")
    st.code(task.get("description", ""), language="markdown")
    st.json(task)
    if st.button("Proceed to Patch Review"):
        st.session_state["phase"] = "Patch Review"
        st.experimental_rerun()
    if st.button("Back to backlog"):
        st.session_state["phase"] = "Backlog"
        st.experimental_rerun()

# ---- Patch Review ----
elif phase == "Patch Review":
    st.title("Patch Review & Approval")
    task_id = st.session_state.get("selected_task_id")
    if not task_id:
        st.warning("No task selected.")
        st.stop()
    task = orch.backlog.get_item(task_id)
    try:
        patch = orch.executor.build_patch(task)
        st.code(patch, language="diff")
        review = orch.reviewer.review_patch(patch, context=task)
        st.markdown("### Review Comments")
        st.markdown(review["comments"] or "_No issues detected._")
        if review["pass"]:
            if st.button("Approve and Apply Patch"):
                # Apply patch, save, and proceed
                orch.shell.git_apply(patch)
                orch.record.save(task, state="patch_applied", extra={})
                st.success("Patch applied.")
                st.session_state["phase"] = "Run Test"
                st.experimental_rerun()
        else:
            st.error("Patch failed review; please revise before continuing.")
            if st.button("Back to task detail"):
                st.session_state["phase"] = "Task Detail"
                st.experimental_rerun()
    except Exception as ex:
        st.error(f"Patch build/review failed: {ex}")
        if st.button("Back to task detail"):
            st.session_state["phase"] = "Task Detail"
            st.experimental_rerun()

# ---- Run Test ----
elif phase == "Run Test":
    st.title("Run Pytest")
    task_id = st.session_state.get("selected_task_id")
    if not task_id:
        st.warning("No task selected.")
        st.stop()
    st.markdown("Apply code patch complete. Run tests to confirm correctness.")
    if st.button("Run tests now"):
        test_result = orch.shell.run_pytest()
        st.text_area("Test Output", test_result["output"], height=200)
        if test_result["success"]:
            st.success("Tests passed!")
            if st.button("Proceed to Archive/Done"):
                # Commit and archive task
                task = orch.backlog.get_item(task_id)
                sha = orch.shell.git_commit(f"[Cadence] {task['id'][:8]} {task.get('title', '')}")
                orch.backlog.update_item(task_id, {"status": "done"})
                orch.backlog.archive_completed()
                orch.record.save(task, state="committed", extra={"commit_sha": sha})
                orch.record.save(task, state="archived", extra={})
                st.session_state["phase"] = "Archive"
                st.experimental_rerun()
        else:
            st.error("Tests failed, fix required before progressing.")
    if st.button("Back to patch review"):
        st.session_state["phase"] = "Patch Review"
        st.experimental_rerun()

# ---- Archive / Task Complete ----
elif phase == "Archive":
    st.title("Task Archived")
    st.success("Task flow completed. You may return to the backlog.")
    if st.button("Back to backlog"):
        st.session_state["selected_task_id"] = None
        st.session_state["phase"] = "Backlog"
        st.experimental_rerun()