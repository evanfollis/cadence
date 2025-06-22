#!/usr/bin/env python3
"""
auto_generate_patches.py  –  context-aware, git-diff backed.

1. Loads docs / code / module_contexts JSON found in ./agent_context and
   formats them into base_execution_prompt.txt.
2. For every open backlog task that lacks `patch` (or --force) it asks an
   ExecutionAgent for file updates, then builds **real** git diffs that
   always pass `git apply --check`.
"""

from __future__ import annotations

import argparse, json, os, re, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
from typing import List, Dict, Any

from cadence.agents.registry import get_agent
from cadence.dev.backlog import BacklogManager

# --------------------------------------------------------------------------- #
# Config  – change dirs here if you move things around
# --------------------------------------------------------------------------- #
BACKLOG_PATH   = Path(os.getenv("CADENCE_BACKLOG", "dev_backlog.json"))
CTX_DIR        = Path("agent_context")
PROMPT_TPL     = CTX_DIR / "base_execution_prompt.txt"
DOCS_JSON      = CTX_DIR / "docs.json"
CODE_JSON      = CTX_DIR / "code.json"
MODULES_JSON   = CTX_DIR / "module_contexts.json"

# --------------------------------------------------------------------------- #
# Build a mega system-prompt
# --------------------------------------------------------------------------- #
if PROMPT_TPL.exists():
    base_template = PROMPT_TPL.read_text()
    try:
        docs_blob    = json.loads(DOCS_JSON.read_text())     if DOCS_JSON.exists()    else {}
        code_blob    = json.loads(CODE_JSON.read_text())     if CODE_JSON.exists()    else {}
        modules_blob = json.loads(MODULES_JSON.read_text())  if MODULES_JSON.exists() else {}

        # stringify with minimal whitespace – keeps token usage reasonable
        base_prompt = base_template.format(
            docs=json.dumps(docs_blob,    separators=(",", ":")),
            codebase=json.dumps(code_blob,separators=(",", ":")),
            contexts=json.dumps(modules_blob, separators=(",", ":")),
        )
    except Exception as exc:
        print(f"[WARN] could not format prompt template ({exc}); using plain template.")
        base_prompt = base_template
else:
    base_prompt = "Cadence ExecutionAgent – full context unavailable."

# ExecutionAgent factory
def _make_agent():
    return get_agent("execution", system_prompt=base_prompt)

# --------------------------------------------------------------------------- #
# Per-task user prompt (escaped braces)
# --------------------------------------------------------------------------- #
_PROMPT_TEMPLATE = """
You are an ExecutionAgent inside the Cadence platform.

TASK JSON (context ONLY – do **not** return this):
```json
{task_json}
```

Return one fenced JSON block with either

    {{ "file": "<path>", "after": "<full text>" }}

or

    {{
      "files": [
        {{ "file": "<path1>", "after": "<full text1>" }},
        {{ "file": "<path2>", "after": "<full text2>" }}
      ]
    }}

No prose outside the ```json block.
""".strip()


def _build_prompt(task: dict) -> str:
    return _PROMPT_TEMPLATE.format(task_json=json.dumps(task, indent=2))


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #
_JSON_RE = re.compile(r"```json\s*([\s\S]*?)```", re.I)

def _extract_json_block(text: str) -> Any | None:
    m = _JSON_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _git_diff(old: Path, new: Path, rel: str, repo: Path) -> str:
    """Generate a robust diff via git --no-index."""
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--relative", "--", str(old), str(new)],
        cwd=repo, text=True, capture_output=True
    )
    if proc.returncode not in (0, 1):           # 0 = identical, 1 = diff
        raise RuntimeError(proc.stderr)
    raw   = proc.stdout

    def _rewrite_header(line: str, side: str) -> str:
        """
        Convert
            --- a/ABS/PATH/TO/FILE
            +++ b/ABS/PATH/TO/FILE.after
        into
            --- a/<rel>
            +++ b/<rel>
        """
        if line.startswith(("--- /dev/null", "+++ /dev/null")):
            return line        # new / deleted file, leave untouched
        prefix, _sep, path = line.partition(f"{side}/")
        # path now contains ABS/PATH/TO/FILE[…]
        # discard everything up to the user-relative path
        return f"{prefix}{side}/{rel}"

    fixed_lines = []
    for ln in raw.splitlines():
        if ln.startswith("--- "):
            fixed_lines.append(_rewrite_header(ln, "a"))
        elif ln.startswith("+++ "):
            fixed_lines.append(_rewrite_header(ln, "b"))
        else:
            fixed_lines.append(ln)

    return "\n".join(fixed_lines) + "\n"


# --------------------------------------------------------------------------- #
def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="Regenerate all patches.")
    return p.parse_args()


def main() -> None:
    args = _cli()
    backlog = BacklogManager(BACKLOG_PATH.as_posix())
    todo = [t for t in backlog.list_items("open") if args.force or "patch" not in t]
    if not todo:
        print("No tasks need patch generation.")
        return

    updated = 0
    for task in todo:
        agent = _make_agent()
        agent.append_message("user", _build_prompt(task))
        reply = agent.run_interaction("")

        payload = _extract_json_block(reply)
        if payload is None:
            print(f"[WARN] No JSON block for '{task['title']}'")
            continue

        # normalise to list[dict]
        if isinstance(payload, dict) and "file" in payload:
            items = [payload]
        elif isinstance(payload, dict) and "files" in payload:
            items = payload["files"]
        elif isinstance(payload, list):
            items = payload
        else:
            print(f"[WARN] Malformed JSON for '{task['title']}'")
            continue

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(Path.cwd(), repo, dirs_exist_ok=True)
            patch_chunks: List[str] = []

            for ent in items:
                try:
                    rel = ent["file"].lstrip("./")
                    after_txt = ent["after"]
                except KeyError:
                    patch_chunks = []
                    break

                before_file = repo / rel
                after_file  = repo / f"{rel}.after"
                after_file.parent.mkdir(parents=True, exist_ok=True)
                after_file.write_text(after_txt, encoding="utf-8")

                diff = _git_diff(before_file, after_file, rel, repo)
                if diff.strip():
                    patch_chunks.append(diff)

            if not patch_chunks:
                continue

            patch = "".join(patch_chunks)

            # final validation
            try:
                with tempfile.TemporaryDirectory() as td2:
                    test_repo = Path(td2) / "repo"
                    shutil.copytree(Path.cwd(), test_repo, dirs_exist_ok=True)
                    subprocess.run(
                        ["git", "apply", "--check", "-"],
                        input=patch, text=True, cwd=test_repo, check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
                    )
            except subprocess.CalledProcessError:
                print(f"[WARN] git apply --check failed for '{task['title']}'")
                continue

        task["patch"] = patch
        task.pop("diff", None)
        backlog.update_item(task["id"], task)
        updated += 1
        print(f"[OK] Attached diff for '{task['title']}' (files={len(items)})")

    print(f"Updated {updated} task(s).")


if __name__ == "__main__":       # pragma: no cover
    main()