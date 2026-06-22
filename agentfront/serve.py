"""Assemble all three agent-first surfaces from one App — and prove they agree.

The point of the single registry is that the CLI, MCP, and HTTP surfaces cannot
present *different* sets of docs/tools. This module both builds the three
surfaces from one :class:`App` and provides the cross-surface **agreement
check** that turns that promise into something testable: it queries each surface
independently (the HTTP sitemap, the CLI ``learn --json`` listing, the MCP
``list_tools`` handler) and confirms they enumerate the same set the registry
holds.
"""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET  # noqa: S405 - parsing our own generated sitemap
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any

from agentfront.app import App

__all__ = ["Surfaces", "build_surfaces", "surface_inventory", "surfaces_agree"]


@dataclass(frozen=True)
class Surfaces:
    """The three surfaces built from one App."""

    http: Any  # a WSGI application callable
    mcp: Any  # an mcp.server.Server
    cli: Any  # an argparse.ArgumentParser


def build_surfaces(app: App) -> Surfaces:
    """Build all three surfaces from a single App."""
    return Surfaces(http=app.http_app(), mcp=app.mcp_server(), cli=app.cli())


def _http_doc_slugs(app: App) -> set[str]:
    """The doc slugs the HTTP surface actually advertises in its sitemap."""
    wsgi = app.http_app()
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/sitemap.xml"}
    body = b"".join(wsgi(environ, lambda status, headers: None))
    root = ET.fromstring(body)  # noqa: S314 - our own sitemap, not untrusted input
    return {(el.text or "").lstrip("/") for el in root.iter("loc")}


def _cli_inventory(app: App) -> tuple[set[str], set[str]]:
    """The (doc slugs, tool names) the CLI ``learn`` surface reports."""
    from agentfront.cli_surface import run_cli

    buf = io.StringIO()
    with redirect_stdout(buf):
        run_cli(app, ["learn", "--json"])
    payload = json.loads(buf.getvalue())
    return (
        {d["slug"] for d in payload["docs"]},
        {t["name"] for t in payload["tools"]},
    )


def _mcp_tool_names(app: App) -> set[str]:
    """The tool names the MCP surface actually lists."""
    import anyio
    from mcp import types

    server = app.mcp_server()

    async def _list() -> set[str]:
        handler = server.request_handlers[types.ListToolsRequest]
        request = types.ListToolsRequest(
            method="tools/list",
            params=types.PaginatedRequestParams(cursor=None),
        )
        result = await handler(request)
        return {tool.name for tool in result.root.tools}

    return anyio.run(_list)


def surface_inventory(app: App) -> dict[str, set[str]]:
    """What each surface independently enumerates, alongside the registry truth."""
    cli_docs, cli_tools = _cli_inventory(app)
    return {
        "registry_docs": {d.slug for d in app.list_docs()},
        "registry_tools": {t.name for t in app.list_tools()},
        "http_docs": _http_doc_slugs(app),
        "cli_docs": cli_docs,
        "cli_tools": cli_tools,
        "mcp_tools": _mcp_tool_names(app),
    }


def surfaces_agree(app: App) -> bool:
    """True iff all three surfaces enumerate the same docs/tools as the registry."""
    inv = surface_inventory(app)
    docs_agree = inv["registry_docs"] == inv["http_docs"] == inv["cli_docs"]
    tools_agree = inv["registry_tools"] == inv["cli_tools"] == inv["mcp_tools"]
    return docs_agree and tools_agree
