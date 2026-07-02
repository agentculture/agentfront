"""Cross-surface agreement assertion — the consumer's proof surfaces never drift.

Wraps :func:`agentfront.serve.surface_inventory` (the same inventory the
agreement gate itself uses) and turns any disagreement into a descriptive
``AssertionError`` naming the disagreeing surface pair and the missing/extra
entries, so a failing consumer test states exactly what drifted instead of
just "surfaces disagree".
"""

from __future__ import annotations

from agentfront import serve
from agentfront.app import App

__all__ = ["assert_surfaces_agree"]

# Doc-bearing and tool-bearing surfaces, each compared against the registry
# (the single source of truth every other surface is derived from).
_DOC_SURFACES: tuple[str, ...] = ("registry_docs", "http_docs", "cli_docs")
_TOOL_SURFACES: tuple[str, ...] = ("registry_tools", "cli_tools", "mcp_tools", "taui_tools")


def assert_surfaces_agree(app: App) -> None:
    """Assert every surface of *app* enumerates the same docs/tools as the registry.

    Raises ``AssertionError`` on the first disagreeing pair found, naming both
    surfaces and the set differences (entries missing from / extra in the
    non-registry surface), e.g.
    ``"cli_tools missing vs registry_tools: {'a/b'}"``.
    """
    inventory = serve.surface_inventory(app)
    _assert_group_agrees(inventory, _DOC_SURFACES)
    _assert_group_agrees(inventory, _TOOL_SURFACES)


def _assert_group_agrees(inventory: dict[str, set[str]], surface_names: tuple[str, ...]) -> None:
    """Compare every surface in *surface_names* against the first (the registry)."""
    baseline_name = surface_names[0]
    baseline = inventory[baseline_name]
    for surface_name in surface_names[1:]:
        surface = inventory[surface_name]
        if surface == baseline:
            continue
        missing = baseline - surface
        extra = surface - baseline
        parts = []
        if missing:
            parts.append(f"{surface_name} missing vs {baseline_name}: {missing!r}")
        if extra:
            parts.append(f"{surface_name} extra vs {baseline_name}: {extra!r}")
        raise AssertionError("; ".join(parts))
