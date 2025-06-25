# src/cadence/context/provider.py
import subprocess, sys, json
from abc import ABC, abstractmethod
from pathlib import Path
class ContextProvider(ABC):
    @abstractmethod
    def get_context(self, *roots: Path, exts=(".py", ".md")) -> str: ...
class SnapshotContextProvider(ContextProvider):
    def get_context(self, *roots, exts=(".py", ".md"), out="-") -> str:
        args = [
            sys.executable, "tools/collect_code.py",
            "--max-bytes", "0",
            "--root", *[str(r) for r in roots],        # all roots in one group
            "--ext",  *exts,                           # all extensions in one group
            "--out",  out,
        ]
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout
