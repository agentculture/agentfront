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

import pytest

# The remote transport needs the optional ``mcp`` extra (which brings httpx and
# uvicorn's ASGI stack along); skip the whole module without it, like the other
# mcp-dependent tests. aiohttp is a host-side dependency, guarded per test.
pytest.importorskip("mcp")
httpx = pytest.importorskip("httpx")
pytest.importorskip("uvicorn")

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402

from agentfront import AgentfrontError, App, current_caller  # noqa: E402
from agentfront.mcp_http import (  # noqa: E402
    CallerRequest,
    make_mcp_http_app,
    mount_aiohttp,
    serve_http,
)
from agentfront.serve import surface_inventory, surfaces_agree  # noqa: E402

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
    web = pytest.importorskip("aiohttp.web")

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
    web = pytest.importorskip("aiohttp.web")

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


# --- review fixes (PR #56) --------------------------------------------------


def test_transport_error_bodies_are_canonical_error_payloads():
    """#10: the transport's own 401/404 bodies come from the canonical helper."""
    from agentfront import mcp_http
    from agentfront._run_dispatch import error_payload

    app = _app()

    async def scenario():
        asgi = make_mcp_http_app(app, path="/mcp", authenticate=_bearer_auth)
        async with _uvicorn(asgi) as base:
            async with httpx.AsyncClient(timeout=10) as http:
                return (
                    await http.post(f"{base}/mcp", json={}),
                    await http.post(f"{base}/elsewhere", json={}),
                )

    refused, missing = asyncio.run(scenario())
    for resp, status in ((refused, 401), (missing, 404)):
        assert resp.status_code == status
        err = resp.json()["error"]
        rebuilt = error_payload(
            AgentfrontError(
                code=err["code"], message=err["message"], remediation=err["remediation"]
            )
        )
        assert resp.json() == rebuilt and err["code"] == status
    assert mcp_http._error_body(401, "x", "y") == error_payload(
        AgentfrontError(code=401, message="x", remediation="y")
    )


def test_transport_options_are_declared_once_and_forwarded_everywhere():
    """#10: one options declaration; every entry point accepts all of it."""
    from typing import get_type_hints

    from agentfront.mcp_http import McpHttpApp, McpHttpOptions

    option_names = set(get_type_hints(McpHttpOptions))
    init = inspect.signature(McpHttpApp.__init__).parameters
    assert option_names == {
        name
        for name, p in init.items()
        if p.kind is inspect.Parameter.KEYWORD_ONLY and name != "path"
    }
    for helper in (make_mcp_http_app, mount_aiohttp, serve_http):
        params = inspect.signature(helper).parameters
        assert "options" in params and params["options"].kind is inspect.Parameter.VAR_KEYWORD
        assert params["path"].kind is inspect.Parameter.KEYWORD_ONLY
    # An unknown option is a TypeError, not silently dropped.
    with pytest.raises(TypeError):
        make_mcp_http_app(_app(), not_an_option=True)  # type: ignore[call-arg]


def test_401_carries_a_configurable_www_authenticate_challenge():
    """#8: RFC 7235 — a 401 names its challenge; consumer-configurable, or off."""
    app = _app()

    async def scenario():
        out = {}
        for label, extra in (
            ("default", {}),
            ("custom", {"www_authenticate": 'Bearer realm="tools"'}),
            ("off", {"www_authenticate": None}),
        ):
            asgi = make_mcp_http_app(app, authenticate=_bearer_auth, **extra)
            async with _uvicorn(asgi) as base:
                async with httpx.AsyncClient(timeout=10) as http:
                    out[label] = await http.post(f"{base}/mcp", json={})
        async with _aiohttp_host(app, "/mcp", authenticate=_bearer_auth) as base:
            async with httpx.AsyncClient(timeout=10) as http:
                out["aiohttp"] = await http.post(f"{base}/mcp", json={})
        return out

    out = asyncio.run(scenario())
    assert all(resp.status_code == 401 for resp in out.values())
    assert out["default"].headers["www-authenticate"] == "Bearer"
    assert out["custom"].headers["www-authenticate"] == 'Bearer realm="tools"'
    assert "www-authenticate" not in out["off"].headers
    assert out["aiohttp"].headers["www-authenticate"] == "Bearer"


def test_www_authenticate_rejects_header_injection():
    with pytest.raises(ValueError):
        make_mcp_http_app(_app(), www_authenticate="Bearer\r\nX-Evil: 1")


