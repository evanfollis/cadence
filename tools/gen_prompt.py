#!/usr/bin/env python3
from __future__ import annotations
"""# MODULE CONTEXT SUMMARY
filepath: tools/gen_prompt.py
purpose: ""
public_api: [
    'tools.gen_prompt._build_prompt',
    'tools.gen_prompt._collect_files',
    'tools.gen_prompt._parse_args',
    'tools.gen_prompt.main',
]
depends_on: []
used_by: []
direct_imports: [
    '__future__',
    'argparse',
    'pathlib',
    'sys',
    'textwrap',
]
related_schemas: []
context_window_expected: ""
escalation_review: ""
# END MODULE CONTEXT SUMMARY"""


"""
gen_prompt.py  –  Assemble a mega-prompt that contains

  • Ground-truth docs (blueprint, progress logs, etc.)
  • Full source snapshot (or whatever roots you point at)
  • A header that gives the LLM an explicit NEXT TASK and ENV context

Usage
-----
python tools/gen_prompt.py \
       --code-root cadence \
       --docs-dir docs \
       --task "Implement FactorRegistry API and unit tests" \
       --env  "Python 3.11, pandas 2.2, scikit-learn 1.4" \
       --out  prompt.txt
"""

from pathlib import Path
import argparse
import sys
import textwrap

# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
DEFAULT_CODE_EXT = (".py", ".md", ".toml", ".ini", ".cfg")


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _collect_files(
    roots: list[Path],
    *,
    include_ext: tuple[str, ...],
    max_bytes: int | None = None,
) -> list[tuple[str, str]]:
    """Return [(relative_path, text), …] for all files matching *include_ext*."""
    records: list[tuple[str, str]] = []
    cwd = Path.cwd()

    for root in roots:
        root = Path(root).resolve()
        if not root.exists():
            print(f"WARNING: directory not found → {root}", file=sys.stderr)
            continue

        for p in root.rglob("*"):
            if (
                p.is_file()
                and p.suffix in include_ext
                and "__pycache__" not in p.parts
                and not any(part.startswith(".") for part in p.parts)
            ):
                if max_bytes and p.stat().st_size > max_bytes:
                    continue
                try:
                    txt = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    txt = p.read_text(encoding="utf-8", errors="replace")
                records.append((str(p.relative_to(cwd)), txt))

    records.sort()
    return records


def _build_prompt(
    docs: list[tuple[str, str]],
    code: list[tuple[str, str]],
    *,
    header: str,
) -> str:
    parts: list[str] = [header]

    # -- docs ---------------------------------------------------------------
    parts.append("\n## 1. Ground-Truth Documents")
    if not docs:
        parts.append("\n_No Markdown / text documents found in docs directory._")
    for path, txt in docs:
        parts.append(f"\n### {path}\n```markdown\n{txt}\n```")

    # -- code ---------------------------------------------------------------
    parts.append("\n## 2. Source Code Snapshot")
    if not code:
        parts.append("\n_No source files found in code roots._")
    for path, txt in code:
        fence = "```python" if path.endswith(".py") else "```text"
        parts.append(f"\n### {path}\n{fence}\n{txt}\n```")

    return "\n".join(parts)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate mega-prompt for LLM.")
    p.add_argument("--code-root", nargs="+", default=["cadence"],
                   help="Package directories to scan (repeatable).")
    p.add_argument("--docs-dir", default="docs",
                   help="Directory holding NORTH_STAR.md, progress logs, etc.")
    p.add_argument("--ext", nargs="+", default=DEFAULT_CODE_EXT,
                   help="File extensions to include from code roots.")
    p.add_argument("--max-bytes", type=int, default=100_000,
                   help="Skip individual files larger than this size (bytes).")
    p.add_argument("--skip-code", action="store_true",
               help="Omit source snapshot (tasks only).")
    p.add_argument("--task", default="Tell me the next highest-leverage step and write the code.",
                   help="Explicit next task instruction injected into header.")
    p.add_argument("--env", default="Python 3.11, pandas 2.2, scikit-learn 1.4",
                   help="Runtime environment string added to header.")
    p.add_argument("--out", default="-",
                   help="Output file path or '-' for stdout.")
    return p.parse_args(argv)


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    args = _parse_args(argv)

    docs = _collect_files(
        [Path(args.docs_dir).resolve()],
        include_ext=(".md", ".txt"),
        max_bytes=args.max_bytes,
    )

    if args.skip_code:
        code = []
    else:
        code = _collect_files(
            [Path(r).resolve() for r in args.code_root],
            include_ext=tuple(args.ext),
            max_bytes=args.max_bytes,
        )

    header = textwrap.dedent(
        f"""\
        ### CADENCE STATUS / ALIGNMENT REQUEST  (auto-generated)

        **Task**: {args.task}
        **Environment**: {args.env}

        You are an expert reviewer. Read ALL content below — docs first, then full
        code — and report:

          1. Alignment gaps between implementation and blueprint  
          2. Missing risk / compliance safeguards  
          3. Highest-leverage next actions  

        Be brutally honest. No cheerleading. Return your analysis **only**.

        ---
        """
    )

    prompt = _build_prompt(docs, code, header=header)

    if args.out == "-":
        sys.stdout.write(prompt)
    else:
        Path(args.out).write_text(prompt, encoding="utf-8")
        print(f"Wrote prompt to {args.out}")


if __name__ == "__main__":
    main()
