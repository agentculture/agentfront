"""Producer/consumer round-trip integration tests (t8 — covers c2, h6).

Both audiences are real:
  - the PRODUCER stands up the surfaces from an App (no surface code of their own);
  - a CONSUMER reaches them with only generic tools — an HTTP fetch (sitemap + page)
    and an MCP client (list + call) — with no bespoke glue.
"""

from __future__ import annotations

import http.client
import threading
import xml.etree.ElementTree as ET  # noqa: S405 - parsing our own sitemap

import anyio
from mcp import types

from agentfront import App
from agentfront.http_surface import serve


def _app() -> App:
    app = App(name="calc", version="1.0", description="a tiny tool")
    app.add_doc(slug="intro", title="Intro", text="# Intro\nwelcome")
    app.add_doc(slug="guide/use", title="Use", text="# Use\nhow to use")

    @app.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    return app


def test_consumer_browses_docs_over_http_with_only_a_fetch():
    # PRODUCER: stand up the HTTP surface from the App, no server code authored here
    app = _app()
    server = serve(app, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # CONSUMER: only an HTTP fetch — discover via sitemap, then pull each page
        conn = http.client.HTTPConnection(host, port)
        conn.request("GET", "/sitemap.xml")
        resp = conn.getresponse()
        assert resp.status == 200
        sitemap = ET.fromstring(resp.read())  # noqa: S314 - our own generated sitemap
        slugs = [(el.text or "").lstrip("/") for el in sitemap.iter("loc")]
        assert sorted(slugs) == ["guide/use", "intro"]

        # follow each link the sitemap advertised
        bodies = {}
        for slug in slugs:
            conn.request("GET", "/" + slug)
            r = conn.getresponse()
            assert r.status == 200
            bodies[slug] = r.read().decode("utf-8")
        assert bodies["intro"] == "# Intro\nwelcome"
        assert bodies["guide/use"] == "# Use\nhow to use"
        conn.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _call_tool(app: App, name: str, arguments: dict) -> object:
    """A consumer calling a tool through the MCP server's request handler."""
    server = app.mcp_server()

    async def _call() -> object:
        handler = server.request_handlers[types.CallToolRequest]
        req = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name=name, arguments=arguments),
        )
        result = await handler(req)
        root = result.root
        if root.structuredContent is not None:
            return root.structuredContent["result"]
        import json

        for content in root.content:
            if hasattr(content, "text"):
                return json.loads(content.text)["result"]
        return root

    return anyio.run(_call)


def test_consumer_invokes_a_tool_over_mcp():
    # PRODUCER: stand up the MCP surface; CONSUMER: list then call a tool
    app = _app()
    server = app.mcp_server()

    async def _list() -> set:
        handler = server.request_handlers[types.ListToolsRequest]
        req = types.ListToolsRequest(
            method="tools/list", params=types.PaginatedRequestParams(cursor=None)
        )
        result = await handler(req)
        return {t.name for t in result.root.tools}

    assert anyio.run(_list) == {"add"}
    # the call actually executes the registered function end-to-end
    assert _call_tool(app, "add", {"x": 2, "y": 3}) == 5
