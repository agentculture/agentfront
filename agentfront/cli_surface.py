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
    from agentfront._registry import Flag, ToolEntry

__all__ = ["make_cli", "run_cli"]

# Help string shared by every ``--json`` flag across the generated surface.
_JSON_HELP = "emit JSON"


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

    Parse-time errors (unknown verbs, missing required args) are emitted as
    structured :class:`AgentfrontError` messages honouring ``--json``.
    """

    class _Exit(Exception):
        """Carries argparse's intended exit code out to ``run_cli``."""

        def __init__(self, code: int) -> None:
            super().__init__(code)
            self.code = code

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._raw_argv: list[str] | None = None

    def _set_raw_argv(self, argv: list[str] | None) -> None:
        """Store raw argv so ``error()`` can peek for ``--json``."""
        self._raw_argv = argv

    @staticmethod
    def _has_json_flag(argv: list[str] | None) -> bool:
        """Pre-parse peek: does *argv* contain ``--json``?"""
        if argv is None:
            return False
        return "--json" in argv

    def error(self, message: str) -> Any:  # type: ignore[override]
        """Emit a structured parse-time error and exit with code 1.

        Honours a pre-parse ``--json`` peek on the raw argv.
        """
        from agentfront.cli._output import emit_error
        from agentfront.errors import EXIT_USER_ERROR, AgentfrontError

        json_mode = self._has_json_flag(self._raw_argv)
        err = AgentfrontError(
            code=EXIT_USER_ERROR,
            message=message,
            remediation="check usage with --help",
        )
        emit_error(err, json_mode=json_mode)
        raise self._Exit(EXIT_USER_ERROR)

    def exit(self, status: int = 0, message: str | None = None) -> Any:  # type: ignore[override]
        if message:
            self._print_message(message, sys.stderr)
        raise self._Exit(status)


