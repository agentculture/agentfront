"""Explain catalog — markdown keyed by command-path tuples.

See :mod:`agentfront.explain.catalog` for the string bodies and :func:`resolve` for
lookup. The rubric-bundle-5 check (``explain``) drives the invariant that
every noun/verb in the CLI has a catalog entry.
"""

from __future__ import annotations

from agentfront.cli._errors import EXIT_USER_ERROR, AfiError
from agentfront.explain.catalog import ENTRIES


def resolve(path: tuple[str, ...]) -> str:
    """Return the markdown body for ``path`` or raise :class:`AfiError`."""
    if path in ENTRIES:
        return ENTRIES[path]
    display = " ".join(path) if path else "<root>"
    raise AfiError(
        code=EXIT_USER_ERROR,
        message=f"no explain entry for: {display}",
        remediation="list known entries with: agentfront explain agentfront",
    )


def known_paths() -> list[tuple[str, ...]]:
    """Return every catalog path (used by tests + rubric check)."""
    return list(ENTRIES.keys())
