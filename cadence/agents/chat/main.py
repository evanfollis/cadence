import os
import streamlit as st
import datetime

from cadence.agents.chat.agent_registry import AgentRegistry
from chat_utils import preview_message
from message_renderer import render_message


def get_timestamp():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def parse_paths(text):
    # Split on comma or space, strip whitespace, filter empty
    return [x.strip() for x in text.replace(",", " ").split() if x.strip()]

# ---- Initialize the registry (persistent per session) ----
if "agent_registry" not in st.session_state:
    st.session_state["agent_registry"] = AgentRegistry()
agent_registry = st.session_state["agent_registry"]

# 1. List agents, handle default
agents = agent_registry.list_agents()
default_agent = agents[0] if agents else None

# 2. Handle "just created" logic *before* rendering selectbox
if "just_created_agent" in st.session_state:
    st.session_state["selected_agent"] = st.session_state["just_created_agent"]
    del st.session_state["just_created_agent"]

if "selected_agent" not in st.session_state:
    st.session_state["selected_agent"] = default_agent

# 3. Prepare agent selection UI
select_options = (["+ Create new agent"] + agents) if agents else ["+ Create new agent"]
default_index = 1 if agents else 0

selected_agent_name = st.sidebar.selectbox(
    "Select agent", select_options, index=default_index, key="selected_agent"
)

# 4. If creating new agent, show creation form
if not agents or selected_agent_name == "+ Create new agent":
    st.sidebar.markdown("### Create a new agent")
    new_agent_name = st.sidebar.text_input("Agent name", key="new_agent_name")
    new_roots = st.sidebar.text_input("Code roots (comma/space separated)", value="docs cadence", key="new_roots")
    roots = parse_paths(new_roots)
    bad_roots = [r for r in roots if not os.path.isdir(r)]
    if bad_roots:
        st.sidebar.error(f"Invalid directory(ies): {', '.join(bad_roots)}")
        st.stop()
    new_ext = st.sidebar.text_input("File extensions (space/comma)", value=".py .md", key="new_ext")
    ext = tuple(parse_paths(new_ext))
    system_prompt = st.sidebar.text_area("System prompt (optional)", key="new_system_prompt")
    if st.sidebar.button("Create agent", key="btn_create_agent"):
        if new_agent_name.strip():
            agent_registry.get_or_create(new_agent_name, roots=roots, ext=ext, system_prompt=system_prompt)
            st.session_state["just_created_agent"] = new_agent_name
            st.rerun()
    st.info("Create an agent to begin chatting.")
    st.stop()

# -- Otherwise, agent exists, display config --
agent = agent_registry._agents[selected_agent_name]
roots_val = " ".join(agent.collect_roots)
ext_val = " ".join(agent.collect_ext)
system_prompt_val = getattr(agent, "system_prompt", "") if hasattr(agent, "system_prompt") else ""

roots_input = st.sidebar.text_input(
    "Code roots (comma/space)", value=roots_val, key="edit_roots"
)
roots = parse_paths(roots_input)
bad_roots = [r for r in roots if not os.path.isdir(r)]
if bad_roots:
    st.sidebar.error(f"Invalid directory(ies): {', '.join(bad_roots)}")
    st.stop()

ext_input = st.sidebar.text_input(
    "Extensions (space/comma)", value=ext_val, key="edit_ext"
)
ext = tuple(parse_paths(ext_input))

system_prompt = st.sidebar.text_area(
    "System prompt (optional)",
    value=system_prompt_val,
    key="edit_system_prompt"
)

if st.sidebar.button("Reset context for this agent", key="reset_ctx_btn"):
    agent.set_collect_code_args(
        roots=roots,
        ext=ext
    )
    agent.reset_context(system_prompt=system_prompt if system_prompt.strip() else None)
    st.rerun()

# ---- Get the active agent ----
if selected_agent_name == "+ Create new agent" or selected_agent_name is None:
    st.info("Create or select an agent to begin chatting.")
    st.stop()
agent = agent_registry._agents[selected_agent_name]

st.title(f"Cadence: Agentic Dev Chat — {selected_agent_name}")

messages = agent.messages

# ---- Render chat history with edit/minimize features ----
if "editing_idx" not in st.session_state:
    st.session_state["editing_idx"] = None
editing_idx = st.session_state["editing_idx"]

for idx, msg in enumerate(messages):
    is_editing = (editing_idx == idx)
    def make_save(idx):
        def save(new_content):
            msg['content'] = new_content
            st.session_state["editing_idx"] = None
        return save
    def make_cancel():
        def cancel():
            st.session_state["editing_idx"] = None
        return cancel

    entered_edit = render_message(
        msg, idx, is_editing,
        save_callback=make_save(idx),
        cancel_callback=make_cancel()
    )
    if entered_edit and not is_editing:
        st.session_state["editing_idx"] = idx
        st.rerun()

# ---- Input box for new user message ----
st.divider()
user_input = st.text_area("Enter your message:", key="new_message")

if st.button("Send", key="send") and user_input.strip():
    # 1. Append user message (with timestamp)
    agent.append_message("user", user_input.strip())
    # 2. Run the agent and get the response
    response = agent.run_interaction(user_input.strip())
    st.rerun()
