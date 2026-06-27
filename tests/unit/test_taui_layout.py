"""Unit tests for agentfront.taui.render.layout — constants and detect_width."""

from __future__ import annotations

from agentfront.taui.render.layout import (
    DEFAULT_WIDTH,
    GAP_LEN,
    MIN_WIDTH,
    SKILL_COL_WIDTH,
    detect_width,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_default_width_value() -> None:
    """DEFAULT_WIDTH is 80."""
    assert DEFAULT_WIDTH == 80


def test_min_width_value() -> None:
    """MIN_WIDTH is 40."""
    assert MIN_WIDTH == 40


def test_skill_col_width_value() -> None:
    """SKILL_COL_WIDTH is 30."""
    assert SKILL_COL_WIDTH == 30


def test_gap_len_value() -> None:
    """GAP_LEN is 2."""
    assert GAP_LEN == 2


def test_min_width_less_than_default_width() -> None:
    """MIN_WIDTH < DEFAULT_WIDTH — clamp floor is below the default."""
    assert MIN_WIDTH < DEFAULT_WIDTH


# ---------------------------------------------------------------------------
# detect_width
# ---------------------------------------------------------------------------


def test_detect_width_returns_int() -> None:
    """detect_width() returns an int."""
    assert isinstance(detect_width(), int)


def test_detect_width_at_least_min_width() -> None:
    """detect_width() always returns a value >= MIN_WIDTH."""
    assert detect_width() >= MIN_WIDTH
