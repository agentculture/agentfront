"""Remote MCP transport — streamable HTTP, embeddable, with a caller-context hook.

The stdio server (:func:`agentfront.mcp_surface.serve_stdio`) serves local
agents. This module serves the *same* MCP server — the one built by
:func:`agentfront.mcp_surface.make_mcp_server`, with its single ``run`` tool and
``{code, message, remediation}`` error payloads — over the MCP **streamable
HTTP** transport, so an agent on another machine can reach an App's commands.
The protocol work is the official SDK's
(:class:`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`);
agentfront only wires it to an App and to a host.

Three ways to host it, none of which hardcodes a host, port, or framework:

* :func:`make_mcp_http_app` — a plain **ASGI** application. Run it under any
  ASGI server, or mount it inside a Starlette/FastAPI host.
* :func:`mount_aiohttp` — mount it into an existing **aiohttp**
  ``web.Application`` under a configurable path.
* :func:`serve_http` — a blocking uvicorn convenience; ``host`` and ``port``
  are required keyword arguments.

Caller-context hook
-------------------

Pass ``authenticate=`` a callable (sync or async) that receives a
:class:`CallerRequest` (method, path, query string, lower-cased headers, client
address) and returns a **caller principal** — any non-``None`` object the
consumer chooses — or ``None`` to refuse. It runs before the request reaches
the MCP session, so a refused request is answered ``401`` with an
``{"error": {code, message, remediation}}`` body and no command runs. An
authenticator that *raises* also fails closed (``401``; the exception is
logged). The accepted principal travels with the request (in the ASGI scope
under :data:`agentfront.mcp_surface.CALLER_SCOPE_KEY`) and is set as call
context around the command handler, which reads it with
:func:`agentfront.current_caller`. **Auth policy stays in the consumer**:
agentfront never interprets the principal — deciding who may run which command
is the handler's (or the authenticator's) job.

Design choice — how aiohttp embedding works
-------------------------------------------

The transport is ASGI-native (that is what the SDK speaks). Rather than
re-implementing streamable HTTP for aiohttp, or requiring a second server
process and a reverse proxy, :func:`mount_aiohttp` runs the **same ASGI app
in-process behind a small ASGI-over-aiohttp bridge**: one aiohttp route (any
method) at the chosen path translates the ``aiohttp.web.Request`` into an ASGI
``http`` scope + ``receive`` and streams the ASGI ``send`` events back through
an ``aiohttp.web.StreamResponse`` (so SSE responses stream too). The session
manager's lifetime is tied to the host's ``on_startup`` / ``on_cleanup``
signals. aiohttp is imported lazily from the host — it is *not* an agentfront
dependency — and the authenticator, dispatch, and payloads are byte-for-byte
the ASGI path's, so the two hostings cannot drift.

The session manager is run in a dedicated background task (``start()`` /
``stop()``), not entered inline in a host callback, because anyio task groups
must be exited by the task that entered them and hosts run startup and
cleanup in different tasks. If a host never sends ASGI lifespan events (e.g.
a mounted sub-app), the manager starts lazily on the first request.

Defaults: ``stateless=True`` and ``json_response=True`` — each POST is a
self-contained request/response, which suits a hosted, horizontally scalable
endpoint of request/response tools and needs no session affinity. Both are
overridable. With ``stateless=False`` the authenticator still runs on *every*
request and the principal is taken per request, so a session never carries a
stale caller.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Optional, TypedDict, Union, Unpack

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from agentfront._run_dispatch import error_payload
from agentfront.app import App
from agentfront.errors import AgentfrontError
from agentfront.mcp_surface import CALLER_SCOPE_KEY, make_mcp_server

__all__ = [
    "CallerRequest",
    "Authenticator",
    "McpHttpApp",
    "McpHttpOptions",
    "make_mcp_http_app",
    "mount_aiohttp",
    "serve_http",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CallerRequest:
    """The framework-neutral view of an incoming request an authenticator sees.

    ``headers`` keys are lower-cased; repeated headers are joined with ``", "``
    (``cookie`` headers with ``"; "``).
    """

    method: str
    path: str
    query_string: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    client: Optional[tuple[str, int]] = None


Authenticator = Callable[[CallerRequest], Union[Any, Awaitable[Any]]]
"""``(CallerRequest) -> principal | None`` — sync or async. ``None`` refuses."""


class McpHttpOptions(TypedDict, total=False):
    """The transport options every entry point accepts (all optional).

    Declared once here; :class:`McpHttpApp` holds the defaults and
    :func:`make_mcp_http_app`, :func:`mount_aiohttp` and :func:`serve_http`
    forward them unchanged as ``**options``.

    * ``authenticate`` — the caller-context hook (see the module docstring).
    * ``stateless`` (default ``True``) / ``json_response`` (default ``True``) —
      passed to the SDK's session manager.
    * ``security_settings`` — passed to the SDK
      (:class:`mcp.server.transport_security.TransportSecuritySettings`).
    * ``www_authenticate`` (default ``"Bearer"``) — the ``WWW-Authenticate``
      challenge sent with every ``401`` (RFC 7235), e.g.
      ``'Bearer realm="tools"'``; ``None`` omits the header.
    """

    authenticate: Optional[Authenticator]
    stateless: bool
    json_response: bool
    security_settings: Any
    www_authenticate: Optional[str]


def _error_body(code: int, message: str, remediation: str) -> dict[str, Any]:
    """A transport-level error body, built by the same helper as the run tool's."""
    return error_payload(AgentfrontError(code=code, message=message, remediation=remediation))


