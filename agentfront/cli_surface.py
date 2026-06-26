"""CLI surface derived from an :class:`agentfront.App`.

The host writes **zero** argparse code — building the CLI is just
``make_cli(app)``.  The surface reads from the App's single registry so it
cannot drift out of sync with the MCP or HTTP surfaces.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from typing import TYPE_CHECKING, Any, Callable

from agentfront.app import App

if TYPE_CHECKING:
    from agentfront._registry import ToolEntry

__all__ = ["make_cli", "run_cli"]


# ---------------------------------------------------------------------------
# Local parser — avoids importing agentfront._cli_core at module level, which
# would create a circular import (cli_surface → _cli_core → cli._output →
# cli.__init__ → _cli_core).  We only need a structured-error parser here;
# the full _cli_core machinery is reserved for agentfront's own CLI.
# ---------------------------------------------------------------------------


class _CliParser(argparse.ArgumentParser):
    """ArgumentParser that signals exit via an internal exception.

    argparse normally calls :func:`sys.exit` for ``--help`` (code 0) and parse
    errors (code 2). ``run_cli`` needs to *translate* those into a return value
    (so hosts and tests can call it in-process), but catching ``SystemExit`` to
    do that is both flagged by static analysis (SonarCloud S5754) and would
    silently swallow a genuine ``sys.exit`` raised by a tool handler. Overriding
    :meth:`exit` to raise a private exception keeps the translation local and
    precise: only argparse's own exits are intercepted.
    """

    class _Exit(Exception):
        """Carries argparse's intended exit code out to ``run_cli``."""

        def __init__(self, code: int) -> None:
            super().__init__(code)
            self.code = code

    def exit(self, status: int = 0, message: str | None = None) -> Any:  # type: ignore[override]
        if message:
            self._print_message(message, sys.stderr)
        raise self._Exit(status)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_args_from_sig(
    parser: argparse.ArgumentParser,
    func: Callable[..., Any],
) -> None:
    """Add arguments to *parser* derived from *func*'s signature.

    - Required params (no default) → positional arguments in order.
    - Params with defaults → optional ``--flag`` with that default.
    - bool-annotated params → ``--flag/--no-flag`` (BooleanOptionalAction).
    - Type hints used for ``type=`` (int/float/str).
    """
    try:
        hints = __import__("typing").get_type_hints(func)
    except Exception:
        hints = {}

    sig = inspect.signature(func)
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        annotation = hints.get(pname, param.annotation)

        if param.default is inspect.Parameter.empty:
            # Required → positional
            kwargs: dict[str, Any] = {}
            if annotation in (int, float, str):
                kwargs["type"] = annotation
            parser.add_argument(pname, **kwargs)
        else:
            # Has default → optional flag
            if annotation is bool:
                parser.add_argument(
                    f"--{pname}",
                    action="store_true",
                    default=param.default,
                    dest=pname,
                )
                parser.add_argument(
                    f"--no-{pname}",
                    action="store_false",
                    default=not param.default,
                    dest=pname,
                )
            else:
                kwargs = {"default": param.default, "dest": pname}
                if annotation in (int, float, str):
                    kwargs["type"] = annotation
                parser.add_argument(f"--{pname}", **kwargs)


def _make_dispatcher(entry: "ToolEntry") -> Callable[[argparse.Namespace], int]:
    """Return a dispatch function that calls *entry*.func with parsed kwargs."""

    def dispatcher(args: argparse.Namespace) -> int:
        from agentfront.cli._output import emit_result

        json_mode = bool(getattr(args, "json", False))
        # Collect parameter values from the namespace
        sig = inspect.signature(entry.func)
        kwargs: dict[str, Any] = {}
        for pname in sig.parameters:
            if pname == "self":
                continue
            if hasattr(args, pname):
                kwargs[pname] = getattr(args, pname)

        result = entry.func(**kwargs)
        if result is not None:
            emit_result(result, json_mode=json_mode)
        return 0

    return dispatcher


def _group_overview_handler(
    group_name: str,
    tools_in_group: list["ToolEntry"],
) -> Callable[[argparse.Namespace], int]:
    """Handler for bare noun group — renders overview of child verbs."""

    def handler(args: argparse.Namespace) -> int:
        lines: list[str] = []
        lines.append(f"Available commands in {group_name}:")
        for entry in tools_in_group:
            desc = entry.description or ""
            lines.append(f"  {entry.name}: {desc}")
        print("\n".join(lines))
        return 0

    return handler


