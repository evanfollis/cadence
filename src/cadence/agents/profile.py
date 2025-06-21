# src/cadence/agents/profile.py
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """
    Immutable definition of an agent’s operational contract.

    Nothing here executes code; it is pure data that can be validated,
    serialised, or inspected by the Meta-agent and CI tooling.
    """
    name: str
    role: str
    model: str
    context_limit: int
    review_policy: str = ""
    default_system_prompt: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Canonical profiles – these are the ONLY ones that Core Agents will default to
# --------------------------------------------------------------------------- #
REASONING_PROFILE = AgentProfile(
    name="reasoning",
    role="plan-review",
    model="o3-2025-04-16",
    context_limit=200_000,
    review_policy="Cannot commit code; must review Execution diff",
)

EXECUTION_PROFILE = AgentProfile(
    name="execution",
    role="implement",
    model="gpt-4.1",
    context_limit=1_000_000,
    review_policy="Needs review by Reasoning or Efficiency",
)

EFFICIENCY_PROFILE = AgentProfile(
    name="efficiency",
    role="lint-summarise",
    model="o4-mini",
    context_limit=200_000,
    review_policy="Reviews Execution unless diff is non-code",
)

# Convenience lookup
BUILTIN_PROFILES = {
    "reasoning": REASONING_PROFILE,
    "execution": EXECUTION_PROFILE,
    "efficiency": EFFICIENCY_PROFILE,
}