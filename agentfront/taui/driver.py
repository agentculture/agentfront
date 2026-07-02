"""TAUI driver — a thin reference TTY driver, plus the live shared-session driver.

Folds keystrokes through :func:`reduce` and repaints via :func:`render_ansi`.
Pure w.r.t. the external world: no real terminal I/O, fully unit-testable
from a Python list of keys.

:class:`LiveDriver` is the human+agent front end over a single live
:class:`~agentfront.taui.session.Session` (see ``agentfront/taui/session.py``,
t6): the human side folds ``KeyPress``/popup actions through
``session.feed_key`` / ``session.dispatch``, the agent side calls
``session.dispatch`` directly, and BOTH write through the session's one
``fold`` — so a human watching a live TUI and an agent driving the same
process via ``dispatch`` see and produce the exact same event trail and
state. This is distinct from the plain :class:`Driver` above, which owns its
own disconnected ``TAUIState`` and has no concept of tool dispatch or a
shared session.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from agentfront.taui.events import Dismiss, KeyPress, SelectorAction
from agentfront.taui.reducer import reduce
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.session import Session
from agentfront.taui.state import Action, Popup, TAUIState


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


class LiveDriver:
    """The human+agent front end over one live :class:`Session`.

    Both audiences share the SAME session: the human side folds keys (and
    popup button presses) via :meth:`feed_key`; the agent side calls
    :meth:`dispatch` directly. Because both routes end up in
    ``session.fold`` under the session's single lock, the next repaint
    (:meth:`render`, or the return value of the next :meth:`feed_key`)
    always reflects whichever side acted most recently — there is no
    separate copy of the state for either audience.

    Popup buttons ACT rather than being inert: when a *visible* popup has an
    :class:`~agentfront.taui.state.Action` whose ``input`` matches the key
    pressed, that action fires instead of ordinary key navigation. A
    ``.dismiss``-suffixed selector folds ``Dismiss(target=<popup.id>)``
    (closing exactly that popup); any other selector dispatches through the
    session as a ``SelectorAction`` (so a popup button wired to a real tool
    executes it, and a non-tool selector degrades to the session's normal
    navigation fallback). When more than one visible popup has an action
    bound to the same key, the TOPMOST popup — the last one in
    ``session.state.popups``, matching the reducer's own topmost-wins
    dismiss convention — wins.

    ``"q"`` always quits: ``feed_key("q")`` sets :attr:`running` to
    ``False`` and returns immediately, even with a blocking popup visible.
    There is no quit-trap — folding nothing for the key itself is a
    deliberate choice (quitting is a driver-local concern, not a
    session-visible event).
    """

    def __init__(
        self,
        session: Session,
        render: Callable[[TAUIState], str] = render_ansi,
    ) -> None:
        self.session = session
        self.running = True
        self._render = render

    def render(self) -> str:
        """Repaint the session's current state with this driver's render callable."""
        return self._render(self.session.state)

    def _matching_popup_action(self, key: str) -> Optional[Tuple[Popup, Action]]:
        """Return the (popup, action) for the topmost visible popup bound to *key*.

        Iterates ``session.state.popups`` from the end (topmost) so that
        when multiple visible popups bind the same key, the most recently
        opened one wins.
        """
        for popup in reversed(self.session.state.popups):
            if not popup.visible:
                continue
            for action in popup.actions:
                if action.input == key:
                    return popup, action
        return None

    def feed_key(self, key: str) -> str:
        """Route a human key press: quit, popup action, or plain navigation.

        1. ``key == "q"`` — set :attr:`running` to ``False`` and return the
           current render. Always wins, even over a blocking popup.
        2. Otherwise, if a visible popup binds *key* to an action, that
           action fires (dismiss or dispatch — see the class docstring).
        3. Otherwise the key routes through ``session.feed_key`` unchanged.

        Returns ``render(session.state)`` after the routing above.
        """
        if key == "q":
            self.running = False
            return self.render()

        matched = self._matching_popup_action(key)
        if matched is not None:
            popup, action = matched
            if action.selector.endswith(".dismiss"):
                self.session.fold(Dismiss(target=popup.id))
            else:
                self.session.dispatch(SelectorAction(selector=action.selector))
        else:
            self.session.feed_key(key)

        return self.render()

    def dispatch(self, action: SelectorAction) -> TAUIState:
        """Agent-side dispatch: proxies straight to ``session.dispatch``.

        The next :meth:`render` (or the frame returned by the next
        :meth:`feed_key`) reflects the outcome, since both sides read the
        same ``session.state``.
        """
        return self.session.dispatch(action)

    def run(self, keys: list[str]) -> list[str]:
        """Feed *keys* in order, collecting frames.

        Stops early — no further keys are processed — once :attr:`running`
        goes ``False`` (i.e. after a ``"q"`` key), so the returned list may
        be shorter than *keys*.
        """
        frames: list[str] = []
        for key in keys:
            frames.append(self.feed_key(key))
            if not self.running:
                break
        return frames
