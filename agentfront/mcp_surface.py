"""MCP surface for agentfront — single-dispatch 'CLI on MCP' tool.

Builds an :class:`mcp.server.Server` from an :class:`App`'s registry so the
host writes zero MCP-protocol code.  The single entry point is
``make_mcp_server(app)``.

The server registers exactly **one** MCP tool (``run``) whose inputSchema
accepts ``{'command': [...], 'args': {...}}``.  The tool's description embeds
the full command catalog derived from ``app.list_tools()``, so an agent can
discover all available commands from the single tool listing.

The server returned by ``make_mcp_server`` (and ``app.mcp_server()``) exposes
that one tool as a public ``run_tool`` attribute, so a consumer can inspect or
round-trip it without importing a private helper.
"""

from __future__ import annotations

import inspect
import json
from typing import Any

from mcp import Tool, types
from mcp.server import Server

from agentfront._run_dispatch import error_payload, result_payload, validate_and_lookup
from agentfront.app import App
from agentfront.context import caller_context

__all__ = ["make_mcp_server", "serve_stdio"]

# ASGI scope key under which the remote transport (agentfront.mcp_http) stores
# the authenticator's caller principal. The MCP SDK hands the originating
# HTTP request to the server's request context, so ``call_tool`` reads the
# principal back from that request's scope — per request, independent of which
# task the session's server loop happens to run in.
CALLER_SCOPE_KEY = "agentfront.caller"


def _request_caller(server: Server) -> Any:
    """The caller principal of the MCP request being handled, or ``None``.

    ``None`` on stdio (no HTTP request behind the message) and when the
    handler is invoked outside a live request context (direct handler calls).
    """
    try:
        request = server.request_context.request
    except LookupError:
        return None
    scope = getattr(request, "scope", None)
    if not isinstance(scope, dict):
        return None
    return scope.get(CALLER_SCOPE_KEY)


def _call_result(payload: dict[str, Any], *, is_error: bool) -> types.CallToolResult:
    """Wrap a ``run`` payload in a :class:`~mcp.types.CallToolResult`.

    Content matches what the SDK builds for a plain dict return (indented JSON
    text plus ``structuredContent``), so the wire payload is identical; only
    ``isError`` differs. The MCP spec reports tool-execution errors with
    ``isError: true`` so clients and models can tell failure from success.
    """
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))],
        structuredContent=payload,
        isError=is_error,
    )


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

    The returned server carries a public ``run_tool`` attribute — the
    :class:`mcp.Tool` the server lists — so a consumer can introspect its
    ``name`` and ``inputSchema``, or drive a ``{command, args}`` round-trip in a
    test, through a supported API rather than the private ``_build_run_tool``::

        server = app.mcp_server()
        server.run_tool.name                      # 'run'
        server.run_tool.inputSchema["required"]   # ['command', 'args']
    """
    server = Server(app.name)

    # The single ``run`` tool, exposed as a public ``server.run_tool`` attribute
    # so a consumer can introspect/round-trip it (its name + inputSchema) without
    # importing the private ``_build_run_tool``. It is (re)built from the *live*
    # registry — seeded here for pre-listing introspection and refreshed on every
    # ``list_tools`` — so the embedded command catalog never goes stale and
    # ``server.run_tool`` always matches what the server most recently listed.
    server.run_tool = _build_run_tool(app)

    # --- list_tools -------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        server.run_tool = _build_run_tool(app)
        return [server.run_tool]

    # --- call_tool --------------------------------------------------------

    @server.call_tool(validate_input=False)
    async def call_tool(tool_name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if tool_name != "run":
            return _call_result(
                {
                    "error": {
                        "code": 1,
                        "message": f"unknown tool: {tool_name!r}",
                        "remediation": "use the 'run' tool",
                    }
                },
                is_error=True,
            )

        command = arguments.get("command", [])
        args = arguments.get("args", {})
        if args is None:
            # An explicit JSON null means "no args" — normalize exactly like
            # agentfront.testing.call_mcp so the surfaces stay payload-identical.
            args = {}

        entry_or_error = validate_and_lookup(app, command)
        if isinstance(entry_or_error, dict):
            return _call_result(entry_or_error, is_error=True)
        entry = entry_or_error

        try:
            with caller_context(_request_caller(server)):
                result = entry.func(**args)
                if inspect.isawaitable(result):
                    result = await result
            return _call_result(result_payload(result), is_error=False)
        except Exception as exc:
            return _call_result(error_payload(exc), is_error=True)

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
