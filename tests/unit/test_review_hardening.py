"""Hardening tests from the ask-colleague (Qwen) review of the pivot.

Each test corresponds to a finding that held up under verification:
  - run_cli must preserve argparse's exit codes (``--help`` is 0, not a failure)
  - the /llms.txt discovery endpoint lists docs + tools
  - a raising tool surfaces as an MCP error result (SDK behavior, locked in)
  - app.tool(f) returns f (verified; the review's "returns register" was wrong)
"""

import anyio

from agentfront import App
from agentfront.cli_surface import run_cli
from agentfront.http_surface import make_http_app


def _wsgi_get(app, path):
    wsgi = make_http_app(app)
    captured = {}

    def start(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)
        return lambda b: None

    body = b"".join(wsgi({"REQUEST_METHOD": "GET", "PATH_INFO": path}, start))
    return captured["status"], captured["headers"], body.decode("utf-8")


def test_run_cli_help_exits_zero():
    app = App(name="t")
    assert run_cli(app, ["--help"]) == 0


def test_run_cli_parse_error_is_nonzero():
    app = App(name="t")
    # an unknown verb is an argparse error (exit 2), not a success
    assert run_cli(app, ["does-not-exist"]) != 0


def test_tool_direct_call_returns_the_function():
    app = App(name="t")

    def f(q: str) -> str:
        """Doc."""
        return q

    assert app.tool(f) is f


def test_llms_txt_lists_docs_and_tools():
    app = App(name="mytool", version="1.0", description="a demo")
    app.add_doc(slug="intro", title="Intro", text="# Intro")

    @app.tool
    def search(query: str) -> str:
        """Find things."""
        return query

    status, headers, body = _wsgi_get(app, "/llms.txt")
    assert status.startswith("200")
    assert "text/markdown" in headers.get("Content-Type", "")
    assert "# mytool" in body
    assert "a demo" in body
    assert "(/intro)" in body
    assert "search: Find things." in body


def test_raising_tool_surfaces_as_mcp_error():
    app = App(name="t")

    @app.tool
    def boom(x: int) -> int:
        """Always raises."""
        raise RuntimeError("kaboom")

    from mcp.shared.memory import create_connected_server_and_client_session as connect

    async def go() -> bool:
        async with connect(app.mcp_server()) as client:
            await client.initialize()
            result = await client.call_tool("boom", {"x": 1})
            return bool(result.isError)

    assert anyio.run(go) is True
