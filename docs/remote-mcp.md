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
are untouched.

Defaults are `stateless=True, json_response=True`: every POST is a
self-contained request/response, which needs no session affinity. Both are
overridable, as is the SDK's `security_settings`
(`mcp.server.transport_security.TransportSecuritySettings`, e.g. to enable
DNS-rebinding protection for a public bind).

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
  `{"error": {code, message, remediation}}` body; nothing is dispatched.
- The principal reaches command handlers as call context:
  `agentfront.current_caller()` returns it inside the handler (sync or async).
  It is `None` on stdio, on the CLI, and when no authenticator is configured.
- **Auth policy stays yours.** agentfront carries the principal; it never
  interprets it. Which caller may run which command is decided in your
  authenticator and handlers.

Handler signatures are untouched — the principal travels in a context
variable — so input schemas and every surface's catalog are unaffected.

## Testing per-caller behaviour

`agentfront.testing.call_mcp` takes the same principal without a server:

```python
from agentfront.testing import call_mcp

assert call_mcp(app, ["my_notes"], caller="agent-a") == {"result": [...]}
```

`assert_surfaces_agree(app)` / `surfaces_agree(app)` also cover the remote
transport: the inventory's `mcp_http_tools` entry is read from the command
catalog of the transport's own `run` tool.
