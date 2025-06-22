# src/cadence/dev/phase_guard.py
"""cadence.dev.phase_guard

Runtime enforcement of Cadence workflow-phase ordering.

A lightweight decorator (enforce_phase) raises PhaseOrderError
whenever a caller tries to execute a phase whose required predecessors
have not yet been completed for the current task.  The decorator is
generic: any object that exposes

· self._current_task   – dict with an “id” key
· self._has_phase(id, phase) -> bool
· self._mark_phase(id, phase)
can use it.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Tuple

class PhaseOrderError(RuntimeError):
    """Raised when workflow phases are executed out of order."""

def enforce_phase(
    *required_phases: str,
    mark: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorate a method representing a phase transition.

    Parameters
    ----------
    *required_phases :
        Zero or more phase labels that **must already be complete**
        for the current task before the wrapped method may run.

    mark :
        Optional phase label to record as *completed* automatically
        **after** the wrapped method returns without raising.

    Notes
    -----
    If the decorated object is used outside an agentic task context
    (`self._current_task is None`) the decorator becomes a no-op.
    """

    req: Tuple[str, ...] = tuple(required_phases)

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def _wrapper(self, *args, **kwargs):
            task = getattr(self, "_current_task", None)
            if task and req:
                tid = task.get("id")
                missing = [p for p in req if not self._has_phase(tid, p)]
                if missing:
                    raise PhaseOrderError(
                        f"{func.__name__} cannot run – unmet phase(s): "
                        f"{', '.join(missing)}"
                    )
            # --- execute wrapped method -----------------------------------
            result = func(self, *args, **kwargs)

            # --- auto-mark completion ------------------------------------
            if task and mark:
                self._mark_phase(task["id"], mark)
            return result

        return _wrapper

    return _decorator