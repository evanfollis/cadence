# src/cadence/context/select.py

def select_context(target_paths: list[str], max_tokens: int = 50_000) -> str:
    """
    Return BFS-ranked source blobs whose cumulative size ≤ max_tokens.
    """
    ...