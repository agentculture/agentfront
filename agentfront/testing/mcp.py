"""In-process MCP dispatch harness — the ``run`` tool payload without a server.

``call_mcp`` builds the exact MCP payload shape (``{"result": ...}`` XOR
``{"error": {...}}``) using the same shared helpers
:mod:`agentfront.mcp_surface` builds from (:mod:`agentfront._run_dispatch`),
but dispatches synchronously and in-process — no ``mcp`` package import, no
server construction — so a consumer's test suite can assert on tool behavior
without installing the optional ``agentfront[mcp]`` extra.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Optional

from agentfront._run_dispatch import error_payload, result_payload, validate_and_lookup
from agentfront.app import App

__all__ = ["call_mcp"]


def call_mcp(app: App, command: list[str], args: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Dispatch *command* against *app*'s registry, returning the MCP payload shape.

    Mirrors ``agentfront.mcp_surface``'s ``run`` tool dispatch exactly — same
    validation, same success/error payload shapes — but runs synchronously
    in-process: no ``mcp`` package import, no server round trip. Awaitable
    tool functions are resolved via ``asyncio.run``. Any exception the tool
    raises (including :class:`agentfront.errors.AgentfrontError`) is caught
    and mapped to the canonical error payload — never propagated.

    Because ``asyncio.run`` cannot be called from inside a running event
    loop, calling ``call_mcp`` on an ASYNC tool from an async test maps that
    ``RuntimeError`` into the error payload instead of executing the tool —
    call it from sync code when the tool is async.
    """
    if args is None:
        args = {}

    entry_or_error = validate_and_lookup(app, command)
    if isinstance(entry_or_error, dict):
        return entry_or_error
    entry = entry_or_error

    try:
        result = entry.func(**args)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        return result_payload(result)
    # dispatch boundary — exception mapped to a payload, not re-raised
    except Exception as exc:  # noqa: BLE001
        return error_payload(exc)