def test_path_filter_honours_starlette_mount_root_path():
    """#6: inside Mount('/api', ...) the filter matches the path *below* the mount."""
    starlette_routing = pytest.importorskip("starlette.routing")
    from starlette.applications import Starlette

    app = _app()

    async def scenario():
        host = Starlette(
            routes=[starlette_routing.Mount("/api", app=make_mcp_http_app(app, path="/mcp"))]
        )
        async with _uvicorn(host) as base:
            _, _, called = await _session_roundtrip(
                f"{base}/api/mcp", None, ["add"], {"x": 2, "y": 2}
            )
            async with httpx.AsyncClient(timeout=10) as http:
                other = await http.post(f"{base}/api/other", json={})
        return called, other

    called, other = asyncio.run(scenario())
    assert _payload(called) == {"result": 4}
    assert other.status_code == 404


def test_aiohttp_mount_inside_a_prefixed_subapp():
    """#6: mount_aiohttp into a sub-app added with add_subapp('/api', ...)."""
    web = pytest.importorskip("aiohttp.web")
    app = _app()

    async def scenario():
        host = web.Application()
        sub = web.Application()
        mount_aiohttp(sub, app, path="/mcp")
        host.add_subapp("/api", sub)
        runner = web.AppRunner(host)
        await runner.setup()
        site = web.TCPSite(runner, LOOPBACK, 0)
        await site.start()
        try:
            port = site._server.sockets[0].getsockname()[1]  # pylint: disable=protected-access
            base = f"http://{LOOPBACK}:{port}"
            _, _, called = await _session_roundtrip(
                f"{base}/api/mcp", None, ["add"], {"x": 3, "y": 3}
            )
            _, _, slashed = await _session_roundtrip(
                f"{base}/api/mcp/", None, ["add"], {"x": 1, "y": 0}
            )
        finally:
            await runner.cleanup()
        return called, slashed

    called, slashed = asyncio.run(scenario())
    assert _payload(called) == {"result": 6}
    assert _payload(slashed) == {"result": 1}


def test_relative_path_strips_root_path_only_as_a_prefix():
    from agentfront.mcp_http import _relative_path

    assert _relative_path({"path": "/api/mcp", "root_path": "/api"}) == "/mcp"
    assert _relative_path({"path": "/api/mcp/", "root_path": "/api/"}) == "/mcp"
    # Servers that already strip root_path from path (older ASGI semantics).
    assert _relative_path({"path": "/mcp", "root_path": "/api"}) == "/mcp"
    # A sibling that merely shares the prefix string is not under the mount.
    assert _relative_path({"path": "/apix/mcp", "root_path": "/api"}) == "/apix/mcp"
    assert _relative_path({"path": "/api", "root_path": "/api"}) == "/"


# --- lifecycle (#1 #2 #3) -----------------------------------------------------

_INITIALIZE = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "0"},
        },
    }
).encode()


async def _asgi_post(asgi: Any, body: bytes = _INITIALIZE, path: str = "/mcp") -> tuple[int, dict]:
    """Drive one in-memory ASGI POST; return (status, decoded JSON body)."""
    sent: list[dict] = []
    pending = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive() -> dict:
        if pending:
            return pending.pop()
        await asyncio.Event().wait()  # never disconnects
        raise AssertionError("unreachable")

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [
            (b"accept", b"application/json, text/event-stream"),
            (b"content-type", b"application/json"),
        ],
        "client": (LOOPBACK, 50000),
        "server": (LOOPBACK, 80),
    }
    await asgi(scope, receive, send)
    raw = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return sent[0]["status"], json.loads(raw)


def _live_runners() -> list[asyncio.Task]:
    return [
        t for t in asyncio.all_tasks() if t.get_name() == "agentfront-mcp-http" and not t.done()
    ]


def test_request_after_stop_is_503_and_never_restarts():
    """#1: once stopping/stopped, refuse with 503 — never lazily start again."""
    from agentfront.mcp_http import McpHttpApp

    async def scenario():
        asgi = McpHttpApp(_app(), path="/mcp")
        status_running, _ = await _asgi_post(asgi)  # lazy start, served
        stopping = asyncio.create_task(asgi.stop())
        await asyncio.sleep(0)  # stop() has begun, not finished
        during = await _asgi_post(asgi)
        await stopping
        after = await _asgi_post(asgi)
        with pytest.raises(RuntimeError):
            await asgi.start()
        return status_running, during, after, asgi.running, _live_runners()

    status_running, during, after, running, runners = asyncio.run(scenario())
    assert status_running == 200
    for status, payload in (during, after):
        assert status == 503
        assert set(payload["error"]) == {"code", "message", "remediation"}
        assert payload["error"]["code"] == 503
    assert running is False
    assert runners == []


