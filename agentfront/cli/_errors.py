"""Re-export of :mod:`agentfront.errors` for backward compatibility.

All definitions live in :mod:`agentfront.errors`; this module exists so
existing ``from agentfront.cli._errors import ...`` import paths continue
to work.
"""

from __future__ import annotations

from agentfront.errors import (
    AgentfrontError,
    EXIT_ENV_ERROR,
    EXIT_SUCCESS,
    EXIT_USER_ERROR,
)

__all__ = [
    "AgentfrontError",
    "EXIT_ENV_ERROR",
    "EXIT_SUCCESS",
    "EXIT_USER_ERROR",
]
