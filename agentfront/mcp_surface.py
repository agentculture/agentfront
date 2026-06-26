"""MCP surface for agentfront — single-dispatch 'CLI on MCP' tool.

Builds an :class:`mcp.server.Server` from an :class:`App`'s registry so the
host writes zero MCP-protocol code.  The single entry point is
``make_mcp_server(app)``.

The server registers exactly **one** MCP tool (``run``) whose inputSchema
accepts ``{'command': [...], 'args': {...}}``.  The tool's description embeds
the full command catalog derived from ``app.list_tools()``, so an agent can
discover all available commands from the single tool listing.
"""

from __future__ import annotations

import inspect
import json
from typing import Any

from mcp import Tool
from mcp.server import Server

from agentfront.app import App

__all__ = ["make_mcp_server", "serve_stdio"]


def _build_catalog(app: App) -> list[dict[str, Any]]:
    """Build the command catalog from the registry."""
    catalog: list[dict[str, Any]] = []
    for entry in app.list_tools():
        path = list(entry.group) + [entry.name]
        catalog.append(
            {
                "path": path,
                "description": entry.description,
                "inputSchema": entry.input_schema,
            }
        )
    return catalog


def _build_run_tool(app: App) -> Tool:
    """Build the single 'run' MCP tool with embedded catalog."""
    catalog = _build_catalog(app)
    catalog_text = json.dumps(catalog, indent=2)

    description = (
        "Execute a registered command. "
        "Pass 'command' as an array of path components (e.g. ['search'] or "
        "['feedback', 'record']) and 'args' as a dict of named arguments. "
        "Available commands:\n" + catalog_text
    )

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Command path (e.g. ['search'] or ['feedback', 'record'])",
            },
            "args": {
                "type": "object",
                "description": "Named arguments for the command",
            },
        },
        "required": ["command", "args"],
    }

    return Tool(name="run", description=description, inputSchema=input_schema)


def make_mcp_server(app: App) -> Server:
    """Return an MCP :class:`Server` exposing a single ``run`` tool.

    The ``run`` tool accepts ``{'command': [...], 'args': {...}}`` and
    dispatches to the matching registered tool via ``app.get_by_path``.
    The tool's description embeds the full command catalog.
    """
    server = Server(app.name)

    # --- list_tools -------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [_build_run_tool(app)]

    # --- call_tool --------------------------------------------------------

    @server.call_tool(validate_input=False)
    async def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name != "run":
            return {
                "error": {
                    "code": 1,
                    "message": f"unknown tool: {tool_name!r}",
                    "remediation": "use the 'run' tool",
                }
            }

        command = arguments.get("command", [])
        args = arguments.get("args", {})

        if not isinstance(command, list):
            return {
                "error": {
                    "code": 1,
                    "message": "'command' must be an array of strings",
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

        try:
            result = entry.func(**args)
            if inspect.isawaitable(result):
                result = await result
            return {"result": result}
        except Exception as exc:
            return {
                "error": {
                    "code": 1,
                    "message": f"{exc.__class__.__name__}: {exc}",
                    "remediation": "check command arguments",
                }
            }

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
