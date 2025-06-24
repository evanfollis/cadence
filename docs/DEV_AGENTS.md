# DEV AGENTS (canonical, auto-linted)

| Profile | Model          | Context Limit | Primary Duties                |
|---------|----------------|---------------|-------------------------------|
| reasoning   | `o3-2025-04-16` | 200 k tok   | Plan, architecture review     |
| execution   | `gpt-4.1`       |   1 M tok   | Generate / refactor code      |
| efficiency  | `o4-mini`       | 200 k tok   | Lint & summarise – MUST return EfficiencyReview JSON |

All Core Agents (`ReasoningAgent`, `ExecutionAgent`, `EfficiencyAgent`) are *final*.  New personas must **delegate** and declare their own `AgentProfile`.

Lint rule: profile table rows **must equal** `cadence.agents.profile.BUILTIN_PROFILES.keys()`.