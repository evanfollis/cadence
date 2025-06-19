# cadence/agents/chat/chat_utils.py

def preview_message(content: str, n_lines=2) -> str:
    lines = content.splitlines()
    return "\n".join(lines[:n_lines]) + ("…" if len(lines) > n_lines else "")
