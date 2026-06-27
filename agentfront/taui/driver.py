"""TAUI driver — a thin reference TTY driver.

Folds keystrokes through :func:`reduce` and repaints via :func:`render_ansi`.
Pure w.r.t. the external world: no real terminal I/O, fully unit-testable
from a Python list of keys.
"""

from __future__ import annotations

from typing import Callable

from agentfront.taui.events import KeyPress
from agentfront.taui.reducer import reduce
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.state import TAUIState


class Driver:
    """Thin reference driver that folds keys through the reducer and repaints.

    Holds the current :class:`TAUIState` and exposes :meth:`feed_key` /
    :meth:`run` for scripted interaction without any real TTY.
    """

    def __init__(
        self,
        state: TAUIState,
        render: Callable[[TAUIState], str] = render_ansi,
    ) -> None:
        self._state = state
        self._render = render

    # -- public API ----------------------------------------------------------

    @property
    def state(self) -> TAUIState:
        """The current :class:`TAUIState`."""
        return self._state

    def feed_key(self, key: str) -> str:
        """Apply a single key-press and return the repainted frame.

        ``state = reduce(state, KeyPress(key))`` then ``render(state)``.
        """
        self._state = reduce(self._state, KeyPress(key))
        return self._render(self._state)

    def run(self, keys: list[str]) -> list[str]:
        """Feed *keys* in order; return the list of frames (one per key)."""
        frames: list[str] = []
        for key in keys:
            frames.append(self.feed_key(key))
        return frames


def drive(state: TAUIState, keys: list[str]) -> TAUIState:
    """Convenience: fold *keys* through the reducer and return the final state."""
    driver = Driver(state)
    driver.run(keys)
    return driver.state
