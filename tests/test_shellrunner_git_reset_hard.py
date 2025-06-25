import os
import shutil
import tempfile
from cadence.dev.shell import ShellRunner
from cadence.dev.orchestrator import DevOrchestrator
import pytest


def test_git_reset_hard_cleans_repo():
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    sr = ShellRunner()
    # initialize empty repo and dirty files
    sr.run(["git", "init"])
    with open("tracked.txt", "w") as f:
        f.write("hello")
    sr.run(["git", "add", "tracked.txt"])
    sr.run(["git", "commit", "-m", "first commit"])
    # make dirty: change tracked, add untracked
    with open("tracked.txt", "a") as f:
        f.write("dirty")
    with open("untracked.txt", "w") as f:
        f.write("no track")
    # attempt rollback
    dev = DevOrchestrator()
    dev.shell = sr
    dev._attempt_rollback()
    status = sr.run(["git", "status", "--porcelain"])
    assert status.strip() == ""
    shutil.rmtree(tmpdir)
