# src/cadence/context/provider.py
import subprocess, sys, json
from abc import ABC, abstractmethod
from pathlib import Path
class ContextProvider(ABC):
    @abstractmethod
    def get_context(self, *roots: Path, exts=(".py", ".md")) -> str: ...
class SnapshotContextProvider(ContextProvider):
    def get_context(self, *roots, exts=(".py", ".md"), out="-") -> str:
        args = [sys.executable, "tools/collect_code.py"]
        for r in roots: args += ["--root", str(r)]
        for e in exts:  args += ["--ext", e]
        args += ["--out", out]
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout
