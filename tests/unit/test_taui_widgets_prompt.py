"""Unit tests for agentfront.taui.widgets.prompt_input."""

from __future__ import annotations

from agentfront.taui.state import Background, Header, TAUIState
from agentfront.taui.widgets.prompt_input import plain_prompt, render_prompt_input

# ---------------------------------------------------------------------------
# plain_prompt
# ---------------------------------------------------------------------------


def test_plain_prompt_default_is_agent() -> None:
    """Default context is 'agent', giving 'agent ❯ '."""
    assert plain_prompt() == "agent ❯ "


def test_plain_prompt_contains_no_ansi_escapes() -> None:
    """plain_prompt must contain no ANSI escape characters."""
    assert "\x1b" not in plain_prompt()


def test_plain_prompt_custom_context_startswith() -> None:
    """Custom context word appears before the chevron."""
    assert plain_prompt("foo").startswith("foo ❯")


def test_plain_prompt_custom_context_no_ansi() -> None:
    """plain_prompt with a custom context also contains no ANSI escapes."""
    assert "\x1b" not in plain_prompt("toolname")


# ---------------------------------------------------------------------------
# render_prompt_input — context word
# ---------------------------------------------------------------------------


def test_render_uses_header_title_as_context() -> None:
    """Header title drives the context word when context is not supplied."""
    state = TAUIState(header=Header("mytool"))
    result = render_prompt_input(state)
    assert "mytool ❯" in result


def test_render_context_override_wins_over_header() -> None:
    """Explicit context kwarg overrides the header title."""
    state = TAUIState(header=Header("other"))
    result = render_prompt_input(state, context="x")
    assert "x ❯" in result
    assert "other" not in result


def test_render_empty_header_falls_back_to_agent() -> None:
    """Empty header title falls back to 'agent'."""
    state = TAUIState(header=Header(""))
    result = render_prompt_input(state)
    assert "agent ❯" in result


def test_render_no_header_falls_back_to_agent() -> None:
    """Default TAUIState (no header title) falls back to 'agent'."""
    state = TAUIState()
    result = render_prompt_input(state)
    assert "agent ❯" in result


# ---------------------------------------------------------------------------
# render_prompt_input — focus brightness
# ---------------------------------------------------------------------------


def test_render_focused_is_bright() -> None:
    """When focused on 'input.prompt', the prompt uses bright SGR (ESC[1m)."""
    state = TAUIState(focused="input.prompt")
    result = render_prompt_input(state)
    assert "\x1b[1m" in result


def test_render_unfocused_is_dim() -> None:
    """When not focused on 'input.prompt', the prompt uses dim SGR (ESC[2m)."""
    state = TAUIState(focused="other.zone")
    result = render_prompt_input(state)
    assert "\x1b[2m" in result


def test_render_focused_and_unfocused_differ() -> None:
    """Focused and unfocused renders produce different strings."""
    state_on = TAUIState(focused="input.prompt")
    state_off = TAUIState(focused="other.zone")
    assert render_prompt_input(state_on) != render_prompt_input(state_off)


# ---------------------------------------------------------------------------
# render_prompt_input — spinner
# ---------------------------------------------------------------------------


def test_render_spinner_present_when_animation_active() -> None:
    """A spinner character from '|/-\\' appears when animation != 'none'."""
    state = TAUIState(background=Background(animation="spinner", frame=1))
    result = render_prompt_input(state)
    assert any(ch in result for ch in "|/-\\")


def test_render_no_spinner_when_animation_none() -> None:
    """No spinner when background animation is the 'none' sentinel."""
    state = TAUIState(background=Background(animation="none", frame=1))
    result = render_prompt_input(state)
    assert not any(ch in result for ch in "|/-\\")


def test_render_no_spinner_by_default() -> None:
    """No spinner with the default state (animation is empty string)."""
    state = TAUIState()
    result = render_prompt_input(state)
    assert not any(ch in result for ch in "|/-\\")


def test_render_spinner_frame_deterministic() -> None:
    """The spinner char is determined by frame % 4, not by clock or random."""
    chars = "|/-\\"
    for frame, expected in enumerate(chars):
        state = TAUIState(background=Background(animation="spin", frame=frame))
        result = render_prompt_input(state)
        assert expected in result, f"frame={frame} should show spinner char {expected!r}"
