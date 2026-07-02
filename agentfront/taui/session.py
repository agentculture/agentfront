"""TAUI Session — the single-process, single-writer live session.

One process owns exactly one :class:`TAUIState`. Both audiences fold their
events through the SAME reducer:

* the agent — :meth:`Session.dispatch`, a ``SelectorAction``
* the human — :meth:`Session.feed_key` / :meth:`Session.user_input`,
  ``KeyPress`` / ``UserInput``

:meth:`Session.fold` is the single mutation point: it appends the event to
the trail and folds it through :func:`agentfront.taui.reducer.reduce` under
one lock, so the trail order IS the fold order no matter which audience (or
thread) produced the event — the trail is the ground truth, never a torn or
lost write.

Tool *dispatch* — actually calling a registered tool's function — happens
OUTSIDE the pure reducer, here in the session layer: :meth:`Session.dispatch`
resolves ``action.selector`` against the app's registry, folds
``ToolInvoked``, executes the tool function, resolves an awaitable result via
``asyncio.run``, and builds the outcome payload with the SAME shared helpers
(:func:`agentfront._run_dispatch.result_payload` /
:func:`agentfront._run_dispatch.error_payload`) that
:func:`agentfront.testing.call_mcp` and the real MCP surface build from — so
``session.last_result`` and ``call_mcp(app, [...], args)`` agree byte-for-byte
for the same call. It then folds ``ToolResult`` with the outcome. When the
selector does not resolve to a registered tool, ``dispatch`` degrades to pure
navigation: it folds the ``SelectorAction`` itself (the same event a
`SelectorAction`-driven navigation always folds) and leaves ``last_result``
untouched.

Cross-process transport — multiple processes or machines sharing one live
session — is explicitly out of scope for v1. This is a single-process,
in-memory session; resumption across process boundaries goes through the
snapshot quad (:mod:`agentfront.taui.snapshot`) instead.

``initial`` / ``replay_base_index`` and resumed sessions
----------------------------------------------------------
``Session(app, state=..., events=...)`` accepts a prior event trail as pure
bookkeeping — it is stored verbatim on the trail but is NEVER replayed on top
of ``state`` at construction time. ``initial`` is always the state the
session STARTED from, i.e. exactly the ``state`` argument (or
``make_baseline(app)`` when omitted) — not the result of folding the prior
trail. ``replay_base_index`` records how many of the events on the trail
predate construction (``len(events)`` at construction, ``0`` for a fresh
session), so a caller that wants replay-equivalence for a *resumed* session
folds only the NEW events on top of ``initial``::

    replay(session.events[session.replay_base_index:], initial=session.initial) == session.state

For a fresh session (no prior trail), ``replay_base_index`` is ``0`` and this
reduces to the familiar ``replay(session.events, initial=session.initial) ==
session.state``.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any, Optional

from agentfront._run_dispatch import error_payload, result_payload
from agentfront.app import App
from agentfront.taui.derive import make_baseline
from agentfront.taui.events import (
    Event,
    KeyPress,
    SelectorAction,
    ToolInvoked,
    ToolResult,
    UserInput,
)
from agentfront.taui.mirror import serialize
from agentfront.taui.reducer import reduce
from agentfront.taui.state import TAUIState

__all__ = ["Session"]


class Session:
    """A single-process, single-writer live TAUI session over one ``App``.

    ``fold`` is the only mutation point; ``feed_key``, ``user_input``, and
    ``dispatch`` all route through it. An internal re-entrant lock makes
    every fold — including the two folds plus tool execution inside
    ``dispatch`` — atomic with respect to every other fold/dispatch call, so
    concurrent agent and human activity can never interleave mid-fold or
    lose/tear an append to the trail.
    """

    def __init__(
        self,
        app: App,
        state: Optional[TAUIState] = None,
        events: Optional[list[Event]] = None,
    ) -> None:
        self._app = app
        # Re-entrant so dispatch() can hold the lock for its whole body
        # (both folds + tool execution) while calling self.fold() inside it,
        # without deadlocking on itself.
        self._lock = threading.RLock()
        self._initial: TAUIState = state if state is not None else make_baseline(app)
        self._state: TAUIState = self._initial
        prior_events = list(events) if events is not None else []
        self._events: list[Event] = prior_events
        self._replay_base_index: int = len(prior_events)
        self._last_result: Optional[dict[str, Any]] = None

    # --- read-only properties ----------------------------------------------

    @property
    def state(self) -> TAUIState:
        """The current folded state."""
        with self._lock:
            return self._state

    @property
    def events(self) -> list[Event]:
        """A copy of the event trail (safe to mutate; the session's own trail is not)."""
        with self._lock:
            return list(self._events)

    @property
    def initial(self) -> TAUIState:
        """The state the session STARTED from (the ``state`` constructor argument).

        A prior ``events`` trail passed to the constructor is bookkeeping
        only — it is never replayed on top of this state. See
        ``replay_base_index`` for reconstructing replay-equivalence on a
        resumed session.
        """
        return self._initial

    @property
    def replay_base_index(self) -> int:
        """Index into ``events`` where events folded by THIS session begin.

        ``0`` for a fresh session. For a resumed session (constructed with a
        prior ``events`` trail), this is ``len(events)`` at construction —
        the events before this index predate the session and are not
        reproducible by replaying from ``initial``.
        """
        return self._replay_base_index

    @property
    def last_result(self) -> Optional[dict[str, Any]]:
        """The most recent tool-dispatch payload, in MCP shape (``None`` until one runs)."""
        with self._lock:
            return self._last_result

    # --- mirror --------------------------------------------------------

    def mirror(self) -> dict[str, Any]:
        """Return the JSON mirror (``serialize``) of the current state."""
        return serialize(self.state)

    # --- the single writer -----------------------------------------------

    def fold(self, event: Event) -> TAUIState:
        """Append *event* to the trail and fold it into the state. THE single writer."""
        with self._lock:
            self._events.append(event)
            self._state = reduce(self._state, event)
            return self._state

    def feed_key(self, key: str) -> TAUIState:
        """Fold a human key press."""
        return self.fold(KeyPress(key))

    def user_input(self, text: str) -> TAUIState:
        """Fold human free-text input."""
        return self.fold(UserInput(text))

    # --- agent dispatch ------------------------------------------------

    def dispatch(self, action: SelectorAction) -> TAUIState:
        """Resolve *action* against the app's registered tools and fold the outcome.

        A registered tool executes: ``ToolInvoked`` folds first, then the
        tool function runs OUTSIDE the reducer, then ``ToolResult`` folds
        with the outcome and ``last_result`` is set to the MCP-shape payload.
        An unresolved selector is pure navigation: the ``SelectorAction``
        itself folds and ``last_result`` is left unchanged. The whole call is
        atomic with respect to other fold/dispatch calls.
        """
        with self._lock:
            entry = self._app.get_by_path(tuple(action.selector.split(".")))
            if entry is None:
                return self.fold(action)

            self.fold(ToolInvoked(selector=action.selector, args=dict(action.args)))
            payload = self._execute(entry.func, action.args)
            self._last_result = payload
            return self.fold(self._tool_result(action.selector, payload))

    @staticmethod
    def _execute(func: Any, args: dict[str, Any]) -> dict[str, Any]:
        """Call *func* with *args*, resolving an awaitable result, as an MCP payload.

        Every exception the tool raises is caught and mapped to the
        canonical error payload (never propagated) — the same rule
        ``agentfront.testing.call_mcp`` and the real MCP surface follow.
        """
        try:
            value = func(**args)
            if inspect.isawaitable(value):
                value = asyncio.run(value)
            return result_payload(value)
        except Exception as exc:  # noqa: BLE001 - dispatch boundary, mapped not re-raised
            return error_payload(exc)

    @staticmethod
    def _tool_result(selector: str, payload: dict[str, Any]) -> ToolResult:
        """Translate an MCP-shape *payload* into the matching ``ToolResult`` event."""
        if "error" in payload:
            return ToolResult(selector=selector, ok=False, error=payload["error"])
        value = payload["result"]
        return ToolResult(selector=selector, ok=True, result="" if value is None else str(value))
