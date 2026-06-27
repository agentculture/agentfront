"""Unit tests for agentfront.taui.colors — should_color and strip_ansi."""

from __future__ import annotations

import io

from agentfront.taui.colors import should_color, strip_ansi

# ---------------------------------------------------------------------------
# strip_ansi
# ---------------------------------------------------------------------------


def test_strip_ansi_removes_sgr_sequences() -> None:
    """SGR sequences are stripped, leaving only visible text."""
    assert strip_ansi("\x1b[31mhi\x1b[0m") == "hi"


def test_strip_ansi_removes_multi_param_sequences() -> None:
    """Multi-parameter SGR sequences (e.g. bold+color) are stripped."""
    assert strip_ansi("\x1b[1;32mgreen bold\x1b[0m") == "green bold"


def test_strip_ansi_noop_on_plain_text() -> None:
    """Plain text without escape sequences passes through unchanged."""
    assert strip_ansi("hello world") == "hello world"


def test_strip_ansi_noop_on_empty_string() -> None:
    """Empty string passes through unchanged."""
    assert strip_ansi("") == ""


def test_strip_ansi_removes_erase_sequence() -> None:
    """Non-SGR CSI sequences (e.g. cursor erase) are also stripped."""
    assert strip_ansi("\x1b[2Jtext") == "text"


# ---------------------------------------------------------------------------
# should_color
# ---------------------------------------------------------------------------


def test_should_color_false_when_no_color_set(monkeypatch) -> None:
    """should_color returns False when NO_COLOR is set to a non-empty value."""
    monkeypatch.setenv("NO_COLOR", "1")
    assert should_color() is False


def test_should_color_false_when_no_color_any_value(monkeypatch) -> None:
    """should_color returns False regardless of NO_COLOR value (any non-empty string)."""
    monkeypatch.setenv("NO_COLOR", "true")
    assert should_color() is False


def test_should_color_false_for_non_tty_stream(monkeypatch) -> None:
    """should_color returns False for a non-TTY stream (io.StringIO)."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert should_color(io.StringIO()) is False


def test_should_color_true_for_fake_tty_stream(monkeypatch) -> None:
    """should_color returns True for a fake stream whose isatty() returns True."""
    monkeypatch.delenv("NO_COLOR", raising=False)

    class _FakeTTY:
        def isatty(self) -> bool:
            return True

    assert should_color(_FakeTTY()) is True  # type: ignore[arg-type]


def test_should_color_false_when_isatty_raises_attribute_error(monkeypatch) -> None:
    """should_color returns False when stream.isatty() raises AttributeError."""
    monkeypatch.delenv("NO_COLOR", raising=False)

    class _BadStream:
        @property
        def isatty(self):
            raise AttributeError("no isatty")

    assert should_color(_BadStream()) is False  # type: ignore[arg-type]


def test_should_color_false_when_isatty_raises_value_error(monkeypatch) -> None:
    """should_color returns False when stream.isatty() raises ValueError."""
    monkeypatch.delenv("NO_COLOR", raising=False)

    class _ClosedStream:
        def isatty(self) -> bool:
            raise ValueError("I/O on closed file")

    assert should_color(_ClosedStream()) is False  # type: ignore[arg-type]