_UNAUTHORIZED = _error_body(
    401,
    "unauthorized: this MCP endpoint requires valid credentials",
    "send the credentials this endpoint's operator issued you",
)
# Sentinel: the authenticator refused (returned None or raised).
_REFUSED = object()

_NOT_FOUND = _error_body(
    404,
    "not found: no MCP endpoint at this path",
    "use the MCP endpoint path this server advertises",
)

_NO_RESPONSE = _error_body(
    500,
    "MCP transport produced no response",
    "retry the request; report it if it persists",
)


def _normalize_path(path: Optional[str]) -> Optional[str]:
    return None if path is None else _check_path(path)


def _check_path(path: str) -> str:
    if not path.startswith("/"):
        raise ValueError(f"path must start with '/': {path!r}")
    return path.rstrip("/") or "/"


def _relative_path(scope: Mapping[str, Any]) -> str:
    """The request path below the app's mount point, normalised like ``path=``.

    ASGI hosts that mount an app under a prefix (Starlette ``Mount``, a
    ``--root-path``) put the prefix in ``root_path`` and keep it in ``path``;
    the path filter compares what lies below it.
    """
    path = scope.get("path", "") or ""
    root = (scope.get("root_path", "") or "").rstrip("/")
    if root and (path == root or path.startswith(root + "/")):
        path = path[len(root) :]
    return path.rstrip("/") or "/"


def _caller_request(scope: Mapping[str, Any]) -> CallerRequest:
    headers: dict[str, str] = {}
    for raw_key, raw_value in scope.get("headers", []):
        key = raw_key.decode("latin-1").lower()
        value = raw_value.decode("latin-1")
        if key in headers:
            joiner = "; " if key == "cookie" else ", "
            headers[key] = headers[key] + joiner + value
        else:
            headers[key] = value
    client = scope.get("client")
    return CallerRequest(
        method=scope.get("method", ""),
        path=scope.get("path", ""),
        query_string=(scope.get("query_string") or b"").decode("latin-1"),
        headers=headers,
        client=tuple(client) if client else None,
    )


