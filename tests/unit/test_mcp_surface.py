"""Unit tests for agentfront.mcp_surface — single-dispatch MCP tool (t1).

Drive ``make_mcp_server`` via the SDK's in-memory client/session so no
subprocess is needed.
"""

from __future__ import annotations

import anyio
import pytest

from agentfront import App
from agentfront.mcp_surface import make_mcp_server


@pytest.fixture
def app() -> App:
    a = App(name="test-app", version="0.1.0")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    @a.tool(name="greet", description="Say hello")
    def say_hello(name: str) -> str:
        return f"hello {name}"

    return a


# --- listing tools -------------------------------------------------------


def test_list_tools_yields_single_run_tool(app: App):
    server = make_mcp_server(app)
    tools = anyio.run(_list_tools, server)
    assert len(tools) == 1
    assert tools[0].name == "run"


def test_run_tool_description_embeds_catalog(app: App):
    server = make_mcp_server(app)
    tools = anyio.run(_list_tools, server)
    tool = tools[0]
    assert tool.name == "run"
    # The description must contain the catalog with command paths
    assert "add" in tool.description
    assert "greet" in tool.description
    # Verify the catalog is valid JSON embedded in the description
    import json

    # Extract the JSON catalog from the description (after "Available commands:")
    desc = tool.description
    marker = "Available commands:\n"
    catalog_start = desc.index(marker) + len(marker)
    catalog_text = desc[catalog_start:]
    catalog = json.loads(catalog_text)
    assert isinstance(catalog, list)
    paths = {tuple(c["path"]) for c in catalog}
    assert ("add",) in paths
    assert ("greet",) in paths


def test_run_tool_input_schema_has_command_and_args(app: App):
    server = make_mcp_server(app)
    tools = anyio.run(_list_tools, server)
    schema = tools[0].inputSchema
    assert schema["type"] == "object"
    assert "command" in schema["properties"]
    assert "args" in schema["properties"]
    assert schema["properties"]["command"]["type"] == "array"
    assert schema["properties"]["args"]["type"] == "object"
    assert "command" in schema["required"]
    assert "args" in schema["required"]


# --- calling tools -------------------------------------------------------


def test_call_run_dispatches_by_command_path(app: App):
    server = make_mcp_server(app)
    result = anyio.run(_call_tool, server, "run", {"command": ["add"], "args": {"x": 3, "y": 4}})
    assert result == 7


def test_call_run_string_result(app: App):
    server = make_mcp_server(app)
    result = anyio.run(_call_tool, server, "run", {"command": ["greet"], "args": {"name": "world"}})
    assert result == "hello world"


def test_call_run_unknown_command_returns_error():
    a = App(name="t")

    @a.tool
    def search(query: str) -> str:
        """Search."""
        return query

    server = make_mcp_server(a)
    result = anyio.run(_call_tool, server, "run", {"command": ["nonexistent"], "args": {}})
    assert "error" in result
    err = result["error"]
    assert "code" in err
    assert "message" in err
    assert "remediation" in err
    assert "nonexistent" in err["message"]


def test_call_run_bad_args_returns_error():
    a = App(name="t")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add."""
        return x + y

    server = make_mcp_server(a)
    # Missing required args
    result = anyio.run(_call_tool, server, "run", {"command": ["add"], "args": {}})
    assert "error" in result


def test_call_run_awaits_async_func():
    """An ``async def`` tool is awaited, not returned as a raw coroutine."""
    a = App(name="async-app")

    @a.tool
    async def fetch(url: str) -> str:
        """Pretend to fetch a URL."""
        return f"fetched {url}"

    server = make_mcp_server(a)
    result = anyio.run(_call_tool, server, "run", {"command": ["fetch"], "args": {"url": "x"}})
    assert result == "fetched x"


def test_call_run_command_items_must_be_strings():
    """Non-string command items return a structured error, not a TypeError."""
    a = App(name="t")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add."""
        return x + y

    server = make_mcp_server(a)
    result = anyio.run(_call_tool, server, "run", {"command": [123], "args": {}})
    assert "error" in result
    err = result["error"]
    assert "code" in err
    assert "message" in err
    assert "remediation" in err


