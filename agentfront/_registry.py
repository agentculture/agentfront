"""The single source of truth behind every agentfront surface.

A :class:`Registry` is the *one* place docs and tools live. The CLI, MCP, and
HTTP surfaces all enumerate from it and nowhere else — there is no second store
to drift out of sync. This module is the keystone the three surfaces build on.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional, get_type_hints

__all__ = [
    "DocEntry",
    "ToolEntry",
    "Registry",
    "derive_input_schema",
]


@dataclass(frozen=True)
class DocEntry:
    """A markdown document, addressable by ``slug``."""

    slug: str
    title: str
    text: str


@dataclass(frozen=True)
class ToolEntry:
    """A callable exposed as a tool, with an agent-facing description + schema."""

    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[..., Any]


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


class DuplicateError(ValueError):
    """Raised when registering a slug/name that is already taken."""


class Registry:
    """The single store. Mutated only through its own methods; read by surfaces."""

    def __init__(self) -> None:
        self._docs: dict[str, DocEntry] = {}
        self._tools: dict[str, ToolEntry] = {}

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
    ) -> ToolEntry:
        tool_name = name or getattr(func, "__name__", None)
        if not tool_name or tool_name == "<lambda>":
            raise ValueError("tool needs a name (pass name= for a lambda/partial)")
        if tool_name in self._tools:
            raise DuplicateError(f"tool name already registered: {tool_name!r}")
        desc = description if description is not None else _first_line(func.__doc__)
        entry = ToolEntry(
            name=tool_name,
            description=desc,
            input_schema=derive_input_schema(func),
            func=func,
        )
        self._tools[tool_name] = entry
        return entry

    def remove_tool(self, name: str) -> None:
        if name not in self._tools:
            raise KeyError(f"no such tool: {name!r}")
        del self._tools[name]

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        return self._tools.get(name)

    def tools(self) -> list[ToolEntry]:
        return list(self._tools.values())
