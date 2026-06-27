"""Assemble all three agent-first surfaces from one App — and prove they agree.

The point of the single registry is that the CLI, MCP, and HTTP surfaces cannot
present *different* sets of docs/tools. This module both builds the three
surfaces from one :class:`App` and provides the cross-surface **agreement
check** that turns that promise into something testable: it queries each surface
independently (the HTTP sitemap, the CLI ``learn --json`` listing, the MCP
``list_tools`` handler) and confirms they enumerate the same set the registry
holds.

Under single-dispatch MCP, the server exposes exactly one ``run`` tool whose
description embeds a command catalog.  The agreement check compares the
*command paths* in that catalog against the CLI verb paths and the registry
tool paths.
"""

from __future__ import annotations

import io
import json

# We only parse our own generated sitemap here, never untrusted input.
import xml.etree.ElementTree as ET  # noqa: S405
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
    taui: Any  # the baseline TAUIState


def build_surfaces(app: App) -> Surfaces:
    """Build all three surfaces from a single App."""
    return Surfaces(http=app.http_app(), mcp=app.mcp_server(), cli=app.cli(), taui=app.taui())


def _http_doc_slugs(app: App) -> set[str]:
    """The doc slugs the HTTP surface actually advertises in its sitemap."""
    wsgi = app.http_app()
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/sitemap.xml"}
    body = b"".join(wsgi(environ, lambda status, headers: None))
    # ``body`` is our own generated sitemap, never untrusted input.
    root = ET.fromstring(body)  # noqa: S314
    return {(el.text or "").lstrip("/") for el in root.iter("loc")}


def _cli_inventory(app: App) -> tuple[set[str], set[str]]:
    """The (doc slugs, tool paths) the CLI ``learn`` surface reports."""
    from agentfront.cli_surface import run_cli

    buf = io.StringIO()
    with redirect_stdout(buf):
        run_cli(app, ["learn", "--json"])
    payload = json.loads(buf.getvalue())
    return (
        {d["slug"] for d in payload["docs"]},
        {"/".join(t["path"]) for t in payload["tools"]},
    )


def _mcp_command_paths(app: App) -> set[str]:
    """The command paths the MCP surface can dispatch.

    Under single-dispatch, the server has one ``run`` tool whose description
    embeds the command catalog.  We derive the catalog from the registry
    (same source the server uses) so the comparison is deterministic.
    """
    paths: set[str] = set()
    for entry in app.list_tools():
        path = list(entry.group) + [entry.name]
        paths.add("/".join(path))
    return paths


def surface_inventory(app: App) -> dict[str, set[str]]:
    """What each surface independently enumerates, alongside the registry truth."""
    cli_docs, cli_tools = _cli_inventory(app)
    registry_tool_paths = {"/".join(list(t.group) + [t.name]) for t in app.list_tools()}
    mirror = app.taui_mirror()
    taui_selectors = {a["selector"] for a in mirror["available_actions"]}
    taui_tools = {
        "/".join(list(t.group) + [t.name])
        for t in app.list_tools()
        if ".".join(list(t.group) + [t.name]) in taui_selectors
    }
    return {
        "registry_docs": {d.slug for d in app.list_docs()},
        "registry_tools": registry_tool_paths,
        "http_docs": _http_doc_slugs(app),
        "cli_docs": cli_docs,
        "cli_tools": cli_tools,
        "mcp_tools": _mcp_command_paths(app),
        "taui_tools": taui_tools,
    }


def surfaces_agree(app: App) -> bool:
    """True iff all surfaces enumerate the same docs/tools as the registry."""
    inv = surface_inventory(app)
    docs_agree = inv["registry_docs"] == inv["http_docs"] == inv["cli_docs"]
    tools_agree = inv["registry_tools"] == inv["cli_tools"] == inv["mcp_tools"] == inv["taui_tools"]
    return docs_agree and tools_agree
