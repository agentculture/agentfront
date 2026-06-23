# Quickstart Example

A minimal third-party package built on agentfront.

## Usage

```python
from mytool import app

# HTTP surface — WSGI app serving markdown docs + sitemap
http_app = app.http_app()

# MCP surface — an mcp.server.Server exposing tools.
# Needs the optional `mcp` extra: install agentfront[mcp].
mcp_server = app.mcp_server()

# CLI surface — argparse parser
cli = app.cli()
```

## Surfaces

- **HTTP**: `GET /quickstart` and `GET /reference` serve markdown; `GET /sitemap.xml` lists them.
- **MCP**: `list_tools` returns `add` and `greet`. Requires the `agentfront[mcp]` extra.
- **CLI**: `mytool learn` prints a summary; `mytool doctor` runs a readiness check.
