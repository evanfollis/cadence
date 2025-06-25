#!/usr/bin/env python3
from __future__ import annotations
"""
collect_code.py – Export Cadence source files to a single JSON payload.

Usage
-----
python tools/collect_code.py \
       --root cadence src/cadence tools docs tests scripts \
       --ext .py .md .json .mermaid .txt \
       --out code_payload.json \
       --max-bytes 0           # 0 (or omit) = unlimited

Result
------
JSON mapping   { "relative/path/to/file": "UTF-8 text …", … }
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple, Dict

DEFAULT_EXT: Tuple[str, ...] = (".py", ".md", ".cfg", ".toml", ".ini", ".json", ".mermaid", ".txt")

# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------

def collect(
    roots: List[Path],
    files: List[Path] | None = None,
    *,
    extensions: Tuple[str, ...] = DEFAULT_EXT,
    max_bytes: int | None = None,
) -> Dict[str, str]:
    """Walk *roots* and return {relative_path: code_text}."""
    out: Dict[str, str] = {}
    files = files or []
    for root in roots:
        for p in root.rglob("*"):
            if (
                p.is_file()
                and p.suffix in extensions
                and "__pycache__" not in p.parts
                and not any(part.startswith(".") for part in p.parts)
            ):
                if max_bytes is not None and max_bytes > 0 and p.stat().st_size > max_bytes:
                    continue
                out[str(p.relative_to(Path.cwd()))] = _read_text(p)
    for f in files:
        if f.is_file() and f.suffix in extensions:
            if max_bytes is None or max_bytes <= 0 or f.stat().st_size <= max_bytes:
                rel = str(f.relative_to(Path.cwd()))
                out.setdefault(rel, _read_text(f))
    return out


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Collect source files into JSON.")
    ap.add_argument("--root", nargs="+", default=["cadence"], help="Directories to scan (repeatable).")
    ap.add_argument("--ext", nargs="+", default=list(DEFAULT_EXT), help="File extensions to include.")
    ap.add_argument(
        "--max-bytes",
        type=int,
        default=0,
        help="Skip files larger than this size (bytes). 0 or omission → unlimited.",
    )
    ap.add_argument("--file", nargs="+", default=[], help="Individual files to include (repeatable).")
    ap.add_argument("--out", default="-", help="Output file path or '-' for stdout.")
    return ap.parse_args(argv)


def main(argv: List[str] | None = None) -> None:  # pragma: no cover
    args = _parse_args(argv)
    payload = collect(
        [Path(r).resolve() for r in args.root],
        files=[Path(f).resolve() for f in args.file],
        extensions=tuple(args.ext),
        max_bytes=None if args.max_bytes <= 0 else args.max_bytes,
    )
    if args.out == "-":
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    else:
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"Wrote {len(payload)} files → {args.out}")

if __name__ == "__main__":  # pragma: no cover
    main()
