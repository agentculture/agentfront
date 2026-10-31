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
``{"error": {code, message, remediation}}`` body, a ``WWW-Authenticate``
challenge (``www_authenticate=``, default ``Bearer``; ``None`` omits it) and no
command runs. An
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
an ``aiohttp.web.StreamResponse`` (so SSE responses stream too; headers are
sent as soon as the app starts its response). When the client goes away
mid-response the bridge delivers ``http.disconnect`` (it watches the
connection, and treats a failed write the same way), so long-lived streams
end with their client. A route on a prefixed sub-app (``add_subapp``) passes
the prefix as ``root_path``. The session
manager's lifetime is tied to the host's ``on_startup`` / ``on_cleanup``
signals. aiohttp is imported lazily from the host — it is *not* an agentfront
dependency — and the authenticator, dispatch, and payloads are byte-for-byte
the ASGI path's, so the two hostings cannot drift.

The session manager is run in a dedicated background task (``start()`` /
``stop()``), not entered inline in a host callback, because anyio task groups
must be exited by the task that entered them and hosts run startup and
cleanup in different tasks. If a host never sends ASGI lifespan events (e.g.
a mounted sub-app), the manager starts lazily on the first request; concurrent
lazy starts share one manager, and a caller cancelled mid-start leaves nothing
running. ``stop()`` is final: while it runs and afterwards requests are
answered ``503`` and nothing restarts. If the manager dies on its own after
startup, the crash is logged and a fresh manager starts on the next request.

The ``path=`` filter compares the path below the ASGI ``root_path``, so the app
can sit under a Starlette ``Mount`` with ``path=`` set.

Defaults: ``stateless=True`` and ``json_response=True`` — each POST is a
self-contained request/response, which suits a hosted, horizontally scalable
endpoint of request/response tools and needs no session affinity. Both are
overridable. With ``stateless=False`` the authenticator still runs on *every*
request and the principal is taken per request, so a session never carries a
stale caller; and each session is bound to the principal that initialized it —
another caller presenting its ``mcp-session-id`` is refused ``403``. Principals
are opaque, so "same caller" is ``session_owner_key(a) == session_owner_key(b)``
(default: the principal itself).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Optional, TypedDict, Union, Unpack

