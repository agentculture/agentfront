"""Unified CLI entry point for afi.

Noun-based command groups and globals are registered here. Top-level globals
(``learn``, ``explain``) live under :mod:`afi.cli._commands`; per-noun groups
(``cli``, later ``mcp``, ``site``) are registered via their own ``register()``
functions following the same pattern.

Error propagation contract
--------------------------
Every handler raises :class:`afi.cli._errors.AfiError` on failure; the
top-level ``main()`` catches it via :func:`_dispatch` and routes through
:mod:`afi.cli._output`. Unknown exceptions are wrapped into an ``AfiError``
so no Python traceback leaks to stderr.

Argparse errors (unknown verb, missing required arg) also route through our
structured format — ``_AfiArgumentParser`` overrides ``.error()``. The
subparsers are built with ``parser_class=_AfiArgumentParser`` so subparser
errors follow the same path. Whether the error is emitted as text or JSON
depends on whether ``--json`` appears in the raw argv (:func:`main` sets
``_AfiArgumentParser._json_hint`` before ``parse_args``).
"""

from __future__ import annotations

import argparse
import sys

from afi import __version__
from afi.cli._errors import EXIT_USER_ERROR, AfiError
from afi.cli._output import emit_error

# Note: _commands submodules are imported lazily inside :func:`_build_parser`
# to avoid a circular dependency. afi.cite._engine imports afi.cli._errors;
# eagerly loading afi.cli._commands.cli (which imports afi.cite) at module
# init would create a cycle when afi.cite is the first-touched package.


class _AfiArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that routes errors through :func:`emit_error`.

    Argparse's default error handler writes ``prog: error: <msg>`` to stderr
    and exits with code 2. That skips our AfiError plumbing and — crucially —
    produces no ``hint:`` line, which would make afi itself fail the rubric's
    error-propagation bundle. This subclass emits our structured error format
    instead and exits with :attr:`EXIT_USER_ERROR`.

    JSON mode: parse-time errors happen before ``args.json`` is populated, so
    we rely on a class-level ``_json_hint`` that :func:`main` pre-populates
    by scanning the raw argv for ``--json`` / ``--json=…``. Best-effort and
    shared across all subparser instances (argparse's subparser factory
    produces instances of the class but doesn't thread state).
    """

    _json_hint: bool = False

    def error(self, message: str) -> None:  # type: ignore[override]
        err = AfiError(
            code=EXIT_USER_ERROR,
            message=message,
            remediation=f"run '{self.prog} --help' to see valid arguments",
        )
        emit_error(err, json_mode=type(self)._json_hint)
        raise SystemExit(err.code)


def _argv_has_json(argv: list[str] | None) -> bool:
    tokens = argv if argv is not None else sys.argv[1:]
    return any(t == "--json" or t.startswith("--json=") for t in tokens)


def _build_parser() -> argparse.ArgumentParser:
    # Deferred imports (see module-level note): avoids afi.cite ↔ afi.cli cycle.
    from afi.cli._commands import cli as _cli_group
    from afi.cli._commands import explain as _explain_cmd
    from afi.cli._commands import learn as _learn_cmd
    from afi.cli._commands import overview as _overview_cmd

    parser = _AfiArgumentParser(
        prog="afi",
        description="afi — Agent First Interface scaffolder",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    # parser_class propagates to every subparser so their .error() routes
    # through _AfiArgumentParser too. Without this, `afi cli bogus --foo`
    # would hit argparse's default error path (no hint: line, wrong code).
    sub = parser.add_subparsers(dest="command", parser_class=_AfiArgumentParser)

    # Globals (top-level, not nested under a noun).
    _learn_cmd.register(sub)
    _explain_cmd.register(sub)
    _overview_cmd.register(sub)

    # Noun groups.
    _cli_group.register(sub)
    # Future noun groups (mcp, site) will register here in v0.4 / v0.5.

    return parser


def _dispatch(args: argparse.Namespace) -> int:
    """Invoke the registered handler and translate exceptions to exit codes.

    Handler protocol: a handler may return ``None`` (treated as success,
    exit 0) or an ``int`` (used directly as the exit code). Failures MUST
    raise :class:`AfiError`; any other exception is wrapped into one so no
    Python traceback leaks.
    """
    json_mode = bool(getattr(args, "json", False))
    try:
        rc = args.func(args)
    except AfiError as err:
        emit_error(err, json_mode=json_mode)
        return err.code
    except Exception as err:  # noqa: BLE001 - last-resort; wrap and route cleanly
        wrapped = AfiError(
            code=EXIT_USER_ERROR,
            message=f"unexpected: {err.__class__.__name__}: {err}",
            remediation="file a bug at https://github.com/agentculture/afi-cli/issues",
        )
        emit_error(wrapped, json_mode=json_mode)
        return wrapped.code
    return rc if rc is not None else 0


def main(argv: list[str] | None = None) -> int:
    # Pre-parse peek so argparse-level errors honour --json.
    _AfiArgumentParser._json_hint = _argv_has_json(argv)
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