def _explain_handler(app: App, args: argparse.Namespace) -> int:
    """Dispatch for the ``explain`` verb — prints an op's doc or group listing."""
    from agentfront.errors import EXIT_USER_ERROR, AgentfrontError

    path = tuple(args.path) if args.path else ()
    if not path:
        # No path given — show root overview
        print(f"# {app.name} v{app.version}")
        if app.description:
            print(app.description)
        return 0

    entry = app.get_by_path(path)
    if entry is not None:
        # Leaf op found — print its doc
        doc = entry.doc or entry.description or ""
        if args.json:
            payload: dict[str, Any] = {"path": list(path), "doc": doc}
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(doc if doc.endswith("\n") else doc + "\n")
        return 0

    # Path is a group prefix — list child verbs
    children: list[tuple[str, str]] = []
    for tool in app.list_tools():
        full = tool.group + (tool.name,)
        if full[: len(path)] == path and len(full) > len(path):
            child_name = full[len(path)]
            children.append((child_name, tool.description or ""))

    if children:
        if args.json:
            payload = {
                "path": list(path),
                "children": [{"name": n, "description": d} for n, d in children],
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            lines: list[str] = []
            lines.append(f"Available commands in {' '.join(path)}:")
            for name, desc in children:
                lines.append(f"  {name}: {desc}")
            print("\n".join(lines))
        return 0

    # Unknown path
    raise AgentfrontError(
        code=EXIT_USER_ERROR,
        message=f"no such path: {' '.join(path)}",
        remediation=f"check available paths with '{app.name} overview'",
    )


def _overview_handler(app: App, args: argparse.Namespace) -> int:
    """Dispatch for the ``overview`` verb — lists registry nouns."""
    # Collect top-level nouns: groups (first element) and top-level ops
    seen: dict[str, str] = {}  # name -> description
    for tool in app.list_tools():
        if tool.group:
            noun = tool.group[0]
            if noun not in seen:
                count = len([t for t in app.list_tools() if t.group and t.group[0] == noun])
                seen[noun] = f"group with {count} commands"
        else:
            if tool.name not in seen:
                seen[tool.name] = tool.description or ""

    if args.scope:
        # Scoped to a specific noun
        noun = args.scope
        children: list[tuple[str, str]] = []
        for tool in app.list_tools():
            if tool.group and tool.group[0] == noun:
                children.append((tool.name, tool.description or ""))
            elif not tool.group and tool.name == noun:
                children.append((tool.name, tool.description or ""))

        if args.json:
            payload = {"noun": noun, "verbs": [{"name": n, "description": d} for n, d in children]}
            print(json.dumps(payload, ensure_ascii=False))
        else:
            lines: list[str] = []
            lines.append(f"Commands in {noun}:")
            for name, desc in children:
                lines.append(f"  {name}: {desc}")
            print("\n".join(lines))
        return 0

    # Full overview
    if args.json:
        payload = [{"name": name, "description": desc} for name, desc in seen.items()]
        print(json.dumps(payload, ensure_ascii=False))
    else:
        lines: list[str] = []
        lines.append(f"{app.name} — available commands")
        for name, desc in seen.items():
            lines.append(f"  {name}: {desc}")
        print("\n".join(lines))
    return 0


def _learn_handler(app: App, args: argparse.Namespace) -> int:
    """Dispatch for the ``learn`` verb — prints the agent-facing summary."""
    docs = [{"slug": d.slug, "title": d.title} for d in app.list_docs()]
    tools: list[dict[str, Any]] = []
    for t in app.list_tools():
        path_parts = list(t.group) + [t.name]
        tools.append({"path": path_parts, "name": t.name, "description": t.description})

    if args.json:
        payload: dict[str, Any] = {
            "name": app.name,
            "version": app.version,
            "docs": docs,
            "tools": tools,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        lines: list[str] = []
        lines.append(f"# {app.name} v{app.version}")
        if app.description:
            lines.append(app.description)
        lines.append("")

        lines.append("## Docs")
        for d in docs:
            lines.append(f"  - {d['slug']}: {d['title']}")
        lines.append("")

        lines.append("## Tools")
        for t in tools:
            path_str = " ".join(t["path"])
            lines.append(f"  - {path_str}: {t['description']}")
        lines.append("")

        print("\n".join(lines))
    return 0


def _doctor_handler(app: App, args: argparse.Namespace) -> int:
    """Dispatch for the ``doctor`` verb — prints a readiness check."""
    doc_count = len(app.list_docs())
    tool_count = len(app.list_tools())

    lines: list[str] = []
    lines.append(f"{app.name} v{app.version} — readiness check")
    lines.append(f"  docs: {doc_count}")
    lines.append(f"  tools: {tool_count}")
    lines.append("  status: healthy")
    print("\n".join(lines))
    return 0


def _dispatch(args: argparse.Namespace, *, json_mode: bool) -> int:
    """Invoke the registered handler and translate exceptions to exit codes.

    AgentfrontError → structured stderr + code, KeyboardInterrupt → 130,
    unexpected → wrapped, no traceback.
    """
    from agentfront.cli._output import emit_error
    from agentfront.errors import EXIT_USER_ERROR, AgentfrontError

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
            remediation="report this issue",
        )
        emit_error(wrapped, json_mode=json_mode)
        return wrapped.code
    return rc if rc is not None else 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_cli(app: App) -> argparse.ArgumentParser:
    """Build an argparse parser from an :class:`App`'s registry.

    Creates nested noun-group subparsers for each registered tool, host
    commands, and the learn/doctor meta-verbs.
    """
    from agentfront._registry import ToolEntry, apply_flags

    parser = _CliParser(
        prog=app.name,
        description=f"{app.name} v{app.version}",
    )

    sub = parser.add_subparsers(dest="command")

    # --- learn, explain, overview, and doctor meta-verbs ------------------
    learn_parser = sub.add_parser("learn", help="agent-facing summary")
    learn_parser.add_argument("--json", action="store_true", help="emit JSON")
    learn_parser.set_defaults(func=lambda a: _learn_handler(app, a))

    explain_parser = sub.add_parser("explain", help="explain a command or group")
    explain_parser.add_argument("path", nargs="*", help="command path (e.g. feedback record)")
    explain_parser.add_argument("--json", action="store_true", help="emit JSON")
    explain_parser.set_defaults(func=lambda a: _explain_handler(app, a))

    overview_parser = sub.add_parser("overview", help="list available commands")
    overview_parser.add_argument("scope", nargs="?", help="optional noun to scope to")
    overview_parser.add_argument("--json", action="store_true", help="emit JSON")
    overview_parser.set_defaults(func=lambda a: _overview_handler(app, a))

    doctor_parser = sub.add_parser("doctor", help="readiness check")
    doctor_parser.set_defaults(func=lambda a: _doctor_handler(app, a))

    # --- grouped tools: build nested subparser chains -------------------
    # Map from group prefix → subparser action so siblings share the same
    # intermediate group subparser.
    group_subparsers: dict[tuple[str, ...], argparse._SubParsersAction] = {}
    group_parsers: dict[tuple[str, ...], argparse.ArgumentParser] = {}

    # Collect tools by group for overview handlers
    tools_by_group: dict[tuple[str, ...], list[ToolEntry]] = {}

    for entry in app.list_tools():
        if not entry.group:
            # Top-level tool: add directly under root subparsers
            verb_parser = sub.add_parser(
                entry.name,
                help=entry.description,
                aliases=list(entry.aliases),
            )
            _derive_args_from_sig(verb_parser, entry.func)
            apply_flags(verb_parser, entry)
            verb_parser.add_argument("--json", action="store_true", help="emit JSON")
            verb_parser.set_defaults(func=_make_dispatcher(entry))
            continue

        # Build nested chain for grouped tool
        group = entry.group
        current_sub = sub

        # Walk/create intermediate group parsers
        for i, noun in enumerate(group):
            prefix = group[: i + 1]
            if prefix not in group_parsers:
                # Create the group subparser
                group_parser = current_sub.add_parser(
                    noun,
                    help=f"commands for {noun}",
                )
                group_parsers[prefix] = group_parser
                # Collect tools for this group
                tools_by_group[prefix] = []
                # Create sub-subparsers for the next level
                next_sub = group_parser.add_subparsers(
                    dest=f"command_{i}",
                )
                group_subparsers[prefix] = next_sub
                current_sub = next_sub
            else:
                # Reuse existing group parser's subparsers
                current_sub = group_subparsers[prefix]

        # Add the leaf verb
        verb_parser = current_sub.add_parser(
            entry.name,
            help=entry.description,
            aliases=list(entry.aliases),
        )
        _derive_args_from_sig(verb_parser, entry.func)
        apply_flags(verb_parser, entry)
        verb_parser.add_argument("--json", action="store_true", help="emit JSON")
        verb_parser.set_defaults(func=_make_dispatcher(entry))

        # Register this tool in its group for overview
        if group not in tools_by_group:
            tools_by_group[group] = []
        tools_by_group[group].append(entry)

    # Set up bare-noun overview handlers on each group parser
    for prefix, tools_list in tools_by_group.items():
        group_parser = group_parsers.get(prefix)
        if group_parser is not None:
            group_name = prefix[-1]
            group_parser.set_defaults(func=_group_overview_handler(group_name, tools_list))

    # --- host commands --------------------------------------------------
    for cmd in app.list_commands():
        cmd_parser = sub.add_parser(
            cmd.name,
            help=cmd.help,
            aliases=list(cmd.aliases),
        )
        if cmd.configure is not None:
            cmd.configure(cmd_parser)
        cmd_parser.set_defaults(func=cmd.handler)

    return parser


def run_cli(app: App, argv: list[str] | None = None) -> int:
    """Parse *argv* against *app*'s CLI and dispatch.

    Returns an exit code. Dispatches via :func:`_dispatch` for structured
    error handling (AgentfrontError → structured stderr + code,
    KeyboardInterrupt → 130, unexpected → wrapped, no traceback).
    """
    parser = make_cli(app)

    try:
        args = parser.parse_args(argv)
    except _CliParser._Exit as exc:
        # argparse exits 0 for --help and 2 for a parse error
        return exc.code

    # No subcommand given
    if not hasattr(args, "command") or getattr(args, "command", None) is None:
        if app.no_command_handler is not None:
            return app.no_command_handler(args)
        parser.print_help()
        return 0

    # Dispatch with structured error handling
    json_mode = bool(getattr(args, "json", False))
    return _dispatch(args, json_mode=json_mode)
