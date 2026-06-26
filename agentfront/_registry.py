"""The single source of truth behind every agentfront surface.

A :class:`Registry` is the *one* place docs and tools live. The CLI, MCP, and
HTTP surfaces all enumerate from it and nowhere else — there is no second store
to drift out of sync. This module is the keystone the three surfaces build on.
"""

from __future__ import annotations

import argparse
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional, get_type_hints

__all__ = [
    "DocEntry",
    "Flag",
    "HostCommand",
    "ToolEntry",
    "Registry",
    "apply_flags",
    "derive_input_schema",
]


@dataclass(frozen=True)
class DocEntry:
    """A markdown document, addressable by ``slug``."""

    slug: str
    title: str
    text: str


@dataclass(frozen=True)
class Flag:
    """A per-verb CLI flag declaration."""

    names: tuple[str, ...]
    type: Optional[Callable[[str], Any]] = None
    action: Optional[str] = None
    nargs: Optional[str | int] = None
    dest: Optional[str] = None
    default: Any = None
    help: str = ""
    required: bool = False


@dataclass(frozen=True)
class ToolEntry:
    """A callable exposed as a tool, with an agent-facing description + schema."""

    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[..., Any]
    group: tuple[str, ...] = ()
    doc: str = ""
    flags: tuple[Flag, ...] = ()
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class HostCommand:
    """A host-written CLI command, registered via :meth:`App.add_command`."""

    name: str
    handler: Callable[..., Any]
    help: str = ""
    configure: Optional[Callable[[argparse.ArgumentParser], None]] = None
    aliases: tuple[str, ...] = ()


# Minimal Python-annotation → JSON-Schema type mapping. Anything unrecognised
# (including bare/missing annotations) falls back to "string", the safe default
# for an agent reading the menu.
_PY_TO_JSON: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _first_line(text: Optional[str]) -> str:
    if not text:
        return ""
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def derive_input_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Derive a JSON-Schema ``object`` from a function's signature + type hints.

    One derivation, shared by every surface, so an MCP tool's schema and any
    other surface's view of the same function cannot disagree.

    Type hints are resolved with :func:`typing.get_type_hints`, so this works
    whether the host uses real annotations or stringized ones (``from __future__
    import annotations`` / PEP 563). Anything that cannot be resolved falls back
    to ``"string"``.

    Limitation: only the base types in ``_PY_TO_JSON`` map to JSON-Schema types;
    ``Optional[T]``, ``Union[...]``, and parameterized generics (``list[int]``
    etc.) currently fall back to ``"string"``. That is acceptable for an
    agent-facing menu but is a known coarse edge.
    """
    try:
        hints = get_type_hints(func)
    except Exception:  # noqa: BLE001 - unresolved annotations just fall back
        hints = {}
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = hints.get(pname, param.annotation)
        json_type = _PY_TO_JSON.get(annotation, "string")
        properties[pname] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _flag_kwargs(flag: Flag) -> dict[str, Any]:
    """Translate a :class:`Flag` into argparse ``add_argument`` kwargs."""
    kwargs: dict[str, Any] = {}
    if flag.type is not None:
        kwargs["type"] = flag.type
    if flag.action is not None:
        kwargs["action"] = (
            argparse.BooleanOptionalAction if flag.action == "boolean_optional" else flag.action
        )
    if flag.nargs is not None:
        kwargs["nargs"] = flag.nargs
    if flag.dest is not None:
        kwargs["dest"] = flag.dest
    if flag.default is not None:
        kwargs["default"] = flag.default
    if flag.help:
        kwargs["help"] = flag.help
    if flag.required:
        kwargs["required"] = flag.required
    return kwargs


def apply_flags(parser: argparse.ArgumentParser, entry: ToolEntry) -> None:
    """Add each :class:`Flag` in *entry* to *parser*."""
    for flag in entry.flags:
        parser.add_argument(*flag.names, **_flag_kwargs(flag))


class DuplicateError(ValueError):
    """Raised when registering a slug/name that is already taken."""


class Registry:
    """The single store. Mutated only through its own methods; read by surfaces."""

    def __init__(self) -> None:
        self._docs: dict[str, DocEntry] = {}
        self._tools: dict[tuple[str, ...], ToolEntry] = {}
        self._aliases: dict[tuple[str, ...], tuple[str, ...]] = {}

    # --- docs -------------------------------------------------------------
    def add_doc(self, *, slug: str, title: str, text: str) -> DocEntry:
        if slug in self._docs:
            raise DuplicateError(f"doc slug already registered: {slug!r}")
        entry = DocEntry(slug=slug, title=title, text=text)
        self._docs[slug] = entry
        return entry

    def remove_doc(self, slug: str) -> None:
        if slug not in self._docs:
            raise KeyError(f"no such doc: {slug!r}")
        del self._docs[slug]

    def get_doc(self, slug: str) -> Optional[DocEntry]:
        return self._docs.get(slug)

    def docs(self) -> list[DocEntry]:
        return list(self._docs.values())

    # --- tools ------------------------------------------------------------
    def add_tool(
        self,
        func: Callable[..., Any],
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        group: tuple[str, ...] = (),
        doc: Optional[str] = None,
        flags: tuple[Flag, ...] = (),
        aliases: tuple[str, ...] = (),
    ) -> ToolEntry:
        tool_name = name or getattr(func, "__name__", None)
        if not tool_name or tool_name == "<lambda>":
            raise ValueError("tool needs a name (pass name= for a lambda/partial)")
        full_path: tuple[str, ...] = group + (tool_name,)
        if full_path in self._tools:
            raise DuplicateError(f"tool path already registered: {full_path!r}")
        desc = description if description is not None else _first_line(func.__doc__)
        full_doc = doc if doc is not None else (inspect.getdoc(func) or "")
        entry = ToolEntry(
            name=tool_name,
            description=desc,
            input_schema=derive_input_schema(func),
            func=func,
            group=group,
            doc=full_doc,
            flags=flags,
            aliases=aliases,
        )
        self._tools[full_path] = entry
        for alias in aliases:
            alias_path: tuple[str, ...] = group + (alias,)
            if alias_path in self._tools or alias_path in self._aliases:
                raise DuplicateError(f"tool path already registered: {alias_path!r}")
            self._aliases[alias_path] = full_path
        return entry

    def remove_tool(self, path: tuple[str, ...] | str) -> None:
        if isinstance(path, str):
            path = (path,)
        if path not in self._tools:
            raise KeyError(f"no such tool: {path!r}")
        entry = self._tools[path]
        for alias in entry.aliases:
            alias_path: tuple[str, ...] = entry.group + (alias,)
            self._aliases.pop(alias_path, None)
        del self._tools[path]

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        """Look up a top-level (ungrouped) tool by bare name."""
        return self.get_by_path((name,))

    def get_by_path(self, path: tuple[str, ...]) -> Optional[ToolEntry]:
        """Resolve a tool by its full path (group + name)."""
        entry = self._tools.get(path)
        if entry is not None:
            return entry
        real_path = self._aliases.get(path)
        if real_path is not None:
            return self._tools[real_path]
        return None

    def tools(self) -> list[ToolEntry]:
        return list(self._tools.values())
