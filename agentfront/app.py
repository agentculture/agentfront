"""``agentfront.App`` — the code-first config object.

A host package does::

    from agentfront import App

    app = App(name="mytool", version="1.0")
    app.add_docs_dir("docs/")

    @app.tool
    def search(query: str) -> str:
        \"\"\"Search the corpus.\"\"\"
        ...

…and then derives all three agent-first surfaces (CLI, MCP, HTTP) from this one
object. Docs and tools are declared *once* into a single :class:`Registry`; the
surfaces only ever read from it, so they cannot drift apart. This is the single
source of truth the whole runtime is built on.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable, Optional

from agentfront._registry import DocEntry, DuplicateError, Flag, HostCommand, Registry, ToolEntry

__all__ = ["App"]


class App:
    """One config object: one registry, three surfaces.

    The registry is private and mutated only through ``add_*`` / ``remove_*`` /
    ``tool``; surfaces enumerate via ``list_docs`` / ``list_tools``. There is no
    surface-level registration path, so nothing can appear on a surface that is
    not in the registry.
    """

    def __init__(self, name: str, version: str = "0.0.0", description: str = "") -> None:
        self.name = name
        self.version = version
        self.description = description
        self._registry = Registry()
        self._commands: dict[str, HostCommand] = {}
        self._no_command_handler: Optional[Callable[..., Any]] = None

    @property
    def registry(self) -> Registry:
        """The single backing store. Surfaces read it; they never copy it."""
        return self._registry

    # --- docs -------------------------------------------------------------
    def add_doc(
        self,
        *,
        slug: str,
        title: str,
        text: Optional[str] = None,
        path: Optional[str] = None,
    ) -> DocEntry:
        """Register one markdown doc, from inline ``text`` or a file ``path``."""
        if text is None and path is None:
            raise ValueError("add_doc requires text= or path=")
        if text is not None and path is not None:
            raise ValueError("add_doc takes text= or path=, not both")
        body = text if text is not None else Path(path).read_text(encoding="utf-8")
        return self._registry.add_doc(slug=slug, title=title, text=body)

    def add_docs_dir(self, directory: str, *, recursive: bool = True) -> list[DocEntry]:
        """Register every ``*.md`` under ``directory`` as a doc.

        The slug is the path relative to ``directory`` without the ``.md``
        suffix; the title is the first ATX ``# heading`` or the slug.
        """
        root = Path(directory)
        if not root.is_dir():
            raise NotADirectoryError(f"not a directory: {directory}")
        pattern = "**/*.md" if recursive else "*.md"
        added: list[DocEntry] = []
        for md in sorted(root.glob(pattern)):
            slug = md.relative_to(root).with_suffix("").as_posix()
            text = md.read_text(encoding="utf-8")
            added.append(self._registry.add_doc(slug=slug, title=_title_of(text, slug), text=text))
        return added

    def remove_doc(self, slug: str) -> None:
        self._registry.remove_doc(slug)

    def get_doc(self, slug: str) -> Optional[DocEntry]:
        return self._registry.get_doc(slug)

    def list_docs(self) -> list[DocEntry]:
        return self._registry.docs()

    # --- tools ------------------------------------------------------------
    def tool(
        self,
        func: Optional[Callable[..., Any]] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        group: Optional[str | tuple[str, ...]] = None,
        doc: Optional[str] = None,
        flags: tuple[Flag, ...] = (),
        aliases: tuple[str, ...] = (),
    ) -> Any:
        """Register a function as a tool.

        Usable as ``@app.tool``, ``@app.tool(name=...)``, or ``app.tool(fn)``.
        ``group`` accepts a single noun string or a tuple of nouns for nested
        paths; the registered op's full path is ``group + (name,)``.
        Returns the original function so it stays callable in the host.
        """
        if isinstance(group, str):
            group = (group,)
        elif group is None:
            group = ()

        def register(f: Callable[..., Any]) -> Callable[..., Any]:
            self._registry.add_tool(
                f,
                name=name,
                description=description,
                group=group,
                doc=doc,
                flags=flags,
                aliases=aliases,
            )
            return f

        if func is not None:
            return register(func)
        return register

    def remove_tool(self, name: str) -> None:
        self._registry.remove_tool(name)

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        return self._registry.get_tool(name)

    def get_by_path(self, path: tuple[str, ...]) -> Optional[ToolEntry]:
        return self._registry.get_by_path(path)

    def list_tools(self) -> list[ToolEntry]:
        return self._registry.tools()

    def group(self, *prefix: str) -> "_GroupRegistrar":
        """Return a sub-registrar that nests tools under *prefix*.

        Chaining is supported::

            app.group("a").group("b").tool  # registers under ("a", "b")
        """
        return _GroupRegistrar(self, tuple(prefix))

    # --- host commands --------------------------------------------------
    _RESERVED_META_VERBS: set[str] = {"learn", "explain", "overview", "doctor"}

    def add_command(
        self,
        name: str,
        handler: Callable[..., Any],
        *,
        help: str = "",
        configure: Optional[Callable[[argparse.ArgumentParser], None]] = None,
        aliases: tuple[str, ...] = (),
    ) -> HostCommand:
        """Register a host-written CLI command.

        Raises :class:`DuplicateError` if *name* or any *alias* collides with:

        * A reserved meta-verb (``learn``, ``explain``, ``overview``, ``doctor``)
        * An existing host command name or alias
        * A top-level (ungrouped) tool name or alias

        The error message includes remediation guidance.
        """
        # Collect all names/aliases to check
        all_names: list[str] = [name] + list(aliases)

        # 1. Check against reserved meta-verbs
        for n in all_names:
            if n in self._RESERVED_META_VERBS:
                raise DuplicateError(
                    f"command name/alias {n!r} is a reserved meta-verb; "
                    f"cannot register host command with that name. "
                    f"Use a different name that does not conflict with "
                    f"{sorted(self._RESERVED_META_VERBS)}."
                )

        # 2. Check against existing host commands (names + aliases)
        occupied: set[str] = set()
        for cmd in self._commands.values():
            occupied.add(cmd.name)
            occupied.update(cmd.aliases)
        for n in all_names:
            if n in occupied:
                raise DuplicateError(
                    f"command name/alias {n!r} already registered; "
                    f"choose a different name or alias."
                )

        # 3. Check against top-level (ungrouped) tool names + aliases
        for entry in self._registry.tools():
            if entry.group:
                continue  # Only top-level tools collide at the CLI root
            occupied.add(entry.name)
            occupied.update(entry.aliases)
        for n in all_names:
            if n in occupied:
                raise DuplicateError(
                    f"command name/alias {n!r} already registered as a tool; "
                    f"choose a different name or alias."
                )

        cmd = HostCommand(
            name=name, handler=handler, help=help, configure=configure, aliases=aliases
        )
        self._commands[name] = cmd
        return cmd

    def get_command(self, name: str) -> Optional[HostCommand]:
        """Return the registered host command, or ``None``."""
        return self._commands.get(name)

    def list_commands(self) -> list[HostCommand]:
        """Return all registered host commands."""
        return list(self._commands.values())

    # --- no-command handler -----------------------------------------------
    def set_no_command_handler(self, handler: Callable[..., Any]) -> None:
        """Set the handler invoked when the CLI is called without a sub-command."""
        self._no_command_handler = handler

    @property
    def no_command_handler(self) -> Optional[Callable[..., Any]]:
        """The current no-command handler, or ``None``."""
        return self._no_command_handler

    # --- surfaces ---------------------------------------------------------
    # One call each, all derived from this App's single registry. Imports are
    # lazy so the SSOT core stays decoupled from the surface modules (and from
    # the mcp SDK) until a surface is actually requested.
    def http_app(self) -> Any:
        """Return the WSGI HTTP surface (markdown pages + sitemap)."""
        from agentfront.http_surface import make_http_app

        return make_http_app(self)

    def mcp_server(self) -> Any:
        """Return the MCP server exposing this App's tools.

        The MCP surface is the one surface that needs the official ``mcp`` SDK,
        which ships as an optional extra. If it is not installed, raise a
        :class:`ModuleNotFoundError` that names the extra to install rather than
        letting a bare ``No module named 'mcp'`` surface from deep in the lazy
        import. The CLI and HTTP surfaces have no such dependency.
        """
        try:
            from agentfront.mcp_surface import make_mcp_server
        except ImportError as exc:
            # Only translate the *mcp* import failure; an ImportError for
            # anything else is a real bug and must not be masked. (A missing
            # install raises ModuleNotFoundError; an evicted module raises a
            # plain ImportError — both carry ``name == "mcp"``.)
            if (getattr(exc, "name", "") or "").split(".", 1)[0] != "mcp":
                raise
            raise ModuleNotFoundError(
                "agentfront's MCP surface needs the optional 'mcp' dependency, "
                "which is not installed. Install it with:\n"
                "    uv tool install 'agentfront[mcp]'\n"
                "    # or, in a project:  uv add 'agentfront[mcp]'\n"
                "    # or, with pip:      pip install 'agentfront[mcp]'\n"
                "The CLI and HTTP surfaces work without it."
            ) from exc

        return make_mcp_server(self)

    def cli(self) -> Any:
        """Return the argparse CLI (``learn`` / ``doctor``) for this App."""
        from agentfront.cli_surface import make_cli

        return make_cli(self)


class _GroupRegistrar:
    """Sub-registrar that prefixes tool registrations with a group path.

    Returned by :meth:`App.group`; supports chaining via :meth:`group`.
    """

    def __init__(self, app: App, prefix: tuple[str, ...]) -> None:
        self._app = app
        self._prefix = prefix

    def group(self, *more: str) -> "_GroupRegistrar":
        """Extend the group prefix and return a new sub-registrar."""
        return _GroupRegistrar(self._app, self._prefix + more)

    def tool(
        self,
        func: Optional[Callable[..., Any]] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        doc: Optional[str] = None,
        flags: tuple[Flag, ...] = (),
        aliases: tuple[str, ...] = (),
    ) -> Any:
        """Register a function as a tool under this registrar's group prefix."""

        def register(f: Callable[..., Any]) -> Callable[..., Any]:
            self._app._registry.add_tool(
                f,
                name=name,
                description=description,
                group=self._prefix,
                doc=doc,
                flags=flags,
                aliases=aliases,
            )
            return f

        if func is not None:
            return register(func)
        return register


def _title_of(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback
