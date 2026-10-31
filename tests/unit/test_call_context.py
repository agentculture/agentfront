"""Unit tests for agentfront.context — the per-call caller principal (issue #52).

The remote MCP transport's authenticator returns a caller principal; command
handlers read it back through :func:`agentfront.current_caller`. These tests
pin the stdlib-only half of that contract: the default (no caller), the
scoping context manager, and the in-process ``call_mcp(..., caller=...)``
harness hook so consumers can unit-test per-caller scoping without a server.
"""

from __future__ import annotations

import asyncio

import pytest

from agentfront import AgentfrontError, App, current_caller
from agentfront.context import caller_context
from agentfront.testing import call_mcp


def test_no_caller_by_default():
    assert current_caller() is None


def test_caller_context_sets_and_restores():
    with caller_context("agent-a"):
        assert current_caller() == "agent-a"
        with caller_context("agent-b"):
            assert current_caller() == "agent-b"
        assert current_caller() == "agent-a"
    assert current_caller() is None


def test_caller_context_restores_on_exception():
    try:
        with caller_context("agent-a"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert current_caller() is None


def test_caller_visible_inside_async_handler():
    async def read() -> object:
        return current_caller()

    with caller_context({"sub": "agent-a"}):
        assert asyncio.run(read()) == {"sub": "agent-a"}


def _scoped_app() -> App:
    app = App(name="scoped", version="0.1.0")

    @app.tool
    def whoami() -> object:
        """Return the caller principal."""
        return current_caller()

    @app.tool
    def admin_only() -> str:
        """Refuse anyone but the admin principal."""
        if current_caller() != "admin":
            raise AgentfrontError(
                code=403, message="forbidden for this caller", remediation="ask an admin"
            )
        return "ok"

    return app


def test_call_mcp_without_caller_sees_none():
    assert call_mcp(_scoped_app(), ["whoami"]) == {"result": None}


def test_call_mcp_passes_caller_through():
    app = _scoped_app()
    assert call_mcp(app, ["whoami"], caller="agent-a") == {"result": "agent-a"}
    assert call_mcp(app, ["admin_only"], caller="admin") == {"result": "ok"}
    assert call_mcp(app, ["admin_only"], caller="agent-a") == {
        "error": {
            "code": 403,
            "message": "forbidden for this caller",
            "remediation": "ask an admin",
        }
    }
    # The caller does not leak past the call.
    assert current_caller() is None


def test_stdio_style_dispatch_has_no_caller():
    """The real MCP server's run tool (stdio path, no HTTP request) sees no caller."""
    pytest.importorskip("mcp")
    import anyio
    from mcp import types

    from agentfront.mcp_surface import make_mcp_server

    server = make_mcp_server(_scoped_app())
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        params=types.CallToolRequestParams(
            name="run", arguments={"command": ["whoami"], "args": {}}
        )
    )
    result = anyio.run(handler, req)
    assert result.root.structuredContent == {"result": None}
