// ... existing imports ...
class ShellRunner:
    # ... existing code ...
    @enforce_phase(mark="workspace_cleaned")
    def git_reset_hard(self, rev="HEAD"):
        try:
            self.run(["git", "reset", "--hard", rev])
            self.run(["git", "clean", "-fd"])
        except Exception as e:
            self._record_failure("failed_git_reset", str(e))
            raise
    # ... rest of class ...
