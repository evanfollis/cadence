
# cadence/dev/reviewer.py

"""
Cadence TaskReviewer
-------------------
Single Responsibility: Adjudicates patch/diff quality via rules/LLM/manual. Never applies code or diffs.
Future extensible: can host local ruleset, shell out to LLM agent, or use human-in-the-loop.
"""

import os
import json
from typing import Optional, Dict

class PatchReviewError(Exception):
    """Raised if review input is malformed or review fails outright (e.g. ruleset not found/valid)."""
    pass

class TaskReviewer:
    def __init__(self, ruleset_file: str = None):
        """
        Optionally specify path to ruleset file (JSON list of rules),
        or leave blank to use default built-in rules.
        """
        self.ruleset_file = ruleset_file
        self.rules = self._load_ruleset(ruleset_file) if ruleset_file else self._default_ruleset()

    def review_patch(self, patch: str, context: Optional[dict] = None) -> Dict:
        """
        Review a diff/patch string (unapplied) and optional context (task, commit message, etc).
        Returns dict {'pass': bool, 'comments': str}
        This uses static (offline) heuristics but can be swapped for agent/LLM in future.
        """
        # Guard: Patch required
        if not patch or not isinstance(patch, str):
            return {'pass': False, 'comments': 'Patch missing or not a string.'}

        # Apply rules in order. If any hard-fail, review fails.
        comments = []
        passed = True

        for rule in self.rules:
            ok, msg = rule(patch, context)
            if not ok:
                passed = False
            if msg:
                comments.append(msg)
            if not ok:
                # For now, fail-hard (but comment all)
                break

        return {'pass': passed, 'comments': "\n".join(comments).strip()}

    def _default_ruleset(self):
        """
        Returns a list of static rule functions: (patch, context) → (bool, str)
        """
        def not_empty_rule(patch, _):
            if not patch.strip():
                return False, "Patch is empty."
            return True, ""
        def startswith_rule(patch, _):
            if not patch.startswith(("---", "diff ", "@@ ")):
                return False, "Patch does not appear to be a valid unified diff."
            return True, ""
        def contains_todo_rule(patch, _):
            if "TODO" in patch:
                return False, "Patch contains 'TODO'—code review must not introduce placeholders."
            return True, ""

        # Optionally check for too-huge diffs, or forbidden patterns, via rules below.
        def size_limit_rule(patch, _):
            line_count = patch.count("\n")
            if line_count > 5000:  # Arbitrary large patch guard
                return False, f"Patch too large for standard review ({line_count} lines)."
            return True, ""
        return [
            not_empty_rule, 
            startswith_rule,
            contains_todo_rule,
            size_limit_rule,
        ]

    def _load_ruleset(self, path: str):
        """
        Loads a simple external ruleset (for human/agent extension), e.g. as list of forbidden strings.
        For extensibility only; advanced policies/LLMs should be subclassed onto this interface.
        """
        if not os.path.exists(path):
            raise PatchReviewError(f"Ruleset file '{path}' not found.")
        with open(path, "r", encoding="utf8") as f:
            obj = json.load(f)
        # Expect a list of {'type':..., 'pattern':..., ...} dicts for pattern rules
        rules = []
        def make_rule(ruleobj):
            typ = ruleobj.get('type')
            pattern = ruleobj.get('pattern')
            msg = ruleobj.get('message', f"Patch contains forbidden pattern: {pattern}")
            if typ == 'forbid':
                def _inner(patch, _):
                    if pattern in patch:
                        return False, msg
                    return True, ""
                return _inner
            elif typ == 'require':
                def _inner(patch, _):
                    if pattern not in patch:
                        return False, msg
                    return True, ""
                return _inner
            else:
                # Ignore unknown rule types
                def _inner(patch, _):
                    return True, ""
                return _inner
        for ruleobj in obj:
            rules.append(make_rule(ruleobj))
        # Default rules always included
        return self._default_ruleset() + rules

# Standalone/example/test run
if __name__ == "__main__":
    reviewer = TaskReviewer()
    # Good patch
    patch = """--- sample.py
+++ sample.py
@@ -1 +1,2 @@
-print('hello')
+print('hello world')
"""
    result = reviewer.review_patch(patch)
    print("Result (should pass):", result)

    bad_patch = "TODO: refactor\n"
    result = reviewer.review_patch(bad_patch)
    print("Result (should fail):", result)