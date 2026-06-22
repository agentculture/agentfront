"""Integration test for the quickstart example package.

Loads examples/quickstart/mytool/__init__.py and asserts that all three
surfaces (HTTP, MCP, CLI) work correctly and agree with the registry.
"""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path
from typing import Any

import anyio
import pytest

from agentfront import App
from agentfront.cli_surface import run_cli
from agentfront.serve import surfaces_agree

EXAMPLE_INIT = (
    Path(__file__).resolve().parent.parent.parent
    / "examples"
    / "quickstart"
    / "mytool"
    / "__init__.py"
)


# --- fixture ----------------------------------------------------------------


@pytest.fixture
def app() -> App:
    """Load the example app from the file system."""
    spec = importlib.util.spec_from_file_location("mytool", str(EXAMPLE_INIT))
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["mytool"] = mod
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod.app


# --- config size -------------------------------------------------------------


def test_config_is_tiny() -> None:
    """The example config must be <= 30 non-blank, non-comment lines."""
    text = EXAMPLE_INIT.read_text(encoding="utf-8")
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    assert count <= 30, f"config has {count} real lines (limit 30)"


# --- HTTP surface ------------------------------------------------------------


def _wsgi_environ(path: str) -> dict[str, Any]:
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "wsgi.url_scheme": "http",
    }


def _call_wsgi(app: App, path: str) -> tuple[str, bytes]:
    wsgi = app.http_app()
    captured_status: list[str] = []

    def _start_response(status: str, _headers: list[tuple[str, str]]):
        captured_status.append(status)
        return lambda b: None

    body = b"".join(wsgi(_wsgi_environ(path), _start_response))
    return captured_status[0], body


def test_http_serves_quickstart_doc(app: App) -> None:
    status, body = _call_wsgi(app, "/quickstart")
    assert status.startswith("200")
    assert b"Quickstart" in body


def test_http_serves_reference_doc(app: App) -> None:
    status, body = _call_wsgi(app, "/reference")
    assert status.startswith("200")
    assert b"Reference" in body


def test_http_sitemap_lists_docs(app: App) -> None:
    status, body = _call_wsgi(app, "/sitemap.xml")
    assert status.startswith("200")
    tree = ET.fromstring(body)  # noqa: S314
    locs = sorted(el.text for el in tree.iter("loc"))
    assert locs == ["/quickstart", "/reference"]


# --- MCP surface -------------------------------------------------------------


def test_mcp_lists_tools(app: App) -> None:
    server = app.mcp_server()

    async def _list() -> list[str]:
        from mcp import types

        req = types.ListToolsRequest(params=types.PaginatedRequestParams(cursor=None))
        handler = server.request_handlers.get(types.ListToolsRequest)
        assert handler is not None
        result = await handler(req)
        return [t.name for t in result.root.tools]

    names = anyio.run(_list)
    assert sorted(names) == ["add", "greet"]


# --- CLI surface -------------------------------------------------------------


def test_cli_learn_returns_zero(app: App) -> None:
    rc = run_cli(app, ["learn"])
    assert rc == 0


# --- surfaces agree ----------------------------------------------------------


def test_surfaces_agree(app: App) -> None:
    assert surfaces_agree(app) is True
