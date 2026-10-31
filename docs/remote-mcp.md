# Remote MCP — streamable HTTP, with a caller-context hook

`app.mcp_server()` plus `serve_stdio(app)` serve **local** agents over stdio.
`agentfront.mcp_http` serves the *same* MCP server — the single `run` tool,
the embedded command catalog, the `{"result": ...}` / `{"error": {code,
message, remediation}}` payloads — over the MCP **streamable HTTP** transport,
so an agent on another machine can reach your App. Needs the `[mcp]` extra.

## Host it

Nothing in the transport picks a host, a port, or a framework for you.

```python
from agentfront.mcp_http import make_mcp_http_app, mount_aiohttp, serve_http

# 1. A plain ASGI app — run it under any ASGI server or mount it in a
#    Starlette/FastAPI host. path=None answers on every path (the host routes);
#    path="/mcp" answers only there and 404s elsewhere.
asgi = make_mcp_http_app(app, path="/mcp")

# 2. Mount into an existing aiohttp application under any path.
mount_aiohttp(web_app, app, path="/agents/mcp")

# 3. Standalone, blocking (uvicorn). host and port are required.
serve_http(app, host=HOST, port=PORT)
```

`mount_aiohttp` runs the same ASGI app in-process behind a small
ASGI-over-aiohttp bridge: one any-method route at `path` (plus `path/`), with
the MCP session manager started and stopped by the host's `on_startup` /
`on_cleanup` signals. aiohttp is imported from the host — it is not an
agentfront dependency. The host's own routes, middleware, and bind address
are untouched. The bridge sends response headers as soon as the app starts a
response (so an SSE stream opens immediately), and delivers ASGI
`http.disconnect` when the client goes away mid-response, so long-lived
streams end with their client.

Mounted under a prefix, `path=` is matched *below* the prefix: inside a
Starlette `Mount("/api", app=make_mcp_http_app(app, path="/mcp"))` the
endpoint is `/api/mcp` (the filter strips the ASGI `root_path`), and
`mount_aiohttp(sub, app, path="/mcp")` on a sub-app added with
`host.add_subapp("/api", sub)` answers at `/api/mcp` too.

## Options

`make_mcp_http_app`, `mount_aiohttp` and `serve_http` take the same keyword
options (declared once as `agentfront.mcp_http.McpHttpOptions`; an unknown one
is a `TypeError`):

| Option | Default | Meaning |
|---|---|---|
| `authenticate` | `None` | The caller-context hook (below). |
| `stateless` | `True` | Each POST is a self-contained request/response; no session affinity. |
| `json_response` | `True` | JSON responses instead of SSE streams. |
| `security_settings` | `None` | Passed to the SDK (`mcp.server.transport_security.TransportSecuritySettings`, e.g. DNS-rebinding protection for a public bind). |
| `www_authenticate` | `"Bearer"` | The `WWW-Authenticate` challenge sent with every `401` (RFC 7235), e.g. `'Bearer realm="tools"'`; `None` omits the header. |
| `session_owner_key` | the principal itself | Stateful mode: what identifies a session's owner (see below). |

## Lifecycle

The MCP session manager runs in a background task. ASGI lifespan
(`lifespan.startup` / `lifespan.shutdown`) or the aiohttp host's
`on_startup` / `on_cleanup` start and stop it; a host that sends no lifespan
events (e.g. a mounted sub-app) gets it started lazily on the first request.

- Concurrent lazy starts share one manager; a caller cancelled while the
  manager starts leaves nothing running.
- **Stopping is final.** While `stop()` runs (host cleanup, lifespan shutdown)
  and afterwards, requests are answered `503` with an
  `{"error": {code, message, remediation}}` body, and `start()` raises — the
  endpoint never restarts behind its host's back.
- If the manager dies on its own after startup, the crash is logged and a
  fresh manager starts on the next request. `stop()` logs a failure instead of
  raising it into the host's cleanup.

## Who is calling: the authenticator and `current_caller()`

```python
from agentfront import AgentfrontError, current_caller
from agentfront.mcp_http import CallerRequest

def authenticate(request: CallerRequest):        # may also be async
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    return lookup_principal(token)                # None -> 401

@app.tool
def my_notes() -> list[str]:
    caller = current_caller()
    if caller is None:
        raise AgentfrontError(code=401, message="sign in first", remediation="...")
    return notes_for(caller)

asgi = make_mcp_http_app(app, authenticate=authenticate)
```

- The authenticator runs **before any command**. It gets a framework-neutral
  `CallerRequest` (`method`, `path`, `query_string`, lower-cased `headers`,
  `client`) and returns a caller principal — any object you like — or `None`.
- `None` (or an authenticator that raises) is answered `401` with an
  `{"error": {code, message, remediation}}` body and a `WWW-Authenticate`
  challenge (the `www_authenticate` option); nothing is dispatched.
- The principal reaches command handlers as call context:
  `agentfront.current_caller()` returns it inside the handler (sync or async).
  It is `None` on stdio, on the CLI, and when no authenticator is configured.
- **Auth policy stays yours.** agentfront carries the principal; it never
  interprets it. Which caller may run which command is decided in your
  authenticator and handlers.

Handler signatures are untouched — the principal travels in a context
variable — so input schemas and every surface's catalog are unaffected.

### Stateful sessions belong to their creator

With `stateless=False` the authenticator still runs on every request, and
each MCP session is bound to the principal that initialized it. A request
presenting an `mcp-session-id` whose owner differs is refused `403` (error
payload) before it reaches the session. Principals are opaque, so "same
owner" means `session_owner_key(a) == session_owner_key(b)`; the default key
is the principal itself. Override it when a fresh principal object is built
per request:

```python
make_mcp_http_app(
    app,
    authenticate=claims_from_token,                 # returns {"sub": ..., ...}
    stateless=False,
    session_owner_key=lambda claims: claims["sub"],
)
```

A key function that raises fails closed (`403`).

## Testing per-caller behaviour

`agentfront.testing.call_mcp` takes the same principal without a server:

```python
from agentfront.testing import call_mcp

assert call_mcp(app, ["my_notes"], caller="agent-a") == {"result": [...]}
```

`assert_surfaces_agree(app)` / `surfaces_agree(app)` also cover the remote
transport: the inventory's `mcp_http_tools` entry is read from the structured
command catalog the transport's `run` tool embeds (without standing up the
transport).