from mcp.server.streamable_http import MCP_SESSION_ID_HEADER
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from agentfront._run_dispatch import error_payload
from agentfront.app import App
from agentfront.errors import AgentfrontError
from agentfront.mcp_surface import CALLER_SCOPE_KEY, _build_catalog, make_mcp_server

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
    * ``session_owner_key`` (default: the principal itself) — with
      ``stateless=False``, maps a principal to the value that identifies its
      owner; a request presenting an ``mcp-session-id`` is refused ``403``
      unless ``session_owner_key(principal) == session_owner_key(creator)``.
    * ``www_authenticate`` (default ``"Bearer"``) — the ``WWW-Authenticate``
      challenge sent with every ``401`` (RFC 7235), e.g.
      ``'Bearer realm="tools"'``; ``None`` omits the header.
    """

    authenticate: Optional[Authenticator]
    stateless: bool
    json_response: bool
    security_settings: Any
    www_authenticate: Optional[str]
    session_owner_key: Callable[[Any], Any]


# ASGI message types the transport emits and inspects.
_RESPONSE_START = "http.response.start"
_RESPONSE_BODY = "http.response.body"


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

_FORBIDDEN_SESSION = _error_body(
    403,
    "forbidden: this MCP session belongs to a different caller",
    "initialize your own session (send no mcp-session-id) with your own credentials",
)

_STOPPED = _error_body(
    503,
    "unavailable: this MCP endpoint is shutting down or stopped",
    "retry later, against a running instance of this endpoint",
)

_START_FAILED = _error_body(
    503,
    "unavailable: the MCP session manager failed to start",
    "retry the request; report it if it persists",
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


def _transport_catalog(app: App) -> list[dict[str, Any]]:
    """The structured command catalog the transport's ``run`` tool serves.

    :class:`McpHttpApp` serves ``make_mcp_server(app)``, whose ``run`` tool
    embeds exactly this catalog (``_build_run_tool`` renders it into the
    description). The surface inventory reads it here — structured, without
    standing up a transport or parsing the human-readable description.
    """
    return _build_catalog(app)


def _same_principal(principal: Any) -> Any:
    """Default ``session_owner_key``: principals are compared by equality."""
    return principal


def _header(scope: Mapping[str, Any], name: bytes) -> Optional[str]:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


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


async def _wait_ready(runner: asyncio.Task, ready: asyncio.Event) -> None:
    """Wait until *ready* is set or *runner* finishes, leaking no helper task."""
    ready_wait = asyncio.ensure_future(ready.wait())
    try:
        await asyncio.wait({runner, ready_wait}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        ready_wait.cancel()


async def _send_json(
    send: Callable[..., Awaitable[None]],
    status: int,
    payload: dict,
    extra_headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": _RESPONSE_START,
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                *extra_headers,
            ],
        }
    )
    await send({"type": _RESPONSE_BODY, "body": body, "more_body": False})


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
        session_owner_key: Callable[[Any], Any] = _same_principal,
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
        self._stopped = False
        self._start_lock = asyncio.Lock()
        self._session_owner_key = session_owner_key
        # Stateful mode: mcp-session-id -> session_owner_key(creating principal).
        self._session_owners: dict[str, Any] = {}

    # --- lifecycle --------------------------------------------------------
    #
    # States: idle (no manager yet) -> running -> stopped (final). A crash of
    # the session manager after startup drops back to idle, so the next
    # request starts a fresh manager; stop() is final — after it (and while
    # it runs) requests are refused with 503 and start() raises.

    @property
    def running(self) -> bool:
        """True while the MCP session manager is started and alive."""
        return self._manager is not None and self._runner is not None and not self._runner.done()

    @property
    def stopped(self) -> bool:
        """True once :meth:`stop` has been called; a stopped app never restarts."""
        return self._stopped

    async def start(self) -> StreamableHTTPSessionManager:
        """Start the MCP session manager (idempotent); return the running manager.

        Concurrent calls are serialised and share one manager. Cancelling the
        caller while it waits for startup tears the half-started manager down
        (nothing is orphaned). Raises :class:`RuntimeError` once the app has
        been stopped.
        """
        self._raise_if_stopped()
        async with self._start_lock:
            self._raise_if_stopped()
            if self.running and self._manager is not None:
                return self._manager
            return await self._start_locked()

    async def _start_locked(self) -> StreamableHTTPSessionManager:
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
        # Owned from the moment it exists, so stop() — or this start() being
        # cancelled — can always reach and end it.
        self._manager, self._runner, self._stop_event = None, runner, stop_event
        runner.add_done_callback(self._on_runner_done)
        try:
            await _wait_ready(runner, ready)
        except BaseException:
            await self._discard(runner, stop_event)
            raise
        if self._stopped:  # stop() ran while we waited
            await self._discard(runner, stop_event)
            self._raise_if_stopped()
        if not ready.is_set() or runner.done():
            await self._discard(runner, stop_event)
            exc = None if runner.cancelled() else runner.exception()
            if exc is not None:
                raise exc
            raise RuntimeError("MCP session manager exited during startup")
        self._manager = manager
        return manager

    def _raise_if_stopped(self) -> None:
        if self._stopped:
            raise RuntimeError("this MCP endpoint has been stopped; it does not restart")

    async def _discard(self, runner: asyncio.Task, stop_event: asyncio.Event) -> None:
        """End a runner that never became (or is no longer) the live one."""
        if self._runner is runner:
            self._manager = self._runner = self._stop_event = None
        stop_event.set()
        runner.cancel()
        await asyncio.wait({runner})

    def _on_runner_done(self, runner: asyncio.Task) -> None:
        """Clear the state of a manager that exited; log it if it crashed live."""
        was_live = runner is self._runner and self._manager is not None
        if runner is self._runner:
            self._manager = self._runner = self._stop_event = None
            self._session_owners.clear()  # the manager's sessions died with it
        # Always retrieve the outcome so asyncio never reports it as unhandled.
        exc = None if runner.cancelled() else runner.exception()
        if was_live and not self._stopped:
            logger.error(
                "agentfront MCP session manager exited unexpectedly; "
                "a fresh one starts on the next request",
                exc_info=exc,
            )

    async def stop(self) -> None:
        """Stop the session manager, cancelling in-flight sessions (idempotent).

        Final: afterwards (and while it runs) requests are answered ``503`` and
        :meth:`start` raises. A failure inside the manager's shutdown, or an
        earlier crash, is logged — never raised into the host's cleanup.
        """
        self._stopped = True
        runner, stop_event = self._runner, self._stop_event
        self._manager = self._runner = self._stop_event = None
        self._session_owners.clear()
        if runner is None or stop_event is None:
            return
        stop_event.set()
        await asyncio.wait({runner})
        exc = None if runner.cancelled() else runner.exception()
        if exc is not None:
            logger.warning("agentfront MCP session manager raised while stopping", exc_info=exc)

    # --- ASGI -------------------------------------------------------------
    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        kind = scope.get("type")
        if kind == "lifespan":
            await self._lifespan(receive, send)
        elif kind == "http":
            await self._handle_http(scope, receive, send)
        elif kind == "websocket":
            # Streamable HTTP has no websocket leg; refuse it (and ignore
            # any other scope type).
            await send({"type": "websocket.close", "code": 1000})

    async def _handle_http(self, scope: dict, receive: Callable, send: Callable) -> None:
        if self.path is not None and _relative_path(scope) != self.path:
            await _send_json(send, 404, _NOT_FOUND)
            return

        if self._stopped:
            await _send_json(send, 503, _STOPPED)
            return

        principal = await self._authenticated_principal(scope)
        if principal is _REFUSED:
            await _send_json(send, 401, _UNAUTHORIZED, self._unauthorized_headers)
            return

        manager = await self._live_manager(send)
        if manager is None:
            return  # already answered 503
        scope = {**scope, CALLER_SCOPE_KEY: principal}
        if self._stateless:
            await manager.handle_request(scope, receive, send)
        else:
            await self._handle_stateful(manager, scope, principal, receive, send)

    async def _live_manager(self, send: Callable) -> Optional[StreamableHTTPSessionManager]:
        """Return the running manager, starting one if needed.

        If it cannot be had, answer the request ``503`` and return ``None``.
        """
        try:
            manager = self._manager if self.running else None
            if manager is None:
                manager = await self.start()
        except Exception:  # noqa: BLE001 - answered 503 and never a crash
            if not self._stopped:
                logger.exception("agentfront MCP session manager failed to start")
            await _send_json(send, 503, _STOPPED if self._stopped else _START_FAILED)
            return None
        return manager

    async def _handle_stateful(
        self,
        manager: StreamableHTTPSessionManager,
        scope: dict,
        principal: Any,
        receive: Callable,
        send: Callable,
    ) -> None:
        """Bind each session to the principal that created it (stateful mode)."""
        try:
            owner_key = self._session_owner_key(principal)
        except Exception:  # noqa: BLE001 - fail closed
            logger.exception("agentfront MCP session_owner_key raised; refusing the request")
            await _send_json(send, 403, _FORBIDDEN_SESSION)
            return
        session_id = _header(scope, MCP_SESSION_ID_HEADER.encode("latin-1"))
        if session_id is None:
            await self._open_session(manager, scope, owner_key, receive, send)
        else:
            await self._resume_session(manager, scope, session_id, owner_key, receive, send)

    async def _resume_session(
        self,
        manager: StreamableHTTPSessionManager,
        scope: dict,
        session_id: str,
        owner_key: Any,
        receive: Callable,
        send: Callable,
    ) -> None:
        """Serve a request naming a session; refuse it unless *owner_key* owns it."""
        if session_id in self._session_owners and not self._same_owner(
            self._session_owners[session_id], owner_key
        ):
            await _send_json(send, 403, _FORBIDDEN_SESSION)
            return
        # Unknown ids fall through: the SDK answers them 404.
        status: list[int] = []

        async def track_end(message: dict) -> None:
            if message["type"] == _RESPONSE_START:
                status.append(message["status"])
            await send(message)

        await manager.handle_request(scope, receive, track_end)
        if scope.get("method") == "DELETE" and status and 200 <= status[0] < 300:
            self._session_owners.pop(session_id, None)

    async def _open_session(
        self,
        manager: StreamableHTTPSessionManager,
        scope: dict,
        owner_key: Any,
        receive: Callable,
        send: Callable,
    ) -> None:
        """Serve a request naming no session; record the owner of one it creates."""

        async def record_owner(message: dict) -> None:
            if message["type"] == _RESPONSE_START:
                created = _header(message, MCP_SESSION_ID_HEADER.encode("latin-1"))
                if created is not None:
                    self._prune_session_owners(manager)
                    self._session_owners[created] = owner_key
            await send(message)

        await manager.handle_request(scope, receive, record_owner)

    @staticmethod
    def _same_owner(recorded: Any, presented: Any) -> bool:
        try:
            return bool(recorded == presented)
        except Exception:  # noqa: BLE001 - an uncomparable key is not a match
            return False

    def _prune_session_owners(self, manager: StreamableHTTPSessionManager) -> None:
        """Forget owners of sessions the SDK no longer holds (ended, timed out)."""
        live = getattr(manager, "_server_instances", None)
        if isinstance(live, dict):
            for session_id in [sid for sid in self._session_owners if sid not in live]:
                del self._session_owners[session_id]

    async def _authenticated_principal(self, scope: Mapping[str, Any]) -> Any:
        if self._authenticate is None:
            return None
        try:
            principal = self._authenticate(_caller_request(scope))
            if inspect.isawaitable(principal):
                principal = await principal
        except Exception:  # noqa: BLE001 - fail closed and never run a command
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


# How often the aiohttp bridge checks whether the client is still connected
# while an ASGI response (e.g. an SSE stream) is in flight.
_DISCONNECT_POLL_INTERVAL = 0.1


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


def _aiohttp_asgi_scope(request: Any, route_path: str) -> dict:
    """The ASGI ``http`` scope for one aiohttp *request* routed at *route_path*."""
    transport = request.transport
    peer = transport.get_extra_info("peername") if transport else None
    sock = transport.get_extra_info("sockname") if transport else None
    return {
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


class _AiohttpBridge:
    """The ASGI ``receive`` / ``send`` pair for one aiohttp request.

    ``finished`` is set once the ASGI app may stop waiting on ``receive()``:
    the response is complete, or the client went away (``http.disconnect``
    either way).
    """

    def __init__(self, request: Any, body: bytes) -> None:
        self.request = request
        self.body = body
        self.body_sent = False
        self.finished = asyncio.Event()
        self.response: Any = None
        self.client_gone = False

    def _mark_client_gone(self) -> None:
        self.client_gone = True
        self.finished.set()

    async def watch_client(self) -> None:
        """Mark the client gone when its connection closes; end with the response."""
        # aiohttp exposes no awaitable "connection lost", so check the
        # transport every tick — but wake at once when the response finishes.
        while not self.finished.is_set():
            transport = self.request.transport
            if transport is None or transport.is_closing():
                self._mark_client_gone()
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.finished.wait(), _DISCONNECT_POLL_INTERVAL)

    async def receive(self) -> dict:
        if not self.body_sent:
            self.body_sent = True
            return {"type": "http.request", "body": self.body, "more_body": False}
        await self.finished.wait()
        return {"type": "http.disconnect"}

    async def send(self, message: dict) -> None:
        if self.client_gone:
            return  # like an ASGI server: sends after a disconnect are dropped
        try:
            await self._forward(message)
        except ConnectionResetError:  # aiohttp's ClientConnectionResetError too
            self._mark_client_gone()

    async def _forward(self, message: dict) -> None:
        if message["type"] == _RESPONSE_START:
            await self._start_response(message)
        elif message["type"] == _RESPONSE_BODY:
            await self._write_body(message)

    async def _start_response(self, message: dict) -> None:
        from aiohttp import web

        response = web.StreamResponse(status=message["status"])
        for key, value in message.get("headers", []):
            response.headers.add(key.decode("latin-1"), value.decode("latin-1"))
        self.response = response
        # Send the status line and headers now: an SSE stream may not produce
        # a body chunk for a long time, and the client is waiting for the
        # headers to start reading it.
        await response.prepare(self.request)

    async def _write_body(self, message: dict) -> None:
        chunk = message.get("body", b"")
        if chunk:
            await self.response.write(chunk)
        if not message.get("more_body", False):
            await self.response.write_eof()
            self.finished.set()


async def _bridge_aiohttp_request(asgi_app: McpHttpApp, request: Any, route_path: str) -> Any:
    """Run one aiohttp request through an ASGI app and return the aiohttp response.

    *route_path* is the path the route was registered with on its (sub-)app.
    """
    from aiohttp import web

    body = await request.read()
    scope = _aiohttp_asgi_scope(request, route_path)
    bridge = _AiohttpBridge(request, body)
    watcher = asyncio.create_task(bridge.watch_client())
    try:
        await asgi_app(scope, bridge.receive, bridge.send)
    finally:
        bridge.finished.set()
        watcher.cancel()

    if bridge.response is None:
        return web.json_response(_NO_RESPONSE, status=500)
    return bridge.response


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
