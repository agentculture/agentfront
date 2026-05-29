"""Fix registry for ``agentfront doctor --fix``.

A fix is a callable keyed by ``fix_id``. When a :class:`CheckResult` flags
itself as ``auto_fixable=True`` and carries a ``fix_id``, ``--fix`` looks
the id up here and invokes the handler. Handlers return a
:class:`FixOutcome` describing what they did; the caller re-runs the
originating check to confirm the fix landed.

v0.5 ships with the registry skeleton and no initial handlers — every
rubric and self-check today emits *explain how to fix* remediations
because the safe auto-fixes (e.g., re-citing a stale ``.agentfront/reference/``
tree on a target) live next to ``agentfront cli cite``, not next to the rubric.
The registry is here so a follow-up can wire fixes without changing the
doctor verb's contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agentfront.rubric._types import VerifyContext

__all__ = ["FixOutcome", "apply_fix", "is_registered", "register_fix"]


@dataclass(frozen=True)
class FixOutcome:
    """Result of applying a fix handler."""

    fix_id: str
    applied: bool
    message: str


_FIX_HANDLERS: dict[str, Callable[[VerifyContext], FixOutcome]] = {}


def register_fix(
    fix_id: str,
) -> Callable[[Callable[[VerifyContext], FixOutcome]], Callable[[VerifyContext], FixOutcome]]:
    """Decorator that registers a fix handler under ``fix_id``."""

    def decorator(
        func: Callable[[VerifyContext], FixOutcome],
    ) -> Callable[[VerifyContext], FixOutcome]:
        if fix_id in _FIX_HANDLERS:
            raise ValueError(f"fix_id already registered: {fix_id}")
        _FIX_HANDLERS[fix_id] = func
        return func

    return decorator


def is_registered(fix_id: str) -> bool:
    return fix_id in _FIX_HANDLERS


def apply_fix(fix_id: str, ctx: VerifyContext) -> FixOutcome:
    """Apply the handler registered for ``fix_id``.

    Returns ``FixOutcome(applied=False, ...)`` when no handler is
    registered. Callers (the ``--fix`` driver) decide what to do with that
    — usually report it and continue.
    """
    handler = _FIX_HANDLERS.get(fix_id)
    if handler is None:
        return FixOutcome(
            fix_id=fix_id,
            applied=False,
            message=f"no auto-fix registered for '{fix_id}'",
        )
    return handler(ctx)
