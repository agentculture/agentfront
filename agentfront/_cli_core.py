"""Shared CLI dispatch and error machinery.

Parameterised out of agentfront's branding so both agentfront's own CLI and a
consumer's generated CLI can reuse one implementation.

This module is stdlib-only (plus agentfront.errors and agentfront.cli._output).
It does NOT import the brand module.
"""

from __future__ import annotations

import argparse
import sys

from agentfront.cli._output import emit_error
from agentfront.errors import EXIT_USER_ERROR, AgentfrontError


def argv_has_json(argv: list[str] | None) -> bool:
    """Pre-parse raw argv for a ``--json`` hint."""
    tokens = argv if argv is not None else sys.argv[1:]
    return any(t == "--json" or t.startswith("--json=") for t in tokens)


class StructuredArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that routes parse-time errors through structured emit_error.

    Honours a pre-parse ``--json`` hint via the class-level ``_json_hint``
    attribute. Subparsers created with ``parser_class=StructuredArgumentParser``
    inherit the class-level state automatically.
    """

    _json_hint: bool = False

    def error(self, message: str) -> None:  # type: ignore[override]
        err = AgentfrontError(
            code=EXIT_USER_ERROR,
            message=message,
            remediation=f"run '{self.prog} --help' to see valid arguments",
        )
        emit_error(err, json_mode=type(self)._json_hint)
        raise SystemExit(err.code)


def dispatch(
    args: argparse.Namespace,
    *,
    issues_url: str,
    json_mode: bool,
) -> int:
    """Invoke the registered handler and translate exceptions to exit codes.

    Handler protocol: a handler may return ``None`` (treated as success,
    exit 0) or an ``int`` (used directly as the exit code). Failures MUST
    raise :class:`AgentfrontError`; any other exception is wrapped into one so
    no Python traceback leaks.
    """
    try:
        rc = args.func(args)
    except AgentfrontError as err:
        emit_error(err, json_mode=json_mode)
        return err.code
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as err:  # noqa: BLE001 - last-resort; wrap and route cleanly
        wrapped = AgentfrontError(
            code=EXIT_USER_ERROR,
            message=f"unexpected: {err.__class__.__name__}: {err}",
            remediation=f"file a bug at {issues_url}",
        )
        emit_error(wrapped, json_mode=json_mode)
        return wrapped.code
    return rc if rc is not None else 0
