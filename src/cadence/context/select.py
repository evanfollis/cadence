import os

try:
    import tiktoken
except ImportError:
    tiktoken = None

def _count_tokens(text):
    if tiktoken:
        enc = tiktoken.encoding_for_model('gpt-3.5-turbo')
        return len(enc.encode(text))
    # Fallback: 1 token ~= 4 chars, or use line count
    return len(text.splitlines())

def select_context(file_paths, max_tokens):
    """
    Given a list of file paths, select files (source blobs) in BFS order (by directory depth, 0=root)
    and concatenate their contents until max_tokens is reached (as approximated by tiktoken or line count).
    Returns a tuple (ordered_paths, concatenated_source_text)
    """
    # Rank files by directory depth (shallowest first)
    def depth(path):
        return path.count(os.sep)
    sorted_paths = sorted(file_paths, key=depth)

    blobs = []
    total_tokens = 0
    selected_paths = []
    for p in sorted_paths:
        with open(p, encoding='utf-8') as f:
            src = f.read()
        tokens = _count_tokens(src)
        if total_tokens + tokens > max_tokens:
            break
        blobs.append(src)
        selected_paths.append(p)
        total_tokens += tokens
    return selected_paths, "".join(blobs)