def _propagate_raw_argv(parser: _CliParser, argv: list[str] | None) -> None:
    """Set ``_raw_argv`` on *parser* and all its descendant ``_CliParser`` subparsers."""
    parser._set_raw_argv(argv)
    # Walk subparsers created via add_subparsers(parser_class=_CliParser)
    if parser._subparsers is None:
        return
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action._name_parser_map.values():
                if isinstance(sub, _CliParser):
                    _propagate_raw_argv(sub, argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_param_argument(
    parser: argparse.ArgumentParser,
    pname: str,
    param: inspect.Parameter,
    annotation: Any,
) -> None:
    """Add a single argparse argument derived from one function parameter."""
    if param.default is inspect.Parameter.empty:
        # Required → positional
        kwargs: dict[str, Any] = {}
        if annotation in (int, float, str):
            kwargs["type"] = annotation
        parser.add_argument(pname, **kwargs)
    elif annotation is bool:
        # bool with default → --flag/--no-flag
        parser.add_argument(
            f"--{pname}",
            action=argparse.BooleanOptionalAction,
            default=param.default,
            dest=pname,
        )
    else:
        # Other default → optional --flag
        kwargs = {"default": param.default, "dest": pname}
        if annotation in (int, float, str):
            kwargs["type"] = annotation
        parser.add_argument(f"--{pname}", **kwargs)


def _covering_flag(pname: str, flags: tuple["Flag", ...]) -> "Flag | None":
    """Return the explicit Flag that covers signature param *pname*, if any.

    A Flag covers *pname* when it writes to the same dest (``dest == pname``)
    or declares the ``--<pname>`` long option that signature-derivation would
    otherwise create — either way argparse would collide on the duplicate
    option string. The covered param is dropped from signature-derivation so
    the explicit Flag (with its choices/type) is the only one added.
    """
    option = "--" + pname
    for flag in flags:
        if flag.dest == pname or option in flag.names:
            return flag
    return None


def _derive_args_from_sig(
    parser: argparse.ArgumentParser,
    func: Callable[..., Any],
    flags: tuple["Flag", ...] = (),
) -> dict[str, Any]:
    """Add arguments to *parser* derived from *func*'s signature.

    Params declared by an explicit :class:`Flag` in *flags* are skipped so the
    Flag (with its choices/type) is the sole source for that argument.

    Returns a dict mapping covered param names to their signature defaults, for
    every covered param that has a default (so the caller can backfill the
    default onto the Flag's argparse action).

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
    covered_defaults: dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        covering = _covering_flag(pname, flags)
        if covering is not None:
            if param.default is not inspect.Parameter.empty:
                covered_defaults[pname] = param.default
            continue
        annotation = hints.get(pname, param.annotation)
        _add_param_argument(parser, pname, param, annotation)
    return covered_defaults


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


def _collect_path_children(app: App, path: tuple[str, ...]) -> list[tuple[str, str]]:
    """Child ``(name, description)`` pairs one level below *path* in the registry."""
    children: list[tuple[str, str]] = []
    for tool in app.list_tools():
        full = tool.group + (tool.name,)
        if full[: len(path)] == path and len(full) > len(path):
            children.append((full[len(path)], tool.description or ""))
    return children


def _flag_label(flag: "Flag") -> str:
    """One human-facing line for a flag in the explain ``Flags:`` section."""
    label = ", ".join(flag.names)
    if flag.choices is not None:
        label += " {" + ",".join(str(c) for c in flag.choices) + "}"
    parts = [f"  {label}"]
    if flag.help:
        parts.append(flag.help)
    if flag.required:
        parts.append("(required)")
    return "  ".join(parts)


def _flag_json(flag: "Flag") -> dict[str, Any]:
    """Structured view of a flag for ``explain --json``."""
    payload: dict[str, Any] = {
        "names": list(flag.names),
        "help": flag.help,
        "required": flag.required,
    }
    if flag.choices is not None:
        payload["choices"] = list(flag.choices)
    return payload


def _print_leaf_doc(
    path: tuple[str, ...],
    doc: str,
    json_mode: bool,
    flags: "tuple[Flag, ...]" = (),
) -> None:
    """Render a single op's doc (the ``explain <path>`` leaf case).

    When the op declares flags, they are surfaced too: a ``Flags:`` section in
    text mode and a ``flags`` array in JSON mode (each entry carrying ``names``,
    ``help``, ``required``, and — for a flag declared with ``choices`` — the
    allowed value set). The ``flags`` key is omitted entirely when the op
    declares none, so a flag-less op renders exactly as before.
    """
    if json_mode:
        payload: dict[str, Any] = {"path": list(path), "doc": doc}
        if flags:
            payload["flags"] = [_flag_json(f) for f in flags]
        print(json.dumps(payload, ensure_ascii=False))
    else:
        body = doc if doc.endswith("\n") else doc + "\n"
        if flags:
            flag_lines = "\n".join(_flag_label(f) for f in flags)
            body = f"{body}\nFlags:\n{flag_lines}\n"
        print(body)


def _print_group_children(
    path: tuple[str, ...], children: list[tuple[str, str]], json_mode: bool
) -> None:
    """Render the child verbs of a group prefix (the ``explain <group>`` case)."""
    if json_mode:
        payload = {
            "path": list(path),
            "children": [{"name": n, "description": d} for n, d in children],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        lines = [f"Available commands in {' '.join(path)}:"]
        lines.extend(f"  {name}: {desc}" for name, desc in children)
        print("\n".join(lines))


def _explain_handler(app: App, args: argparse.Namespace) -> None:
    """Dispatch for the ``explain`` verb — prints an op's doc or group listing."""
    from agentfront.errors import EXIT_USER_ERROR, AgentfrontError

    path = tuple(args.path) if args.path else ()
    if not path:
        # No path given — show root overview
        print(f"# {app.name} v{app.version}")
        if app.description:
            print(app.description)
        return

    entry = app.get_by_path(path)
    if entry is not None:
        _print_leaf_doc(path, entry.doc or entry.description or "", args.json, entry.flags)
        return

    children = _collect_path_children(app, path)
    if children:
        _print_group_children(path, children, args.json)
        return

    # Unknown path
    raise AgentfrontError(
        code=EXIT_USER_ERROR,
        message=f"no such path: {' '.join(path)}",
        remediation=f"check available paths with '{app.name} overview'",
    )


def _collect_top_level_nouns(app: App) -> dict[str, str]:
    """Map each top-level noun (group head or ungrouped op) to its description."""
    seen: dict[str, str] = {}
    tools = app.list_tools()
    for tool in tools:
        if tool.group:
            noun = tool.group[0]
            if noun not in seen:
                count = len([t for t in tools if t.group and t.group[0] == noun])
                seen[noun] = f"group with {count} commands"
        elif tool.name not in seen:
            seen[tool.name] = tool.description or ""
    return seen


def _print_scoped_overview(app: App, noun: str, json_mode: bool) -> None:
    """Render the verbs under a single noun (``overview <noun>``)."""
    children: list[tuple[str, str]] = []
    for tool in app.list_tools():
        if (tool.group and tool.group[0] == noun) or (not tool.group and tool.name == noun):
            children.append((tool.name, tool.description or ""))

    if json_mode:
        payload = {"noun": noun, "verbs": [{"name": n, "description": d} for n, d in children]}
        print(json.dumps(payload, ensure_ascii=False))
    else:
        lines = [f"Commands in {noun}:"]
        lines.extend(f"  {name}: {desc}" for name, desc in children)
        print("\n".join(lines))


def _print_full_overview(app: App, json_mode: bool) -> None:
    """Render the top-level noun listing (``overview`` with no scope)."""
    seen = _collect_top_level_nouns(app)
    if json_mode:
        payload = [{"name": name, "description": desc} for name, desc in seen.items()]
        print(json.dumps(payload, ensure_ascii=False))
    else:
        lines = [f"{app.name} — available commands"]
        lines.extend(f"  {name}: {desc}" for name, desc in seen.items())
        print("\n".join(lines))


def _overview_handler(app: App, args: argparse.Namespace) -> None:
    """Dispatch for the ``overview`` verb — lists registry nouns."""
    if args.scope:
        _print_scoped_overview(app, args.scope, args.json)
    else:
        _print_full_overview(app, args.json)


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


def _doctor_handler(app: App) -> None:
    """Dispatch for the ``doctor`` verb — prints a readiness check."""
    doc_count = len(app.list_docs())
    tool_count = len(app.list_tools())

    lines = [
        f"{app.name} v{app.version} — readiness check",
        f"  docs: {doc_count}",
        f"  tools: {tool_count}",
        "  status: healthy",
    ]
    print("\n".join(lines))


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


def _backfill_covered_defaults(
    parser: argparse.ArgumentParser,
    entry: "ToolEntry",
    covered_defaults: dict[str, Any],
) -> None:
    """Give a merged value-carrying flag the signature param's default.

    When an explicit Flag replaces a signature param that had a default but the
    Flag declares no ``default=``, the flag would default to None and the
    dispatcher would forward None over the function's own default. Setting the
    argparse action default to the signature default keeps omission equivalent
    to the pure signature-derived flag.
    """
    if not covered_defaults:
        return
    for flag in entry.flags:
        if flag.default is not None:
            continue  # an explicit Flag default already wins
        dest = flag.dest
        if dest is None:
            for name in flag.names:
                if name.startswith("--"):
                    dest = name[2:].replace("-", "_")
                    break
        if dest in covered_defaults:
            for action in parser._actions:
                if action.dest == dest and action.default is None:
                    action.default = covered_defaults[dest]


def _add_leaf_verb(subparsers: Any, entry: "ToolEntry") -> None:
    """Add one tool as a leaf verb parser (signature args, flags, ``--json``)."""
    from agentfront._registry import apply_flags

    verb_parser = subparsers.add_parser(
        entry.name,
        help=entry.description,
        aliases=list(entry.aliases),
    )
    covered_defaults = _derive_args_from_sig(verb_parser, entry.func, entry.flags)
    apply_flags(verb_parser, entry)
    _backfill_covered_defaults(verb_parser, entry, covered_defaults)
    verb_parser.add_argument("--json", action="store_true", help=_JSON_HELP)
    verb_parser.set_defaults(func=_make_dispatcher(entry))


def _ensure_group_chain(
    root_sub: Any,
    group: tuple[str, ...],
    group_parsers: dict[tuple[str, ...], Any],
    group_subparsers: dict[tuple[str, ...], Any],
    tools_by_group: dict[tuple[str, ...], list["ToolEntry"]],
) -> Any:
    """Walk/create the nested subparser chain for *group*; return its leaf subparsers.

    Intermediate group parsers are shared across siblings via *group_parsers* /
    *group_subparsers*, so calling this once per grouped tool builds each level
    exactly once.
    """
    current_sub = root_sub
    for i, noun in enumerate(group):
        prefix = group[: i + 1]
        if prefix not in group_parsers:
            group_parser = current_sub.add_parser(noun, help=f"commands for {noun}")
            group_parsers[prefix] = group_parser
            tools_by_group[prefix] = []
            current_sub = group_parser.add_subparsers(
                dest=f"command_{i}",
                parser_class=_CliParser,
            )
            group_subparsers[prefix] = current_sub
        else:
            current_sub = group_subparsers[prefix]
    return current_sub


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_cli(app: App) -> argparse.ArgumentParser:
    """Build an argparse parser from an :class:`App`'s registry.

    Creates nested noun-group subparsers for each registered tool, host
    commands, and the learn/doctor meta-verbs.
    """
    from agentfront._registry import ToolEntry

    parser = _CliParser(
        prog=app.name,
        description=f"{app.name} v{app.version}",
    )

    sub = parser.add_subparsers(dest="command", parser_class=_CliParser)

    # --- learn, explain, overview, and doctor meta-verbs ------------------
    learn_parser = sub.add_parser("learn", help="agent-facing summary")
    learn_parser.add_argument("--json", action="store_true", help=_JSON_HELP)
    learn_parser.set_defaults(func=lambda a: _learn_handler(app, a))

    explain_parser = sub.add_parser("explain", help="explain a command or group")
    explain_parser.add_argument("path", nargs="*", help="command path (e.g. feedback record)")
    explain_parser.add_argument("--json", action="store_true", help=_JSON_HELP)
    explain_parser.set_defaults(func=lambda a: _explain_handler(app, a))

    overview_parser = sub.add_parser("overview", help="list available commands")
    overview_parser.add_argument("scope", nargs="?", help="optional noun to scope to")
    overview_parser.add_argument("--json", action="store_true", help=_JSON_HELP)
    overview_parser.set_defaults(func=lambda a: _overview_handler(app, a))

    doctor_parser = sub.add_parser("doctor", help="readiness check")
    doctor_parser.set_defaults(func=lambda a: _doctor_handler(app))

    # --- grouped tools: build nested subparser chains -------------------
    # Maps from group prefix → parser / subparser action, so siblings share the
    # same intermediate group parser.
    group_subparsers: dict[tuple[str, ...], argparse._SubParsersAction] = {}
    group_parsers: dict[tuple[str, ...], argparse.ArgumentParser] = {}
    tools_by_group: dict[tuple[str, ...], list[ToolEntry]] = {}

    for entry in app.list_tools():
        if not entry.group:
            _add_leaf_verb(sub, entry)
            continue
        leaf_sub = _ensure_group_chain(
            sub, entry.group, group_parsers, group_subparsers, tools_by_group
        )
        _add_leaf_verb(leaf_sub, entry)
        tools_by_group.setdefault(entry.group, []).append(entry)

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

    # Store raw argv so _CliParser.error() can peek for --json
    if isinstance(parser, _CliParser):
        _propagate_raw_argv(parser, argv)

    try:
        args = parser.parse_args(argv)
    except _CliParser._Exit as exc:
        # argparse exits 0 for --help and 1 for a parse error
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
