# teken — deprecated alias for `agentfront`

`teken` was renamed to **[`agentfront`](https://pypi.org/project/agentfront/)**.
This package is a thin compatibility wrapper: installing it pulls in
`agentfront`, which provides the canonical `agentfront` command and a deprecated
`teken` alias.

```bash
uv tool install teken       # still works — installs agentfront under the hood
uv tool install agentfront  # preferred going forward
```

## MCP surface

As of `agentfront` 0.11.0 the official [`mcp`](https://pypi.org/project/mcp/)
SDK is an **optional extra** — `agentfront`'s CLI and HTTP surfaces are pure
standard library, and only the MCP server surface pulls a wire SDK. The wrapper
mirrors that extra at parity, so either install gives you the MCP server:

```bash
uv tool install "agentfront[mcp]"   # canonical
uv tool install "teken[mcp]"        # wrapper parity — pulls agentfront[mcp]
```

`teken[mcp]` simply depends on `agentfront[mcp]==<same version>`, kept in
lockstep with the canonical project (see
[issue #31](https://github.com/agentculture/agentfront/issues/31)).

New code should depend on `agentfront` directly. This wrapper is published in
lockstep with `agentfront` and will be retired once the migration window closes.
