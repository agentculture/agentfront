"""MCP surface for agentfront — expose an App's tools as MCP tools.

Builds an :class:`mcp.server.Server` from an :class:`App`'s registry so the
host writes zero MCP-protocol code.  The single entry point is
``make_mcp_server(app)``.
"""

from __future__ import annotations

import inspect
from typing import Any

from mcp import Tool
from mcp.server import Server

from agentfront.app import App

__all__ = ["make_mcp_server", "serve_stdio"]


def make_mcp_server(app: App) -> Server:
    """Return an MCP :class:`Server` exposing every registered tool.

    Each :class:`ToolEntry` becomes one MCP tool with matching name,
    description, and inputSchema.  Invoking a tool calls
    ``ToolEntry.func`` with the provided arguments and returns its
    result.
    """
    server = Server(app.name)

    # --- list_tools ------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=entry.name,
                description=entry.description,
                inputSchema=entry.input_schema,
            )
            for entry in app.list_tools()
        ]

    # --- call_tool --------------------------------------------------------

    @server.call_tool(validate_input=False)
    async def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        entry = app.get_tool(tool_name)
        if entry is None:
            raise ValueError(f"unknown tool: {tool_name!r}")
        result = entry.func(**arguments)
        # A host may register an ``async def`` tool; calling it returns a
        # coroutine that must be awaited before it can be serialized back to
        # the MCP client. Sync tools return their value directly.
        if inspect.isawaitable(result):
            result = await result
        return {"result": result}

    return server


def serve_stdio(app: App) -> None:
    """Run the MCP server over stdio (blocking).

    Convenience helper so the host can start the server with::

        from agentfront.mcp_surface import serve_stdio

        serve_stdio(app)
    """
    import anyio
    from mcp.server.stdio import stdio_server

    server = make_mcp_server(app)

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    anyio.run(_run)