def _check_header_value(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or any(ch in value for ch in "\r\n\0"):
        raise ValueError(f"{name} must be a single-line header value: {value!r}")
    value.encode("latin-1")  # header values must be latin-1; raises otherwise
    return value


async def _send_json(
    send: Callable[..., Awaitable[None]],
    status: int,
    payload: dict,
    extra_headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                *extra_headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class McpHttpApp:
    """ASGI application serving one App's MCP server over streamable HTTP.

    Build it with :func:`make_mcp_http_app` (or :func:`mount_aiohttp`). The
    underlying :class:`mcp.server.Server` is exposed as ``.server`` (with the
    same public ``run_tool`` as the stdio server).
    """

    def __init__(
        self,
        app: App,
        *,
        authenticate: Optional[Authenticator] = None,
        path: Optional[str] = None,
        stateless: bool = True,
        json_response: bool = True,
        security_settings: Any = None,
        www_authenticate: Optional[str] = "Bearer",
    ) -> None:
        self.app = app
        self.server = make_mcp_server(app)
        self.path = _normalize_path(path)
        self._authenticate = authenticate
        self._stateless = stateless
        self._json_response = json_response
        self._security_settings = security_settings
        challenge = _check_header_value("www_authenticate", www_authenticate)
        self._unauthorized_headers: tuple[tuple[bytes, bytes], ...] = (
            () if challenge is None else ((b"www-authenticate", challenge.encode("latin-1")),)
        )
        self._manager: Optional[StreamableHTTPSessionManager] = None
        self._runner: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._start_lock = asyncio.Lock()

    # --- lifecycle --------------------------------------------------------
    @property
    def running(self) -> bool:
        """True while the MCP session manager is started."""
        return self._manager is not None

    async def start(self) -> StreamableHTTPSessionManager:
        """Start the MCP session manager (idempotent); return the running manager."""
        async with self._start_lock:
            if self._manager is not None:
                return self._manager
            manager = StreamableHTTPSessionManager(
                app=self.server,
                json_response=self._json_response,
                stateless=self._stateless,
                security_settings=self._security_settings,
            )
            ready = asyncio.Event()
            stop_event = asyncio.Event()

            async def _run() -> None:
                async with manager.run():
                    ready.set()
                    await stop_event.wait()

            runner = asyncio.create_task(_run(), name="agentfront-mcp-http")
            ready_wait = asyncio.create_task(ready.wait())
            await asyncio.wait({runner, ready_wait}, return_when=asyncio.FIRST_COMPLETED)
            if not ready.is_set():
                ready_wait.cancel()
                runner.result()  # re-raise the startup failure
                raise RuntimeError("MCP session manager exited during startup")
            self._manager, self._runner, self._stop_event = manager, runner, stop_event
            return manager

    async def stop(self) -> None:
        """Stop the session manager, cancelling in-flight sessions (idempotent).

        A stopped app can be started again; each start uses a fresh manager.
        """
        runner, stop_event = self._runner, self._stop_event
        self._manager = self._runner = self._stop_event = None
        if runner is None or stop_event is None:
            return
        stop_event.set()
        await runner

    # --- ASGI -------------------------------------------------------------
    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        kind = scope.get("type")
        if kind == "lifespan":
            await self._lifespan(receive, send)
            return
        if kind != "http":
            # Streamable HTTP has no websocket leg; refuse anything else.
            if kind == "websocket":
                await send({"type": "websocket.close", "code": 1000})
            return
        if self.path is not None and _relative_path(scope) != self.path:
            await _send_json(send, 404, _NOT_FOUND)
            return

        principal = await self._authenticated_principal(scope)
        if principal is _REFUSED:
            await _send_json(send, 401, _UNAUTHORIZED, self._unauthorized_headers)
            return

        manager = self._manager or await self.start()
        await manager.handle_request({**scope, CALLER_SCOPE_KEY: principal}, receive, send)

    async def _authenticated_principal(self, scope: Mapping[str, Any]) -> Any:
        if self._authenticate is None:
            return None
        try:
            principal = self._authenticate(_caller_request(scope))
            if inspect.isawaitable(principal):
                principal = await principal
        except Exception:  # noqa: BLE001 - fail closed, never run a command
            logger.exception("agentfront MCP authenticator raised; refusing the request")
            return _REFUSED
        return _REFUSED if principal is None else principal

    async def _lifespan(self, receive: Callable, send: Callable) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await self.start()
                except Exception as exc:  # noqa: BLE001 - reported to the server
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.stop()
                await send({"type": "lifespan.shutdown.complete"})
                return


def make_mcp_http_app(
    app: App,
    *,
    path: Optional[str] = None,
    **options: Unpack[McpHttpOptions],
) -> McpHttpApp:
    """Return an ASGI app serving *app*'s MCP server over streamable HTTP.

    ``path=None`` (default) answers on every path, for hosts that route to it
    (e.g. a Starlette ``Mount``); pass ``path="/mcp"`` to answer only there and
    ``404`` elsewhere. ``security_settings`` is passed through to the SDK
    (:class:`mcp.server.transport_security.TransportSecuritySettings`, e.g. for
    DNS-rebinding protection). See :class:`McpHttpOptions` for ``**options``
    and the module docstring for ``authenticate``.
    """
    return McpHttpApp(app, path=path, **options)


def mount_aiohttp(
    web_app: Any,
    app: App,
    *,
    path: str = "/mcp",
    **options: Unpack[McpHttpOptions],
) -> McpHttpApp:
    """Mount *app*'s MCP endpoint into an aiohttp ``web.Application`` at *path*.

    Adds one any-method route at *path* and hooks the session manager to the
    host's ``on_startup`` / ``on_cleanup`` signals; the host keeps its own
    routes, middleware, host and port. Returns the :class:`McpHttpApp` handle.
    Call before the host app is frozen (i.e. before it starts serving).
    ``**options`` are the :class:`McpHttpOptions`.
    """
    normalized = _check_path(path)
    mcp_app = McpHttpApp(app, path=normalized, **options)

    async def _handle(request: Any) -> Any:
        return await _bridge_aiohttp_request(mcp_app, request, normalized)

    async def _handle_slash(request: Any) -> Any:
        return await _bridge_aiohttp_request(mcp_app, request, normalized + "/")

    async def _on_startup(_web_app: Any) -> None:
        await mcp_app.start()

    async def _on_cleanup(_web_app: Any) -> None:
        await mcp_app.stop()

    web_app.router.add_route("*", normalized, _handle)
    if normalized != "/":
        web_app.router.add_route("*", normalized + "/", _handle_slash)
    web_app.on_startup.append(_on_startup)
    web_app.on_cleanup.append(_on_cleanup)
    return mcp_app


def _aiohttp_root_path(request_path: str, route_path: str) -> str:
    """The prefix aiohttp routed through before reaching *route_path*.

    A route added to a sub-app (``add_subapp("/api", sub)``) matches the full
    ``/api/<route_path>``; the prefix becomes the ASGI ``root_path`` so the
    path filter sees the route's own, relative path.
    """
    if route_path != "/" and request_path.endswith(route_path):
        return request_path[: -len(route_path)]
    if route_path == "/" and request_path.endswith("/"):
        return request_path[:-1]
    return ""


async def _bridge_aiohttp_request(asgi_app: McpHttpApp, request: Any, route_path: str) -> Any:
    """Run one aiohttp request through an ASGI app and return the aiohttp response.

    *route_path* is the path the route was registered with on its (sub-)app.
    """
    from aiohttp import web

    body = await request.read()
    transport = request.transport
    peer = transport.get_extra_info("peername") if transport else None
    sock = transport.get_extra_info("sockname") if transport else None
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": f"{request.version.major}.{request.version.minor}",
        "method": request.method,
        "scheme": request.scheme,
        "path": request.path,
        "raw_path": request.raw_path.split("?", 1)[0].encode("latin-1"),
        "query_string": request.query_string.encode("latin-1"),
        "root_path": _aiohttp_root_path(request.path, route_path),
        "headers": [(k.lower(), v) for k, v in request.raw_headers],
        "client": tuple(peer[:2]) if isinstance(peer, tuple) else None,
        "server": tuple(sock[:2]) if isinstance(sock, tuple) else None,
    }

    body_sent = False
    response_done = asyncio.Event()
    state: dict[str, Any] = {"response": None, "prepared": False}

    async def receive() -> dict:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await response_done.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            response = web.StreamResponse(status=message["status"])
            for key, value in message.get("headers", []):
                response.headers.add(key.decode("latin-1"), value.decode("latin-1"))
            state["response"] = response
        elif message["type"] == "http.response.body":
            response = state["response"]
            if not state["prepared"]:
                await response.prepare(request)
                state["prepared"] = True
            chunk = message.get("body", b"")
            if chunk:
                await response.write(chunk)
            if not message.get("more_body", False):
                await response.write_eof()
                response_done.set()

    try:
        await asgi_app(scope, receive, send)
    finally:
        response_done.set()

    response = state["response"]
    if response is None:
        return web.json_response(_NO_RESPONSE, status=500)
    if not state["prepared"]:
        await response.prepare(request)
        await response.write_eof()
    return response


def serve_http(
    app: App,
    *,
    host: str,
    port: int,
    path: str = "/mcp",
    **options: Unpack[McpHttpOptions],
) -> None:
    """Serve *app*'s MCP endpoint over streamable HTTP with uvicorn (blocking).

    ``host`` and ``port`` are required — agentfront never picks a bind address
    for you. For embedding in an existing server use :func:`make_mcp_http_app`
    or :func:`mount_aiohttp` instead. ``**options`` are the
    :class:`McpHttpOptions`.
    """
    import uvicorn

    asgi = make_mcp_http_app(app, path=path, **options)
    uvicorn.run(asgi, host=host, port=port, lifespan="on")
