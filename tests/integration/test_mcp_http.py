"""Remote MCP transport (streamable HTTP) — agentfront#52.

Every test here drives a *stock* MCP client (``mcp.client.streamable_http`` +
``mcp.ClientSession``) over real TCP against agentfront's transport, hosted two
ways:

* the standalone ASGI app (``make_mcp_http_app``) under uvicorn, and
* the aiohttp adapter (``mount_aiohttp``) mounted into a host aiohttp
  application under a configurable, non-default path.

Both bind ``127.0.0.1`` on an ephemeral port chosen by the OS — nothing in the
transport hardcodes a host or port.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agentfront import AgentfrontError, App, current_caller
from agentfront.mcp_http import CallerRequest, make_mcp_http_app, mount_aiohttp, serve_http
from agentfront.serve import surface_inventory, surfaces_agree

LOOPBACK = "127.0.0.1"
TOKENS = {"token-a": "agent-a", "token-admin": "admin"}


def _app() -> App:
    app = App(name="remote-app", version="0.1.0")
    app.add_doc(slug="intro", title="Intro", text="# Intro\n\nhello\n")
    calls: list[str] = []
    app.calls = calls  # type: ignore[attr-defined]

    @app.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        calls.append("add")
        return x + y

    @app.tool
    def whoami() -> Any:
        """Return the caller principal."""
        calls.append("whoami")
        return current_caller()

    @app.tool(group="admin", name="purge")
    async def admin_purge() -> str:
        """Admin-only command (async, to prove the principal survives awaits)."""
        calls.append("admin/purge")
        await asyncio.sleep(0)
        if current_caller() != "admin":
            raise AgentfrontError(
                code=403, message="admin only", remediation="authenticate as an admin"
            )
        return "purged"

    return app


def _bearer_auth(request: CallerRequest) -> Any:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return None
    return TOKENS.get(header.removeprefix("Bearer "))


async def _async_bearer_auth(request: CallerRequest) -> Any:
    await asyncio.sleep(0)
    return _bearer_auth(request)


# --- hosting helpers ------------------------------------------------------


@asynccontextmanager
async def _uvicorn(asgi: Any) -> AsyncIterator[str]:
    import uvicorn

    config = uvicorn.Config(asgi, host=LOOPBACK, port=0, lifespan="on", log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(500):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started, "uvicorn did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://{LOOPBACK}:{port}"
    finally:
        server.should_exit = True
        await task


@asynccontextmanager
async def _aiohttp_host(app: App, path: str, **kwargs: Any) -> AsyncIterator[str]:
    from aiohttp import web

    host = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="host ok")

    host.router.add_get("/health", health)
    mount_aiohttp(host, app, path=path, **kwargs)
    runner = web.AppRunner(host)
    await runner.setup()
    site = web.TCPSite(runner, LOOPBACK, 0)
    await site.start()
    try:
        port = site._server.sockets[0].getsockname()[1]  # pylint: disable=protected-access
        yield f"http://{LOOPBACK}:{port}"
    finally:
        await runner.cleanup()


async def _session_roundtrip(url: str, token: str | None, command: list[str], args: dict):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(headers=headers, timeout=15) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _sid):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                listed = await session.list_tools()
                called = await session.call_tool("run", {"command": command, "args": args})
    return init, listed, called


def _payload(call_result: Any) -> dict:
    """The ``{result}`` / ``{error}`` payload of a tools/call, via structuredContent."""
    assert call_result.structuredContent is not None
    # The text content block must carry the same JSON (clients without
    # structured-content support read this one).
    text = call_result.content[0].text
    assert json.loads(text) == call_result.structuredContent
    return call_result.structuredContent


# --- ASGI app under uvicorn ----------------------------------------------


def test_stock_client_initialize_list_call_over_asgi():
    app = _app()

    async def scenario():
        async with _uvicorn(make_mcp_http_app(app)) as base:
            return await _session_roundtrip(f"{base}/mcp", None, ["add"], {"x": 2, "y": 3})

    init, listed, called = asyncio.run(scenario())
    assert init.serverInfo.name == "remote-app"
    assert [t.name for t in listed.tools] == ["run"]
    catalog = listed.tools[0].description.split("Available commands:\n", 1)[1]
    assert {"/".join(c["path"]) for c in json.loads(catalog)} == {"add", "whoami", "admin/purge"}
    assert _payload(called) == {"result": 5}


def test_error_payload_shape_preserved_over_http():
    app = _app()

    async def scenario():
        async with _uvicorn(make_mcp_http_app(app)) as base:
            _, _, unknown = await _session_roundtrip(f"{base}/mcp", None, ["nope"], {})
            _, _, bad = await _session_roundtrip(f"{base}/mcp", None, ["add"], {"x": 1})
        return unknown, bad

    unknown, bad = asyncio.run(scenario())
    assert _payload(unknown) == {
        "error": {
            "code": 1,
            "message": "unknown command: nope",
            "remediation": "check available commands in the 'run' tool description",
        }
    }
    err = _payload(bad)["error"]
    assert set(err) == {"code", "message", "remediation"}
    assert err["code"] == 1


def test_authenticator_principal_reaches_handler_over_asgi():
    app = _app()

    async def scenario():
        asgi = make_mcp_http_app(app, authenticate=_bearer_auth)
        async with _uvicorn(asgi) as base:
            _, _, me = await _session_roundtrip(f"{base}/mcp", "token-a", ["whoami"], {})
            _, _, denied = await _session_roundtrip(
                f"{base}/mcp", "token-a", ["admin", "purge"], {}
            )
            _, _, allowed = await _session_roundtrip(
                f"{base}/mcp", "token-admin", ["admin", "purge"], {}
            )
        return me, denied, allowed

    me, denied, allowed = asyncio.run(scenario())
    assert _payload(me) == {"result": "agent-a"}
    assert _payload(denied) == {
        "error": {"code": 403, "message": "admin only", "remediation": "authenticate as an admin"}
    }
    assert _payload(allowed) == {"result": "purged"}
    # Context does not leak out of the request into this thread.
    assert current_caller() is None


def test_refused_authentication_is_401_and_runs_no_command():
    app = _app()
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "run", "arguments": {"command": ["add"], "args": {"x": 1, "y": 1}}},
    }
    headers = {"Accept": "application/json, text/event-stream"}

    async def scenario():
        asgi = make_mcp_http_app(app, authenticate=_async_bearer_auth)
        async with _uvicorn(asgi) as base:
            async with httpx.AsyncClient(timeout=10) as http:
                missing = await http.post(f"{base}/mcp", json=body, headers=headers)
                wrong = await http.post(
                    f"{base}/mcp",
                    json=body,
                    headers={**headers, "Authorization": "Bearer not-a-token"},
                )
        return missing, wrong

    missing, wrong = asyncio.run(scenario())
    for resp in (missing, wrong):
        assert resp.status_code == 401
        err = resp.json()["error"]
        assert set(err) == {"code", "message", "remediation"}
    assert app.calls == []  # type: ignore[attr-defined]


def test_authenticator_exception_fails_closed():
    app = _app()

    def broken(_request: CallerRequest) -> Any:
        raise RuntimeError("auth backend down")

    async def scenario():
        async with _uvicorn(make_mcp_http_app(app, authenticate=broken)) as base:
            async with httpx.AsyncClient(timeout=10) as http:
                return await http.post(f"{base}/mcp", json={"jsonrpc": "2.0", "id": 1})

    assert asyncio.run(scenario()).status_code == 401
    assert app.calls == []  # type: ignore[attr-defined]


def test_asgi_path_filter_is_configurable():
    app = _app()

    async def scenario():
        async with _uvicorn(make_mcp_http_app(app, path="/tools/mcp")) as base:
            _, _, called = await _session_roundtrip(
                f"{base}/tools/mcp", None, ["add"], {"x": 1, "y": 1}
            )
            async with httpx.AsyncClient(timeout=10) as http:
                other = await http.post(f"{base}/mcp", json={})
        return called, other

    called, other = asyncio.run(scenario())
    assert _payload(called) == {"result": 2}
    assert other.status_code == 404


# --- aiohttp adapter --------------------------------------------------------


def test_stock_client_over_aiohttp_mount_with_custom_path_and_auth():
    app = _app()

    async def scenario():
        async with _aiohttp_host(app, "/api/agent-mcp", authenticate=_bearer_auth) as base:
            init, listed, me = await _session_roundtrip(
                f"{base}/api/agent-mcp", "token-a", ["whoami"], {}
            )
            _, _, summed = await _session_roundtrip(
                f"{base}/api/agent-mcp", "token-admin", ["add"], {"x": 4, "y": 5}
            )
            async with httpx.AsyncClient(timeout=10) as http:
                health = await http.get(f"{base}/health")
                refused = await http.post(f"{base}/api/agent-mcp", json={"jsonrpc": "2.0"})
        return init, listed, me, summed, health, refused

    init, listed, me, summed, health, refused = asyncio.run(scenario())
    assert init.serverInfo.name == "remote-app"
    assert [t.name for t in listed.tools] == ["run"]
    assert _payload(me) == {"result": "agent-a"}
    assert _payload(summed) == {"result": 9}
    # The host's own routes are untouched by the mount.
    assert health.status_code == 200 and health.text == "host ok"
    assert refused.status_code == 401
    assert set(refused.json()["error"]) == {"code", "message", "remediation"}


def test_aiohttp_mount_returns_handle_and_rejects_bad_path():
    from aiohttp import web

    handle = mount_aiohttp(web.Application(), _app(), path="/mcp")
    assert handle.path == "/mcp"
    with pytest.raises(ValueError):
        mount_aiohttp(web.Application(), _app(), path="mcp")


# --- no hardcoded host/port; agreement; stdio unchanged ---------------------


def test_serve_http_requires_explicit_host_and_port():
    params = inspect.signature(serve_http).parameters
    for name in ("host", "port"):
        assert params[name].default is inspect.Parameter.empty
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_surface_inventory_covers_remote_mcp_transport():
    app = _app()
    inv = surface_inventory(app)
    assert inv["mcp_http_tools"] == inv["registry_tools"] == {"add", "whoami", "admin/purge"}
    assert surfaces_agree(app)


def test_stdio_entry_point_unchanged():
    from agentfront import mcp_surface

    assert "serve_stdio" in mcp_surface.__all__
    assert list(inspect.signature(mcp_surface.serve_stdio).parameters) == ["app"]


def test_inventory_falls_back_to_registry_without_mcp_extra(monkeypatch):
    """Without the ``mcp`` extra the remote transport can't be built; the
    inventory still reports the registry's command paths instead of crashing."""
    import sys

    for name in [m for m in sys.modules if m == "mcp" or m.startswith("mcp.")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.delitem(sys.modules, "agentfront.mcp_http", raising=False)
    monkeypatch.delitem(sys.modules, "agentfront.mcp_surface", raising=False)

    from agentfront.serve import _mcp_http_command_paths

    assert _mcp_http_command_paths(_app()) == {"add", "whoami", "admin/purge"}
