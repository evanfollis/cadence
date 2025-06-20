# ./cadence/utils/mvp_loop.py

import pytest
from cadence.dev.executor import TaskExecutor
from cadence.dev.shell import ShellRunner

def manual_test():
    result = pytest.main(["tests"])
    if result != 0:
        print("Tests failed.")
        # Read before
        before = open("cadence/utils/add.py").read()
        print("Paste fixed implementation for utils/add.py below. End input with EOF (Ctrl+D):")
        after = []
        try:
            while True:
                after.append(input())
        except EOFError:
            pass
        after = "\n".join(after)
        # build diff
        task = {"diff": {"file": "cadence/utils/add.py", "before": before, "after": after}}
        patch = TaskExecutor("cadence/utils").build_patch(task)
        print("---Proposed Diff---")
        print(patch)

def OOP_test():
    executor = TaskExecutor(src_root=".")
    shell = ShellRunner(repo_dir=".")

    # Dynamically read and patch the file
    with open("cadence/utils/add.py") as f:
        before = f.read()
    if "return x + y" not in before:
        after = before.replace("return x - 1 + y", "return x + y")
    else:
        print("Already correct: no patch needed.")
        return

    task = {
        "diff": {
            "file": "cadence/utils/add.py",
            "before": before,
            "after": after
        }
    }

    patch = executor.build_patch(task)
    try:
        shell.git_apply(patch)
        # Run tests via ShellRunner
        result = shell.run_pytest()
        if result["success"]:
            sha = shell.git_commit("Fix add(): correct return expression")
            print(f"Patch applied and tests passed. Commit SHA: {sha}")
        else:
            print("Tests failed after patch:\n", result["output"])
    except Exception as e:
        print("Patch failed:", e)



if __name__ == "__main__":
    OOP_test()