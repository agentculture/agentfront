"""Unified CLI entry point for agentfront.

Noun-based command groups and globals are registered here. Top-level globals
(``learn``, ``explain``) live under :mod:`agentfront.cli._commands`; per-noun groups
(``cli``, later ``mcp``, ``site``) are registered via their own ``register()``
functions following the same pattern.

Error propagation contract
--------------------------
Every handler raises :class:`agentfront.errors.AgentfrontError` on failure; the
top-level ``main()`` catches it via :func:`_dispatch` and routes through
:mod:`agentfront.cli._output`. Unknown exceptions are wrapped into an ``AgentfrontError``
so no Python traceback leaks to stderr.

Argparse errors (unknown verb, missing required arg) also route through our
structured format — :class:`agentfront._cli_core.StructuredArgumentParser` overrides
``.error()``. The subparsers are built with ``parser_class=StructuredArgumentParser``
so subparser errors follow the same path. Whether the error is emitted as text or JSON
depends on whether ``--json`` appears in the raw argv (:func:`main` sets
``StructuredArgumentParser._json_hint`` before ``parse_args``).
"""

from __future__ import annotations

import argparse
import sys

from agentfront import __version__, _brand
from agentfront._cli_core import (
    StructuredArgumentParser,
    argv_has_json,
    dispatch,
)

# Note: _commands submodules are imported lazily inside :func:`_build_parser`
# to keep import of :mod:`agentfront.cli` cheap and avoid eagerly pulling in the
# overview/rubric machinery at module init.


def _build_parser() -> argparse.ArgumentParser:
    # Deferred imports (see module-level note): keeps `import agentfront.cli` cheap.
    from agentfront.cli._commands import cli as _cli_group
    from agentfront.cli._commands import doctor as _doctor_cmd
    from agentfront.cli._commands import explain as _explain_cmd
    from agentfront.cli._commands import learn as _learn_cmd
    from agentfront.cli._commands import overview as _overview_cmd

    parser = StructuredArgumentParser(
        prog=_brand.PROG,
        description=f"{_brand.PROG} — Agent First Interface runtime",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    # parser_class propagates to every subparser so their .error() routes
    # through StructuredArgumentParser too. Without this, `agentfront cli bogus --foo`
    # would hit argparse's default error path (no hint: line, wrong code).
    sub = parser.add_subparsers(dest="command", parser_class=StructuredArgumentParser)

    # Globals (top-level, not nested under a noun).
    _learn_cmd.register(sub)
    _explain_cmd.register(sub)
    _overview_cmd.register(sub)
    _doctor_cmd.register(sub)

    # Noun groups.
    _cli_group.register(sub)
    # Future noun groups (mcp, site) will register here in v0.4 / v0.5.

    return parser


def _dispatch(args: argparse.Namespace) -> int:
    """Invoke the registered handler and translate exceptions to exit codes.

    Delegates to :func:`agentfront._cli_core.dispatch` with agentfront's
    brand-specific ``issues_url``.
    """
    json_mode = bool(getattr(args, "json", False))
    return dispatch(
        args,
        issues_url=_brand.ISSUES_URL,
        json_mode=json_mode,
    )


def main(argv: list[str] | None = None) -> int:
    # Pre-parse peek so argparse-level errors honour --json.
    StructuredArgumentParser._json_hint = argv_has_json(argv)
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return _dispatch(args)


def main_teken_alias(argv: list[str] | None = None) -> int:
    """Entry point for the deprecated ``teken`` command.

    The project was renamed ``teken`` → ``agentfront``. The ``teken`` console script is
    retained as an alias; it prints a one-line deprecation note to **stderr**
    (never stdout, so ``--json`` output stays clean) and forwards to :func:`main`.
    """
    print(
        f"deprecated: the '{_brand.LEGACY_PROG}' command is now '{_brand.PROG}'; "
        f"'{_brand.LEGACY_PROG}' will be removed in a future release.",
        file=sys.stderr,
    )
    return main(argv)


if __name__ == "__main__":
    sys.exit(main())
