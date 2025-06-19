# DEV_AGENTS.md — Canonical Agent Roles, Models, and Assignment Rules

> **Last updated:** 2025‑06‑19  
> **Maintainer:** Cadence Platform Owners  
> **Status:** *Single source of truth. All agentic orchestration MUST conform.*

---

## 1. Purpose & Design Philosophy

Agent roles are defined by a strict matrix of *model capability × task requirement*. This ensures:
1. **Context-fit** — models never exceed their window.
2. **Reasoning safety** — code giving is always reviewed.
3. **Cost-efficiency** — model selection based on prompt size and complexity.

---

## 2. Agent Role Matrix

| Agent Type        | Class Name          | Model                  | Context Window | Task Scope                              | Output Type              | Review Requirement                              |
|-------------------|---------------------|------------------------|----------------|------------------------------------------|--------------------------|-------------------------------------------------|
| **Plan/Review**   | `ReasoningAgent`    | **o3**                 | 200 K tokens    | Deep planning, policy checks, critique   | Plans, design, code review | Not for auto-code; may self-approve small scopes |
| **Implement/Execute** | `ExecutionAgent` | **GPT‑4.1 (1 M)**      | **1 M tokens**  | Full-codebase change, refactoring        | Diffs, tests, scripts     | Required review: by Reasoning or EfficiencyAgent |
| **Sanity/Utility**| `EfficiencyAgent`   | **o4‑mini**            | 200 K tokens    | Lint, detect, summarize, static checks   | Summaries, regex diffs    | Yes—on code output, unless trivially harmless   |

**Validated Claims**:
- GPT‑4.1 supports 1 M-token window (API-only; UI capped at 32 K) :contentReference[oaicite:1]{index=1}  
- o4-mini: lowest latency and cost for <50 K-token tasks :contentReference[oaicite:2]{index=2}  
- GPT‑4.1 outperforms o3 on coding/instruction metrics at similar latency :contentReference[oaicite:3]{index=3}  
- Use-of-window must align to endpoint variant (e.g., GPT‑4.1 vs GPT‑4.1 variant) :contentReference[oaicite:4]{index=4}

---

## 3. Phase Boundary: Codebase Growth & Role Shift

- **Early Phase** (≤200 K tokens codebase):  
  - It’s justified to *temporarily* run the full codebase with o3 for maximal reasoning.
- **Growth Phase** (when codebase exceeds ~200 K tokens):  
  - ↑ALL full-code operations must move to `ExecutionAgent` (GPT‑4.1).
  - `ReasoningAgent` reverts to working with summaries or modular contexts.
  - Violations must trigger explicit warnings in orchestration logs.

---

## 4. Model Behavior & Default Assignment

- **EfficiencyAgent using o4‑mini**  
    - Default for tasks <50 K tokens.  
    - Tech lint, search, transform patches with minimal cost and max responsiveness.
- **ExecutionAgent using GPT‑4.1 (1 M)**  
    - Default for full-code changes, implementations, and chunked large context jobs.  
    - Capable of mid-level critique—light review allowed.
- **ReasoningAgent using o3**  
    - Default for deep critique, architecture planning, policy enforcement.  
    - May self-approve narrow reasoning-only patches to optimize cost (≤10 K token outputs).

---

## 5. Review & Output Escalation Policy