def test_call_run_unknown_tool_name_returns_error():
    a = App(name="t")
    server = make_mcp_server(a)
    result = anyio.run(_call_tool, server, "not-run", {})
    assert "error" in result
    err = result["error"]
    assert "not-run" in err["message"]


# --- grouped tools -------------------------------------------------------


def test_grouped_tool_dispatch():
    a = App(name="grouped")

    @a.tool(group="feedback")
    def record(text: str) -> str:
        """Record feedback."""
        return text

    server = make_mcp_server(a)
    result = anyio.run(
        _call_tool, server, "run", {"command": ["feedback", "record"], "args": {"text": "hello"}}
    )
    assert result == "hello"


def test_grouped_tool_in_catalog():
    a = App(name="grouped")

    @a.tool(group="feedback")
    def record(text: str) -> str:
        """Record feedback."""
        return text

    server = make_mcp_server(a)
    tools = anyio.run(_list_tools, server)
    import json

    desc = tools[0].description
    marker = "Available commands:\n"
    catalog_text = desc[desc.index(marker) + len(marker) :]
    catalog = json.loads(catalog_text)
    paths = {tuple(c["path"]) for c in catalog}
    assert ("feedback", "record") in paths


# --- empty app ----------------------------------------------------------


def test_empty_app_has_one_tool():
    a = App(name="empty")
    server = make_mcp_server(a)
    tools = anyio.run(_list_tools, server)
    assert len(tools) == 1
    assert tools[0].name == "run"


# --- optional mcp extra --------------------------------------------------


def test_mcp_server_without_mcp_extra_raises_friendly_error(monkeypatch):
    """``app.mcp_server()`` names the optional extra when mcp isn't installed.

    The MCP SDK is an optional extra (``agentfront[mcp]``); the CLI and HTTP
    surfaces don't need it. We simulate the missing install by evicting ``mcp``
    from ``sys.modules`` (so the lazy ``from mcp import ...`` re-runs and fails)
    and dropping the cached surface module so the import is actually retried.
    """
    import sys

    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.delitem(sys.modules, "agentfront.mcp_surface", raising=False)

    app = App(name="t")
    with pytest.raises(ModuleNotFoundError, match=r"agentfront\[mcp\]"):
        app.mcp_server()


# --- helpers ----------------------------------------------------------------


async def _list_tools(server) -> list:
    """Invoke the list_tools request handler registered on *server*."""
    from mcp import types

    req = types.ListToolsRequest(params=types.PaginatedRequestParams(cursor=None))
    handler = server.request_handlers.get(types.ListToolsRequest)
    assert handler is not None, "list_tools handler not registered"
    result = await handler(req)
    return result.root.tools


async def _call_tool(server, tool_name: str, arguments: dict) -> object:
    """Invoke the call_tool handler and extract the raw return value.

    Returns the unwrapped result (the actual function return value) on success,
    or the full structuredContent dict (which contains 'error' key) on failure.
    """
    from mcp import types

    req = types.CallToolRequest(
        params=types.CallToolRequestParams(name=tool_name, arguments=arguments)
    )
    handler = server.request_handlers.get(types.CallToolRequest)
    assert handler is not None, "call_tool handler not registered"
    result = await handler(req)
    call_result = result.root
    if call_result.structuredContent is not None:
        sc = call_result.structuredContent
        # Unwrap {"result": value} to just value; pass through {"error": ...}
        if "result" in sc:
            return sc["result"]
        return sc
    # Fallback: parse from text content
    for content in call_result.content:
        if hasattr(content, "text"):
            import json

            parsed = json.loads(content.text)
            if "result" in parsed:
                return parsed["result"]
            return parsed
    return call_result
