import os
from pathlib import Path
from textwrap import dedent

root = Path("src/cadence")
tree_lines = []
for dirpath, dirnames, filenames in os.walk(root):
    # Skip hidden dirs
    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
    depth = len(Path(dirpath).relative_to(root).parts)
    indent = "  " * depth
    dirname = os.path.basename(dirpath)
    if depth == 0:
        tree_lines.append(f"{dirname}/")
    else:
        tree_lines.append(f"{indent}{dirname}/")
    for fname in sorted(filenames):
        if fname.startswith('.'):
            continue
        tree_lines.append(f"{indent}  {fname}")

file_tree_md = "# Cadence File Tree (src/cadence)\n\n```\n" + "\n".join(tree_lines) + "\n```\n"

# Quick-start guide
quick_start_md = dedent("""\
    # Cadence Quick‑Start

    ## 1. Clone
    ```bash
    git clone <your-fork-or-repo>
    cd cadence
    ```

    ## 2. Install
    ```bash
    poetry install --with dev
    # or
    pip install -e .[dev]
    ```

    ## 3. Run tests
    ```bash
    pytest -q
    ```

    ## 4. Start an orchestrator task cycle
    ```bash
    python -m cadence.dev.orchestrator start
    ```

    *Optional flags*  
    - `--force-efficiency-pass` Skip efficiency review during offline runs.  
    - `--disable-meta` Disable MetaAgent analytics.

    ## 5. React Front‑End (future)
    The legacy Streamlit UI is archived under `legacy/`. A React GUI will
    connect over the CLI in a future loop.
    """)

# fresh_context script
fresh_script = dedent("""\
    #!/usr/bin/env bash
    # fresh_context.sh — Reset Cadence local state.
    # Usage: bash scripts/fresh_context.sh

    set -eu

    echo "==> Removing agent logs & records"
    rm -rf .cadence_logs || true
    rm -f dev_backlog.json dev_record.json

    echo "==> Initialising single blueprint task"
    cat > dev_backlog.json <<'JSON'
    [
      {
        "id": "$(uuidgen)",
        "title": "Hello Cadence — first blueprint",
        "type": "blueprint",
        "status": "open",
        "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "description": "Replace this with your first high‑level goal."
      }
    ]
    JSON

    echo "==> Done. Run: python -m cadence.dev.orchestrator start"
    """)

# Save files
docs_dir = Path("docs")
docs_dir.mkdir(exist_ok=True)
(tree_path := docs_dir / "FILE_TREE.md").write_text(file_tree_md, encoding="utf-8")
(docs_dir / "Quick-start.md").write_text(quick_start_md, encoding="utf-8")

scripts_dir = Path("scripts")
scripts_dir.mkdir(exist_ok=True)
(script_path := scripts_dir / "fresh_context.sh").write_text(fresh_script, encoding="utf-8")
# make executable
os.chmod(script_path, 0o755)

(tree_path, script_path, docs_dir / "Quick-start.md")