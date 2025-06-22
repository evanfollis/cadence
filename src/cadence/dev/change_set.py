# src/cadence/dev/change_set.py
"""
Structured representation of a code change.

Execution-agents (LLMs or humans) now produce **ChangeSet** JSON instead of
hand-written diffs.  A single PatchBuilder later converts the ChangeSet into a
valid git patch, eliminating fragile string-diff manipulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import hashlib


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class FileEdit:
    """
    One logical modification to a file.

    • `path`  – repository-relative path using POSIX slashes.
    • `after` – full new file contents (None for deletions).
    • `before_sha` – optional SHA-1 of the *current* file to protect
                     against stale edits; raise if it no longer matches.
    • `mode` –  "add" | "modify" | "delete"
    """

    path: str
    after: Optional[str] = None
    before_sha: Optional[str] = None
    mode: str = "modify"

    # --- helpers --------------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "FileEdit":
        return FileEdit(
            path=obj["path"],
            after=obj.get("after"),
            before_sha=obj.get("before_sha"),
            mode=obj.get("mode", "modify"),
        )


@dataclass(slots=True)
class ChangeSet:
    """
    A collection of FileEdits plus commit metadata.
    """

    edits: List[FileEdit] = field(default_factory=list)
    message: str = ""
    author: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    # --- helpers --------------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edits": [e.to_dict() for e in self.edits],
            "message": self.message,
            "author": self.author,
            "meta": self.meta,
        }

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "ChangeSet":
        return ChangeSet(
            edits=[FileEdit.from_dict(ed) for ed in obj.get("edits", [])],
            message=obj.get("message", ""),
            author=obj.get("author", ""),
            meta=obj.get("meta", {}),
        )

    # Convenient JSON helpers -------------------------------------------- #
    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_json(text: str | bytes) -> "ChangeSet":
        return ChangeSet.from_dict(json.loads(text))

    # -------------------------------------------------------------------- #
    # Validation helpers
    # -------------------------------------------------------------------- #
    def validate_against_repo(self, repo_path: Path) -> None:
        """
        Raises RuntimeError if any `before_sha` no longer matches current file.
        """
        for e in self.edits:
            if e.before_sha:
                file_path = repo_path / e.path
                if not file_path.exists():
                    raise RuntimeError(f"{e.path} missing – SHA check impossible.")
                sha = _sha1_of_file(file_path)
                if sha != e.before_sha:
                    raise RuntimeError(
                        f"{e.path} SHA mismatch (expected {e.before_sha}, got {sha})"
                    )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _sha1_of_file(p: Path) -> str:
    buf = p.read_bytes()
    return hashlib.sha1(buf).hexdigest()