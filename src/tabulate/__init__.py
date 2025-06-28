"""Minimal tabulate stub for tests."""

def tabulate(rows, headers, tablefmt="github"):
    """Return a simple table string representation."""
    lines = [" | ".join(headers)]
    for r in rows:
        lines.append(" | ".join(str(c) for c in r))
    return "\n".join(lines)