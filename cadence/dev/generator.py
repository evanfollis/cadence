# cadence/dev/generator.py

"""
Cadence TaskGenerator
-------------------
Single Responsibility: Propose/generate well-formed tasks, optionally from template or rules/LLM seed.
Never applies code or diffs. Future extensible to LLM/human agent.
"""

import os
import json
import uuid
from typing import List, Dict, Optional
import datetime

class TaskTemplateError(Exception):
    """Raised if template file is not valid or incomplete."""
    pass

REQUIRED_FIELDS = ("title", "type", "status", "created_at")

class TaskGenerator:
    def __init__(self, template_file: str = None):
        """
        Optionally specify a JSON (or Markdown with JSON front-matter) template file.
        """
        self.template_file = template_file
        self._template_cache = None
        if template_file:
            self._template_cache = self._load_template(template_file)
    
    def generate_tasks(self, mode: str = "micro", count: int = 1, human_prompt: Optional[str]=None) -> List[Dict]:
        """
        Return a list of well-formed tasks. 
        - mode: "micro", "story", "epic", etc.
        - count: number of tasks to generate
        - human_prompt: if provided, use as summary/title for each (e.g., "Add new test", for human CLI prompt workflow)
        If template_file is used, will fill in mode-related templates.
        """
        tasks = []
        base_tpl = self._get_template_for_mode(mode)
        now = datetime.datetime.utcnow().isoformat()
        for i in range(count):
            task = dict(base_tpl)
            # Minimal fields: id, title, type, status, created_at
            task["id"] = str(uuid.uuid4())
            task["type"] = mode
            task.setdefault("status", "open")
            task.setdefault("created_at", now)
            if human_prompt:
                # Provide a default/barebones title/desc from human input
                task["title"] = human_prompt if count == 1 else f"{human_prompt} [{i+1}]"
                task.setdefault("description", human_prompt)
            else:
                # Fallback: title must be present; if not, use template/title from mode or 'Untitled'
                task["title"] = task.get("title", f"{mode.capitalize()} Task {i+1}")
                task.setdefault("description", "")
            self._validate_task(task)
            tasks.append(task)
        return tasks

    def overwrite_tasks(self, new_tasks: List[Dict], output_path: Optional[str]=None) -> None:
        """
        Replace all backlog tasks with given well-formed list (writes to output_path, else self.template_file).
        """
        path = output_path or self.template_file
        if not path:
            raise TaskTemplateError("No output path specified to write tasks.")
        with open(path, "w", encoding="utf8") as f:
            json.dump([self._validate_task(t) for t in new_tasks], f, indent=2)

    def _get_template_for_mode(self, mode: str) -> Dict:
        """
        Get template for the given mode; falls back to default/minimal template.
        """
        if self._template_cache and mode in self._template_cache:
            return dict(self._template_cache[mode])  # deep copy
        # Fallback: minimal template
        return {
            "title": "",
            "type": mode,
            "status": "open",
            "created_at": "",
            "description": "",
        }

    def _load_template(self, path: str) -> Dict:
        """
        Loads a JSON template file mapping mode→template-dict.
        If Markdown file with front-matter, parse the JSON front-matter.
        """
        if not os.path.exists(path):
            raise TaskTemplateError(f"Template file not found: {path}")
        if path.endswith(".md"):
            with open(path, "r", encoding="utf8") as f:
                lines = f.readlines()
            start, end = None, None
            for i, line in enumerate(lines):
                if line.strip() == "```json":
                    start = i + 1
                elif line.strip().startswith("```") and start is not None and end is None:
                    end = i
                    break
            if start is not None and end is not None:
                json_str = "".join(lines[start:end])
                tpl = json.loads(json_str)
            else:
                raise TaskTemplateError("Markdown template missing ```json ... ``` block.")
        else:
            with open(path, "r", encoding="utf8") as f:
                tpl = json.load(f)
        if not isinstance(tpl, dict):
            raise TaskTemplateError("Task template must be a dict mapping mode->template.")
        return tpl

    def _validate_task(self, task: Dict) -> Dict:
        """
        Ensures task has all required fields and correct types/formats.
        Throws TaskTemplateError if not.
        """
        for field in REQUIRED_FIELDS:
            if field not in task or (field == "title" and not task["title"].strip()):
                raise TaskTemplateError(f"Task missing required field: '{field}'")
        if not isinstance(task["type"], str):
            raise TaskTemplateError("Task type must be str.")
        if "id" in task and not isinstance(task["id"], str):
            task["id"] = str(task["id"])
        # Optionally: check status value, etc.
        return task

    # For future agentic/LLM/human input: accept strings, call LLM API, etc.
    # Extend here with agent hooks.

# Standalone/test CLI example (not for production)
if __name__ == "__main__":
    # Example: generate 2 microtasks from default, print as JSON:
    g = TaskGenerator()
    tasks = g.generate_tasks(mode="micro", count=2, human_prompt="Example user-initiated task")
    print(json.dumps(tasks, indent=2))