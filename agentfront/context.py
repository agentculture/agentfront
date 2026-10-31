"""Per-call caller context — who is invoking a command right now.

The remote MCP transport (:mod:`agentfront.mcp_http`) runs a consumer-supplied
authenticator before any command and gets back a *caller principal* — any
object the consumer chooses (a user id, a dict of claims, a dataclass). That
principal is made available to command handlers as call context::

    from agentfront import current_caller

    @app.tool
    def my_notes() -> list[str]:
        caller = current_caller()       # None on stdio / CLI / unauthenticated
        return notes_for(caller)

agentfront only *carries* the principal; what it means and which commands a
caller may run is the consumer's policy. Handler signatures (and therefore
the registry's input schemas and every surface's catalog) are untouched —
the principal travels in a :mod:`contextvars` variable, which follows ``await``
chains, so it is visible to sync and async handlers alike.

Stdlib only, so it is importable without the optional ``agentfront[mcp]``
extra.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator

__all__ = ["current_caller", "caller_context"]

_CALLER: contextvars.ContextVar[Any] = contextvars.ContextVar("agentfront_caller", default=None)


def current_caller() -> Any:
    """Return the principal of the call in progress, or ``None``.

    ``None`` means "no authenticated caller": the stdio MCP server, the CLI,
    the in-process harness without ``caller=``, or a remote transport mounted
    without an authenticator.
    """
    return _CALLER.get()


@contextmanager
def caller_context(principal: Any) -> Iterator[Any]:
    """Run the enclosed block with *principal* as the current caller.

    Restores the previous caller on exit (including on exception), so nested
    and concurrent calls never see each other's principal.
    """
    token = _CALLER.set(principal)
    try:
        yield principal
    finally:
        _CALLER.reset(token)
