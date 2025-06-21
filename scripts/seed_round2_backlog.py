# scripts/seed_round2_backlog.py
from cadence.dev.generator import TaskGenerator
from cadence.dev.backlog   import BacklogManager

# ----- 2.1  create plain-language task shells -------------------------
TASKS = [
    {"title": "TASK-1 Auto-replenish backlog",            "description": """Title: Auto-replenish backlog when empty
Goal: Keep the pipeline perpetually flowing without human babysitting.
Implementation Steps:

1. Add **`DevOrchestrator._ensure_backlog()`** • If **`self.backlog.list_items("open")`** is empty, call **`TaskGenerator.generate_tasks(mode="micro", count=<N>)`** (N default = 3; expose CLI flag). • Persist the newly generated tasks with **`BacklogManager.add_item`**. • Record snapshot: **`state="backlog_replenished"`**, extra={"count": N}.
2. Call **`_ensure_backlog()`** at the very top of **`run_task_cycle()`**.
3. Unit test: run an orchestrator in a temp repo with an empty backlog, assert it auto-populates.

Acceptance: **`run_task_cycle(interactive=False)`** no longer raises **`RuntimeError`** when no tasks exist.
""", "status": "open"},
    {"title": "TASK-2 EfficiencyAgent second review",     "description": """Title: Wire EfficiencyAgent as mandatory second review
Goal: Conform to DEV_PROCESS phase table (“Review” → Reasoning *and* Efficiency).
Implementation Steps:

1. In **`DevOrchestrator.__init__`** create **`self.efficiency = get_agent("efficiency")`**.
2. After **first** review passes, call **`eff_review = self.efficiency.run_interaction(<prompt_with_patch>)`** or, simpler for now, reuse **`TaskReviewer`** but tag the state **`"efficiency_reviewed"`**.
3. Fail the task cycle unless both reviews pass.
4. Record both review results with distinct states: **`"patch_reviewed_reasoning"`** / **`"patch_reviewed_efficiency"`**.
5. Extend phase flags so **`git_commit`** requires **`"efficiency_passed"`** as well.

Acceptance: A commit cannot occur unless *both* reviews have succeeded; tests updated accordingly.""", "status": "open"},
    {"title": "TASK-3 MetaAgent hook",                    "description": """Title: First-class MetaAgent hook
Goal: Provide real-time governance / drift detection per DEV_PROCESS.
Implementation Steps:

1. Add simple **`MetaAgent.analyse(run_summary: dict)`** stub that just logs or appends to TaskRecord.
2. Call it at the end of every **`run_task_cycle()`** (success *or* failure) with the full result dict.
3. Record state **`"meta_analysis"`** plus whatever telemetry the MetaAgent returns.
4. (Future-proof) Keep invocation behind **`config["enable_meta"]`** flag (default True).

Acceptance: TaskRecord shows a **`meta_analysis`** snapshot for every cycle; meta failures do not crash the run.""", "status": "open"},
    {"title": "TASK-4 Reviewer strict rule types",        "description": """Title: Harden TaskReviewer rule parsing
Goal: Unknown rule types must never be ignored silently.
Implementation Steps:

1. In **`TaskReviewer._load_ruleset`** raise **`PatchReviewError`** **or** emit **`logger.warning`** when **`type`** is unrecognised.
2. Provide **`strict`** constructor flag (default True).
3. Add regression test loading a ruleset with an invalid type → expect exception or warning.

Acceptance: CI fails (or logs) on an unrecognised rule type; no silent pass.""", "status": "open"},
    {"title": "TASK-5 Commit guard review flags",         "description": """Title: Expand enforce_phase → include review guards
Goal: Prevent any commit unless **`"review_passed"`** *and* **`"efficiency_passed"`** flags exist.
Implementation Steps:

1. Add new decorator usage or explicit check in **`ShellRunner.git_commit`**: required = ["patch_applied", "tests_passed", "review_passed", "efficiency_passed"]
2. Set those flags inside DevOrchestrator right after each successful review.
3. Update tests in test_phase_ordering_and_precheck.py to assert commit fails without both review flags.

Acceptance: New tests pass; existing tests updated to set the new flags on the happy path.""", "status": "open"},
    {"title": "TASK-6 Cross-process file locks",          "description": """Title: Cross-process file-locking for backlog & record
Goal: Prevent two orchestrators on the same repo from racing.
Implementation Steps:

1. Add lightweight cross-process lock via **`filelock`** (pip-light) or portalocker.
2. Acquire the lock in **`.save()`** and **`.load()`** of BacklogManager & TaskRecord *in addition* to the existing RLock. Lock file path = **`<jsonfile>.lock`**.
3. Time-out (e.g., 10 s) then raise custom **`FileLockTimeoutError`**; caller should retry or alert.
4. Add smoke test: spawn two **`multiprocessing.Process`** objects that hammer **`.add_item`**; assert no JSON corruption.

Acceptance: Concurrency test passes; manual ctrl-C leaves **`.lock`** cleaned up.""", "status": "open"},
    {"title": "TASK-7 LLMClient stub mode",               "description": """Title: Graceful LLMClient fallback when env is missing
Goal: Allow offline/CI runs without exporting OPENAI_API_KEY.
Implementation Steps:

1. In **`LLMClient.__init__`**, if api_key is missing: – log a **warning**; – enter “stub-mode”: **`.call()`** and **`.acall()`** return a canned message (e.g., **`"LLM unavailable"`**).
2. Add **`self.stub = True`** flag; tests can assert behaviour.
3. Update existing CI tests to expect stub-mode (they already monkey-patch OpenAI).

Acceptance: Running orchestrator without the env var no longer crashes; warning is emitted exactly once per process.""", "status": "open"},
]

tg = TaskGenerator()
with_backfill = [*TASKS]            # TaskGenerator will fill id/created_at
bm = BacklogManager("dev_backlog.json")
for t in with_backfill:
    bm.add_item(t)

print(f"Backlog now contains {len(bm.list_items('open'))} open tasks.")