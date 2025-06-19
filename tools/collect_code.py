#!/usr/bin/env python3
"""
collect_code.py  –  Export Cadence source files to a single JSON payload.

Usage
-----
python tools/collect_code.py \
       --root cadence              # package folder(s) to scan (repeatable)
       --out  code_payload.json   # written JSON (stdout if omitted)
       --ext .py .md              # file extensions to keep
       --max-bytes 50000          # skip giant files (>50 kB)

Result
------
A JSON dict   { "relative/path/to/file": "UTF-8 text …", ... }
"""

from __future__ import annotations
from pathlib import Path
import argparse
import json
import sys

DEFAULT_EXT = (".py", ".md", ".cfg", ".toml", ".ini")


def collect(
    roots: list[Path],
    *,
    extensions: tuple[str, ...] = DEFAULT_EXT,
    max_bytes: int | None = None,
) -> dict[str, str]:
    """
    Walk *roots* and return {relative_path: code_text}.
    Skips __pycache__, hidden folders, and files larger than *max_bytes*.
    """
    out: dict[str, str] = {}
    for root in roots:
        for path in root.rglob("*"):
            if (
                path.is_file()
                and path.suffix in extensions
                and "__pycache__" not in path.parts
                and not any(p.startswith(".") for p in path.parts)
            ):
                if max_bytes and path.stat().st_size > max_bytes:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = path.read_text(encoding="utf-8", errors="replace")
                out[str(path.relative_to(Path.cwd()))] = text
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect source files into JSON.")
    p.add_argument(
        "--root",
        nargs="+",
        default=["cadence"],
        help="Directories to scan (repeatable).",
    )
    p.add_argument(
        "--ext",
        nargs="+",
        default=DEFAULT_EXT,
        help="File extensions to include (repeatable).",
    )
    p.add_argument(
        "--max-bytes",
        type=int,
        default=50000,
        help="Skip files larger than this size (bytes).",
    )
    p.add_argument(
        "--out",
        type=str,
        default="-",
        help="Output JSON file path or '-' for stdout.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    args = parse_args(argv)
    payload = collect(
        [Path(r).resolve() for r in args.root],
        extensions=tuple(args.ext),
        max_bytes=args.max_bytes,
    )
    if args.out == "-":
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    else:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"Wrote {len(payload)} files → {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
