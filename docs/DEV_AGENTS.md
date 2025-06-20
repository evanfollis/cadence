
# DEV AGENTS — Model Assignment, Profiles & Context Rules  

*Last-updated: 2025-06-20*

## 1 · Why This File Exists  
This is the **single source of truth** for how Cadence maps logical roles to concrete LLM
models, context windows, review policy and—new in this revision—`AgentProfile`
objects that keep those concerns *out of the Python class hierarchy*.

## 2 · Key Concepts  

| Term            | Description                                                                    |
| --------------- | ------------------------------------------------------------------------------ |
| **AgentProfile**| Immutable dataclass declaring model, context limit, review policy, etc.        |
| **Core Agent**  | Final class that *implements* a capability (Reasoning / Execution / Efficiency)|
| **Persona**     | Thin wrapper that *delegates* to a Core Agent but presents a different prompt. |
| **Capability**  | A mix-in or helper that adds specific behaviour (e.g. `CodeContextCapability`).|

Separation of concerns:  

```
+------------------+     +--------------+     +----------+
|  Persona (Sidekick)----> Core Agent ----->  AgentProfile
+------------------+     +--------------+     +----------+
                   delegates            references
```

## 3 · Profiles (Canonical)

| Profile Name | Role Tag          | Model          | Context Limit | Review Path                                   |
| ------------ | ----------------- | -------------- | ------------- | --------------------------------------------- |
| `REASONING`  | `plan-review`     | `o3-2025-04-16`| 200 K         | Cannot commit code; must review Execution diff|
| `EXECUTION`  | `implement`       | `gpt-4.1`      | 1 M           | Needs review by Reasoning or Efficiency       |
| `EFFICIENCY` | `lint-summarise`  | `o4-mini`      | 200 K         | Reviews Execution unless diff is non-code     |

All profiles live in `cadence/agents/profile.py`.

## 4 · Core Agents (final)

| Class Name                | Uses Profile | Responsibilities                              |
| ------------------------- | ------------ | --------------------------------------------- |
| `ReasoningAgent`          | `REASONING`  | Planning, architecture review, policy checks  |
| `ExecutionAgent`          | `EXECUTION`  | Code generation / refactor                    |
| `EfficiencyAgent`         | `EFFICIENCY` | Linting, summarisation, static analysis       |

These classes are **final**—do not subclass for personas.

## 5 · Personas

A persona combines a *profile* + *prompt* + optional extra helpers by **delegating**
to one of the Core Agents. Example: `Sidekick` (advisor persona) delegates to
`ReasoningAgent` but overrides only the system prompt.

## 6 · Context Injection Rules (unchanged)

1. ExecutionAgent may receive full codebase when ≤ 1 M tokens; otherwise chunk.  
2. Reasoning/Efficiency agents limited to ≤ 200 K tokens per call.  
3. Module summaries (`# MODULE CONTEXT SUMMARY`) are mandatory for every file.  

## 7 · Governance (unchanged)

* All agent calls log: timestamp, model, prompt token count, hash of output.
* CI step `lint_docs.py` verifies correct model names and context annotations.

---

*Change-log:*  
2025-06-20 — Introduced AgentProfile pattern; Core Agents made final; personas use delegation.