# message_renderer.py

import streamlit as st

def render_message(msg, idx, is_editing, save_callback, cancel_callback):
    role = msg["role"]
    content = msg["content"]
    timestamp = msg.get("timestamp", "")
    preview = content.split("\n")[0]
    with st.expander(f"{role.capitalize()} ({timestamp}) — {preview}", expanded=False):
        if is_editing:
            # Show editable text area with save/cancel
            new_content = st.text_area("Edit message:", value=content, key=f"edit_{idx}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save", key=f"save_{idx}"):
                    save_callback(new_content)
            with col2:
                if st.button("Cancel", key=f"cancel_{idx}"):
                    cancel_callback()
        else:
            # Show message and an Edit button
            st.markdown(content)
            if st.button("Edit", key=f"edit_btn_{idx}"):
                return True  # signals to enter edit mode
    return False  # not in edit mode
