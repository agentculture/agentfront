"""The MCP SDK pin must stay capped below 2 and in lockstep across both places.

mcp 2.x removed the low-level ``Server.list_tools`` / ``Server.call_tool``
decorators ``agentfront/mcp_surface.py`` is built on, so an uncapped pin lets a
fresh ``agentfront[mcp]`` install resolve mcp 2.x and break at import. The
``mcp`` extra and the ``dev`` group carry the same pin (see the comments in
``pyproject.toml``); this catches either one losing the cap or drifting.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _mcp_pins() -> tuple[str, str]:
    data = tomllib.loads(_PYPROJECT.read_text())
    (extra,) = [d for d in data["project"]["optional-dependencies"]["mcp"] if d.startswith("mcp")]
    (dev,) = [d for d in data["dependency-groups"]["dev"] if d.startswith("mcp")]
    return extra, dev


def test_mcp_extra_is_capped_below_2() -> None:
    extra, _ = _mcp_pins()
    assert "<2" in extra.replace(" ", "")


def test_mcp_dev_pin_matches_extra() -> None:
    extra, dev = _mcp_pins()
    assert dev == extra
