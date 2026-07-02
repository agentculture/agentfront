"""Public consumer testing harness for apps built on ``agentfront``.

A host app built with :class:`agentfront.App` gets its CLI, MCP, and HTTP
surfaces generated for free — this package is the matching harness for
*testing* that app: in-process CLI invocation (no subprocess), in-process MCP
dispatch (no ``mcp`` package import required), a cross-surface agreement
assertion, and TAUI drive/parity/replay helpers, so a consumer's own test
suite can prove its surfaces never drift apart and that its agent and human
audiences see the same world.

``resume`` (``agentfront.taui.snapshot.resume``) is re-exported LAZILY via a
module-level ``__getattr__`` (PEP 562), forwarding to
:mod:`agentfront.testing.taui`'s own lazy re-export — see that module's
docstring. Everything else here is imported eagerly.
"""

from __future__ import annotations

from typing import Any

from agentfront.testing import taui as _taui
from agentfront.testing.agreement import assert_surfaces_agree
from agentfront.testing.cli import CliResult, run_cli
from agentfront.testing.mcp import call_mcp
from agentfront.testing.taui import (
    Snapshot,
    assert_agent_human_parity,
    assert_replay_equivalent,
    drive,
    read_snapshot,
    replay,
    write_snapshot,
)

__all__ = [  # noqa: F822 — "resume" is a lazy PEP 562 attribute, resolved by __getattr__ below
    "CliResult",
    "run_cli",
    "assert_surfaces_agree",
    "call_mcp",
    "drive",
    "assert_agent_human_parity",
    "assert_replay_equivalent",
    "write_snapshot",
    "read_snapshot",
    "replay",
    "Snapshot",
    "resume",
]


def __getattr__(name: str) -> Any:
    """PEP 562 lazy module attribute — forwards to ``agentfront.testing.taui``."""
    if name == "resume":
        return _taui.resume
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
