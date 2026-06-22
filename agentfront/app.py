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

from pathlib import Path
from typing import Any, Callable, Optional

from agentfront._registry import DocEntry, Registry, ToolEntry

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
    ) -> Any:
        """Register a function as a tool.

        Usable as ``@app.tool``, ``@app.tool(name=...)``, or ``app.tool(fn)``.
        Returns the original function so it stays callable in the host.
        """

        def register(f: Callable[..., Any]) -> Callable[..., Any]:
            self._registry.add_tool(f, name=name, description=description)
            return f

        if func is not None:
            return register(func)
        return register

    def remove_tool(self, name: str) -> None:
        self._registry.remove_tool(name)

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        return self._registry.get_tool(name)

    def list_tools(self) -> list[ToolEntry]:
        return self._registry.tools()

    # --- surfaces ---------------------------------------------------------
    # One call each, all derived from this App's single registry. Imports are
    # lazy so the SSOT core stays decoupled from the surface modules (and from
    # the mcp SDK) until a surface is actually requested.
    def http_app(self) -> Any:
        """Return the WSGI HTTP surface (markdown pages + sitemap)."""
        from agentfront.http_surface import make_http_app

        return make_http_app(self)

    def mcp_server(self) -> Any:
        """Return the MCP server exposing this App's tools."""
        from agentfront.mcp_surface import make_mcp_server

        return make_mcp_server(self)

    def cli(self) -> Any:
        """Return the argparse CLI (``learn`` / ``doctor``) for this App."""
        from agentfront.cli_surface import make_cli

        return make_cli(self)


def _title_of(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback
