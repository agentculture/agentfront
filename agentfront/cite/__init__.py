"""``agentfront cli cite`` engine — emit the agent-first reference tree.

Public API:

* :func:`emit_reference` — copy the reference tree for ``lang`` into
  ``<target>/.agentfront/reference/<lang>-cli/`` (tokens left literal) and add
  ``.agentfront/`` to ``.gitignore`` if missing.
* :class:`CiteReport` — structured outcome (used by CLI for json/text output).
* :data:`SUPPORTED_LANGS` — tuple of renderer names shipped today.

The tree under :mod:`agentfront.cite.references` is package data; token substitution
is *not* performed — the consuming agent does that.
"""

from __future__ import annotations

from agentfront.cite._engine import SUPPORTED_LANGS, CiteReport, emit_reference

__all__ = ["CiteReport", "SUPPORTED_LANGS", "emit_reference"]
