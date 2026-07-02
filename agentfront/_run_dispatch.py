"""Shared 'run' dispatch helpers — the single source of the MCP payload shape.

Both :mod:`agentfront.mcp_surface` (the real ``mcp`` server's ``run`` tool)
and :mod:`agentfront.testing.mcp` (the in-process, ``mcp``-free harness) build
their ``{"result": value}`` / ``{"error": {...}}`` payloads from these three
helpers, so the two paths can never drift apart. This module is stdlib only —
no ``argparse``, no ``mcp`` import — so it stays importable without the
optional ``agentfront[mcp]`` extra.

Extracted verbatim from the validation + payload-building body that used to
live inline in ``mcp_surface.call_tool``.
"""

from __future__ import annotations

from typing import Any

from agentfront._registry import ToolEntry
from agentfront.app import App
from agentfront.errors import AgentfrontError

__all__ = ["validate_and_lookup", "result_payload", "error_payload"]


def validate_and_lookup(app: App, command: Any) -> ToolEntry | dict[str, Any]:
    """Validate *command* and resolve it to a :class:`ToolEntry` on *app*.

    Returns the matching entry on success, or the exact ``{"error": ...}``
    payload the MCP surface has always emitted for a non-list ``command``, a
    ``command`` with non-string items, or an unknown command path.
    """
    if not isinstance(command, list):
        return {
            "error": {
                "code": 1,
                "message": "'command' must be an array of strings",
                "remediation": "pass command as ['noun', 'verb']",
            }
        }

    if not all(isinstance(x, str) for x in command):
        return {
            "error": {
                "code": 1,
                "message": "'command' items must be strings",
                "remediation": "pass command as ['noun', 'verb']",
            }
        }

    path = tuple(command)
    entry = app.get_by_path(path)
    if entry is None:
        return {
            "error": {
                "code": 1,
                "message": f"unknown command: {' '.join(command)}",
                "remediation": "check available commands in the 'run' tool description",
            }
        }

    return entry


def result_payload(value: Any) -> dict[str, Any]:
    """Wrap a successful tool return value in the canonical ``{"result": ...}`` shape."""
    return {"result": value}


def error_payload(exc: Exception) -> dict[str, Any]:
    """Wrap a raised exception in the canonical ``{"error": {...}}`` shape.

    An :class:`AgentfrontError` maps via its own ``.to_dict()`` (its
    structured ``code``/``message``/``remediation``); any other exception
    maps to the generic ``code=1`` shape carrying its class name and message.
    """
    if isinstance(exc, AgentfrontError):
        return {"error": exc.to_dict()}
    return {
        "error": {
            "code": 1,
            "message": f"{type(exc).__name__}: {exc}",
            "remediation": "check command arguments",
        }
    }