def test_cancelled_start_leaves_no_orphan_runner():
    """#2: cancelling the task that called start() must not orphan the runner."""
    from agentfront.mcp_http import McpHttpApp

    async def scenario():
        asgi = McpHttpApp(_app())
        starting = asyncio.create_task(asgi.start())
        await asyncio.sleep(0)  # start() is now waiting for the manager to be ready
        starting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await starting
        await asyncio.sleep(0.05)
        orphans = _live_runners()
        # The app is still usable, and concurrent lazy starts share one manager.
        first, second = await asyncio.gather(asgi.start(), asgi.start())
        live = len(_live_runners())
        await asgi.stop()
        return orphans, first is second, live, _live_runners()

    orphans, shared, live, after_stop = asyncio.run(scenario())
    assert orphans == []
    assert shared and live == 1
    assert after_stop == []


def test_runner_crash_after_startup_is_detected_and_restarts_lazily():
    """#3: a manager that dies after startup is cleared; the next request starts a
    fresh one, and stop() does not re-raise the old failure into host cleanup."""
    from agentfront.mcp_http import McpHttpApp

    async def _boom() -> None:
        raise RuntimeError("session manager crashed")

    async def scenario():
        asgi = McpHttpApp(_app())
        dead = await asgi.start()
        dead._task_group.start_soon(_boom)  # pylint: disable=protected-access
        await asyncio.sleep(0.05)
        running_after_crash = asgi.running
        status, _ = await _asgi_post(asgi, path="/anything")
        fresh = asgi._manager  # pylint: disable=protected-access
        # Crash again, then stop without any request in between: no re-raise.
        fresh._task_group.start_soon(_boom)  # pylint: disable=protected-access
        await asyncio.sleep(0.05)
        await asgi.stop()
        return running_after_crash, status, fresh is not dead, _live_runners()

    running_after_crash, status, restarted, runners = asyncio.run(scenario())
    assert running_after_crash is False
    assert status == 200
    assert restarted
    assert runners == []


# --- aiohttp bridge: client disconnect (#4) -----------------------------------


def test_aiohttp_bridge_delivers_disconnect_and_ends_sse_stream(monkeypatch):
    """#4: stateful + SSE over the aiohttp mount; the client drops a long-lived
    GET stream and the bridged request (the stream's server-side task) ends."""
    pytest.importorskip("aiohttp")
    from agentfront import mcp_http

    finished: dict[str, asyncio.Event] = {}
    real_bridge = mcp_http._bridge_aiohttp_request

    async def tracking_bridge(asgi_app: Any, request: Any, route_path: str) -> Any:
        done = finished.setdefault(request.method, asyncio.Event())
        try:
            return await real_bridge(asgi_app, request, route_path)
        finally:
            if request.method == "GET":
                done.set()

    monkeypatch.setattr(mcp_http, "_bridge_aiohttp_request", tracking_bridge)
    accept = {"Accept": "application/json, text/event-stream"}

    async def scenario():
        async with _aiohttp_host(_app(), "/mcp", stateless=False, json_response=False) as base:
            url = f"{base}/mcp"
            async with httpx.AsyncClient(timeout=10) as http:
                init = await http.post(
                    url, content=_INITIALIZE, headers={**accept, "Content-Type": "application/json"}
                )
                sid = init.headers["mcp-session-id"]
                session = {**accept, "mcp-session-id": sid}
                note = await http.post(
                    url,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    headers=session,
                )
            stream_client = httpx.AsyncClient(timeout=10)
            request = stream_client.build_request(
                "GET", url, headers={"Accept": "text/event-stream", "mcp-session-id": sid}
            )
            response = await stream_client.send(request, stream=True)
            opened = response.status_code
            await asyncio.sleep(0.2)  # the server is now parked on the stream
            still_open = not finished["GET"].is_set()
            await response.aclose()
            await stream_client.aclose()  # the client goes away
            try:
                await asyncio.wait_for(finished["GET"].wait(), timeout=3)
                ended = True
            except asyncio.TimeoutError:
                ended = False
            return init.status_code, note.status_code, opened, still_open, ended

    init_status, note_status, opened, still_open, ended = asyncio.run(scenario())
    assert init_status == 200 and note_status == 202
    assert opened == 200 and still_open
    assert ended, "the bridged SSE stream did not end after the client disconnected"
