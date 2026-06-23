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
standard library, and only the MCP server surface pulls a wire SDK. If you want
that surface, install the extra directly:

```bash
uv tool install "agentfront[mcp]"   # CLI + HTTP + MCP server
```

**This wrapper deliberately exposes no `teken[mcp]` extra.** `teken` is a
deprecated alias whose only job is to keep `uv tool install teken` resolving to
`agentfront`; growing a parallel `[mcp]` extra here would widen the
version-lockstep surface for no real consumers (none use the MCP surface through
the wrapper). MCP users should depend on `agentfront[mcp]` directly. See
[issue #31](https://github.com/agentculture/agentfront/issues/31).

New code should depend on `agentfront` directly. This wrapper is published in
lockstep with `agentfront` and will be retired once the migration window closes.
