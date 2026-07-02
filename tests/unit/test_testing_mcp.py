"""Tests for ``agentfront.testing.mcp`` — the in-process MCP dispatch harness (t7).

``call_mcp`` builds the exact MCP payload shape (``{"result": ...}`` XOR
``{"error": {...}}``) without importing the ``mcp`` package or standing up a
server, so a consumer's test suite can assert on tool behavior without
installing the optional ``agentfront[mcp]`` extra. A guarded cross-check test
asserts byte-identical parity with the real MCP surface when ``mcp`` is
installed.
"""

from __future__ import annotations

import pytest

from agentfront import App
from agentfront.errors import AgentfrontError
from agentfront.testing import call_mcp

# --- fixtures ----------------------------------------------------------------


@pytest.fixture
def app() -> App:
    a = App(name="test-app", version="0.1.0")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    @a.tool
    def boom(message: str) -> None:
        """Always raise a structured AgentfrontError."""
        raise AgentfrontError(code=3, message=message, remediation="fix your input")

    @a.tool
    def explode() -> None:
        """Always raise a generic exception."""
        raise ValueError("kaboom")

    @a.tool
    async def fetch(url: str) -> str:
        """Pretend to fetch a URL (async tool)."""
        return f"fetched {url}"

    @a.tool(group="feedback")
    def record(text: str) -> str:
        """Record feedback."""
        return text

    return a


# --- success -------------------------------------------------------------


def test_call_mcp_success_returns_result_payload(app: App) -> None:
    result = call_mcp(app, ["add"], {"x": 3, "y": 4})
    assert result == {"result": 7}


def test_call_mcp_success_grouped_command(app: App) -> None:
    result = call_mcp(app, ["feedback", "record"], {"text": "hi"})
    assert result == {"result": "hi"}


def test_call_mcp_args_defaults_to_empty_dict_when_omitted() -> None:
    a = App(name="t")

    @a.tool
    def ping() -> str:
        """Ping."""
        return "pong"

    result = call_mcp(a, ["ping"])
    assert result == {"result": "pong"}


# --- AgentfrontError maps via .to_dict() ----------------------------------


def test_call_mcp_agentfront_error_maps_to_its_to_dict(app: App) -> None:
    result = call_mcp(app, ["boom"], {"message": "bad input"})
    assert result == {
        "error": {
            "code": 3,
            "message": "bad input",
            "remediation": "fix your input",
        }
    }


# --- generic exception -----------------------------------------------------


def test_call_mcp_generic_exception_returns_generic_shape(app: App) -> None:
    result = call_mcp(app, ["explode"], {})
    assert result == {
        "error": {
            "code": 1,
            "message": "ValueError: kaboom",
            "remediation": "check command arguments",
        }
    }


# --- malformed / unknown command (byte-identical to mcp_surface today) -----


def test_call_mcp_command_not_a_list_returns_error(app: App) -> None:
    result = call_mcp(app, "add", {})  # type: ignore[arg-type]
    assert result == {
        "error": {
            "code": 1,
            "message": "'command' must be an array of strings",
            "remediation": "pass command as ['noun', 'verb']",
        }
    }


def test_call_mcp_command_items_must_be_strings(app: App) -> None:
    result = call_mcp(app, [123], {})  # type: ignore[list-item]
    assert result == {
        "error": {
            "code": 1,
            "message": "'command' items must be strings",
            "remediation": "pass command as ['noun', 'verb']",
        }
    }


def test_call_mcp_unknown_command_returns_error(app: App) -> None:
    result = call_mcp(app, ["nonexistent"], {})
    assert result == {
        "error": {
            "code": 1,
            "message": "unknown command: nonexistent",
            "remediation": "check available commands in the 'run' tool description",
        }
    }


def test_call_mcp_unknown_grouped_command_message_joins_path(app: App) -> None:
    result = call_mcp(app, ["feedback", "delete"], {})
    assert result["error"]["message"] == "unknown command: feedback delete"


# --- async tool function ----------------------------------------------------


def test_call_mcp_awaits_async_tool_function(app: App) -> None:
    result = call_mcp(app, ["fetch"], {"url": "x"})
    assert result == {"result": "fetched x"}


# --- cross-check parity with the real MCP surface ---------------------------


def test_call_mcp_matches_mcp_surface_for_success(app: App) -> None:
    pytest.importorskip("mcp")
    import anyio

    from agentfront.mcp_surface import make_mcp_server

    server = make_mcp_server(app)
    mcp_payload = anyio.run(_call_run, server, {"command": ["add"], "args": {"x": 3, "y": 4}})
    assert mcp_payload == call_mcp(app, ["add"], {"x": 3, "y": 4})


def test_call_mcp_matches_mcp_surface_for_agentfront_error(app: App) -> None:
    pytest.importorskip("mcp")
    import anyio

    from agentfront.mcp_surface import make_mcp_server

    server = make_mcp_server(app)
    mcp_payload = anyio.run(
        _call_run, server, {"command": ["boom"], "args": {"message": "bad input"}}
    )
    assert mcp_payload == call_mcp(app, ["boom"], {"message": "bad input"})
    # And: the parity fix actually applies (.to_dict(), not the generic shape).
    assert mcp_payload == {
        "error": {"code": 3, "message": "bad input", "remediation": "fix your input"}
    }


def test_call_mcp_matches_mcp_surface_for_generic_exception(app: App) -> None:
    pytest.importorskip("mcp")
    import anyio

    from agentfront.mcp_surface import make_mcp_server

    server = make_mcp_server(app)
    mcp_payload = anyio.run(_call_run, server, {"command": ["explode"], "args": {}})
    assert mcp_payload == call_mcp(app, ["explode"], {})


# --- helpers -----------------------------------------------------------------


async def _call_run(server, arguments: dict) -> dict:
    """Invoke the 'run' call_tool handler, returning the raw payload dict.

    Unlike ``tests/unit/test_mcp_surface.py``'s ``_call_tool`` (which unwraps
    ``{"result": value}`` down to the bare value for convenience), this keeps
    the full ``{"result": ...}`` / ``{"error": ...}`` envelope so it can be
    compared directly against ``call_mcp``'s return value.
    """
    from mcp import types

    req = types.CallToolRequest(params=types.CallToolRequestParams(name="run", arguments=arguments))
    handler = server.request_handlers.get(types.CallToolRequest)
    assert handler is not None, "call_tool handler not registered"
    result = await handler(req)
    call_result = result.root
    if call_result.structuredContent is not None:
        return call_result.structuredContent
    for content in call_result.content:
        if hasattr(content, "text"):
            import json

            return json.loads(content.text)
    raise AssertionError("call result had neither structuredContent nor text content")