```text
            +----------------------+
            | Request Implementation |
            +-----------+----------+
                        |
            +-----------v----------+
            | ExecutionAgent (GPT‑4.1) |
            +-----------+----------+
                        |
        +---------------+---------------+
        |                               |
+-------v-------+               +-------v--------+
| EfficiencyAgent|             | ReasoningAgent |
| (o4‑mini)      |             | (o3)           |
+-------+-------+             +--------+--------+
        |                                |
        +--------------+-----------------+
                       |
              +--------v---------+
              |   Commit Merge   |
              +------------------+
````

* Every code change from ExecutionAgent must be reviewed by one downstream agent.
* ReasoningAgent handles policy or deep reasoning critiques.
* EfficiencyAgent checks technical safety, patterns, linting.
* `ReasoningAgent` may self-vet small pure‐reasoning diffs (<10 K tokens) to leverage cost advantage.
* Review agents must log decisions explicitly.

---

## 6. Context Injection & Module Summaries

* ExecutionAgent may receive **entire codebase** (when GPT‑4.1 supports 1 M tokens).
* Reasoning/Efficiency agents only receive module summaries or chunks, never >200 K tokens.
* **Module Summary Standard** (at top of every `.py` or `.md`):

```yaml
# MODULE CONTEXT SUMMARY
filepath: <relative path>
role: <Reasoning|Execution|EfficiencyAgent>
purpose: <role-specific purpose>
public_api: [ … ]
depends_on: [ … ]
context_window_expected: <model window>
escalation_review: <Required review agent or "self (<=10K tokens)">
```

A health-check script (e.g., `tools/collect_module_context.py`) must enforce this format and flag missing or incorrect summaries.

---

## 7. Costs & Token-Usage Optimization

* **GPT‑4.1**: \$2 input + \$8 output per 1 M tokens ([artificialanalysis.ai][1], [en.wikipedia.org][2], [blog.getzep.com][3], [artificialanalysis.ai][4])

* **o4-mini**: input \$1.10, output \$4.40 per 1 M tokens ([docsbot.ai][5])

* **o3**: similar to GPT‑4.1, but hidden CoT tokens still billed.

  * For pure reasoning tasks, token efficiency is sometimes superior if outputs are concise.

* **Policy**:

  * Allow o3 self-verify for small patches to reduce cost and latency.
  * Escalation to GPT‑4.1 only when patch-level critique is insufficient or context size requires.

---

## 8. Model Variants & Endpoint Precision

* Explicit invocation required:

  * `gpt-4.1` (1 M token window)
  * `gpt-4.1-mini` or `-nano`: smaller context but for other use cases
* o3/o4-mini context windows capped at **200K tokens** ([reddit.com][6])
* Azure deployments may present lower context limits—**always query actual window size** via model metadata&#x20;

---

## 9. Governance & Auditability

* All agent actions, decisions, reviews, and overrides must be logged with:

  * Timestamp
  * Agent class & model used
  * Context size and prompt snippet
  * Output summary
  * Review agent identity and flag
* **Silent mode workflows (no logs)** are forbidden.

---

## 10. Change Log

| Date       | Author | Summary                                             |
| ---------- | ------ | --------------------------------------------------- |
| 2025-06‑19 | E.     | Full vetting of model behavior & context limits     |
| 2025‑06‑18 | E.     | Initial corrected assignment matrix, phase boundary |

---

Commitment to this document is **mandatory**—all agents, orchestration, and health checks must align with it.

### ✅ Vetted & Verified

- **Speed/cost claims** are backed with real benchmarks :contentReference[oaicite:38]{index=38}.  
- **Context windows** carefully checked, with API caveats noted :contentReference[oaicite:39]{index=39}  
- **Real-world behavior** of GPT‑4.1 vs o3 & o4-mini supported :contentReference[oaicite:40]{index=40} 

[1]: https://artificialanalysis.ai/models/gpt-4-1?utm_source=chatgpt.com "GPT-4.1 - Intelligence, Performance & Price Analysis"
[2]: https://en.wikipedia.org/wiki/GPT-4.1?utm_source=chatgpt.com "GPT-4.1"
[3]: https://blog.getzep.com/gpt-4-1-and-o4-mini-is-openai-overselling-long-context/?utm_source=chatgpt.com "GPT-4.1 and o4-mini: Is OpenAI Overselling Long-Context? - Zep"
[4]: https://artificialanalysis.ai/models/comparisons/o4-mini-vs-gpt-4-1?utm_source=chatgpt.com "o4-mini (high) vs GPT-4.1: Model Comparison - Artificial Analysis"
[5]: https://docsbot.ai/models/compare/gpt-4-1-mini/o4-mini?utm_source=chatgpt.com "GPT-4.1 Mini vs o4-mini - DocsBot AI"
[6]: https://www.reddit.com/r/OpenAI/comments/1kwg3c6/gpt41_supports_a_1m_token_contextwhy_is_chatgpt/?utm_source=chatgpt.com "GPT-4.1 Supports a 1M Token Context—Why Is ChatGPT ... - Reddit"

---
