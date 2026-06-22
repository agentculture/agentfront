"""Unit tests for agentfront.mcp_surface — the MCP surface (t1).

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


def test_list_tools_yields_registered_names(app: App):
    server = make_mcp_server(app)
    tools = anyio.run(_list_tools, server)
    names = [t.name for t in tools]
    assert names == ["add", "greet"]


def test_list_tools_includes_description_and_schema(app: App):
    server = make_mcp_server(app)
    tools = anyio.run(_list_tools, server)
    by_name = {t.name: t for t in tools}

    add_tool = by_name["add"]
    assert add_tool.description == "Add two numbers."
    assert add_tool.inputSchema["type"] == "object"
    assert "x" in add_tool.inputSchema["properties"]
    assert "y" in add_tool.inputSchema["properties"]

    greet_tool = by_name["greet"]
    assert greet_tool.description == "Say hello"
    assert "name" in greet_tool.inputSchema["properties"]


# --- calling tools -------------------------------------------------------


def test_call_tool_routes_to_func(app: App):
    server = make_mcp_server(app)
    result = anyio.run(_call_tool, server, "add", {"x": 3, "y": 4})
    assert result == 7


def test_call_tool_string_result(app: App):
    server = make_mcp_server(app)
    result = anyio.run(_call_tool, server, "greet", {"name": "world"})
    assert result == "hello world"


# --- schema from typed signature ----------------------------------------


def test_typed_signature_surfaces_schema():
    a = App(name="typed")

    @a.tool
    def search(query: str, limit: int = 10) -> str:
        """Search things."""
        return query

    server = make_mcp_server(a)
    tools = anyio.run(_list_tools, server)
    assert len(tools) == 1
    schema = tools[0].inputSchema
    assert schema["type"] == "object"
    assert schema["properties"]["query"]["type"] == "string"
    assert schema["properties"]["limit"]["type"] == "integer"
    # "query" is required (no default), "limit" is not
    assert "query" in schema["required"]
    assert "limit" not in schema["required"]


# --- empty app ----------------------------------------------------------


def test_empty_app_has_no_tools():
    a = App(name="empty")
    server = make_mcp_server(a)
    tools = anyio.run(_list_tools, server)
    assert tools == []


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
    """Invoke the call_tool handler and extract the raw return value."""
    from mcp import types

    req = types.CallToolRequest(
        params=types.CallToolRequestParams(name=tool_name, arguments=arguments)
    )
    handler = server.request_handlers.get(types.CallToolRequest)
    assert handler is not None, "call_tool handler not registered"
    result = await handler(req)
    call_result = result.root
    # The server returns {"result": <func_return>} as structuredContent
    if call_result.structuredContent is not None:
        return call_result.structuredContent["result"]
    # Fallback: parse from text content
    for content in call_result.content:
        if hasattr(content, "text"):
            import json

            return json.loads(content.text)["result"]
    return call_result
